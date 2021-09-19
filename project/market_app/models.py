from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import F, QuerySet, Sum
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _

User = get_user_model()
MAX_PRODUCT_PRICE_DIGITS_COUNT = settings.MAX_PRODUCT_PRICE_DIGITS_COUNT
MAX_BALANCE_DIGITS_COUNT = settings.MAX_BALANCE_DIGITS_COUNT
MONEY_DECIMAL_PLACES = settings.MONEY_DECIMAL_PLACES
MONEY_DECIMAL_QUANTIZE = Decimal('1.' + '0' * MONEY_DECIMAL_PLACES)
MAX_OPERATION_DIGITS_COUNT = MAX_BALANCE_DIGITS_COUNT


class ProductCategory(models.Model):
    name = models.CharField(verbose_name=_('category'), max_length=63)

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')

    def __str__(self):
        return self.name


class Market(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('market owner'))
    name = models.CharField(verbose_name=_('name'), max_length=63)
    description = models.TextField(verbose_name=_('description'), blank=True)
    created_at = models.DateTimeField(verbose_name=_('created at'), auto_now_add=True)
    logo = models.ImageField(
        verbose_name=_('logo'),
        null=True,
        blank=True,
        upload_to='markets_logos/'
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
    created_at = models.DateTimeField(verbose_name=_('created at'), auto_now_add=True)
    available = models.BooleanField(verbose_name=_('is available'), default=True)
    image = models.ImageField(
        verbose_name=_('image'),
        null=True,
        blank=True,
        upload_to='product_images/'
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

    attributes = models.TextField('attributes', blank=True)

    @property
    def get_attributes(self):
        return map(str.strip, self.attributes.split('\n'))

    def get_types(self) -> QuerySet['ProductType']:
        return getattr(self, 'product_types')

    @property
    def sale_price(self):
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
    product = models.ForeignKey(Product, related_name='product_types', on_delete=models.CASCADE)
    units_count = models.PositiveIntegerField(
        'number of units on sale',
        blank=True,
        default=0
    )
    properties = models.JSONField('properties', blank=True, default=dict)
    markup_percent = models.DecimalField(
        'markup percent of this type',
        decimal_places=2,
        max_digits=5,
        blank=True,
        default=0
    )

    @property
    def original_price(self):
        return round(self.product.original_price * (1 + (self.markup_percent / 100)), MONEY_DECIMAL_PLACES)

    @property
    def sale_price(self):
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
    def str_attributes(self):
        return ', '.join(f'{key}: {value}' for key, value in self.properties.items())

    @property
    def dict_attributes(self):
        return {attr: self.properties.get(attr, "") for attr in self.product.get_attributes}

    def __str__(self):
        return f'{self.str_attributes or f"id={self.id}"}'


class ProductImage(models.Model):
    product = models.OneToOneField(Product, verbose_name=_('product'), on_delete=models.CASCADE)
    image = models.ImageField(verbose_name=_('image'), upload_to='products_images/')

    class Meta:
        verbose_name = _('product image')
        verbose_name_plural = _('products images')


def _validate_units_quantity(quantity):
    if not isinstance(quantity, int) or quantity < 0:
        raise ValueError(f'Expected a natural number, got {quantity} instead')


def _format_product_type_data(product_type, units_in_order):
    return {
        'units_count': units_in_order,
        'properties': product_type.properties.copy(),
        'sale_price': product_type.sale_price,
        'discount_percent': product_type.product.discount_percent,
        'markup_percent': product_type.markup_percent,
        'original_price': round(product_type.product.original_price * (100 + product_type.markup_percent) / 100, 2),
        'product_name': product_type.product.name,
        'product_id': product_type.product_id,
        'market_id': product_type.product.market_id
    }


class Cart(models.Model):
    _default_cart_value = dict
    max_product_type_count_on_cart = 20
    items = models.JSONField(verbose_name=_('items'), default=_default_cart_value)

    def get_items_data(self):
        query = ProductType.objects.filter(id__in=self.items.keys()).select_related('product').only(
            'properties', 'markup_percent',
            'product__name', 'product__market_id',
            'product__discount_percent', 'product__original_price'
        )
        data = {str(item.pk): _format_product_type_data(item, self.get_count(item.pk)) for item in query}
        return data

    def get_count(self, pk):
        return self.items[str(pk)]

    def get_types_pks(self):
        return tuple(self.items.keys())

    def set_item(self, product_type_pk, quantity):
        _validate_units_quantity(quantity)
        product_type_pk = str(product_type_pk)
        if quantity == 0:
            if product_type_pk in self.items:
                del self.items[product_type_pk]
        elif product_type_pk not in self.items:
            self.items[product_type_pk] = quantity
        else:
            self.items[product_type_pk] = quantity
        self.save(update_fields=['items'])

    def clear(self):
        return Cart.objects.filter(pk=self.pk).update(items=self._default_cart_value())

    def _remove_nonexistent_product_types(self):
        old_pks = self.get_types_pks()
        new_pks = ProductType.objects.values_list('pk', flat=True)
        for pk in old_pks:
            if int(pk) not in new_pks:
                del self.items[str(pk)]
        self.save(update_fields=['items'])

    def _remove_own_products_types_from_cart(self):
        own_products_types_pks = ProductType.objects.filter(
            product__market__owner=self.shopping_account.user).values_list('pk', flat=True)
        self.items = {pk: count for pk, count in self.items.items() if int(pk) not in own_products_types_pks}
        self.save(update_fields=['items'])

    def _to_valid_units_count(self):
        valid_items = {item: count for item, count in self.items.items()}
        Cart.objects.filter(pk=self.pk).update(items=valid_items)

    def prepare_items(self):
        self._remove_nonexistent_product_types()
        self._remove_own_products_types_from_cart()
        self._to_valid_units_count()


def _create_cart():
    return Cart.objects.create()


class ShoppingAccount(models.Model):
    user = models.OneToOneField(
        to=User,
        verbose_name=_('user'),
        on_delete=models.CASCADE,
        related_name='shopping_account'
    )
    balance = models.DecimalField(
        verbose_name=_('balance'),
        max_digits=MAX_BALANCE_DIGITS_COUNT,
        decimal_places=MONEY_DECIMAL_PLACES,
        blank=True,
        default=0
    )

    cart = models.OneToOneField(
        Cart,
        verbose_name=_('cart'),
        on_delete=models.PROTECT,
        null=True,
        related_name='shopping_account'
    )

    def get_operations_amount_sum(self):
        result = getattr(self, 'operations').aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')
        return result.quantize(Decimal('1.00'))


class Operation(models.Model):
    shopping_account = models.ForeignKey(
        ShoppingAccount, verbose_name=_('customer account'),
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


class Order(models.Model):
    class OrderStatusChoices(models.TextChoices):
        UNPAID = 'UNPAID', _("awaiting for payment")
        CANCELED = "CANCEL", _("canceled")
        HAS_PAID = "HAS_PAID", _("has successfully paid")
        SHIPPED = 'SHIPPED', _("Shipped")
        DELIVERED = 'DELIVERED', _("successfully completed")

    shopping_account = models.ForeignKey(
        ShoppingAccount, verbose_name=_('customer account'),
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders'
    )
    operation = models.OneToOneField(
        to=Operation,
        verbose_name=_('customer account'),
        on_delete=models.CASCADE,
        null=True,
        related_name='order'
    )
    items = models.JSONField(verbose_name=_('order items'))
    status = models.CharField(
        max_length=15,
        choices=OrderStatusChoices.choices,
        default=OrderStatusChoices.UNPAID,
    )
    activated_coupon = models.ForeignKey(
        'Coupon',
        verbose_name=_('activated coupon'),
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    @property
    def is_unpaid(self):
        return self.status == self.OrderStatusChoices.UNPAID.name

    def get_units_count(self):
        units_count = {}
        for pk in self.items.keys():
            units_count[str(pk)] = self.get_units_count_of(pk)
        return units_count

    def get_units_count_of(self, pk) -> int:
        return self.get_item(pk)['units_count']

    def get_item(self, pk):
        return self.items.get(str(pk))

    def get_absolute_url(self):
        return reverse_lazy('market_app:order_detail', kwargs={'pk': self.pk})

    def _get_coupon_discount(self, total_price):
        coupon = self.activated_coupon
        coupon_discount = total_price * coupon.discount_percent / 100
        if coupon.max_discount:
            coupon_discount = min(coupon_discount, coupon.max_discount)
        return coupon_discount

    def set_coupon(self, coupon):
        Order.objects.filter(pk=self.pk).update(activated_coupon=coupon)

    @property
    def total_price(self):
        total_price = 0
        for item_data in self.items.values():
            total_price += item_data['units_count'] * Decimal(item_data['sale_price'])
        if self.activated_coupon:
            coupon_discount = self._get_coupon_discount(total_price)
            total_price -= coupon_discount
        return total_price


class Coupon(models.Model):
    customers = models.ManyToManyField(
        ShoppingAccount, verbose_name=_('customer')
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

    def __str__(self):
        str_class = _('Coupon')
        return f'{str_class}: {self.description}'
