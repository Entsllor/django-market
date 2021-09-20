from django.contrib import admin

# from .models import Currency


class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'rate', 'sym']


# admin.site.register(Currency, CurrencyAdmin)
