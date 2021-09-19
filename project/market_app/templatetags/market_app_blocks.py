from django import template

from market_app.models import Product

register = template.Library()


@register.inclusion_tag('market_app/include/side_nav.html', takes_context=True)
def side_nav(context):
    return context


@register.inclusion_tag('market_app/include/search.html')
def product_search_form():
    return


@register.inclusion_tag('market_app/include/catalogue.html', takes_context=True)
def products_catalogue(context, count=36, ordering="discount_percent"):
    products = Product.objects.select_related('productimage').filter(
        available=True).order_by(ordering)[:count]
    context['products'] = products
    return context
