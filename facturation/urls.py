from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'), 
    path('login/', views.login_selection, name='login'),  
    path('logout/', views.logout_user, name='logout'),
    path('login/admin/', views.login_admin, name='login_admin'),
    path('login/caissier/', views.login_caissier, name='login_caissier'),
    path('register/', views.register_client, name='register_client'),
    path('login/client/', views.login_client, name='login_client'),
    path('register/client/', views.register_client, name='register_client'),

    path('dashboard/dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('dashboard/ventes/', views.ventes_admin, name='ventes_admin'),
    path('dashboard/stocks/', views.stocks_admin, name='stocks_admin'),
    path('dashboard/utilisateurs/', views.utilisateurs_admin, name='utilisateurs_admin'),
]