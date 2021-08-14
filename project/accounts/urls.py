from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.LogIn.as_view(), name='log_in'),
    path('logout/', views.LogOut.as_view(), name='log_out'),
    path('change_password/', views.PasswordChange.as_view(), name='change_password'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit', views.UpdateProfile.as_view(), name='update_profile'),
    path('registration/', views.Registration.as_view(), name='registration'),
]
