from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import F, QuerySet
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _

User = get_user_model()


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
    original_price = models.DecimalField(verbose_name=_('price'), max_digits=15, decimal_places=2)
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
        return round(self.original_price * ((100 - self.discount_percent) / 100), 2)

    @property
    def is_available_to_buy(self) -> bool:
        return self.available and any(self.get_types().values_list('units_count', flat=True))

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
        return round(self.product.original_price * (1 + (self.markup_percent / 100)), 2)

    @property
    def sale_price(self):
        return round(self.product.sale_price * (1 + (self.markup_percent / 100)), 2)

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


class ShoppingAccount(models.Model):
    user = models.OneToOneField(
        to=User,
        verbose_name=_('user'),
        on_delete=models.CASCADE,
        related_name='shopping_account'
    )
    balance = models.DecimalField(
        verbose_name=_('balance'),
        max_digits=15,
        decimal_places=2,
        blank=True,
        default=0
    )

    order = models.JSONField('order', default=dict, blank=True)

    activated_coupon = models.ForeignKey(
        'Coupon',
        verbose_name=_('activated coupon'),
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    def set_units_count_to_order(self, product_type_pk, quantity: int) -> int:
        """Try to set quantity of product-type's units.
        Return the number of units after setting"""
        if not isinstance(quantity, int) or quantity < 0:
            raise ValueError(f'Expected a natural number, got {quantity} instead')
        product_type = ProductType.objects.only('id').get(pk=product_type_pk)
        if product_type.product.market.owner == self.user:
            raise PermissionError(f'Cannot add your own product to your order.')
        product_type_pk = str(product_type_pk)
        units_count_at_start = self.order.get(product_type_pk, 0)
        difference = quantity - units_count_at_start
        # need to add
        if difference > 0:
            added_units_count = difference if difference < product_type.units_count else product_type.units_count
            if added_units_count != 0 and product_type.remove_product_units(added_units_count):
                self.order[product_type_pk] = units_count_at_start + added_units_count
        # need to reduce
        elif difference < 0:
            product_type.create_product_units(-difference)
            self.order[product_type_pk] = quantity
        units_count_after_setting = self.order.get(product_type_pk, 0)
        # don't keep order items if number of units to buy equal zero
        if units_count_after_setting == 0 and product_type_pk in self.order:
            del self.order[product_type_pk]
        self.save()
        return units_count_after_setting

    def get_order_list(self, *fields):
        result = []
        types = ProductType.objects.only(*fields).filter(id__in=self.order.keys())
        for i_type in types:
            i_type.units_on_cart = self.order[str(i_type.pk)]
            result.append(i_type)
        return result

    def clear_order(self):
        for type_pk in self.order.copy():
            self.set_units_count_to_order(type_pk, 0)

    @property
    def total_price(self):
        total_price = 0
        for item in self.get_order_list('id'):
            total_price += item.sale_price * item.units_on_cart
        if self.activated_coupon:
            coupon = self.activated_coupon
            coupon_discount_percent = coupon.discount_percent / 100
            coupon_discount = total_price * coupon_discount_percent
            if coupon.max_discount:
                coupon_discount = min(coupon_discount, coupon.max_discount)
            total_price -= coupon_discount
        return total_price


class ShoppingReceipt(models.Model):
    shopping_account = models.ForeignKey(
        ShoppingAccount, verbose_name=_('customer account'),
        on_delete=models.SET_NULL,
        null=True,
        related_name='receipts'
    )
    transaction_time = models.DateTimeField(
        verbose_name=_('transaction time'),
        auto_now=True
    )
    description = models.TextField(blank=True)
    order_items = models.JSONField(verbose_name=_('order items'))
    total_price = models.IntegerField(verbose_name=_('total price'))


class Coupon(models.Model):
    customers = models.ManyToManyField(
        ShoppingAccount, verbose_name=_('customer')
    )
    description = models.TextField(verbose_name=_('description'), blank=True)
    max_discount = models.DecimalField(
        verbose_name=_('max discount'), blank=True, null=True,
        max_digits=15, decimal_places=2
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
