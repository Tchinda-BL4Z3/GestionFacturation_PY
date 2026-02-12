from django.urls import path
from . import views

urlpatterns = [
    # --- Accès et Authentification ---
    path('', views.home, name='home'), 
    path('login/', views.login_selection, name='login'),  
    path('logout/', views.logout_user, name='logout'),
    path('login/admin/', views.login_admin, name='login_admin'),
    path('login/caissier/', views.login_caissier, name='login_caissier'),
    path('login/client/', views.login_client, name='login_client'),
    path('register/client/', views.register_client, name='register_client'),

    path('dashboard/dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('dashboard/ventes/', views.ventes_admin, name='ventes_admin'),
    path('dashboard/stocks/', views.stocks_admin, name='stocks_admin'),
    
    path('dashboard/utilisateurs/', views.utilisateurs_admin, name='utilisateurs_admin'),
    path('dashboard/utilisateurs/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    
    path('dashboard/clients/', views.clients_admin, name='clients_admin'),
    
    path('dashboard/facturations/', views.facturations_admin, name='facturations_admin'),
    path('dashboard/facturations/export/', views.export_factures_csv, name='export_factures_csv'),
    path('dashboard/facturations/api/<int:facture_id>/', views.facture_detail_api, name='facture_detail_api'),
    path('dashboard/facturations/imprimer/<int:facture_id>/', views.imprimer_facture, name='imprimer_facture'),
    path('dashboard/factures/export/<str:format>/', views.export_factures, name='export_factures'),

    path('dashboard/analyse/', views.analyse_admin, name='analyse_admin'),
]