from rest_framework import serializers

from market_app.models import (
    Product, Market, User, ProductCategory, ProductType, Cart, Order, OrderItem,
    Coupon, Operation, Balance
)


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "id", 'image', 'original_price', 'discount_percent', 'name', 'image', "market_id",
            "description",  "attributes", "created_at", "category_id", "available"
        )


class MarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Market
        fields = ('id', "name", "description", "created_at", 'owner_id')


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username")


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ("id", "name")


class ProductTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductType
        fields = ("id", "product_id", "units_count", "properties", "markup_percent")


class CartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cart
        fields = ("id", "user_id", "items")


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "user_id", "operation_id", "coupon_id", "address", "items")


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("id", "order_id", "is_shipped", "payment_id", "product_type_id")


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ("id", "customers", "discount_limit", "discount_percent")


class OperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Operation
        fields = ("id", "user_id", "amount", "transaction_time")


class BalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Balance
        fields = ("id", "user_id", "amount")
