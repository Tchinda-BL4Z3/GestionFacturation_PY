from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'), 
    path('login/', views.login_selection, name='login'),  
    path('logout/', views.logout_user, name='logout'),
    path('logout/', views.logout_view, name='logout_admin'),
    path('login/admin/', views.login_admin, name='login_admin'),
    path('login/caissier/', views.login_caissier, name='login_caissier'),
    path('login/client/', views.login_client, name='login_client'),
    path('register/client/', views.register_client, name='register_client'),

    path('dashboard/dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('dashboard/ventes/', views.ventes_admin, name='ventes_admin'),
    path('dashboard/stocks/', views.stocks_admin, name='stocks_admin'),
    path('dashboard/utilisateurs/', views.utilisateurs_admin, name='utilisateurs_admin'),
    path('dashboard/utilisateurs/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('dashboard/facturations/', views.facturations_admin, name='facturations_admin'),
    path('dashboard/facturations/export/', views.export_factures_csv, name='export_factures_csv'),
    path('dashboard/facturations/api/<int:facture_id>/', views.facture_detail_api, name='facture_detail_api'),
    path('dashboard/facturations/imprimer/<int:facture_id>/', views.imprimer_facture, name='imprimer_facture'),
    path('dashboard/factures/export/<str:format>/', views.export_factures, name='export_factures'),
    path('dashboard/analyse/', views.analyse_admin, name='analyse_admin'),

    path('dashboard/clients/', views.clients_admin, name='clients_admin'),
    path('session/caissier/', views.dashboard_caissier, name='dashboard_caissier'),
    path('session/vente/nouvelle/', views.nouvelle_vente, name='nouvelle_vente'),
    path('chercher-article/', views.chercher_article, name='chercher_article'),
    path('session/vente/valider/', views.valider_vente, name='valider_vente'),
    path('session/ventes/', views.nouvelle_vente, name='nouvelle_vente'),
    path('session/ventes/valider/', views.valider_encaissement, name='valider_encaissement'),
    path('session/clients/', views.clients_caissier, name='clients_caissier'),
    path('session/achat-rapide/', views.caissier_achat_rapide, name='caissier_achat_rapide'),
    path('session/stocks/', views.caissier_stocks, name='caissier_stocks'),
    path('session/facturations/', views.caissier_facturations, name='caissier_facturations'),
    path('session/graphiques/', views.caissier_graphiques, name='caissier_graphiques'),

    path('client/dashboard/', views.client_dashboard, name='client_dashboard'),
    path('client/achats/', views.achats_client, name='achats_client'),
    path('client/stocks/', views.client_stocks, name='client_stocks'),
    path('client/facturations/', views.facturations_client, name='facturations_client'),

]