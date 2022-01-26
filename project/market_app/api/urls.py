from rest_framework.routers import DefaultRouter

from market_app.api.views import (
    ProductViewSet, MarketViewSet, ProductTypeViewSet,
    ProductCategoryViewSet, OrderViewSet, OrderItemViewSet, OperationViewSet,
    BalanceViewSet, CartViewSet, CouponViewSet, UserViewSet,
)

app_name = "market-api"

router = DefaultRouter()
router.register("products", ProductViewSet)
router.register("markets", MarketViewSet)
router.register("product-categories", ProductCategoryViewSet)
router.register("product-types", ProductTypeViewSet)
router.register("order-items", OrderItemViewSet)
router.register("operations", OperationViewSet)
router.register("balances", BalanceViewSet)
router.register("coupons", CouponViewSet)
router.register("orders", OrderViewSet)
router.register("users", UserViewSet)
router.register("carts", CartViewSet)

urlpatterns = router.urls
