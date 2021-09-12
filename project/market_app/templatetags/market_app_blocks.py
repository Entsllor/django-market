from django import template

register = template.Library()


@register.inclusion_tag('market_app/include/side_nav.html', takes_context=True)
def side_nav(context):
    return context


@register.inclusion_tag('market_app/include/search.html')
def product_search_form():
    return
