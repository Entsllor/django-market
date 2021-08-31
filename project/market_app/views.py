import re

from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views import generic

from currencies.services import get_currency_code_by_language, DEFAULT_CURRENCY, \
    get_exchanger
from .forms import ProductForm, MarketForm, ProductUpdateForm, AddToCartForm, ProductTypeForm, CreditCardForm, \
    AdvancedSearchForm, SelectCouponForm, CartForm, CheckOutForm
from .models import Product, Market, ProductType, Operation, Order
from .services import top_up_balance, make_purchase, prepare_order


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
        fields = ('image', 'original_price', 'discount_percent', 'name')
        queryset = self.model.objects.distinct().only(*fields).filter(available=True, product_types__isnull=False)
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
        self.request.user.shopping_account.cart.set_item(
            product_type_pk=form.cleaned_data['product_type'].pk,
            quantity=quantity)
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
    context_object_name = 'shopping_account'
    form_class = CartForm

    def get_context_data(self, **kwargs):
        context = super(CartView, self).get_context_data(**kwargs)
        context['cart'] = self.request.user.shopping_account.cart
        return context

    def get_form_kwargs(self):
        kwargs = super(CartView, self).get_form_kwargs()
        kwargs['cart'] = self.request.user.shopping_account.cart
        return kwargs

    def form_valid(self, form):
        order = prepare_order(self.request.user.shopping_account.cart)
        return HttpResponseRedirect(reverse_lazy('market_app:checkout', kwargs={'pk': order.pk}))


class OrderDetail(PermissionRequiredMixin, generic.DetailView):
    template_name = 'market_app/order_detail.html'
    model = Order

    def has_permission(self):
        user = self.request.user
        return user.id == self.get_object().shopping_account.user_id


class OrderListView(generic.ListView):
    template_name = 'market_app/orders_history.html'
    model = Order

    def get_queryset(self):
        return Order.objects.filter(shopping_account_id=self.request.user.shopping_account.id)


class CheckOutView(PermissionRequiredMixin, generic.DetailView):
    template_name = 'market_app/checkout_page.html'
    success_url = reverse_lazy('market_app:order_confirmation')
    model = Order
    context_object_name = 'order'

    def get(self, request, *args, **kwargs):
        shopping_account = self.request.user.shopping_account
        if shopping_account.balance < self.get_object().total_price:
            return HttpResponseRedirect(
                reverse_lazy('market_app:top_up'))
        return super(CheckOutView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CheckOutView, self).get_context_data(**kwargs)
        context['coupon_form'] = SelectCouponForm(shopping_account=self.request.user.shopping_account)
        context['form'] = CheckOutForm
        return context

    def has_permission(self):
        user = self.request.user
        return user.id == self.get_object().shopping_account.user_id

    def post(self, request, *args, **kwargs):
        coupon = request.POST.get('coupon')
        if request.POST.get('agreement') == 'on':
            make_purchase(self.get_object(), self.request.user.shopping_account, coupon)
            return HttpResponseRedirect(self.success_url)
        else:
            return HttpResponseRedirect(reverse_lazy('market_app:orders'))


class TopUpView(LoginRequiredMixin, generic.FormView):
    form_class = CreditCardForm
    template_name = 'market_app/top_up_page.html'
    success_url = reverse_lazy('market_app:catalogue')

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


class MarketsList(generic.ListView):
    template_name = 'market_app/markets_list.html'
    model = Market
    context_object_name = 'markets'
    paginate_by = 18


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


class SearchProducts(CatalogueView, generic.edit.FormMixin):
    template_name = 'market_app/advanced_search.html'
    success_url = reverse_lazy('market_app:catalogue')
    form_class = AdvancedSearchForm

    def get_form_kwargs(self):
        kwargs = super(SearchProducts, self).get_form_kwargs()
        currency_code = get_currency_code_by_language(self.request.LANGUAGE_CODE)
        kwargs['currency_code'] = currency_code
        return kwargs

    def get_form(self, form_class=AdvancedSearchForm):
        form = super(SearchProducts, self).get_form(form_class)
        visible_field_names = tuple(field.name for field in form.visible_fields())
        initials = {key: value for key, value in self.request.GET.items()
                    if key in visible_field_names}
        initials.update(form.initial)
        form.initial = initials
        return form

    def get_queryset(self):
        fields = ('image', 'original_price', 'discount_percent', 'name')
        query_params = {'available': True}

        show_if_sold_out = self.request.GET.get('show_if_sold_out')
        if not show_if_sold_out or show_if_sold_out in ('0', 'False', 'false'):
            query_params['product_types__isnull'] = False

        market = self.request.GET.get('market')
        if market:
            query_params['market__name'] = market

        category = self.request.GET.get('category')
        if category:
            query_params['category'] = category

        currency_code = self.request.GET.get('currency_code', DEFAULT_CURRENCY)
        exchange_to_default = get_exchanger(to=DEFAULT_CURRENCY, _from=currency_code)
        min_price = self.request.GET.get('min_price')
        if min_price and re.fullmatch(r'[0-9]+(\.[0-9]{1,2})?', min_price):
            query_params['original_price__gte'] = exchange_to_default(min_price)

        max_price = self.request.GET.get('max_price')
        if max_price and re.fullmatch(r'[0-9]+(\.[0-9]{1,2})?', max_price):
            query_params['original_price__lte'] = exchange_to_default(max_price)
        query_set = Product.objects.distinct().only(*fields).filter(**query_params)

        exclude_market = self.request.GET.get('-market') or self.request.GET.get('market!')
        if exclude_market:
            query_set = query_set.exclude(market__name__iexact=exclude_market)
        text_from_search_field = self.request.GET.get('q')
        if text_from_search_field:
            query_set = query_set.filter(
                Q(name__icontains=text_from_search_field) |
                Q(description__icontains=text_from_search_field))
        return query_set


class OperationHistoryView(LoginRequiredMixin, generic.ListView):
    template_name = 'market_app/operation_history.html'
    model = Operation

    def get_queryset(self):
        user_shopping_account_id = self.request.user.shopping_account.id
        return Operation.objects.filter(shopping_account_id=user_shopping_account_id)
