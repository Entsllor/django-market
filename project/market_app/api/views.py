from rest_framework import viewsets

from market_app.api.serializers import *


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter().order_by()
    serializer_class = ProductSerializer


class MarketViewSet(viewsets.ModelViewSet):
    queryset = Market.objects.all().order_by("-created_at")
    serializer_class = MarketSerializer


class ProductTypeViewSet(viewsets.ModelViewSet):
    queryset = ProductType.objects.filter().order_by()
    serializer_class = ProductTypeSerializer


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.filter().order_by()
    serializer_class = ProductCategorySerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.filter().order_by()
    serializer_class = OrderSerializer


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.filter().order_by()
    serializer_class = OrderItemSerializer


class OperationViewSet(viewsets.ModelViewSet):
    queryset = Operation.objects.filter().order_by()
    serializer_class = OperationSerializer


class BalanceViewSet(viewsets.ModelViewSet):
    queryset = Balance.objects.filter().order_by()
    serializer_class = BalanceSerializer


class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.filter().order_by()
    serializer_class = CartSerializer


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.filter().order_by()
    serializer_class = CouponSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter().order_by()
    serializer_class = UserSerializer
