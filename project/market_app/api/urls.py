from rest_framework.routers import DefaultRouter

from market_app.api.views import (
    ProductViewSet, MarketViewSet, ProductTypeViewSet,
    ProductCategoryViewSet, OrderViewSet, OrderItemViewSet, OperationViewSet,
    BalanceViewSet, CartViewSet, CouponViewSet, UserViewSet,
)

router = DefaultRouter()
router.register("products", ProductViewSet)
router.register("markets", MarketViewSet)
router.register("product-category", ProductCategoryViewSet)
router.register("product-type", ProductTypeViewSet)
router.register("order-item", OrderItemViewSet)
router.register("operation", OperationViewSet)
router.register("balance", BalanceViewSet)
router.register("coupon", CouponViewSet)
router.register("order", OrderViewSet)
router.register("user", UserViewSet)
router.register("cart", CartViewSet)

urlpatterns = router.urls
