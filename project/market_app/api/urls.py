from rest_framework.routers import DefaultRouter

from market_app.api.views import ProductViewSet, MarketViewSet

router = DefaultRouter()
router.register("products", ProductViewSet)
router.register("markets", MarketViewSet)

urlpatterns = router.urls
