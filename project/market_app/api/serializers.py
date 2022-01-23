from rest_framework import serializers

from market_app.models import Product, Market


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class MarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Market
        fields = ('pk', "name", "description", "created_at", 'owner_id')
