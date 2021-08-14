import logging
from decimal import Decimal
from typing import Iterable

from django.db.models import F

from .models import ShoppingAccount, ProductType, ShoppingReceipt

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
    return ShoppingReceipt.objects.create(
        shopping_account=shopping_account,
        description=description_text,
        order_items=shopping_account.order.copy(),
        total_price=shopping_account.total_price
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


def make_purchase(shopping_account: ShoppingAccount) -> ShoppingReceipt:
    items: Iterable[ProductType] = shopping_account.get_order_list('id')
    debt_to_sellers = get_debt_to_sellers(items)
    customer_balance = shopping_account.balance
    total_debt = sum(debt_to_sellers.values())
    if customer_balance < total_debt:
        raise NotEnoughMoneyError(
            f"{shopping_account.user} doesn't have enough money to the transaction."
        )
    else:
        ShoppingAccount.objects.filter(pk=shopping_account.pk).update(balance=F('balance') - total_debt)
        logger.info(
            f'User(id={shopping_account.user.pk}) sends money ({total_debt})'
        )
        shopping_account.refresh_from_db(fields=['balance'])
    sellers_pks = debt_to_sellers.keys()
    sellers = ShoppingAccount.objects.only('id', 'balance').filter(user_id__in=sellers_pks)
    for seller in sellers:
        amount_of_money = debt_to_sellers[seller.pk]
        logger.info(
            f'Transaction {amount_of_money} from User(id={shopping_account.user.pk}) to User(id={seller.user.pk})'
        )
        top_up_balance(seller, amount_of_money)
    receipt = create_shopping_receipt(shopping_account)
    shopping_account.clear_order()
    return receipt


def withdraw_money(shopping_account: ShoppingAccount, amount_of_money):
    valid_money_sum_number(amount_of_money)
    if shopping_account.balance < amount_of_money:
        raise NotEnoughMoneyError
    shopping_account.balance = F('balance') - amount_of_money
    logger.info(f'User(id={shopping_account.user.pk}) has withdrew {amount_of_money} money.')
    shopping_account.save()


def top_up_balance(shopping_account: ShoppingAccount, amount_of_money):
    valid_money_sum_number(amount_of_money)
    shopping_account.balance = F('balance') + amount_of_money
    logger.info(
        f'User(id={shopping_account.user.pk})\'s balance has been topped up. +{amount_of_money}'
    )
    shopping_account.save()
