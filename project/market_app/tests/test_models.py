from .base_case import BaseMarketTestCase, assert_difference, TestBaseWithFilledCatalogue
from ..models import OrderStatusChoices, ProductType, Order
from ..services import top_up_balance, withdraw_money, make_purchase, prepare_order


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

    def assertUnitsCount(self, expected_count):
        self.assertEqual(self.product_type.units_count, expected_count)

    def create_units(self, count):
        self.product_type.create_product_units(count)

    def test_can_create_product_units(self):
        self.assertUnitsCount(0)
        quantity = 10
        self.create_units(quantity)
        self.assertUnitsCount(quantity)

    def test_remove_product_units(self):
        self.create_units(15)
        self.product_type.remove_product_units(10)
        self.assertUnitsCount(5)

    def test_remove_more_units_than_have(self):
        self.create_units(5)
        with self.assertRaises(ValueError):
            self.product_type.remove_product_units(10)
        self.assertUnitsCount(5)

    def test_take_units_from_db(self):
        self.create_units(15)
        taken_units = self.product_type.take_units(10)
        self.assertEqual(taken_units, 10)
        self.assertUnitsCount(5)

    def test_flag_raise_exc_when_expected_count_gt_real_count(self):
        self.create_units(10)
        with self.assertRaises(ValueError):
            self.product_type.take_units(15, raise_exc_when_expected_count_gt_real_count=True)

    def test_take_zero_units_from_db(self):
        self.create_units(10)
        taken_count = self.product_type.take_units(0)
        self.assertEqual(taken_count, 0)
        self.assertUnitsCount(10)

    def test_try_take_negative_count_from_db(self):
        self.create_units(10)
        taken_count = self.product_type.take_units(-5)
        self.assertEqual(taken_count, 0)
        self.assertUnitsCount(10)

    def test_take_enable_units_if_cant_take_expected_count(self):
        self.product_type.create_product_units(10)
        start_count = self.product_type.units_count
        expected_count = 100
        taken_count = self.product_type.take_units(expected_count)
        self.assertEqual(start_count, taken_count)
        self.assertEqual(taken_count, 10)


class BalanceTest(BaseMarketTestCase):
    def setUp(self) -> None:
        super(BalanceTest, self).setUp()
        self.log_in_as_customer()

    def test_balance_equals_amount_sum_of_user_operations(self):
        self.assertEqual(self.balance.get_operations_amount_sum(), 0)
        top_up_balance(self.user.id, 100)
        counted_sum = self.balance.get_operations_amount_sum()
        self.assertEqual(counted_sum, 100)
        withdraw_money(self.user.id, 20)
        counted_sum = self.balance.get_operations_amount_sum()
        self.assertEqual(counted_sum, 80)


class CartTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(CartTest, self).setUp()
        self.log_in_as_customer()

    def check_data_to_compare(self):
        return self.cart.items

    def test_cart_items_equal_default(self):
        items_at_start = self.cart.items
        self.assertEqual(items_at_start, self.cart._default_cart_value())

    def test_can_set_item(self):
        self.cart.set_item(3, 5)
        self.assertEqual(self.cart.items, {'3': 5})

    def test_get_taken_units_count(self):
        units_to_add = {'1': 5, '7': 5, '11': 10}
        self.fill_cart(units_to_add)
        for pk, count in units_to_add.items():
            self.assertEqual(count, self.cart.get_count(pk))

    @assert_difference({})
    def test_got_negative_numbers(self):
        with self.assertRaises(ValueError):
            self.cart.set_item('1', -10)

    @assert_difference({})
    def test_got_float_number(self):
        with self.assertRaises(ValueError):
            self.cart.set_item('1', 1.1)

    @assert_difference({'11': 1})
    def test_del_items_with_no_units(self):
        self.fill_cart({'1': 5, '7': 5, '11': 1})
        self.fill_cart({'1': 0, '7': 0})

    @assert_difference({})
    def test_pass_adding_if_quantity_is_zero(self):
        self.cart.set_item('1', 0)

    @assert_difference({'1': 3, '7': 2})
    def test_reduce_units_count_in_order(self):
        self.fill_cart({'1': 5, '7': 5})
        self.cart.set_item('1', 3)
        self.cart.set_item('7', 2)

    def test_clear_order(self):
        self.cart.set_item('2', 3)
        self.cart.set_item('4', 1)
        self.assertNotEqual(self.cart.items, {})
        self.cart.clear()
        self.assertEqual(self.cart.items, {})

    def test_remove_nonexistent_product_types(self):
        self.cart.set_item('2', 3)
        self.cart.set_item('256', 1)
        self.assertEqual(self.cart.items, {'2': 3, '256': 1})
        count_of_removed_items = self.cart.prepare_items()
        self.assertEqual(count_of_removed_items, 1)
        self.assertEqual(self.cart.items, {'2': 3})

    @assert_difference({'10': 3, '7': 3})
    def test_remove_own_products_from_cart(self):
        self.log_in_as_seller()
        self.cart.set_item('1', 5)
        self.cart.set_item('3', 5)
        self.cart.set_item('7', 3)
        self.cart.set_item('5', 3)
        self.cart.set_item('10', 3)
        self.cart.set_item('2', 1)
        count_of_removed_items = self.cart.prepare_items()
        self.assertEqual(count_of_removed_items, 4)


class OrderTest(TestBaseWithFilledCatalogue):
    def setUp(self) -> None:
        super(OrderTest, self).setUp()
        self.log_in_as_customer()

    def test_change_status(self):
        top_up_balance(self.user.id, 10000)
        self.prepare_order({'1': 5, '3': 2, '5': 4, '8': 4})
        self.assertEqual(self.order.status, OrderStatusChoices.UNPAID.value)
        make_purchase(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatusChoices.HAS_PAID.value)
        self.order.items.update(is_shipped=True)
        self.assertEqual(self.order.status, OrderStatusChoices.SHIPPED.value)

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
        order.cancel()
        self.assertEqual(order.get_units_count(), {})

    def test_add_units_from_canceled_order_to_db(self):
        units_to_add = {'1': 3, '2': 5, '7': 2}
        product_types_pks = units_to_add.keys()
        global_units_count_at_start = self.get_global_units_count(product_types_pks)
        self.fill_cart(units_to_add)
        order = prepare_order(self.cart)
        for pk, count in self.get_global_units_count(product_types_pks).items():
            self.assertEqual(global_units_count_at_start[pk], count + units_to_add[str(pk)])
        order.cancel()
        self.assertEqual(global_units_count_at_start, self.get_global_units_count(product_types_pks))
