import logging
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F

from .models import ShoppingAccount, ProductType, Order, Operation, Cart, Coupon, OrderItem

logger = logging.getLogger(__name__)
SUBTRACT = '-'
ADD = '+'


class NotEnoughMoneyError(Exception):
    """Raises if user doesn't have enough money to a transaction"""


class EmptyOrderError(Exception):
    """Raises if the order is empty"""


class OrderCannotBeCancelledError(BaseException):
    """Raise if the order cannot be cancelled"""


def _set_order_operation(operation: Operation, order: Order):
    order.operation = operation


def _take_units_from_db(product_type, expected_count):
    if not isinstance(product_type, ProductType):
        product_type = ProductType.objects.only('units_count').get(pk=product_type)
    total_units = product_type.units_count
    if expected_count < 1:
        return 0
    elif total_units < expected_count:
        taken_units = total_units
    else:
        taken_units = expected_count
    product_type.remove_product_units(taken_units)
    return taken_units


def validate_money_amount(money_amount):
    if not isinstance(money_amount, (Decimal, int)):
        raise TypeError(f'Expected a decimal or integer number, got "{money_amount}" instead.')
    elif money_amount < 0:
        raise ValueError(f'Expected a positive number, got "{money_amount}" instead.')


def prepare_order(cart: Cart):
    cart.prepare_items()
    product_types = cart.get_cart_items()
    order = Order.objects.create(shopping_account=cart.shopping_account)
    order_items = []
    for product_type in product_types:
        expected_count = cart.get_count(product_type.pk)
        if expected_count > 0:
            taken_units = _take_units_from_db(product_type, expected_count)
            order_item = OrderItem(
                order=order,
                amount=taken_units,
                product_type=product_type
            )
            order_items.append(order_item)
    OrderItem.objects.bulk_create(order_items)
    cart.clear()
    return order


def _cancel_order(order: Order) -> None:
    items = order.items.select_related('product_type').only('pk', 'product_type', 'amount')
    product_types = []
    for item in items:
        units_in_order = item.amount
        item.product_type.units_count = F('units_count') + units_in_order
        product_types.append(item.product_type)
    ProductType.objects.bulk_update(product_types, ['units_count'])
    order.delete()


def try_to_cancel_order(order, user_id):
    customer_id = Order.objects.filter(pk=order.pk).values_list('shopping_account__user_id', flat=True).first()
    if customer_id != user_id:
        raise OrderCannotBeCancelledError(f"User(id={user_id}) cannot cancel Order(id={order.id})")
    elif not order.is_unpaid:
        raise OrderCannotBeCancelledError("The order cannot be cancelled because of its status.")
    _cancel_order(order)


def activate_coupon_to_order(order: Order, shopping_account: ShoppingAccount, coupon: Coupon):
    if not isinstance(coupon, Coupon):
        coupon = Coupon.objects.get(pk=coupon)
    if shopping_account.coupon_set.filter(pk=coupon.pk).exists():
        order.set_coupon(coupon)
        coupon.customers.remove(shopping_account)
        order.refresh_from_db()


def _send_money_to_sellers(order: Order):
    operations = []
    order_items = order.items.only(
        'amount', 'product_type__product__original_price', 'product_type__product__discount_percent',
        'product_type__markup_percent', 'order__shopping_account__balance',
        'product_type__product__market__owner__shopping_account__id'
    ).select_related(
        'product_type', 'product_type__product', 'product_type__product__market',
        'product_type__product__market__owner', 'product_type__product__market__owner__shopping_account'
    )
    for item in order_items:
        seller = item.product_type.product.market.owner.shopping_account
        total_price = item.amount * item.product_type.sale_price
        logger.info(
            f'Transaction {total_price} '
            f'from ShoppingAccount(id={order.shopping_account_id}) to ShoppingAccount(id={seller.pk})'
        )
        operation = _change_balance_amount(seller, ADD, total_price, commit=True)
        item.payment = operation
        operations.append(operation)
    OrderItem.objects.bulk_update(order_items, fields=['payment'])


def _check_if_already_paid(order: Order, raise_error=True):
    if order.operation:
        if raise_error:
            raise PermissionDenied('Cannot pay twice for one order.')
        return order.operation


def _check_if_order_empty(order: Order):
    if not order.items:
        raise EmptyOrderError('This order is empty.')


def _validate_order(order: Order):
    """Check if order is ready do purchase."""
    order.refresh_from_db()
    _check_if_order_empty(order)
    _check_if_already_paid(order)


@transaction.atomic
def make_purchase(order: Order, shopping_account: ShoppingAccount, coupon: Coupon = None) -> Operation:
    _validate_order(order)
    if coupon:
        activate_coupon_to_order(order, shopping_account, coupon)
    purchase_operation = _change_balance_amount(shopping_account, SUBTRACT, order.total_price)
    _send_money_to_sellers(order)
    _set_order_operation(purchase_operation, order)
    order.status = order.OrderStatusChoices.HAS_PAID.name
    order.save()
    return purchase_operation


def _change_balance_amount(shopping_account, operation_type, amount_of_money, commit=True):
    validate_money_amount(amount_of_money)
    if operation_type == SUBTRACT:
        if shopping_account.balance < amount_of_money:
            raise NotEnoughMoneyError(
                f"Shopping_account(pk={shopping_account.pk}) balance doesn't have enough money to the transaction"
                f"Balance: {shopping_account.balance}. Expected at least {amount_of_money}.")
        amount_of_money = -amount_of_money
    shopping_account.balance = F('balance') + amount_of_money
    operation = Operation(shopping_account=shopping_account, amount=amount_of_money)
    if commit:
        shopping_account.save(update_fields=['balance'])
        operation.save()
        logger.info(
            f'Shopping_account(pk={shopping_account.pk}) balance has been successfully changed. '
            f'Amount: {amount_of_money}')
    return operation


def withdraw_money(shopping_account, amount_of_money):
    logger.info(f'Try to withdraw Shopping_account(pk={shopping_account.pk}) balance. Amount: {amount_of_money}.')
    operation = _change_balance_amount(shopping_account, SUBTRACT, amount_of_money)
    return operation


def top_up_balance(shopping_account: ShoppingAccount, amount_of_money):
    logger.info(f"Try to top-up Shopping_account(pk={shopping_account.pk}) balance. Amount: {amount_of_money}.")
    operation = _change_balance_amount(shopping_account, ADD, amount_of_money)
    return operation
