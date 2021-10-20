from django import template
from django.core.paginator import Paginator

from market_app.services import get_products

register = template.Library()


@register.inclusion_tag('market_app/include/side_nav.html', takes_context=True)
def side_nav(context):
    return context


@register.inclusion_tag('market_app/include/search.html')
def product_search_form():
    return


def get_page_obj(request, queryset, page_size):
    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)
    return paginator, page_obj


@register.inclusion_tag('market_app/include/catalogue.html', takes_context=True)
def products_catalogue(context, products=None, limit=None, page_size=None, ordering="discount_percent"):
    request = context['request']
    if products is None:
        products = get_products(ordering)
    if isinstance(page_size, int) and page_size > 0:
        paginator, page_obj = get_page_obj(request, products, page_size)
        context['products'] = page_obj.object_list
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['is_paginated'] = page_obj.has_other_pages()
    else:
        context['products'] = products[:limit]
    return context
