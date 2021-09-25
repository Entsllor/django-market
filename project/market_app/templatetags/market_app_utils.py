from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, field, value):
    query = context['request'].GET.copy()
    query[field] = value
    return query.urlencode()


@register.simple_tag
def units_in_cart_count(cart, pk):
    return cart.get_count(pk)
