import copy
from decimal import Decimal

from django.test import SimpleTestCase

from .base_case import TestBaseWithFilledCatalogue, BaseMarketTestCase, assert_difference
from ..models import ShoppingAccount, ShoppingReceipt, Coupon
from ..services import (
    top_up_balance, make_purchase, withdraw_money,
    NotEnoughMoneyError, get_currency, exchange_to,
    DEFAULT_CURRENCY, currencies, language_currency, Currency
)


class ChangeBalanceTest(BaseMarketTestCase):
    def setUp(self) -> None:
        self.customer = self.create_customer()
        self.log_in_as_customer()

    def check_data_to_compare(self):
        return self.balance

    @assert_difference(100)
    def test_can_top_up(self):
        top_up_balance(self.shopping_account, 100)

    @assert_difference(200)
    def test_can_top_up(self):
        top_up_balance(self.shopping_account, 100)
        top_up_balance(self.shopping_account, 100)

    @assert_difference(0)
    def test_get_invalid_value(self):
        with self.assertRaises(TypeError):
            top_up_balance(self.shopping_account, None)
        with self.assertRaises(ValueError):
            top_up_balance(self.shopping_account, -100)

    @assert_difference(Decimal('100.33'))
    def test_get_decimal_value(self):
        top_up_balance(self.shopping_account, Decimal('100.33'))

    @assert_difference(0)
    def test_get_float(self):
        with self.assertRaises(TypeError):
            top_up_balance(self.shopping_account, 3.33)

    @assert_difference(50)
    def test_withdraw_money(self):
        top_up_balance(self.shopping_account, 100)
        withdraw_money(self.shopping_account, 50)

    @assert_difference(0)
    def test_withdraw_all__money(self):
        top_up_balance(self.shopping_account, 100)
        withdraw_money(self.shopping_account, 50)
        withdraw_money(self.shopping_account, 50)


class MakePurchaseTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(MakePurchaseTest, self).setUp()
        self.log_in_as_customer()

    @property
    def sellers_balance(self):
        return {seller.pk: seller.shopping_account.balance for seller in self.sellers}

    # check total sum of user's money
    def check_data_to_compare(self):
        return sum(self.sellers_balance.values()) + self.balance

    @assert_difference(2000)
    def test_sellers_get_money_after_purchase(self):
        top_up_balance(self.shopping_account, 2000)
        units_to_buy = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(units_to_buy)
        make_purchase(self.shopping_account)
        self.assertEqual(sum(self.sellers_balance.values()), 1300)

    @assert_difference(2000)
    def test_will_customer_balance_be_reduced(self):
        top_up_balance(self.shopping_account, 2000)
        units_to_buy = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(units_to_buy)
        make_purchase(self.shopping_account)
        self.assertEqual(self.balance, 700)

    def test_will_order_be_cleaned_after_purchase(self):
        top_up_balance(self.shopping_account, 2000)
        self.assertEqual(self.shopping_account.order, {})
        units_to_buy = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(units_to_buy)
        self.assertNotEqual(self.shopping_account.order, {})
        make_purchase(self.shopping_account)
        self.assertEqual(self.shopping_account.order, {})

    @assert_difference(500)
    def test_user_has_not_enough_money_to_purchase(self):
        top_up_balance(self.shopping_account, 500)
        units_to_buy = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(units_to_buy)
        with self.assertRaises(NotEnoughMoneyError):
            make_purchase(self.shopping_account)
        self.assertEqual(self.balance, 500)
        self.assertEqual(sum(self.sellers_balance.values()), 0)

    def test_get_receipt_after_buying(self):
        top_up_balance(self.shopping_account, 2000)
        units_to_buy = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(units_to_buy)
        order_list = self.shopping_account.order
        total_price = self.shopping_account.total_price
        receipt = make_purchase(self.shopping_account)
        self.assertIsInstance(receipt, ShoppingReceipt)
        self.assertEqual(receipt.total_price, total_price)
        self.assertEqual(receipt.order_items, order_list)

    def test_check_receipt_description(self):
        top_up_balance(self.shopping_account, 2000)
        units_to_buy = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(units_to_buy)
        items = self.shopping_account.get_order_list()
        receipt = make_purchase(self.shopping_account)
        for item in items:
            self.assertIn(item.product.name, receipt.description)
            self.assertIn(str(item.units_on_cart), receipt.description)
            self.assertIn(str(item.sale_price), receipt.description)


class CouponTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(CouponTest, self).setUp()
        self.log_in_as_customer()

    @property
    def sellers_balance(self):
        return {seller.pk: seller.shopping_account.balance for seller in self.sellers}

    def test_unlink_activated_coupon_after_buying(self):
        activated_coupon = Coupon.objects.create(discount_percent=10)
        activated_coupon.customers.add(self.shopping_account)
        ShoppingAccount.objects.filter(pk=self.shopping_account.pk).update(activated_coupon=activated_coupon)
        self.assertEqual(self.shopping_account.activated_coupon.pk, activated_coupon.pk)
        self.assertTrue(self.shopping_account.coupon_set.filter(pk=activated_coupon.pk).exists())
        make_purchase(self.shopping_account)
        self.assertIsNone(self.shopping_account.activated_coupon)
        self.assertFalse(self.shopping_account.coupon_set.filter(pk=activated_coupon.pk).exists())


class CurrencyTest(SimpleTestCase):
    def setUp(self) -> None:
        self.currencies_backup = copy.deepcopy(currencies)

    def test_get_currency(self):
        for language_code, currency_code in language_currency.items():
            currency = get_currency(language_code)
            self.assertEqual(currency.code, currency_code)

    def test_return_default_if_unexpected_language(self):
        self.assertNotEqual('TEST_CODE', DEFAULT_CURRENCY)
        currency = get_currency('TEST_CODE')
        self.assertEqual(currency.code, DEFAULT_CURRENCY)

    def test_exchange_to(self):
        amount_to_exchange = 100
        rate_of_test_currency = Decimal('2.33')
        currencies['test'] = Currency(code='TEST', sym='T', rate=rate_of_test_currency)
        exchanged_amount = exchange_to('test', amount_to_exchange)
        self.assertEqual(exchanged_amount, rate_of_test_currency * amount_to_exchange)

    def test_pass_exchanging_if_codes_are_equal(self):
        amount_to_exchange = 100
        rate_of_test_currency = Decimal('2.33')
        currencies['test'] = Currency(code='TEST', sym='T', rate=rate_of_test_currency)
        exchanged_amount = exchange_to('test', amount_to_exchange, 'test')
        self.assertEqual(exchanged_amount, amount_to_exchange)

    def test_exchange_to_default(self):
        amount_to_exchange = 100
        rate_of_test_currency = Decimal('5')
        currencies['test'] = Currency(code='TEST', sym='T', rate=rate_of_test_currency)
        exchanged_amount = exchange_to(DEFAULT_CURRENCY, amount_to_exchange, _from='test')
        self.assertEqual(exchanged_amount, 20)

    def tearDown(self) -> None:
        currencies = self.currencies_backup
