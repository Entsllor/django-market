from decimal import Decimal

from .base_case import BaseMarketTestCase, assert_difference, TestBaseWithFilledCatalogue
from ..models import ProductType
from ..services import top_up_balance, withdraw_money


class ProductTest(BaseMarketTestCase):
    def setUp(self) -> None:
        super(ProductTest, self).setUp()
        self.product = self.create_product()

    def test_get_sale_price(self):
        product = self.create_product(original_price=100, discount_percent=0)
        self.assertEqual(product.original_price, product.sale_price)
        product.discount_percent = 10
        self.assertNotEqual(product.original_price, product.sale_price)
        self.assertEqual(product.sale_price, 90)

    def test_is_available_to_buy(self):
        product = self.create_product(available=True)
        self.assertFalse(product.is_available_to_buy)
        product.create_product_type(units_count=0)
        self.assertFalse(product.is_available_to_buy)
        product.create_product_type(units_count=10)
        self.assertTrue(product.is_available_to_buy)
        product.available = False
        self.assertFalse(product.is_available_to_buy)


class ProductTypeTest(BaseMarketTestCase):
    def setUp(self) -> None:
        super(ProductTypeTest, self).setUp()
        self.product = self.create_product()
        self._product_type = self.product.create_product_type()

    @property
    def product_type(self):
        self._product_type.refresh_from_db()
        return self._product_type

    def check_data_to_compare(self):
        return self.product_type.units_count

    @assert_difference(10)
    def test_can_create_product_units(self):
        quantity = 10
        self.product_type.create_product_units(quantity=quantity)

    @assert_difference(5)
    def test_remove_product_units(self):
        self.product_type.create_product_units(15)
        self.product_type.remove_product_units(10)

    @assert_difference(5)
    def test_remove_more_units_than_have(self):
        self.product_type.create_product_units(5)
        with self.assertRaises(ValueError):
            self.product_type.remove_product_units(10)


class ShoppingAccountTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(ShoppingAccountTest, self).setUp()
        self.log_in_as_customer()

    def check_data_to_compare(self):
        return self.shopping_account.order

    def test_result_len_is_equal_products_num(self):
        self.fill_cart({'1': 5, '7': 5, '11': 1})
        self.assertEqual(len(self.shopping_account.order), 3)

    @assert_difference({'1': 5})
    def test_can_add_one_type_units(self):
        self.fill_cart({'1': 5})

    @assert_difference({'1': 5, '7': 5, '11': 1})
    def test_can_add_units(self):
        self.fill_cart({'1': 5, '7': 5, '11': 1})

    @assert_difference({'1': 3, '7': 2})
    def test_reduce_units_count_in_order(self):
        self.fill_cart({'1': 5, '7': 5})
        self.shopping_account.set_units_count_to_order('1', 3)
        self.shopping_account.set_units_count_to_order('7', 2)

    @assert_difference({})
    def test_try_add_if_product_is_sold_out(self):
        units_after_setting = self.shopping_account.set_units_count_to_order('13', 100)
        self.assertEqual(units_after_setting, 0)

    @assert_difference({'11': 1})
    def test_can_del_items_with_no_units(self):
        self.fill_cart({'1': 5, '7': 5, '11': 1})
        self.fill_cart({'1': 0, '7': 0})

    @assert_difference({'1': 2, '2': 5, '7': 5})
    def test_return_result_code(self):
        self.assertEqual(self.shopping_account.set_units_count_to_order('1', 10), 10)
        self.assertEqual(self.shopping_account.set_units_count_to_order('1', 2), 2)
        self.assertEqual(self.shopping_account.set_units_count_to_order('2', 5), 5)
        self.assertEqual(self.shopping_account.set_units_count_to_order('7', 10), 5)
        self.assertEqual(self.shopping_account.set_units_count_to_order('13', 0), 0)
        self.assertEqual(self.shopping_account.set_units_count_to_order('13', 5), 0)

    @assert_difference({'7': 5})
    def test_user_try_take_more_units_than_exists(self):
        self.fill_cart({'7': 10})

    @assert_difference({})
    def test_got_negative_numbers(self):
        with self.assertRaises(ValueError):
            self.fill_cart({'1': -10})

    @assert_difference({})
    def test_got_float_number(self):
        with self.assertRaises(ValueError):
            self.fill_cart({'1': 1.1})

    def test_get_order_list(self):
        self.fill_cart({'1': 5, '7': 5, '11': 1})
        order_list = self.cart.get_order_list()
        for item in order_list:
            self.assertIn(str(item.pk), self.shopping_account.order.keys())
            self.assertEqual(item.product.id, ProductType.objects.get(pk=item.pk).product.id)
            self.assertEqual(item.units_on_cart, self.shopping_account.order[str(item.pk)])

    def test_len_of_order_list(self):
        self.fill_cart({'1': 5, '7': 5, '11': 1})
        items_count = sum(item.units_on_cart for item in self.cart.get_order_list())
        self.assertEqual(
            items_count,
            sum(self.shopping_account.order.values())
        )

    def test_constantly_of_total_units_count(self):
        count_at_start = 10
        product_type = self.create_product().create_product_type(units_count=count_at_start)
        for num_to_set in (3, 5, 2, 0):
            self.shopping_account.set_units_count_to_order(product_type.pk, num_to_set)
            product_type.refresh_from_db()
            self.assertEqual(product_type.units_count, count_at_start - num_to_set)

    def test_can_cancel_order(self):
        units_to_buy = {'1': 5, '7': 5, '11': 1}
        total_units_count_at_start = {
            i_type.pk: i_type.units_count for i_type in ProductType.objects.filter(id__in=units_to_buy.keys())
        }
        self.fill_cart(units_to_buy)
        self.assertEqual(self.shopping_account.order, units_to_buy)
        self.shopping_account.cancel_order()
        self.assertEqual(self.shopping_account.order, {})
        total_units_count_at_end = {
            i_type.pk: i_type.units_count for i_type in ProductType.objects.filter(id__in=units_to_buy.keys())
        }
        self.assertEqual(total_units_count_at_end, total_units_count_at_start)

    @staticmethod
    def get_total_units_count_from_db(**kwargs):
        return {
            i_type.pk: i_type.units_count for i_type in ProductType.objects.filter(**kwargs)
        }

    def test_return_units_from_order_to_db_after_order_canceling(self):
        units_to_buy = {'1': 5, '7': 5, '11': 1}
        total_units_count_at_start = self.get_total_units_count_from_db(id__in=units_to_buy.keys())
        self.fill_cart(units_to_buy)
        total_units_count = self.get_total_units_count_from_db(id__in=units_to_buy.keys())
        self.assertEqual(total_units_count, {1: 5, 7: 0, 11: 0})
        self.assertNotEqual(total_units_count, total_units_count_at_start)
        self.shopping_account.cancel_order()
        total_units_count = self.get_total_units_count_from_db(id__in=units_to_buy.keys())
        self.assertEqual(total_units_count, total_units_count_at_start)


class ShoppingAccountBalanceTest(BaseMarketTestCase):
    def setUp(self) -> None:
        super(ShoppingAccountBalanceTest, self).setUp()
        self.log_in_as_customer()

    def test_balance_equals_amount_sum_of_user_operations(self):
        self.assertEqual(self.shopping_account.get_operations_amount_sum(), 0)
        top_up_balance(self.shopping_account, 100)
        counted_sum = self.shopping_account.get_operations_amount_sum()
        self.assertEqual(counted_sum, 100)
        withdraw_money(self.shopping_account, 20)
        counted_sum = self.shopping_account.get_operations_amount_sum()
        self.assertEqual(counted_sum, 80)

    def test_get_operations_amount_sum_if_decimal(self):
        top_up_balance(self.shopping_account, Decimal('100.5'))
        top_up_balance(self.shopping_account, Decimal('50.23'))
        counted_sum = self.shopping_account.get_operations_amount_sum()
        self.assertEqual(counted_sum, Decimal('150.73'))
