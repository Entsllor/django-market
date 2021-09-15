import logging
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import F

from .models import ShoppingAccount, ProductType, Order, Operation, Cart, Coupon, Market

logger = logging.getLogger('market.transactions')
SUBTRACT = '-'
ADD = '+'


class NotEnoughMoneyError(Exception):
    """Raises if user doesn't have enough money to a transaction"""


class EmptyOrderError(Exception):
    """Raises if the order is empty"""


def _set_order_operation(operation: Operation, order: Order):
    return Order.objects.filter(pk=order.pk).update(operation=operation)


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


def get_debt_to_sellers(order_items) -> dict:
    debt_to_sellers = {}
    for pk, data in order_items.items():
        seller_pk = data['market_owner_id']
        sale_price = Decimal(data['sale_price'])
        units_count = data['units_count']
        total_price = sale_price * units_count
        if seller_pk in debt_to_sellers:
            debt_to_sellers[seller_pk] += total_price
        else:
            debt_to_sellers[seller_pk] = total_price
    return debt_to_sellers


def _get_sellers_data(markets_pks, *fields):
    markets = Market.objects.filter(id__in=markets_pks).values('id', *fields)
    return {market_data['id']: market_data['owner_id'] for market_data in markets}


def prepare_order(cart: Cart):
    cart.prepare_items()
    order_items = cart.get_items_data()
    markets_pks = [value['market_id'] for value in order_items.values()]
    sellers_data = _get_sellers_data(markets_pks, 'owner_id')
    for pk, data in order_items.copy().items():
        expected_count = data['units_count']
        if expected_count > 0:
            taken_units = _take_units_from_db(pk, expected_count)
            data['units_count'] = taken_units
            data['sale_price'] = str(data['sale_price'])
            data['discount_percent'] = str(data['discount_percent'])
            data['original_price'] = str(data['original_price'])
            data['markup_percent'] = str(data['markup_percent'])
            owner_id = sellers_data[data['market_id']]
            data['market_owner_id'] = owner_id
        else:
            del order_items[pk]
    order = Order.objects.create(items=order_items, shopping_account=cart.shopping_account)
    cart.clear()
    return order


def activate_coupon_to_order(order: Order, shopping_account: ShoppingAccount, coupon: Coupon):
    if not isinstance(coupon, Coupon):
        coupon = Coupon.objects.get(pk=coupon)
    if shopping_account.coupon_set.filter(pk=coupon.pk).exists():
        order.set_coupon(coupon)
        coupon.customers.remove(shopping_account)
        order.refresh_from_db()


def _send_money_to_sellers(shopping_account, debt_to_sellers):
    sellers_pks = debt_to_sellers.keys()
    sellers = ShoppingAccount.objects.only('id', 'balance').filter(user_id__in=sellers_pks)
    for seller in sellers:
        amount_of_money = debt_to_sellers[seller.pk]
        logger.info(
            f'Transaction {amount_of_money} '
            f'from ShoppingAccount(id={shopping_account.pk}) to ShoppingAccount(id={seller.pk})'
        )
        top_up_balance(seller, amount_of_money)


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


def make_purchase(order: Order, shopping_account: ShoppingAccount, coupon: Coupon = None) -> Operation:
    _validate_order(order)
    if coupon:
        activate_coupon_to_order(order, shopping_account, coupon)
    debt_to_sellers = get_debt_to_sellers(order.items)
    purchase_operation = _change_balance_amount(shopping_account, SUBTRACT, order.total_price)
    _send_money_to_sellers(shopping_account, debt_to_sellers)
    _set_order_operation(purchase_operation, order)
    return purchase_operation


def _change_balance_amount(shopping_account, operation_type, amount_of_money):
    validate_money_amount(amount_of_money)
    if operation_type == SUBTRACT:
        if shopping_account.balance < amount_of_money:
            raise NotEnoughMoneyError(
                f"Shopping_account(pk={shopping_account.pk}) balance doesn't have enough money to the transaction"
                f"Balance: {shopping_account.balance}. Expected at least {amount_of_money}.")
        amount_of_money = -amount_of_money
    updated = ShoppingAccount.objects.filter(pk=shopping_account.pk).update(balance=F('balance') + amount_of_money)
    if updated:
        logger.info(
            f'Shopping_account(pk={shopping_account.pk}) balance has been successfully changed. '
            f'Amount: {amount_of_money}')
        return Operation.objects.create(shopping_account=shopping_account, amount=amount_of_money)
    else:
        logger.error(f'Failed to change Shopping_account(pk={shopping_account.pk}) balance. Amount: {amount_of_money}')


def withdraw_money(shopping_account, amount_of_money):
    logger.info(f'Try to withdraw Shopping_account(pk={shopping_account.pk}) balance. Amount: {amount_of_money}.')
    operation = _change_balance_amount(shopping_account, SUBTRACT, amount_of_money)
    return operation


def top_up_balance(shopping_account: ShoppingAccount, amount_of_money):
    logger.info(f"Try to top-up Shopping_account(pk={shopping_account.pk}) balance. Amount: {amount_of_money}.")
    operation = _change_balance_amount(shopping_account, ADD, amount_of_money)
    return operation
