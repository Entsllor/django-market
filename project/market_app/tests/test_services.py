from decimal import Decimal

from django.core.exceptions import PermissionDenied

from .base_case import TestBaseWithFilledCatalogue, BaseMarketTestCase, assert_difference
from ..models import Order, ProductType, Operation, Coupon
from ..services import (
    top_up_balance, make_purchase, withdraw_money, NotEnoughMoneyError, prepare_order
)


def get_product_type(pk):
    return ProductType.objects.get(pk=pk)


class ChangeBalanceTest(BaseMarketTestCase):
    def setUp(self) -> None:
        self._customer = self.create_customer()
        self.log_in_as(self._customer)

    def check_data_to_compare(self):
        return self.balance.amount

    @assert_difference(100)
    def test_can_top_up(self):
        top_up_balance(self.user.id, 100)

    @assert_difference(200)
    def test_can_top_up_twice(self):
        top_up_balance(self.user.id, 100)
        top_up_balance(self.user.id, 100)

    def test_get_operation_object_if_topped_up(self):
        operation = top_up_balance(self.user.id, 100)
        self.assertIsInstance(operation, Operation)
        self.assertEqual(operation.user_id, self.user.id)

    def test_operation_amount_is_equal_top_up_amount(self):
        operation = top_up_balance(self.user.id, 100)
        self.assertEqual(operation.amount, 100)
        operation = top_up_balance(self.user.id, 50)
        self.assertEqual(operation.amount, 50)

    @assert_difference(0)
    def test_get_invalid_value(self):
        with self.assertRaises(TypeError):
            top_up_balance(self.user.id, None)
        with self.assertRaises(ValueError):
            top_up_balance(self.user.id, -100)

    @assert_difference(Decimal('100.33'))
    def test_get_decimal_value(self):
        top_up_balance(self.user.id, Decimal('100.33'))

    @assert_difference(0)
    def test_get_float(self):
        with self.assertRaises(TypeError):
            top_up_balance(self.user.id, 3.33)

    @assert_difference(50)
    def test_withdraw_money(self):
        top_up_balance(self.user.id, 100)
        withdraw_money(self.user.id, 50)

    @assert_difference(0)
    def test_withdraw_all_money(self):
        top_up_balance(self.user.id, 100)
        withdraw_money(self.user.id, 50)
        withdraw_money(self.user.id, 50)

    def test_get_operation_object_if_withdrew(self):
        top_up_balance(self.user.id, 200)
        operation = withdraw_money(self.user.id, 100)
        self.assertIsInstance(operation, Operation)
        self.assertEqual(operation.user_id, self.user.id)

    def test_operation_amount_is_negative_withdraw_amount(self):
        top_up_balance(self.user.id, 200)
        operation = withdraw_money(self.user.id, 100)
        self.assertEqual(operation.amount, -100)
        operation = withdraw_money(self.user.id, 50)
        self.assertEqual(operation.amount, -50)


class MakePurchaseTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(MakePurchaseTest, self).setUp()
        self.log_in_as_customer()

    @property
    def sellers_balance(self):
        return {seller.pk: seller.balance.amount for seller in self.sellers}

    def test_sellers_get_money_after_purchase(self):
        top_up_balance(self.user.id, 2000)
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        make_purchase(order)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 800)
        self.assertEqual(self.sellers.get(pk=2).balance.amount, 500)
        self.assertEqual(sum(self.sellers_balance.values()), 1300)

    def test_customer_balance_reduced_after_purchase(self):
        top_up_balance(self.user.id, 2000)
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        make_purchase(order)
        self.assertEqual(self.balance.amount, 700)

    def test_will_cart_be_cleaned_after_purchase(self):
        top_up_balance(self.user.id, 2000)
        self.assertEqual(self.user.cart.items, {})
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        self.assertNotEqual(self.user.cart.items, {})
        order = prepare_order(self.cart)
        make_purchase(order)
        self.assertEqual(self.user.cart.items, {})

    def test_raise_if_user_has_not_enough_money_to_purchase(self):
        top_up_balance(self.user.id, 500)
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        with self.assertRaises(NotEnoughMoneyError):
            make_purchase(order)
        self.assertEqual(self.balance.amount, 500)
        self.assertEqual(sum(self.sellers_balance.values()), 0)

    def test_get_operation_object_after_purchase(self):
        top_up_balance(self.user.id, 2000)
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        total_price = order.total_price
        operation = make_purchase(order)
        self.assertIsInstance(operation, Operation)
        self.assertEqual(operation.amount, -total_price)

    def test_order_has_all_expected_items(self):
        top_up_balance(self.user.id, 2000)
        units_to_buy = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        purchased_units = {
            str(item['product_type_id']): item['amount']
            for item in order.items.values('product_type_id', 'amount')
        }
        self.assertEqual(purchased_units, units_to_buy)

    def test_cant_pay_twice_for_one_order(self):
        top_up_balance(self.user.id, 2000)
        units_to_buy = {'1': 5}
        self.fill_cart(units_to_buy)
        order = prepare_order(self.cart)
        make_purchase(order)
        self.assertEqual(self.balance.amount, 1500)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 500)
        with self.assertRaises(PermissionDenied):
            make_purchase(order)
        self.assertEqual(self.balance.amount, 1500)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 500)

    def test_raise_error_if_order_is_empty(self):
        top_up_balance(self.user.id, 2000)
        self.fill_cart({})
        order = prepare_order(self.cart)
        with self.assertRaises(Order.EmptyOrderError):
            make_purchase(order)

    def _test_use_coupon(self, coupon, expected_balance_amount):
        top_up_balance(self.user.id, 2000)
        units_to_add = {'1': 5, '4': 1, '8': 4}
        order = self.prepare_order(units_to_add)
        order.set_coupon(coupon.pk)
        make_purchase(order)
        self.assertEqual(self.balance.amount, expected_balance_amount)

    def test_use_coupon_without_discount_limit(self):
        coupon = self.create_and_set_coupon(discount_percent=10)
        self._test_use_coupon(coupon, 1100)

    def test_use_coupon_with_discount_limit(self):
        coupon = self.create_and_set_coupon(discount_percent=10, discount_limit=80)
        self._test_use_coupon(coupon, 1080)

    def test_coupon_dont_decrease_seller_income(self):
        coupon = self.create_and_set_coupon(discount_percent=10, discount_limit=80)
        self._test_use_coupon(coupon, 1080)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 600)
        self.assertEqual(self.sellers.get(pk=2).balance.amount, 400)

    def test_cannot_use_coupon_if_user_have_no_access_to_the_coupon(self):
        coupon = Coupon.objects.create(discount_percent=10, discount_limit=80)
        with self.assertRaises(Coupon.CannotBeUsedError):
            self._test_use_coupon(coupon, 2000)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 0)
        self.assertEqual(self.sellers.get(pk=2).balance.amount, 0)

    def test_remove_coupon_from_user_coupon_set_after_purchasing(self):
        coupon = self.create_and_set_coupon(discount_percent=10, discount_limit=80)
        self.assertTrue(self.user.coupon_set.filter(pk=coupon.pk).exists())
        self._test_use_coupon(coupon, 1080)
        self.assertFalse(self.user.coupon_set.filter(pk=coupon.pk).exists())


class PrepareOrderTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(PrepareOrderTest, self).setUp()
        self.log_in_as_customer()

    def test_return_order_object(self):
        self.fill_cart({'1': 5, '2': 3, '7': 5})
        order = prepare_order(self.cart)
        self.assertIsInstance(order, Order)

    def test_reduce_total_units_count_after_preparing(self):
        self.assertEqual(self.user.cart.items, {})
        units_count_at_start = ProductType.objects.get(pk=1).units_count
        self.fill_cart({'1': 5})
        prepare_order(self.cart)
        self.assertEqual(ProductType.objects.get(pk=1).units_count, units_count_at_start - 5)

    def test_remove_own_products(self):
        self.log_in_as_seller()
        top_up_balance(self.user.id, 2000)
        self.fill_cart({'1': 5, '7': 3})
        order = prepare_order(self.cart)
        self.assertEqual(len(order.items.all()), 1)
        self.assertEqual(order.items.first().product_type_id, 7)
