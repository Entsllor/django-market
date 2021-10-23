import json
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Prefetch
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from currencies.models import Currency
from currencies.services import get_currency_code_by_language, DEFAULT_CURRENCY_CODE, \
    get_exchanger
from .forms import ProductForm, MarketForm, ProductUpdateForm, AddToCartForm, ProductTypeForm, CreditCardForm, \
    AdvancedSearchForm, CartForm, CheckOutForm, TopUpForm, AgreementForm
from .models import Product, Market, ProductType, Operation, Order, OrderItem
from .services import top_up_balance, make_purchase, prepare_order, EmptyOrderError, OrderCannotBeCancelledError, \
    try_to_cancel_order, get_products, OrderCouponError


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
        return Product.objects.filter(pk=self.kwargs['pk']).values_list('market__owner_id', flat=True)[0]


class ProductCreateView(LoginRequiredMixin, generic.CreateView):
    form_class = ProductForm
    template_name = 'market_app/create_product.html'

    def form_valid(self, form):
        product = form.save(commit=False)
        product.market = self.request.user.market
        product.save()
        return HttpResponseRedirect(product.get_absolute_url())


class ProductTypeCreate(MarketOwnerRequiredMixin, generic.CreateView):
    model = ProductType
    form_class = ProductTypeForm
    template_name = 'market_app/product_type_create.html'

    def get_current_market_owner_id(self):
        return Product.objects.filter(pk=self.kwargs['pk']).values_list('market__owner_id', flat=True)[0]

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
        return ProductType.objects.filter(pk=self.kwargs['pk']).values_list('product__market__owner_id', flat=True)[0]


class CatalogueView(generic.ListView):
    template_name = 'market_app/catalogue.html'
    context_object_name = 'products'

    def get_queryset(self):
        return get_products()


class ProductView(generic.FormView):
    model = Product
    template_name = 'market_app/product.html'
    form_class = AddToCartForm
    success_url = reverse_lazy('market_app:catalogue')

    def setup(self, request, *args, **kwargs):
        super(ProductView, self).setup(request, *args, **kwargs)
        self.object = Product.objects.prefetch_related(
            Prefetch('product_types', ProductType.objects.filter(units_count__gt=0))
        ).select_related('market').get(pk=self.kwargs['pk'])
        self.product_types = self.object.product_types.all()

    def get_context_data(self, **kwargs):
        context = super(ProductView, self).get_context_data(**kwargs)
        context['product'] = self.object
        context['products'] = get_products().filter(category_id=self.object.category_id)
        context['markup_percents'] = json.dumps(
            {i_type.pk: str(i_type.markup_percent) for i_type in self.product_types}
        )
        context['is_market_owner'] = self.object.market.owner_id == self.request.user.id
        return context

    def get_form_kwargs(self):
        kwargs = super(ProductView, self).get_form_kwargs()
        kwargs['types'] = self.product_types
        return kwargs

    def post(self, request, *args, **kwargs):
        return super(ProductView, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        if not self.request.user.is_authenticated:
            return redirect_to_login(next=self.object.get_absolute_url())
        quantity = form.cleaned_data['quantity']
        if self.object.market.owner_id == self.request.user.id:
            form.add_error('product_type', _('Cannot buy your own product.'))
            return super(ProductView, self).form_invalid(form)
        self.request.user.cart.set_item(
            product_type_pk=form.cleaned_data['product_type'],
            quantity=quantity)
        return super(ProductView, self).form_valid(form)


class MarketCreateView(LoginRequiredMixin, generic.CreateView):
    template_name = 'market_app/market_create.html'
    form_class = MarketForm
    success_url = reverse_lazy('market_app:user_market')

    def setup(self, request, *args, **kwargs):
        super(MarketCreateView, self).setup(request, *args, **kwargs)
        self.has_market = Market.objects.filter(owner_id=request.user.id).exists()

    def get(self, request, *args, **kwargs):
        if self.has_market:
            return HttpResponseRedirect(reverse_lazy('market_app:user_market'), status=302)
        return super(MarketCreateView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.has_market:
            raise PermissionDenied('User can have only one market')
        return super(MarketCreateView, self).post(request, *args, **kwargs)

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
        return self.model.objects.filter(pk=self.kwargs['pk']).values_list('owner_id', flat=True).first()


class CartView(LoginRequiredMixin, generic.FormView):
    template_name = 'market_app/cart_page.html'
    form_class = CartForm

    def get_context_data(self, **kwargs):
        context = super(CartView, self).get_context_data(**kwargs)
        context['cart'] = self.request.user.cart
        return context

    def get_form_kwargs(self):
        kwargs = super(CartView, self).get_form_kwargs()
        kwargs['cart'] = self.request.user.cart
        return kwargs

    def form_valid(self, form):
        if unpaid_order := Order.objects.filter(user=self.request.user, operation__isnull=True).first():
            message = _('Sorry, but you can not create a new order because you have an unpaid order. '
                        'Please pay for this unpaid order or cancel it')
            messages.warning(self.request, message)
            return HttpResponseRedirect(unpaid_order.get_absolute_url(), status=302)
        cart = self.request.user.cart
        cart.items = form.cleaned_data
        order: Order = prepare_order(cart)
        almost_sold_types_pks = {
            item.product_type_id: item.amount for item in order.items.all() if
            item.amount < form.cleaned_data.get(str(item.product_type_id))
        }
        if almost_sold_types_pks:
            types = ProductType.objects.filter(
                id__in=almost_sold_types_pks).select_related('product').only('product__name')
            for product_type in types:
                amount = almost_sold_types_pks[product_type.pk]
                message = _('Sorry, product "{}" is almost sold out and we can sell only {} of these.')
                messages.warning(self.request, message.format(product_type.product.name, amount))
        return HttpResponseRedirect(reverse_lazy('market_app:checkout', kwargs={'pk': order.pk}))


class OrderDetail(PermissionRequiredMixin, generic.DetailView):
    template_name = 'market_app/order_detail.html'
    model = Order
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super(OrderDetail, self).get_context_data(**kwargs)
        return context

    def get_object(self, queryset=None):
        order_pk = self.kwargs['pk']
        if not hasattr(self, 'object'):
            try:
                self.object = Order.objects.prefetch_related(
                    Prefetch('items', OrderItem.objects.only(
                        'product_type__product__name', 'amount', 'payment__amount',
                        'order', 'product_type__properties', 'product_type__markup_percent',
                        'product_type__product__discount_percent',
                        'product_type__product__original_price', 'is_shipped'
                    ).filter(order_id=order_pk).select_related(
                        'product_type', 'product_type__product', 'payment'
                    ))
                ).select_related('operation').get(pk=self.kwargs['pk'])
            except Order.DoesNotExist:
                raise Http404(f"Order(pk={order_pk}) does not exists")
        return self.object

    def has_permission(self):
        user = self.request.user
        return user.id == self.get_object().user_id


class OrderListView(generic.ListView):
    template_name = 'market_app/orders_history.html'
    model = Order

    def get_queryset(self):
        user_id = self.request.user.id
        return Order.objects.filter(user_id=user_id).prefetch_related(
            Prefetch(
                'items',
                OrderItem.objects.only(
                    'product_type__product__name', 'amount', 'payment__amount',
                    'order', 'product_type__markup_percent',
                    'product_type__product__discount_percent',
                    'product_type__product__original_price', 'is_shipped').select_related(
                    'product_type', 'product_type__product'
                )
            )
        ).select_related('operation')


@login_required
def cancel_order_view(request, pk):
    order = get_object_or_404(Order, pk=pk)
    try:
        try_to_cancel_order(order, request.user.id)
        return HttpResponseRedirect(reverse_lazy('market_app:orders'))
    except OrderCannotBeCancelledError as exc:
        raise PermissionDenied(exc)


class CheckOutView(PermissionRequiredMixin, generic.UpdateView):
    template_name = 'market_app/checkout_page.html'
    form_class = CheckOutForm
    model = Order
    context_object_name = 'order'

    def get_success_url(self):
        return reverse_lazy('market_app:paying', kwargs={'pk': self.object.pk})

    def get_object(self, queryset=None) -> Order:
        if not hasattr(self, 'object'):
            order_pk = self.kwargs['pk']
            self.object: Order = Order.objects.prefetch_related(
                Prefetch('items', OrderItem.objects.only(
                    'product_type__product__name', 'amount', 'payment__amount',
                    'order', 'product_type__properties', 'product_type__markup_percent',
                    'product_type__product__discount_percent',
                    'product_type__product__original_price'
                ).filter(order_id=order_pk).select_related(
                    'product_type', 'product_type__product', 'payment'
                ))
            ).select_related('operation').get(pk=order_pk)
        return self.object

    def get_context_data(self, **kwargs):
        context = super(CheckOutView, self).get_context_data(**kwargs)
        total_price_without_coupon_discount = self.object.get_total_price_without_coupon_discount()
        context['total_price_without_coupon_discount'] = total_price_without_coupon_discount
        return context

    def has_permission(self):
        user = self.request.user
        return user.id == self.get_object().user_id


class PayingView(LoginRequiredMixin, generic.FormView):
    template_name = 'market_app/paying_page.html'
    success_url = reverse_lazy('market_app:order_confirmation')

    def setup(self, request, *args, **kwargs):
        super(PayingView, self).setup(request, *args, **kwargs)
        self.unpaid_order: Order = Order.objects.prefetch_related(
            Prefetch('items', OrderItem.objects.only(
                'amount', 'order', 'product_type__markup_percent',
                'product_type__product__discount_percent',
                'product_type__product__original_price', 'payment_id'
            ).select_related(
                'product_type', 'product_type__product'
            ))
        ).filter(
            operation_id=None, pk=kwargs['pk']).first()
        if not self.unpaid_order:
            raise Http404(f"Order({kwargs['pk']}) does not exist")
        if self.unpaid_order.user_id != request.user.id:
            raise PermissionDenied()
        self.total_order_price = self.unpaid_order.total_price
        self.top_up_amount = max(0, self.total_order_price - self.request.user.balance.amount)

    def try_to_make_order(self):
        try:
            make_purchase(self.unpaid_order, self.request.user)
        except PermissionDenied as exc:
            raise exc
        except EmptyOrderError:
            messages.warning(self.request, 'Cannot perform empty order')
            return HttpResponseRedirect(reverse_lazy('market_app:cart'))
        except OrderCouponError:
            messages.warning(
                self.request, f"You can't use this coupon '{self.unpaid_order.coupon.description}'"
            )
            return HttpResponseRedirect(reverse_lazy('market_app:checkout', kwargs={'pk': self.unpaid_order.pk}))
        return HttpResponseRedirect(self.success_url)

    def get_form_class(self):
        if self.top_up_amount:
            return CreditCardForm
        return AgreementForm

    def get_template_names(self):
        if self.top_up_amount:
            return super(PayingView, self).get_template_names()
        return 'market_app/paying_if_user_balance_gte_order_price.html'

    def get_context_data(self, **kwargs):
        context = super(PayingView, self).get_context_data(**kwargs)
        context['unpaid_order'] = self.unpaid_order
        context['total_order_price'] = self.total_order_price
        context['top_up_amount'] = self.top_up_amount
        return context

    def form_valid(self, form):
        if isinstance(form, CreditCardForm):
            top_up_balance(self.request.user, self.top_up_amount)
            self.request.user.refresh_from_db()
        return self.try_to_make_order()


class TopUpView(LoginRequiredMixin, generic.FormView):
    form_class = TopUpForm
    template_name = 'market_app/top_up_page.html'
    success_url = reverse_lazy('market_app:catalogue')

    def form_valid(self, form):
        amount = form.cleaned_data['top_up_amount']
        top_up_balance(self.request.user, amount)
        unpaid_order_pk = Order.objects.values_list('pk', flat=True).filter(
            user_id=self.request.user, operation__isnull=True).first()
        if unpaid_order_pk:
            return HttpResponseRedirect(
                reverse_lazy('market_app:checkout', kwargs={'pk': unpaid_order_pk}))
        return super(TopUpView, self).form_valid(form)


class OrderConfirmationView(LoginRequiredMixin, generic.ListView):
    template_name = 'market_app/order_confirmation_page.html'
    queryset = Product.objects.all()[:8]
    context_object_name = 'products'


class MarketsList(generic.ListView):
    template_name = 'market_app/markets_list.html'
    model = Market
    context_object_name = 'markets'
    paginate_by = 18
    ordering = 'created_at'

    def get_queryset(self):
        return super(MarketsList, self).get_queryset(
        ).prefetch_related('product_set')


class UserMarketView(LoginRequiredMixin, generic.DetailView):
    template_name = 'market_app/user_market.html'
    model = Market
    context_object_name = 'market'

    def get(self, request, *args, **kwargs):
        if not self.get_object():
            return HttpResponseRedirect(reverse_lazy('market_app:create_market'), status=302)
        return super(UserMarketView, self).get(request, *args, **kwargs)

    def get_object(self, queryset=None):
        if not hasattr(self, 'object'):
            self.object = Market.objects.select_related('owner').filter(owner_id=self.request.user.id).first()
        return self.object

    def get_context_data(self, **kwargs):
        context = super(UserMarketView, self).get_context_data(**kwargs)
        context['products'] = Product.objects.filter(market_id=self.object.pk)
        return context


class MarketView(generic.DetailView):
    template_name = 'market_app/market_page.html'
    context_object_name = 'market'
    model = Market

    def get_object(self, queryset=None):
        if not hasattr(self, 'object'):
            self.object = Market.objects.select_related('owner').get(pk=self.kwargs['pk'])
        return self.object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = get_products().filter(market_id=self.object.pk).all()
        return context


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

        market_name = self.request.GET.get('market')
        if market_name:
            query_params['market__name'] = market_name

        category = self.request.GET.get('category')
        if category:
            query_params['category'] = category

        currency_code = self.request.GET.get('currency_code', DEFAULT_CURRENCY_CODE)
        try:
            exchange_to_default = get_exchanger(to=DEFAULT_CURRENCY_CODE, _from=currency_code)
        except Currency.DoesNotExist:
            exchange_to_default = get_exchanger(DEFAULT_CURRENCY_CODE, DEFAULT_CURRENCY_CODE)
            messages.warning(
                self.request,
                _('Sorry, but we cannot find current rate for this currency: {}').format(currency_code)
            )

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
        user_id = self.request.user.id
        return Operation.objects.filter(user_id=user_id)


class ShippingPage(MarketOwnerRequiredMixin, generic.ListView):
    template_name = 'market_app/order_items_list.html'
    model = OrderItem
    context_object_name = 'orders_items'

    def get_current_market_owner_id(self):
        return Market.objects.filter(pk=self.kwargs['pk']).values_list('owner_id', flat=True).first()

    def get_queryset(self):
        self.queryset = OrderItem.objects.select_related(
            'product_type', 'product_type__product', 'order', 'payment').filter(
            payment__user_id=self.request.user.id).only(
            'product_type__product__name', 'amount',
            'order__address', 'is_shipped', 'product_type__properties', 'payment__amount',
            'payment__transaction_time'
        )
        return self.queryset

    def post(self, request, *args, **kwargs):
        pks = [pk[5:] for pk, value in request.POST.items()
               if isinstance(pk, str) and pk.startswith('item_') and value == 'on']
        if self.queryset is None:
            self.get_queryset()
        self.queryset.filter(id__in=pks).update(is_shipped=True)
        return HttpResponseRedirect(reverse_lazy('market_app:shipping', kwargs=self.kwargs))
