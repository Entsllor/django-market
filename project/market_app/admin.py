from django.contrib import admin

from .models import *


class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']


class MarketAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'created_at']


class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'market', 'original_price', 'discount_percent', 'available']
    list_filter = ['market', 'available']


class ProductUnitAdmin(admin.ModelAdmin):
    list_display = ['product', 'id']


admin.site.register(ProductCategory, CategoryAdmin)
admin.site.register(Market, MarketAdmin)
admin.site.register(Product, ProductAdmin)
