from decimal import Decimal

from .base_case import TestBaseWithFilledCatalogue, BaseMarketTestCase, assert_difference
from ..models import ShoppingAccount, Order, Coupon, ProductType, Operation
from ..services import (
    top_up_balance, make_purchase, withdraw_money, NotEnoughMoneyError, _take_units_from_db, prepare_order
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
    def test_can_top_up_twice(self):
        top_up_balance(self.shopping_account, 100)
        top_up_balance(self.shopping_account, 100)

    def test_get_operation_object_if_topped_up(self):
        operation = top_up_balance(self.shopping_account, 100)
        self.assertIsInstance(operation, Operation)
        self.assertEqual(operation.shopping_account_id, self.shopping_account.id)

    def test_operation_amount_is_equal_top_up_amount(self):
        operation = top_up_balance(self.shopping_account, 100)
        self.assertEqual(operation.amount, 100)
        operation = top_up_balance(self.shopping_account, 50)
        self.assertEqual(operation.amount, 50)

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
    def test_withdraw_all_money(self):
        top_up_balance(self.shopping_account, 100)
        withdraw_money(self.shopping_account, 50)
        withdraw_money(self.shopping_account, 50)

    def test_get_operation_object_if_withdrew(self):
        top_up_balance(self.shopping_account, 200)
        operation = withdraw_money(self.shopping_account, 100)
        self.assertIsInstance(operation, Operation)
        self.assertEqual(operation.shopping_account_id, self.shopping_account.id)

    def test_operation_amount_is_negative_withdraw_amount(self):
        top_up_balance(self.shopping_account, 200)
        operation = withdraw_money(self.shopping_account, 100)
        self.assertEqual(operation.amount, -100)
        operation = withdraw_money(self.shopping_account, 50)
        self.assertEqual(operation.amount, -50)


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
        self.assertEqual(self.shopping_account.cart.items, {})
        units_to_buy = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(units_to_buy)
        self.assertNotEqual(self.shopping_account.cart.items, {})
        make_purchase(self.shopping_account)
        self.assertEqual(self.shopping_account.cart.items, {})

    def test_reduce_total_units_count_after_purchasing(self):
        top_up_balance(self.shopping_account, 2000)
        self.assertEqual(self.shopping_account.cart.items, {})
        units_to_buy = {'1': 5}
        units_at_start = ProductType.objects.get(pk=1).units_count
        self.fill_cart(units_to_buy)
        make_purchase(self.shopping_account)
        self.assertEqual(ProductType.objects.get(pk=1).units_count, units_at_start - 5)

    @assert_difference(500)
    def test_user_has_not_enough_money_to_purchase(self):
        top_up_balance(self.shopping_account, 500)
        units_to_buy = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(units_to_buy)
        with self.assertRaises(NotEnoughMoneyError):
            make_purchase(self.shopping_account)
        self.assertEqual(self.balance, 500)
        self.assertEqual(sum(self.sellers_balance.values()), 0)

    def test_get_order_after_purchase(self):
        top_up_balance(self.shopping_account, 2000)
        units_to_buy = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(units_to_buy)
        total_price = self.shopping_account.total_price
        order = make_purchase(self.shopping_account)
        self.assertIsInstance(order, Order)
        self.assertEqual(order.operation.amount, -total_price)

    def test_check_order_items(self):
        top_up_balance(self.shopping_account, 2000)
        units_to_buy = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(units_to_buy)
        order = make_purchase(self.shopping_account)
        self.assertEqual(len(order.items), len(units_to_buy))


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
        top_up_balance(self.shopping_account, 1000)
        self.fill_cart({'1': 1})
        make_purchase(self.shopping_account)
        self.assertIsNone(self.shopping_account.activated_coupon)
        self.assertFalse(self.shopping_account.coupon_set.filter(pk=activated_coupon.pk).exists())


class TakeUnitsFromDBTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(TakeUnitsFromDBTest, self).setUp()
        self.log_in_as_customer()

    def check_data_to_compare(self):
        return {i_type.pk: i_type.units_count for i_type in self.product_types.only('units_count')}

    @assert_difference({1: 0, 2: 2, 5: 6})
    def test_take_units_from_db(self):
        self.assertEqual(_take_units_from_db(1, 10), 10)
        self.assertEqual(_take_units_from_db(2, 8), 8)
        self.assertEqual(_take_units_from_db(5, 4), 4)

    @assert_difference({1: 10})
    def test_take_zero_units_from_db(self):
        taken_count = _take_units_from_db(1, 0)
        self.assertEqual(taken_count, 0)

    @assert_difference({1: 10})
    def test_try_take_negative_count_from_db(self):
        taken_count = _take_units_from_db(1, -5)
        self.assertEqual(taken_count, 0)

    @assert_difference({1: 0})
    def test_take_enable_counts_if_cant_take_expected_count(self):
        start_count = self.product_types.get(pk=1).units_count
        expected_count = 100
        taken_count = _take_units_from_db(1, expected_count)
        self.assertEqual(start_count, taken_count)
        self.assertLess(taken_count, expected_count)


class PrepareOrderTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(PrepareOrderTest, self).setUp()
        self.log_in_as_customer()

    def test_return_order_object(self):
        self.fill_cart({'1': 5, '2': 3, '4': 5})
        order = prepare_order(self.cart.get_order_list())
        self.assertIsInstance(order, Order)

    def test_format_order_items(self):
        types_to_take = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(types_to_take)
        order = prepare_order(self.cart.get_order_list())
        items = self.cart.get_order_list()
        for item in items:
            order_item_data = order.items[str(item.pk)]
            self.assertEqual(order_item_data['units_count'], item.units_on_cart)
            self.assertEqual(order_item_data['properties'], item.properties)
            self.assertEqual(order_item_data['sale_price'], str(item.sale_price))
            self.assertEqual(order_item_data['product_name'], item.product.name)
            self.assertEqual(order_item_data['product_id'], item.product_id)
            self.assertEqual(order_item_data['market_id'], item.product.market_id)
            self.assertEqual(order_item_data['market_owner_id'], item.product.market.owner_id)
