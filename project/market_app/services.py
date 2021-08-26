import logging
from decimal import Decimal
from typing import Iterable

from django.db.models import F

from .models import ShoppingAccount, ProductType, ShoppingReceipt, Operation

logger = logging.getLogger('market.transactions')


class NotEnoughMoneyError(Exception):
    """Raises if user doesn't have enough money to a transaction"""


def create_shopping_receipt(shopping_account):
    description_text = ''
    for item in shopping_account.get_order_list():
        units_count = item.units_on_cart
        sale_price = item.sale_price
        description_text += (
            f"product: {item.product}, attributes: {item.str_attributes}\n"
            f"count: {units_count}, sale price: {sale_price}\n"
            f"total price: {units_count * item.sale_price} = {units_count} * {sale_price}\n"
            f"market owner id: {item.product.market.owner.id}\n"
        )
    operation = Operation.objects.create(
        amount=-shopping_account.total_price, shopping_account=shopping_account, description=description_text)
    return ShoppingReceipt.objects.create(
        operation=operation,
        order_items=shopping_account.order.copy(),
    )


def valid_money_sum_number(money_sum):
    if not isinstance(money_sum, (Decimal, int)):
        raise TypeError(f'Expected a decimal or integer number, got "{money_sum}" instead.')
    elif money_sum <= 0:
        raise ValueError(f'Expected a positive number, got "{money_sum}" instead.')


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


def make_purchase(shopping_account: ShoppingAccount) -> ShoppingReceipt:
    items: Iterable[ProductType] = shopping_account.get_order_list('id')
    debt_to_sellers = get_debt_to_sellers(items)
    total_debt = sum(debt_to_sellers.values())
    customer_balance = shopping_account.balance
    if customer_balance < total_debt:
        raise NotEnoughMoneyError(
            f"{shopping_account.user} doesn't have enough money to the transaction."
        )
    else:
        ShoppingAccount.objects.filter(
            pk=shopping_account.pk).update(balance=F('balance') - shopping_account.total_price)
        shopping_account = ShoppingAccount.objects.get(pk=shopping_account.pk)
        logger.info(
            f'User(id={shopping_account.user.pk}) sends money ({shopping_account.total_price})')
    sellers_pks = debt_to_sellers.keys()
    sellers = ShoppingAccount.objects.only('id', 'balance').filter(user_id__in=sellers_pks)
    for seller in sellers:
        amount_of_money = debt_to_sellers[seller.pk]
        logger.info(
            f'Transaction {amount_of_money} '
            f'from ShoppingAccount(id={shopping_account.pk}) to ShoppingAccount(id={seller.pk})'
        )
        top_up_balance(seller, amount_of_money)
    receipt = create_shopping_receipt(shopping_account)
    shopping_account.set_default_value_to_order()
    unlink_activated_coupon(shopping_account)
    return receipt


def withdraw_money(shopping_account, amount_of_money):
    valid_money_sum_number(amount_of_money)
    if shopping_account.balance < amount_of_money:
        raise NotEnoughMoneyError
    ShoppingAccount.objects.filter(pk=shopping_account.pk).update(balance=F('balance') - amount_of_money)
    logger.info(f'Shopping_account(id={shopping_account.pk}) has withdrew {amount_of_money} money.')
    return Operation.objects.create(
        shopping_account=shopping_account,
        amount=-amount_of_money,
    )


def top_up_balance(shopping_account: ShoppingAccount, amount_of_money):
    valid_money_sum_number(amount_of_money)
    ShoppingAccount.objects.filter(pk=shopping_account.pk).update(balance=F('balance') + amount_of_money)
    logger.info(
        f'Shopping_account(id={shopping_account.pk})\'s balance has been topped up. +{amount_of_money}'
    )
    return Operation.objects.create(
        shopping_account=shopping_account,
        amount=amount_of_money,
    )
