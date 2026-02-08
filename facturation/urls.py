from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'), 
    path('login/', views.login_selection, name='login'), 
    path('login/admin/', views.login_admin, name='login_admin'),
    path('login/caissier/', views.login_caissier, name='login_caissier'),
    path('register/', views.register_client, name='register_client'),
    path('login/client/', views.login_client, name='login_client'),
    path('register/client/', views.register_client, name='register_client'),
]