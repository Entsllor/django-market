import logging
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F, QuerySet

from .models import Order, Operation, Cart, Coupon, OrderItem, User, Product, Money, Balance

logger = logging.getLogger(__name__)
SUBTRACT = '-'
ADD = '+'


class NotEnoughMoneyError(Exception):
    """Raises if user doesn't have enough money to a transaction"""


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
            taken_units = product_type.take_units(expected_count)
            order_item = OrderItem(
                order=order,
                amount=taken_units,
                product_type=product_type
            )
            order_items.append(order_item)
    OrderItem.objects.bulk_create(order_items)
    cart.clear()
    return order


def activate_coupon_to_order(order: Order, user: User, coupon: Coupon) -> None:
    if user.coupon_set.filter(pk=coupon.pk).exists():
        order.set_coupon(coupon.pk)
        coupon.customers.remove(user)
        order.refresh_from_db()


def _send_money_to_sellers(order: Order) -> None:
    operations = []
    order_items = order.items.only(
        'amount', 'product_type__product__original_price', 'product_type__product__discount_percent',
        'product_type__markup_percent', 'order__user__balance__amount',
        'product_type__product__market__owner_id'
    ).select_related(
        'product_type', 'product_type__product', 'product_type__product__market', 'order__user__balance'
    )
    for item in order_items:
        seller_id = item.product_type.product.market.owner_id
        total_price = item.amount * item.product_type.sale_price
        logger.info(
            f'Transaction {total_price} '
            f'from User(id={order.user_id}) to User(id={seller_id})'
        )
        operation = _change_balance_amount(seller_id, ADD, total_price, commit=True)
        item.payment = operation
        operations.append(operation)
    OrderItem.objects.bulk_update(order_items, fields=['payment'])


def get_order_price_if_use_coupon(order: Order, coupon: Coupon):
    order_coupon_at_start = order.coupon
    order.coupon = coupon
    total_price = order.total_price
    order.coupon = order_coupon_at_start
    return total_price


def check_if_user_can_use_order_coupon(order: Order) -> None:
    if not Coupon.objects.filter(customers__exact=order.user_id, pk=order.coupon_id).exists():
        raise Coupon.CannotBeUsedError(
            f"User(id={order.user_id}) cannot use Coupon(id={order.coupon_id})"
        )


def _check_order_is_valid_for_purchasing(order: Order) -> None:
    """Check if order is ready for purchasing."""
    order.refresh_from_db()
    if order.has_paid:
        raise PermissionDenied('Cannot pay twice for one order.')
    if order.is_empty():
        raise Order.EmptyOrderError('This order is empty.')


@transaction.atomic
def make_purchase(order: Order) -> Operation:
    _check_order_is_valid_for_purchasing(order)
    user_id = order.user_id
    if order.coupon_id:
        check_if_user_can_use_order_coupon(order)
        order.coupon.customers.remove(order.user_id)
    total_order_price = order.total_price
    logger.info(f'User(id={user_id}) try to pay for Order(id={order.pk}). Total order price: {total_order_price}')
    purchase_operation = _change_balance_amount(user_id, SUBTRACT, total_order_price)
    _send_money_to_sellers(order)
    order.set_operation(purchase_operation.pk)
    order.save()
    return purchase_operation


def _change_balance_amount(user_id, operation_type: str, amount_of_money: Decimal, commit=True) -> Operation:
    validate_money_amount(amount_of_money)
    balance = Balance.objects.get(user_id=user_id)
    if operation_type == SUBTRACT:
        if balance.amount < amount_of_money:
            raise NotEnoughMoneyError(
                f"User(id={user_id}) balance doesn't have enough money to the transaction"
                f"Balance: {balance.amount}. Expected at least {amount_of_money}.")
        amount_of_money = -amount_of_money
    balance.amount = F('amount') + amount_of_money
    operation = Operation(user_id=user_id, amount=amount_of_money)
    if commit:
        balance.save(update_fields=['amount'])
        operation.save()
        logger.info(
            f'User(id={user_id}) balance has been successfully changed. '
            f'Amount: {amount_of_money}')
    return operation


def withdraw_money(user_id: int, amount_of_money: Money) -> Operation:
    logger.info(f'Try to withdraw User(id={user_id}) balance. Amount: {amount_of_money}.')
    operation = _change_balance_amount(user_id, SUBTRACT, amount_of_money)
    return operation


def top_up_balance(user_id: int, amount_of_money: Money) -> Operation:
    logger.info(f"Try to top-up User(pk={user_id}) balance. Amount: {amount_of_money}.")
    operation = _change_balance_amount(user_id, ADD, amount_of_money)
    return operation


def get_products(ordering: str = '-discount_percent') -> QuerySet(Product):
    fields = ('image', 'original_price', 'discount_percent', 'name', 'image')
    queryset = Product.objects.distinct().only(*fields).filter(
        available=True, product_types__isnull=False).order_by(ordering)
    return queryset
