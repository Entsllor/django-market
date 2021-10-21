from decimal import Decimal
from typing import Iterable, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import F, QuerySet, Sum
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from market_app.validators import default_image_format_validator, product_image_size_validator, \
    market_logo_size_validator, product_attributes_symbols_validator

User = get_user_model()
MAX_PRODUCT_PRICE_DIGITS_COUNT = settings.MAX_PRODUCT_PRICE_DIGITS_COUNT
MAX_BALANCE_DIGITS_COUNT = settings.MAX_BALANCE_DIGITS_COUNT
MONEY_DECIMAL_PLACES = settings.MONEY_DECIMAL_PLACES
MONEY_DECIMAL_QUANTIZE = Decimal('1.' + '0' * MONEY_DECIMAL_PLACES)
MAX_OPERATION_DIGITS_COUNT = MAX_BALANCE_DIGITS_COUNT
Money = Union[Decimal, int]


class OrderStatusChoices(models.TextChoices):
    UNPAID = _("awaiting for payment")
    CANCELED = _("canceled")
    HAS_PAID = _("has successfully paid")
    SHIPPED = _("Shipped")
    DELIVERED = _("successfully completed")


class ProductCategory(models.Model):
    name = models.CharField(verbose_name=_('category'), max_length=63)

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
    name = models.CharField(verbose_name=_('name'), max_length=63)
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
    properties = models.JSONField(verbose_name=_('properties'), blank=True, default=dict)
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

    @property
    def properties_as_str(self) -> str:
        return ', '.join(f'{key}: {value}' for key, value in self.properties.items())

    @property
    def properties_as_dict(self) -> dict:
        return {attr: value for attr, value in self.properties.items()}

    def __str__(self):
        return f'{self.properties_as_str or f"id={self.id}"}'

    class Meta:
        verbose_name = _('Product type')
        verbose_name_plural = _('Product types')


class ProductImage(models.Model):
    product = models.OneToOneField(Product, verbose_name=_('product'), on_delete=models.CASCADE)
    image = models.ImageField(verbose_name=_('image'), upload_to='products_images/')

    class Meta:
        verbose_name = _('product image')
        verbose_name_plural = _('products images')


def _validate_units_quantity(quantity) -> None:
    if not isinstance(quantity, int) or quantity < 0:
        raise ValueError(f'Expected a natural number, got {quantity} instead')


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
        _validate_units_quantity(quantity)
        product_type_pk = str(product_type_pk)
        if quantity == 0:
            if product_type_pk in self.items:
                del self.items[product_type_pk]
        elif product_type_pk not in self.items:
            self.items[product_type_pk] = quantity
        else:
            self.items[product_type_pk] = quantity
        if commit:
            self.save(update_fields=['items'])

    def clear(self) -> int:
        return Cart.objects.filter(pk=self.pk).update(items=self._default_cart_value())

    def _remove_nonexistent_product_types(self) -> None:
        old_pks = self.get_types_pks()
        new_pks = ProductType.objects.values_list('pk', flat=True)
        for pk in old_pks:
            if int(pk) not in new_pks:
                del self.items[str(pk)]
        self.save(update_fields=['items'])

    def _remove_own_products_types_from_cart(self) -> None:
        own_products_types_pks = ProductType.objects.filter(
            product__market__owner=self.user).values_list('pk', flat=True)
        self.items = {pk: count for pk, count in self.items.items() if int(pk) not in own_products_types_pks}
        self.save(update_fields=['items'])

    def _to_valid_units_count(self) -> int:
        valid_items = {item: count for item, count in self.items.items()}
        return Cart.objects.filter(pk=self.pk).update(items=valid_items)

    def prepare_items(self) -> None:
        self._remove_nonexistent_product_types()
        self._remove_own_products_types_from_cart()
        self._to_valid_units_count()


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

    @property
    def has_paid(self) -> bool:
        return self.operation_id is not None

    @property
    def status(self) -> str:
        if not self.has_paid:
            return OrderStatusChoices.UNPAID
        elif not all(item.is_shipped for item in self.items.all()):
            return OrderStatusChoices.HAS_PAID
        else:
            return OrderStatusChoices.SHIPPED

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
        if coupon.max_discount:
            coupon_discount = min(coupon_discount, coupon.max_discount)
        return coupon_discount

    def set_coupon(self, coupon_id: int) -> int:
        return Order.objects.filter(pk=self.pk).update(coupon_id=coupon_id)

    def get_total_price_without_coupon_discount(self) -> Money:
        total_price = 0
        items = self.items.all()
        for item in items:
            total_price += item.total_price
        return total_price

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
    description = models.TextField(verbose_name=_('description'), blank=True)
    max_discount = models.DecimalField(
        verbose_name=_('max discount'), blank=True, null=True,
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

    class Meta:
        verbose_name = _('coupon')
        verbose_name_plural = _('coupons')

    def __str__(self):
        str_class = _('Coupon')
        return f'{str_class}: {self.description}'
