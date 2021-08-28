import logging
from decimal import Decimal
from typing import Iterable

from django.db.models import F

from .models import ShoppingAccount, ProductType, Order, Operation, Cart

logger = logging.getLogger('market.transactions')
SUBTRACT = '-'
ADD = '+'


class NotEnoughMoneyError(Exception):
    """Raises if user doesn't have enough money to a transaction"""


def _create_purchase_operation_description(items):
    description_text = ''
    for item in items:
        units_count = item.units_on_cart
        sale_price = item.sale_price
        description_text += f"""product: {item.product},
            attributes: {item.str_attributes},
            market: {item.product.market},
            count: {units_count},
            sale price: {sale_price},
            total price: {units_count} * {sale_price} = {units_count * item.sale_price}"""
    return description_text


def _set_operation_description(operation_pk, description):
    return Operation.objects.filter(pk=operation_pk.pk).update(description=description)


def _create_shopping_receipt(operation_pk, items):
    return Order.objects.create(
        operation_id=operation_pk,
        order_items=items.copy(),
    )


def _take_units_from_db(product_type, expected_count):
    if not isinstance(product_type, ProductType):
        product_type = ProductType.objects.get(pk=product_type)
    total_units = product_type.units_count
    if expected_count < 1:
        return 0
    elif total_units < expected_count:
        taken_units = total_units
    else:
        taken_units = expected_count
    product_type.remove_product_units(taken_units)
    return taken_units


def prepare_order(cart: Cart):
    cart.remove_nonexistent_product_types()
    order_items = {}
    product_types = cart.get_order_list('units_count')
    for product_type in product_types:
        units_on_cart = product_type.units_on_cart
        taken_units = _take_units_from_db(product_type, units_on_cart)
        order_items[str(product_type.pk)] = taken_units
    return Order.objects.create(order_items=cart.items)


def validate_money_amount(money_amount):
    if not isinstance(money_amount, (Decimal, int)):
        raise TypeError(f'Expected a decimal or integer number, got "{money_amount}" instead.')
    elif money_amount <= 0:
        raise ValueError(f'Expected a positive number, got "{money_amount}" instead.')


def get_debt_to_sellers(order_items) -> dict:
    debt_to_sellers = {}
    for item in order_items:
        seller_pk = item.product.market.owner.pk
        if seller_pk in debt_to_sellers:
            debt_to_sellers[seller_pk] += item.sale_price * item.units_on_cart
        else:
            debt_to_sellers[seller_pk] = item.sale_price * item.units_on_cart
    return debt_to_sellers


def unlink_activated_coupon(shopping_account: ShoppingAccount) -> None:
    coupon = shopping_account.activated_coupon
    if coupon:
        coupon.customers.remove(shopping_account)
        ShoppingAccount.objects.filter(pk=shopping_account.pk).update(activated_coupon=None)


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


def make_purchase(shopping_account: ShoppingAccount) -> Order:
    items: Iterable[ProductType] = shopping_account.cart.get_order_list('id')
    debt_to_sellers = get_debt_to_sellers(items)
    total_debt = sum(debt_to_sellers.values())
    purchase_operation = _change_balance_amount(shopping_account, SUBTRACT, total_debt)
    _send_money_to_sellers(shopping_account, debt_to_sellers)
    _set_operation_description(purchase_operation, _create_purchase_operation_description(items))
    receipt = _create_shopping_receipt(purchase_operation.pk, shopping_account.cart.items)
    shopping_account.cart.clear()
    unlink_activated_coupon(shopping_account)
    return receipt


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
