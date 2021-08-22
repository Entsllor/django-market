import re

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views import generic

from .forms import ProductForm, MarketForm, ProductUpdateForm, AddToCartForm, ProductTypeForm, CreditCardForm, \
    CheckOutForm, SelectCouponForm
from .models import Product, Market, ProductType, ShoppingAccount
from .services import top_up_balance, make_purchase


class MarketOwnerRequiredMixin(PermissionRequiredMixin):
    def get_permission_denied_message(self):
        return self.permission_denied_message or "Current user isn't the market owner"

    def has_permission(self):
        is_current_user_the_market_owner = getattr(
            self, 'request').user.id == self.get_current_market_owner_id()
        if self.permission_required is None:
            return is_current_user_the_market_owner
        return super(MarketOwnerRequiredMixin, self).has_permission() and is_current_user_the_market_owner

    def get_current_market_owner_id(self):
        raise NotImplementedError("""Method get_current_market_owner_id hasn't been implemented yet.""")


class ProductEditView(MarketOwnerRequiredMixin, generic.UpdateView):
    form_class = ProductUpdateForm
    model = Product
    context_object_name = 'product'
    template_name = 'market_app/edit_product.html'

    def get_success_url(self):
        return reverse_lazy('market_app:product', args=[self.object.pk])

    def get_current_market_owner_id(self):
        return self.model.objects.get(pk=self.kwargs['pk']).market.owner.id


class ProductCreateView(LoginRequiredMixin, generic.CreateView):
    form_class = ProductForm
    template_name = 'market_app/create_product.html'

    def get_form_kwargs(self):
        kwargs = super(ProductCreateView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class ProductTypeCreate(MarketOwnerRequiredMixin, generic.CreateView):
    model = ProductType
    form_class = ProductTypeForm
    template_name = 'market_app/product_type_create.html'

    def get_current_market_owner_id(self):
        return Product.objects.get(pk=self.kwargs['pk']).market.owner.id

    def get_success_url(self):
        return reverse_lazy('market_app:product', args=[self.kwargs['pk']])

    def get_form_kwargs(self):
        kwargs = super(ProductTypeCreate, self).get_form_kwargs()
        kwargs['product'] = Product.objects.get(pk=self.kwargs['pk'])
        return kwargs


class ProductTypeEdit(MarketOwnerRequiredMixin, generic.UpdateView):
    model = ProductType
    form_class = ProductTypeForm
    template_name = 'market_app/product_type_edit.html'

    def get_form_kwargs(self):
        kwargs = super(ProductTypeEdit, self).get_form_kwargs()
        kwargs['product'] = self.object.product
        kwargs['product_type'] = self.object
        return kwargs

    def get_success_url(self):
        return self.get_object().product.get_absolute_url()

    def get_current_market_owner_id(self):
        return self.get_object().product.market.owner.id


class CatalogueView(generic.ListView):
    model = Product
    template_name = 'market_app/catalogue.html'
    context_object_name = 'products'
    paginate_by = 36

    def get_queryset(self):
        queryset = self.model.objects.filter(available=True, product_types__isnull=False)
        return queryset


class ProductPageView(generic.FormView):
    model = Product
    template_name = 'market_app/product.html'
    form_class = AddToCartForm
    success_url = reverse_lazy('market_app:catalogue')

    def setup(self, request, *args, **kwargs):
        super(ProductPageView, self).setup(request, *args, **kwargs)
        self.product = Product.objects.get(pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super(ProductPageView, self).get_context_data(**kwargs)
        if 'product' not in context:
            context['product'] = self.product
        return context

    def get_form_kwargs(self):
        kwargs = super(ProductPageView, self).get_form_kwargs()
        kwargs['types'] = self.product.product_types.filter(units_count__gt=0)
        return kwargs

    def form_valid(self, form):
        quantity = form.cleaned_data['quantity']
        if self.product.market.owner_id == self.request.user.id:
            form.add_error('product_type', _('Cannot buy your own product.'))
            return super(ProductPageView, self).form_invalid(form)
        added_units_count = self.request.user.shopping_account.set_units_count_to_order(
            product_type_pk=form.cleaned_data['product_type'].pk,
            quantity=quantity
        )
        if added_units_count == 0 and quantity != 0:
            form.add_error('product_type', _('This type is old out'))
            return super(ProductPageView, self).form_invalid(form)
        return super(ProductPageView, self).form_valid(form)


class MarketCreateView(generic.CreateView):
    template_name = 'market_app/market_create.html'
    form_class = MarketForm

    def get_form_kwargs(self):
        kwargs = super(MarketCreateView, self).get_form_kwargs()
        kwargs['owner'] = self.request.user
        return kwargs


class MarketEditView(MarketOwnerRequiredMixin, generic.UpdateView):
    model = Market
    fields = ['name', 'description', 'logo']
    template_name = 'market_app/market_edit.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_current_market_owner_id(self):
        return self.model.objects.get(pk=self.kwargs['pk']).owner.id


class CartView(LoginRequiredMixin, generic.FormView):
    template_name = 'market_app/cart_page.html'
    model = ShoppingAccount
    form_class = SelectCouponForm
    context_object_name = 'shopping_account'
    success_url = reverse_lazy('market_app:cart')

    def form_valid(self, form):
        activated_coupon = form.cleaned_data['activated_coupon']
        self.request.user.shopping_account.activated_coupon = activated_coupon
        self.request.user.shopping_account.save()
        return super(CartView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(CartView, self).get_context_data(**kwargs)
        context['shopping_account'] = self.request.user.shopping_account
        return context

    def get_form_kwargs(self):
        kwargs = super(CartView, self).get_form_kwargs()
        kwargs['shopping_account'] = self.request.user.shopping_account
        return kwargs


class CheckOutView(LoginRequiredMixin, generic.FormView):
    template_name = 'market_app/checkout_page.html'
    success_url = reverse_lazy('market_app:order_confirmation')
    form_class = CheckOutForm

    def get(self, request, *args, **kwargs):
        shopping_account = self.request.user.shopping_account
        if not shopping_account.order:
            messages.warning(request=self.request, message='Your order is empty')
            return HttpResponseRedirect(reverse_lazy('market_app:cart'))
        if shopping_account.balance < shopping_account.total_price:
            return HttpResponseRedirect(
                reverse_lazy('market_app:top_up'))
        return super(CheckOutView, self).get(request, *args, **kwargs)

    def form_valid(self, form):
        is_agree = form.cleaned_data['agreement']
        if not is_agree:
            return HttpResponseRedirect(reverse_lazy('market_app:cart'))
        make_purchase(self.request.user.shopping_account)
        return super(CheckOutView, self).form_valid(form)


class TopUpView(LoginRequiredMixin, generic.FormView):
    form_class = CreditCardForm
    template_name = 'market_app/top_up_page.html'
    success_url = reverse_lazy('market_app:cart')

    def form_valid(self, form):
        amount = form.cleaned_data['top_up_amount']
        top_up_balance(self.request.user.shopping_account, amount)
        return super(TopUpView, self).form_valid(form)


class OrderConfirmationView(LoginRequiredMixin, generic.ListView):
    template_name = 'market_app/order_confirmation_page.html'
    queryset = Product.objects.all()[:8]
    context_object_name = 'products'


class UserMarketsView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'market_app/user_markets.html'


class MarketView(generic.detail.SingleObjectMixin, generic.ListView):
    template_name = 'market_app/market_page.html'
    context_object_name = 'market'
    paginate_by = 36

    def get(self, request, *args, **kwargs):
        self.object = Market.objects.get(pk=self.kwargs['pk'])
        return super(MarketView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['market'] = self.object
        return context

    def get_queryset(self):
        return self.object.product_set.all()


class SearchProducts(CatalogueView):
    template_name = 'market_app/catalogue.html'
    success_url = reverse_lazy('market_app:catalogue')

    def get_queryset(self):
        query_params = {'available': True}

        show_if_sold_out = self.request.GET.get('show_if_sold_out')
        if not show_if_sold_out or show_if_sold_out in ('0', 'False', 'false'):
            query_params['product_types__isnull'] = False

        market = self.request.GET.get('market')
        if market:
            query_params['market__name'] = market

        min_price = self.request.GET.get('min_price')
        if min_price and re.fullmatch(r'[0-9]+(\.[0-9]{1,2})?', min_price):
            query_params['original_price__gte'] = min_price

        max_price = self.request.GET.get('max_price')
        if max_price and re.fullmatch(r'[0-9]+(\.[0-9]{1,2})?', max_price):
            query_params['original_price__lte'] = max_price
        query_set = Product.objects.filter(**query_params)

        exclude_market = self.request.GET.get('-market') or self.request.GET.get('market!')
        if exclude_market:
            query_set = query_set.exclude(market__name__iexact=exclude_market)
        text_from_search_field = self.request.GET.get('q')
        if text_from_search_field:
            query_set = query_set.filter(
                Q(name__icontains=text_from_search_field) |
                Q(description__icontains=text_from_search_field))
        return query_set
