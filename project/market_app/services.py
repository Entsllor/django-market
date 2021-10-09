import logging
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F

from .models import ProductType, Order, Operation, Cart, Coupon, OrderItem, User

logger = logging.getLogger(__name__)
SUBTRACT = '-'
ADD = '+'


class NotEnoughMoneyError(Exception):
    """Raises if user doesn't have enough money to a transaction"""


class EmptyOrderError(Exception):
    """Raises if the order is empty"""


class OrderCannotBeCancelledError(BaseException):
    """Raise if the order cannot be cancelled"""


def _set_order_operation(operation: Operation, order: Order) -> None:
    order.operation = operation


def _take_units_from_db(product_type: ProductType, expected_count: int) -> int:
    total_units = product_type.units_count
    if expected_count < 1:
        return 0
    elif total_units < expected_count:
        taken_units = total_units
    else:
        taken_units = expected_count
    product_type.remove_product_units(taken_units)
    return taken_units


def validate_money_amount(money_amount: Decimal) -> None:
    if not isinstance(money_amount, (Decimal, int)):
        raise TypeError(f'Expected a decimal or integer number, got "{money_amount}" instead.')
    elif money_amount < 0:
        raise ValueError(f'Expected a positive number, got "{money_amount}" instead.')


def prepare_order(cart: Cart) -> Order:
    cart.prepare_items()
    product_types = cart.get_cart_items()
    order = Order.objects.create(user_id=cart.user_id)
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


def try_to_cancel_order(order: Order, user_id: int) -> None:
    customer_id = Order.objects.filter(pk=order.pk).values_list('user_id', flat=True).first()
    if customer_id != user_id:
        raise OrderCannotBeCancelledError(f"User(id={user_id}) cannot cancel Order(id={order.id})")
    elif order.has_paid:
        raise OrderCannotBeCancelledError("The order cannot be cancelled because of its status.")
    _cancel_order(order)


def activate_coupon_to_order(order: Order, user: User, coupon: Coupon) -> None:
    if user.coupon_set.filter(pk=coupon.pk).exists():
        order.set_coupon(coupon)
        coupon.customers.remove(user)
        order.refresh_from_db()


def _send_money_to_sellers(order: Order) -> None:
    operations = []
    order_items = order.items.only(
        'amount', 'product_type__product__original_price', 'product_type__product__discount_percent',
        'product_type__markup_percent', 'order__user__balance__amount',
        'product_type__product__market__owner_id'
    ).select_related(
        'product_type', 'product_type__product', 'product_type__product__market',
        'product_type__product__market__owner', 'order__user__balance'
    )
    for item in order_items:
        seller = item.product_type.product.market.owner
        total_price = item.amount * item.product_type.sale_price
        logger.info(
            f'Transaction {total_price} '
            f'from User(id={order.user_id}) to User(id={seller.pk})'
        )
        operation = _change_balance_amount(seller, ADD, total_price, commit=True)
        item.payment = operation
        operations.append(operation)
    OrderItem.objects.bulk_update(order_items, fields=['payment'])


def _check_if_already_paid(order: Order) -> None:
    if order.operation_id:
        raise PermissionDenied('Cannot pay twice for one order.')


def _check_if_order_empty(order: Order, use_exists=False) -> None:
    if use_exists:
        is_empty = not order.items.exists()
    else:
        is_empty = not order.items
    if is_empty:
        raise EmptyOrderError('This order is empty.')


def _validate_order(order: Order) -> None:
    """Check if order is ready do purchase."""
    order.refresh_from_db()
    _check_if_order_empty(order)
    _check_if_already_paid(order)


@transaction.atomic
def make_purchase(order: Order, user: User, coupon: Coupon = None) -> Operation:
    _validate_order(order)
    if coupon:
        activate_coupon_to_order(order, user, coupon)
    purchase_operation = _change_balance_amount(user, SUBTRACT, order.total_price)
    _send_money_to_sellers(order)
    _set_order_operation(purchase_operation, order)
    order.save()
    return purchase_operation


def _change_balance_amount(user: User, operation_type: str, amount_of_money: Decimal, commit=True) -> Operation:
    validate_money_amount(amount_of_money)
    balance = user.balance
    if operation_type == SUBTRACT:
        if balance.amount < amount_of_money:
            raise NotEnoughMoneyError(
                f"User(pk={user.pk}) balance doesn't have enough money to the transaction"
                f"Balance: {balance.amount}. Expected at least {amount_of_money}.")
        amount_of_money = -amount_of_money
    balance.amount = F('amount') + amount_of_money
    operation = Operation(user_id=user.pk, amount=amount_of_money)
    if commit:
        balance.save(update_fields=['amount'])
        operation.save()
        logger.info(
            f'User(pk={user.pk}) balance has been successfully changed. '
            f'Amount: {amount_of_money}')
    return operation


def withdraw_money(user: User, amount_of_money: Decimal) -> Operation:
    logger.info(f'Try to withdraw User(pk={user.pk}) balance. Amount: {amount_of_money}.')
    operation = _change_balance_amount(user, SUBTRACT, amount_of_money)
    return operation


def top_up_balance(user: User, amount_of_money) -> Operation:
    logger.info(f"Try to top-up User(pk={user.pk}) balance. Amount: {amount_of_money}.")
    operation = _change_balance_amount(user, ADD, amount_of_money)
    return operation
