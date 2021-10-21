import json

from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _

from currencies.services import exchange_to, get_currency_choices
from .models import Product, Market, ProductType, ProductCategory, Cart, Order, Coupon
from .validators import product_type_property_symbols_validator

DEFAULT_CURRENCY = settings.DEFAULT_CURRENCY_CODE
product_attributes_placeholder = _(
    'Enter product attributes separated by newline here. \nFor example:\nheight\ncolor\nmaterial\n\n'
    'You will set value to these attributes while creating new product types.'
)


class MoneyExchangerMixin(forms.Form):
    currency_code = forms.ChoiceField(
        label=_('Currency code'),
        choices=get_currency_choices,
        initial=DEFAULT_CURRENCY,
        required=False
    )

    def _clean_field_with_money_exchanging(self, field_name):
        currency_code: str = self.data.get('currency_code')
        amount = self.data[field_name]
        try:
            return exchange_to(
                DEFAULT_CURRENCY,
                amount=amount,
                _from=currency_code
            )
        except ObjectDoesNotExist:
            self.add_error(
                'currency_code',
                _(f"Sorry, but we can't find exchange rate for this currency '{currency_code}'")
            )
        return amount


class ProductUpdateForm(MoneyExchangerMixin, forms.ModelForm):
    field_order = ['name', 'description', 'currency_code', 'original_price']

    def __init__(self, *args, **kwargs):
        super(ProductUpdateForm, self).__init__(*args, **kwargs)
        self.fields['attributes'].widget.attrs = {
            'placeholder': product_attributes_placeholder,
            'rows': 10, 'cols': 40
        }

    class Meta:
        model = Product
        exclude = ['market', 'created_at']

    def clean_attributes(self):
        value = self.data.get('attributes')
        if not value:
            return ''
        rows = map(str.strip, value.splitlines())
        return '\n'.join(row for row in rows if row)

    def clean_original_price(self):
        return self._clean_field_with_money_exchanging('original_price')


class ProductForm(ProductUpdateForm):
    class Meta:
        model = Product
        exclude = ['market']


class MarketForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.owner = kwargs.pop('owner')
        super(MarketForm, self).__init__(*args, **kwargs)
        self.instance.owner = self.owner

    class Meta:
        model = Market
        exclude = ['owner']


class ProductTypeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.product = kwargs.pop('product')
        if 'product_type' in kwargs:
            self.product_type = kwargs.pop('product_type')
        super(ProductTypeForm, self).__init__(*args, **kwargs)
        self.instance.product = self.product
        for attr in self.product.get_attributes:
            if attr:
                self.fields[attr] = forms.CharField(
                    label=attr,
                    max_length=63,
                    required=False,
                    validators=[product_type_property_symbols_validator]
                )
                if hasattr(self, 'product_type'):
                    self.fields[attr].initial = self.product_type.properties.get(attr, '')

    def save(self, commit=True):
        properties = {}
        for attr in self.product.get_attributes:
            if attr:
                properties[attr] = self.cleaned_data.get(attr, '')
        self.instance.properties = properties
        super(ProductTypeForm, self).save(commit)

    class Meta:
        model = ProductType
        exclude = ['product', 'properties']


class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(min_value=0, max_value=Cart.max_product_type_count_on_cart)

    def __init__(self, *args, **kwargs):
        self.types = kwargs.pop('types')
        super(AddToCartForm, self).__init__(*args, **kwargs)
        choices = ((i_type.pk, str(i_type)) for i_type in self.types)
        self.fields['product_type'] = forms.ChoiceField(
            choices=choices, initial=1
        )
        self.fields['product_type'].widget.attrs.update(
            onchange='onChangeCount()'
        )
        self.fields['quantity'].widget.attrs.update(
            onchange='onChangeCount()'
        )


class AgreementForm(forms.Form):
    agreement = forms.BooleanField(label=_('I am sure'), required=True)


class CreditCardForm(forms.Form):
    name_on_card = forms.CharField(max_length=63)
    card_number = forms.IntegerField(min_value=1000_0000_0000_0000, max_value=9999_9999_9999_9999)


class TopUpForm(MoneyExchangerMixin, CreditCardForm):
    top_up_amount = forms.DecimalField(min_value=1, max_value=1000000)

    def clean_top_up_amount(self):
        return self._clean_field_with_money_exchanging('top_up_amount')


class CheckOutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['coupon', 'address']

    def __init__(self, *args, **kwargs):
        super(CheckOutForm, self).__init__(*args, **kwargs)
        coupons = Coupon.objects.filter(customers__exact=self.instance.user_id)
        self.coupons_json = json.dumps(
            {str(coupon.pk): {
                'discount_percent': str(coupon.discount_percent),
                'max_discount': str(coupon.max_discount) if coupon.max_discount else None
            } for coupon in coupons})
        self.fields['coupon'].queryset = coupons
        self.fields['coupon'].widget.attrs.update(
            onchange='onChangeActivatedCoupon()'
        )
        self.order_fields(['address', 'coupon'])


class CartForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.cart = kwargs.pop('cart')
        super(CartForm, self).__init__(*args, **kwargs)
        for pk, count in self.cart.items.items():
            self.fields[pk] = forms.IntegerField(
                initial=count,
                min_value=0,
                max_value=Cart.max_product_type_count_on_cart
            )


class AdvancedSearchForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.currency_code = kwargs.pop('currency_code')
        super(AdvancedSearchForm, self).__init__(*args, **kwargs)
        self.fields['min_price'].label = _('Min price') + f' ({self.currency_code}):'
        self.fields['max_price'].label = _('Max price') + f' ({self.currency_code}):'
        self.fields['currency_code'] = forms.CharField(
            max_length=3, initial=self.currency_code, widget=forms.HiddenInput())

    q = forms.CharField(label=_('Query'), max_length=63, required=False)
    min_price = forms.IntegerField(min_value=0, max_value=1000000000, required=False)
    max_price = forms.IntegerField(min_value=0, max_value=1000000000, required=False)
    category = forms.ModelChoiceField(label=_('Category'), queryset=ProductCategory.objects.all(), required=False)
    show_if_sold_out = forms.BooleanField(label=_('Show if sold out'), required=False)
