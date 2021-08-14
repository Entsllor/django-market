from django.urls import path
from . import views

app_name = 'market_app'

urlpatterns = [
    path('product/<int:pk>', views.ProductPageView.as_view(), name='product'),
    path('', views.CatalogueView.as_view(), name='catalogue'),
    path('create_product/', views.ProductCreateView.as_view(), name='create_product'),
    path('edit_product/<int:pk>', views.ProductEditView.as_view(), name='edit_product'),
    path('create_type/product/<int:pk>', views.ProductTypeCreate.as_view(), name='create_type'),
    path('edit_type/<int:pk>', views.ProductTypeEdit.as_view(), name='edit_type'),
    path('create_market/', views.MarketCreateView.as_view(), name='create_market'),
    path('edit_market/<int:pk>', views.MarketEditView.as_view(), name='edit_market'),
    path('my_cart/', views.CartView.as_view(), name='cart'),
    path('my_markets/', views.UserMarketsView.as_view(), name='my_markets'),
    path('market/<int:pk>', views.MarketView.as_view(), name='market'),
    path('check_out/', views.CheckOutView.as_view(), name='checkout'),
    path('top_up', views.TopUpView.as_view(), name='top_up'),
    path('order_confirmation/', views.OrderConfirmationView.as_view(), name='order_confirmation')
]
