from rest_framework import viewsets

from market_app.models import Market
from market_app.api.serializers import ProductSerializer, MarketSerializer
from market_app.services import get_products


class ProductViewSet(viewsets.ModelViewSet):
    queryset = get_products()
    serializer_class = ProductSerializer


class MarketViewSet(viewsets.ModelViewSet):
    queryset = Market.objects.all().order_by("-created_at")
    serializer_class = MarketSerializer
