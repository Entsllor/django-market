from decimal import Decimal

from django.core.exceptions import PermissionDenied

from .base_case import TestBaseWithFilledCatalogue, BaseMarketTestCase, assert_difference
from ..models import Order, ProductType, Operation
from ..services import (
    top_up_balance, make_purchase, withdraw_money, NotEnoughMoneyError, _take_units_from_db, prepare_order,
    _cancel_order
)


def get_product_type(pk):
    return ProductType.objects.get(pk=pk)


class ChangeBalanceTest(BaseMarketTestCase):
    def setUp(self) -> None:
        self.customer = self.create_customer()
        self.log_in_as_customer()

    def check_data_to_compare(self):
        return self.balance.amount

    @assert_difference(100)
    def test_can_top_up(self):
        top_up_balance(self.user, 100)

    @assert_difference(200)
    def test_can_top_up_twice(self):
        top_up_balance(self.user, 100)
        top_up_balance(self.user, 100)

    def test_get_operation_object_if_topped_up(self):
        operation = top_up_balance(self.user, 100)
        self.assertIsInstance(operation, Operation)
        self.assertEqual(operation.user_id, self.user.id)

    def test_operation_amount_is_equal_top_up_amount(self):
        operation = top_up_balance(self.user, 100)
        self.assertEqual(operation.amount, 100)
        operation = top_up_balance(self.user, 50)
        self.assertEqual(operation.amount, 50)

    @assert_difference(0)
    def test_get_invalid_value(self):
        with self.assertRaises(TypeError):
            top_up_balance(self.user, None)
        with self.assertRaises(ValueError):
            top_up_balance(self.user, -100)

    @assert_difference(Decimal('100.33'))
    def test_get_decimal_value(self):
        top_up_balance(self.user, Decimal('100.33'))

    @assert_difference(0)
    def test_get_float(self):
        with self.assertRaises(TypeError):
            top_up_balance(self.user, 3.33)

    @assert_difference(50)
    def test_withdraw_money(self):
        top_up_balance(self.user, 100)
        withdraw_money(self.user, 50)

    @assert_difference(0)
    def test_withdraw_all_money(self):
        top_up_balance(self.user, 100)
        withdraw_money(self.user, 50)
        withdraw_money(self.user, 50)

    def test_get_operation_object_if_withdrew(self):
        top_up_balance(self.user, 200)
        operation = withdraw_money(self.user, 100)
        self.assertIsInstance(operation, Operation)
        self.assertEqual(operation.user_id, self.user.id)

    def test_operation_amount_is_negative_withdraw_amount(self):
        top_up_balance(self.user, 200)
        operation = withdraw_money(self.user, 100)
        self.assertEqual(operation.amount, -100)
        operation = withdraw_money(self.user, 50)
        self.assertEqual(operation.amount, -50)


class MakePurchaseTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(MakePurchaseTest, self).setUp()
        self.log_in_as_customer()

    @property
    def sellers_balance(self):
        return {seller.pk: seller.balance.amount for seller in self.sellers}

    # check total sum of user's money
    def check_data_to_compare(self):
        return sum(self.sellers_balance.values()) + self.balance.amount

    @assert_difference(2000)
    def test_sellers_get_money_after_purchase(self):
        top_up_balance(self.user, 2000)
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        make_purchase(order, self.user)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 800)
        self.assertEqual(self.sellers.get(pk=2).balance.amount, 500)
        self.assertEqual(sum(self.sellers_balance.values()), 1300)

    @assert_difference(2000)
    def test_will_customer_balance_be_reduced(self):
        top_up_balance(self.user, 2000)
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        make_purchase(order, self.user)
        self.assertEqual(self.balance.amount, 700)

    def test_will_cart_be_cleaned_after_purchase(self):
        top_up_balance(self.user, 2000)
        self.assertEqual(self.user.cart.items, {})
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        self.assertNotEqual(self.user.cart.items, {})
        order = prepare_order(self.cart)
        make_purchase(order, self.user)
        self.assertEqual(self.user.cart.items, {})

    def test_reduce_total_units_count_after_purchasing(self):
        top_up_balance(self.user, 2000)
        self.assertEqual(self.user.cart.items, {})
        units_to_buy = {'1': 5}
        units_at_start = ProductType.objects.get(pk=1).units_count
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        make_purchase(order, self.user)
        self.assertEqual(ProductType.objects.get(pk=1).units_count, units_at_start - 5)

    def test_pay_only_for_enable_product_units(self):
        top_up_balance(self.user, 5000)
        self.assertEqual(self.user.cart.items, {})
        units_to_buy = {'1': 5, '11': 6}
        self.fill_cart(units_to_buy)
        balance_before_purchase = self.balance.amount
        order = prepare_order(self.cart)
        make_purchase(order, self.user)
        balance_after_purchase = self.balance.amount
        self.assertEqual(balance_after_purchase, balance_before_purchase - 1000)
        self.assertEqual(self.sellers.get(pk=2).balance.amount, 500)

    @assert_difference(500)
    def test_user_has_not_enough_money_to_purchase(self):
        top_up_balance(self.user, 500)
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        with self.assertRaises(NotEnoughMoneyError):
            make_purchase(order, self.user)
        self.assertEqual(self.balance.amount, 500)
        self.assertEqual(sum(self.sellers_balance.values()), 0)

    def test_get_operation_object_after_purchase(self):
        top_up_balance(self.user, 2000)
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        total_price = order.total_price
        operation = make_purchase(order, self.user)
        self.assertEqual(operation.amount, -total_price)

    def test_check_order_items(self):
        top_up_balance(self.user, 2000)
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        self.assertEqual(order.items.count(), len(units_to_buy))

    def test_cant_pay_twice_for_one_order(self):
        top_up_balance(self.user, 2000)
        units_to_buy = {'1': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        make_purchase(order, self.user)
        self.assertEqual(self.balance.amount, 1500)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 500)
        with self.assertRaises(PermissionDenied):
            make_purchase(order, self.user)
        self.assertEqual(self.balance.amount, 1500)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 500)


class CouponTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(CouponTest, self).setUp()
        self.log_in_as_customer()

    def test_unlink_activated_coupon_after_buying(self):
        coupon = self.create_and_set_coupon(10)
        top_up_balance(self.user, 1000)
        self.fill_cart({'1': 1})
        order = prepare_order(self.cart)
        order.set_coupon(coupon)
        self.assertTrue(self.user.coupon_set.filter(pk=coupon.pk).exists())
        make_purchase(order, self.user)
        self.assertFalse(self.user.coupon_set.filter(pk=coupon.pk).exists())

    def test_coupon_decreases_total_order_price(self):
        coupon = self.create_and_set_coupon(10)
        top_up_balance(self.user, 1000)
        self.fill_cart({'1': 1})
        order = prepare_order(self.cart)
        order.set_coupon(coupon)
        make_purchase(order, self.user)
        self.assertEqual(self.balance.amount, 910)

    def test_coupon_dont_decrease_seller_income(self):
        coupon = self.create_and_set_coupon(10)
        top_up_balance(self.user, 1000)
        self.fill_cart({'1': 1})
        order = prepare_order(self.cart)
        order.set_coupon(coupon)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 0)
        make_purchase(order, self.user)
        self.assertEqual(self.balance.amount, 910)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 100)


class TakeUnitsFromDBTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(TakeUnitsFromDBTest, self).setUp()
        self.log_in_as_customer()

    def check_data_to_compare(self):
        return {i_type.pk: i_type.units_count for i_type in self.product_types.only('units_count')}

    @assert_difference({1: 0, 2: 0, 8: 1})
    def test_take_units_from_db(self):
        self.assertEqual(_take_units_from_db(get_product_type(1), 10), 10)
        self.assertEqual(_take_units_from_db(get_product_type(2), 5), 5)
        self.assertEqual(_take_units_from_db(get_product_type(8), 4), 4)

    @assert_difference({1: 10})
    def test_take_zero_units_from_db(self):
        taken_count = _take_units_from_db(get_product_type(1), 0)
        self.assertEqual(taken_count, 0)

    @assert_difference({1: 10})
    def test_try_take_negative_count_from_db(self):
        taken_count = _take_units_from_db(get_product_type(1), -5)
        self.assertEqual(taken_count, 0)

    @assert_difference({1: 0})
    def test_take_enable_counts_if_cant_take_expected_count(self):
        start_count = self.product_types.get(pk=1).units_count
        expected_count = 100
        taken_count = _take_units_from_db(get_product_type(1), expected_count)
        self.assertEqual(start_count, taken_count)
        self.assertLess(taken_count, expected_count)


class PrepareOrderTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(PrepareOrderTest, self).setUp()
        self.log_in_as_customer()

    def test_return_order_object(self):
        self.fill_cart({'1': 5, '2': 3, '7': 5})
        order = prepare_order(self.cart)
        self.assertIsInstance(order, Order)


class CancelOrderTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(CancelOrderTest, self).setUp()
        self.log_in_as_customer()

    @staticmethod
    def get_global_units_count(pks):
        units_count = {}
        for product_type in ProductType.objects.filter(id__in=pks):
            pk = str(product_type.pk)
            units_count[pk] = product_type.units_count
        return units_count

    def test_can_cancel_order(self):
        self.fill_cart({'1': 3, '2': 5, '7': 2})
        order: Order = prepare_order(self.cart)
        self.assertEqual(order.get_units_count(), {'1': 3, '2': 5, '7': 2})
        _cancel_order(order)
        self.assertEqual(order.get_units_count(), {})

    def test_add_units_from_canceled_order_to_db(self):
        units_to_add = {'1': 3, '2': 5, '7': 2}
        product_types_pks = units_to_add.keys()
        global_units_count_at_start = self.get_global_units_count(product_types_pks)
        self.fill_cart(units_to_add)
        order = prepare_order(self.cart)
        for pk, count in self.get_global_units_count(product_types_pks).items():
            self.assertEqual(global_units_count_at_start[pk], count + units_to_add[str(pk)])
        _cancel_order(order)
        self.assertEqual(global_units_count_at_start, self.get_global_units_count(product_types_pks))
