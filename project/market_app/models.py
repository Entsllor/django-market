from decimal import Decimal
from enum import Enum
from typing import Iterable, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import F, QuerySet, Sum
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from market_app.validators import default_image_format_validator, product_image_size_validator, \
    market_logo_size_validator, product_attributes_symbols_validator, product_type_property_symbols_validator

User = get_user_model()
MAX_PRODUCT_PRICE_DIGITS_COUNT = settings.MAX_PRODUCT_PRICE_DIGITS_COUNT
MAX_BALANCE_DIGITS_COUNT = settings.MAX_BALANCE_DIGITS_COUNT
MONEY_DECIMAL_PLACES = settings.MONEY_DECIMAL_PLACES
MONEY_DECIMAL_QUANTIZE = Decimal('1.' + '0' * MONEY_DECIMAL_PLACES)
MAX_OPERATION_DIGITS_COUNT = MAX_BALANCE_DIGITS_COUNT
Money = Union[Decimal, int]


def validate_natural_number(number) -> None:
    if not isinstance(number, int) or number < 0:
        raise ValueError(f'Expected a natural number, got {number} instead')


class OrderStatusChoices(Enum):
    UNPAID = _("awaiting for payment")
    CANCELED = _("canceled")
    HAS_PAID = _("has successfully paid")
    SHIPPED = _("Shipped")
    DELIVERED = _("successfully completed")


class ProductCategory(models.Model):
    name = models.CharField(verbose_name=_('category'), max_length=63, unique=True)

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')

    def __str__(self):
        return self.name


class Market(models.Model):
    owner = models.OneToOneField(
        to=User,
        on_delete=models.CASCADE,
        related_name='market',
        verbose_name=_('market owner')
    )
    name = models.CharField(verbose_name=_('name'), max_length=63, unique=True)
    description = models.TextField(verbose_name=_('description'), blank=True)
    created_at = models.DateTimeField(verbose_name=_('created at'), auto_now_add=True)
    logo = models.ImageField(
        verbose_name=_('logo'),
        null=True,
        blank=True,
        upload_to='markets_logos/',
        validators=[default_image_format_validator, market_logo_size_validator]
    )

    class Meta:
        verbose_name = _('market')
        verbose_name_plural = _('markets')

    def get_img_url(self):
        if self.logo and hasattr(self.logo, 'url'):
            return self.logo.url
        else:
            # return default img
            return settings.STATIC_URL + 'market_app/img/no_image.png'

    def get_absolute_url(self):
        return reverse_lazy('market_app:market', kwargs={'pk': self.pk})

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(verbose_name=_('name'), max_length=63)
    description = models.TextField(verbose_name=_('description'), blank=True)
    market = models.ForeignKey(Market, verbose_name=_('market'), on_delete=models.CASCADE)
    original_price = models.DecimalField(
        verbose_name=_('price'),
        max_digits=MAX_PRODUCT_PRICE_DIGITS_COUNT,
        decimal_places=MONEY_DECIMAL_PLACES)
    discount_percent = models.DecimalField(
        verbose_name=_('discount percent'),
        max_digits=5,
        decimal_places=2,
        default=0,
        blank=True
    )
    attributes = models.TextField(
        verbose_name=_('attributes'),
        blank=True,
        validators=[product_attributes_symbols_validator]
    )
    created_at = models.DateTimeField(verbose_name=_('created at'), auto_now_add=True)
    available = models.BooleanField(verbose_name=_('available'), default=True)
    image = models.ImageField(
        verbose_name=_('image'),
        null=True,
        blank=True,
        upload_to='product_images/',
        validators=[default_image_format_validator, product_image_size_validator]
    )

    category = models.ForeignKey(
        'ProductCategory',
        verbose_name=_('category'),
        on_delete=models.CASCADE,
    )

    def get_img_url(self):
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        else:
            # return default img
            return settings.STATIC_URL + 'market_app/img/no_image.png'

    class Meta:
        verbose_name = _('product')
        verbose_name_plural = _('products')

    def __str__(self):
        return self.name

    @property
    def get_attributes(self) -> Iterable:
        return map(str.strip, self.attributes.split('\n'))

    def get_types(self) -> QuerySet['ProductType']:
        return getattr(self, 'product_types')

    @property
    def sale_price(self) -> Money:
        return round(self.original_price * ((100 - self.discount_percent) / 100), MONEY_DECIMAL_PLACES)

    @property
    def is_available_to_buy(self) -> bool:
        return self.available and self.get_types().filter(units_count__gt=0).exists()

    def create_product_type(self, properties=None, markup_percent=0, units_count=0) -> 'ProductType':
        product_type = ProductType.objects.create(
            product=self,
            markup_percent=markup_percent,
            units_count=units_count
        )
        if properties:
            product_type.properties = properties
        return product_type

    def get_absolute_url(self):
        return reverse_lazy('market_app:product', kwargs={'pk': self.pk})


class ProductType(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name=_('product'),
        related_name='product_types',
        on_delete=models.CASCADE
    )
    units_count = models.PositiveIntegerField(
        verbose_name=_('Amount'),
        blank=True,
        default=0
    )
    properties = models.JSONField(
        verbose_name=_('properties'),
        blank=True,
        default=dict,
        validators=[product_type_property_symbols_validator]
    )
    markup_percent = models.DecimalField(
        verbose_name=_('markup percent'),
        decimal_places=2,
        max_digits=5,
        blank=True,
        default=0
    )

    @property
    def original_price(self) -> Money:
        return round(self.product.original_price * (1 + (self.markup_percent / 100)), MONEY_DECIMAL_PLACES)

    @property
    def sale_price(self) -> Money:
        return round(self.product.sale_price * (1 + (self.markup_percent / 100)), MONEY_DECIMAL_PLACES)

    @property
    def has_units(self) -> bool:
        return self.units_count > 0

    def create_product_units(self, quantity: int) -> bool:
        status_code = ProductType.objects.filter(pk=self.pk).update(units_count=F('units_count') + quantity)
        return bool(status_code)

    def remove_product_units(self, quantity: int) -> bool:
        if self.units_count < quantity:
            raise ValueError(f"Can't remove {quantity} units. Current number of units: {self.units_count}")
        status_code = ProductType.objects.filter(pk=self.pk).update(units_count=F('units_count') - quantity)
        return bool(status_code)

    def take_units(self, expected_count: int, raise_exc_when_expected_count_gt_real_count=False) -> int:
        """
        Decrease product_type units count by expected count
        and return count of taken units.
        Set raise_exc_when_expected_count_gt_real_count=True if it's necessary to raise error
        when real product type units count is smaller than expected count to take.
        """
        real_count = self.units_count
        if expected_count < 1:
            return 0
        elif real_count < expected_count:
            if raise_exc_when_expected_count_gt_real_count:
                raise ValueError(f"Cannot take {expected_count} there are only {real_count}")
            taken_units = real_count
        else:
            taken_units = expected_count
        self.remove_product_units(taken_units)
        return taken_units

    @property
    def properties_as_str(self) -> str:
        return ', '.join(f'{key}: {value}' for key, value in self.properties.items() if value)

    @property
    def properties_as_dict(self) -> dict:
        return {attr: value for attr, value in self.properties.items()}

    def __str__(self):
        return f'{self.properties_as_str or f"id={self.id}"}'

    class Meta:
        verbose_name = _('Product type')
        verbose_name_plural = _('Product types')


class Cart(models.Model):
    _default_cart_value = dict
    max_product_type_count_on_cart = 20
    user = models.OneToOneField(
        to=User,
        verbose_name=_('user'),
        related_name='cart',
        on_delete=models.CASCADE
    )
    items = models.JSONField(verbose_name=_('items'), default=_default_cart_value)

    class Meta:
        verbose_name = _('cart')
        verbose_name_plural = _('carts')

    def get_cart_items(self) -> QuerySet[ProductType]:
        items = ProductType.objects.filter(id__in=self.items.keys()).select_related('product').only(
            'properties', 'markup_percent', 'units_count',
            'product__name', 'product__market_id',
            'product__discount_percent', 'product__original_price'
        )
        return items

    def get_count(self, pk) -> int:
        return self.items[str(pk)]

    def get_types_pks(self) -> tuple:
        return tuple(self.items.keys())

    def set_item(self, product_type_pk, quantity: int, commit: bool = True) -> None:
        validate_natural_number(quantity)
        product_type_pk = str(product_type_pk)
        if quantity == 0:
            if product_type_pk in self.items:
                del self.items[product_type_pk]
        else:
            self.items[product_type_pk] = quantity
        if commit:
            self.save(update_fields=['items'])

    def clear(self) -> int:
        return Cart.objects.filter(pk=self.pk).update(items=self._default_cart_value())

    def _remove_own_products_and_nonexistent_types_from_cart(self) -> int:
        """Remove invalid items and return count of removed items"""
        items_count_at_start = len(self.items)
        valid_types_pks = ProductType.objects.exclude(
            product__market__owner_id=self.user_id).values_list('pk', flat=True)
        self.items = {pk: count for pk, count in self.items.items() if int(pk) in valid_types_pks}
        return items_count_at_start - len(self.items)

    def _remove_items_with_non_natural_number_as_count(self):
        items_count_at_start = len(self.items)
        self.items = {pk: count for pk, count in self.items.items() if isinstance(count, int) and count > 0}
        return items_count_at_start - len(self.items)

    @property
    def is_filled(self):
        return self.items != self._default_cart_value

    def prepare_items(self) -> int:
        """Remove invalid items if filled, save valid items and return count of removed items"""
        count_of_removed_items = 0
        items_at_start = self.items.copy()
        if self.is_filled:
            count_of_removed_items += self._remove_own_products_and_nonexistent_types_from_cart()
            count_of_removed_items += self._remove_items_with_non_natural_number_as_count()
            if items_at_start != self.items:
                self.save(update_fields=['items'])
        return count_of_removed_items


class Balance(models.Model):
    user = models.OneToOneField(
        to=User,
        verbose_name=_('user'),
        on_delete=models.CASCADE,
        related_name='balance'
    )
    amount = models.DecimalField(
        verbose_name=_('amount'),
        max_digits=MAX_BALANCE_DIGITS_COUNT,
        decimal_places=MONEY_DECIMAL_PLACES,
        blank=True,
        default=0
    )

    def get_operations_amount_sum(self) -> Decimal:
        result = getattr(self.user, 'operations').aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')
        return result.quantize(Decimal('1.00'))


class Operation(models.Model):
    user = models.ForeignKey(
        to=User,
        verbose_name=_('user'),
        on_delete=models.SET_NULL,
        null=True,
        related_name='operations'
    )
    amount = models.DecimalField(
        verbose_name=_('amount'),
        max_digits=MAX_OPERATION_DIGITS_COUNT,
        decimal_places=MONEY_DECIMAL_PLACES)

    transaction_time = models.DateTimeField(
        verbose_name=_('transaction time'),
        auto_now=True
    )

    def get_absolute_url(self):
        return reverse_lazy('market_app:order_detail', kwargs={'pk': self.pk})

    @property
    def absolute_amount(self) -> Money:
        return abs(self.amount)

    class Meta:
        verbose_name = _('operation')
        verbose_name_plural = _('operations')


class Order(models.Model):
    operation = models.OneToOneField(
        to=Operation,
        verbose_name=_('operation'),
        on_delete=models.CASCADE,
        null=True,
        related_name='order'
    )
    coupon = models.ForeignKey(
        to='Coupon',
        verbose_name=_('coupon'),
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    user = models.ForeignKey(
        to=User,
        verbose_name=_('user'),
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders'
    )

    address = models.TextField(
        verbose_name=_('address'),
        blank=False,
        max_length=200
    )

    class OrderError(Exception):
        pass

    class CannotBeCancelledError(OrderError):
        """Raise if the order cannot be cancelled"""

    class EmptyOrderError(OrderError):
        """Raises if the order is empty"""

    @property
    def has_paid(self) -> bool:
        return self.operation_id is not None

    def is_empty(self, use_exists=False):
        if use_exists:
            # make additional query even if the order.items queryset has already been evaluated
            return not self.items.exists()
        return not self.items.all()

    @property
    def status(self) -> str:
        if not self.has_paid:
            return OrderStatusChoices.UNPAID.value
        elif not all(item.is_shipped for item in self.items.all()):
            return OrderStatusChoices.HAS_PAID.value
        else:
            return OrderStatusChoices.SHIPPED.value

    def get_units_count(self) -> dict:
        return {str(pk): amount for pk, amount in self.items.values_list('product_type_id', 'amount')}

    def get_units_count_of(self, product_type_pk) -> int:
        return self.items.values_list('amount', flat=True).filter(product_type_id=product_type_pk).first()

    def get_item(self, pk):
        return self.items.get(pk=pk)

    def get_absolute_url(self):
        return reverse_lazy('market_app:order_detail', kwargs={'pk': self.pk})

    def get_coupon_discount(self, total_price: Money) -> Money:
        if not self.coupon_id:
            return 0
        coupon = self.coupon
        coupon_discount = total_price * coupon.discount_percent / 100
        if coupon.discount_limit:
            coupon_discount = min(coupon_discount, coupon.discount_limit)
        return coupon_discount

    def get_total_price_without_coupon_discount(self) -> Money:
        total_price = 0
        items = self.items.all()
        for item in items:
            total_price += item.total_price
        return total_price

    def set_operation(self, operation_id):
        self.operation_id = operation_id

    def set_coupon(self, coupon_id: int) -> int:
        return Order.objects.filter(pk=self.pk).update(coupon_id=coupon_id)

    def cancel(self):
        if self.has_paid:
            raise Order.CannotBeCancelledError("The order cannot be cancelled because of its status.")
        items = self.items.select_related('product_type').only('pk', 'product_type', 'amount')
        product_types = []
        for item in items:
            units_in_order = item.amount
            item.product_type.units_count = F('units_count') + units_in_order
            product_types.append(item.product_type)
        ProductType.objects.bulk_update(product_types, ['units_count'])
        self.delete()

    def cancel_by_user(self, user_id) -> None:
        if self.user_id != user_id:
            raise Order.CannotBeCancelledError(f"User(id={user_id}) cannot cancel Order(id={self.pk})")
        self.cancel()

    @property
    def total_price(self) -> Money:
        if not self.operation_id:
            total_price = self.get_total_price_without_coupon_discount()
            if self.coupon_id:
                coupon_discount = self.get_coupon_discount(total_price)
                total_price -= coupon_discount
        else:
            total_price = self.operation.absolute_amount
        return round(total_price, MONEY_DECIMAL_PLACES)


class OrderItem(models.Model):
    product_type = models.ForeignKey(
        to=ProductType,
        verbose_name=_('product type'),
        related_name='order_items',
        on_delete=models.SET_NULL,
        null=True
    )
    order = models.ForeignKey(
        to=Order,
        verbose_name=_('order'),
        related_name='items',
        on_delete=models.CASCADE
    )
    # Related to seller top-up operation (However Order.operation relates to all order)
    payment = models.ForeignKey(
        to=Operation,
        on_delete=models.CASCADE,
        verbose_name=_('payment'),
        null=True,
        default=None,
    )
    amount = models.PositiveIntegerField(verbose_name=_('amount'))
    is_shipped = models.BooleanField(verbose_name=_('is shipped'), default=False)

    @property
    def total_price(self) -> Money:
        if self.payment_id:
            return self.payment.amount
        return self.product_type.sale_price * self.amount


class Coupon(models.Model):
    customers = models.ManyToManyField(
        to=User, verbose_name=_('customer')
    )

    discount_limit = models.DecimalField(
        verbose_name=_('discount limit'), blank=True, null=True,
        max_digits=15, decimal_places=MONEY_DECIMAL_PLACES
    )
    discount_percent = models.DecimalField(
        verbose_name=_('discount percent'),
        max_digits=5,
        decimal_places=2,
        default=0,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    @property
    def description(self):
        return f'-{self.discount_percent}%'

    class Meta:
        verbose_name = _('coupon')
        verbose_name_plural = _('coupons')

    class CannotBeUsedError(Exception):
        """Raises if the coupon cannot be used"""

    def __str__(self):
        str_class = _('Coupon')
        return f'{str_class}: {self.description}'
