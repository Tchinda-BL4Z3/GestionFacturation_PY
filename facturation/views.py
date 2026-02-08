from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.utils.timezone import now
from django.contrib.auth import logout as django_logout
from django.db.models import Avg, Sum, Max, Count, F, Q, Prefetch 
from .models import Article, Categorie, Facture, LigneFacture, Client
from .models import Facture


def home(request):
    return render(request, 'facturation/homePage.html')

def login_selection(request):
    return render(request, 'facturation/LogIn.html')

def login_admin(request):
    error = None
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        if email == "admin@gmail.com" and password == "admin1234":
            
            request.session['role'] = 'admin'
            return redirect('dashboard_admin') 
        else:
            error = "Identifiants administrateur incorrects."
    return render(request, 'facturation/login_admin.html', {'error': error})

# =========================[ Vue pour le dashboard admin ]==========================

def dashboard_admin(request):
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # 1. Calcul du Chiffre d'affaires total (uniquement les factures valides)
    stats_ca = Facture.objects.filter(statut='valide').aggregate(total=Sum('montant_ttc'))
    total_ca = stats_ca['total'] or 0

    # 2. Nombre de transactions
    total_transactions = Facture.objects.filter(statut='valide').count()

    # 3. Stock Critique (Articles dont le stock est inférieur ou égal au seuil minimum)
    stock_critique_count = Article.objects.filter(stock_actuel__lte=F('stock_minimum'), actif=True).count()

    # 4. Nombre de clients
    total_clients = Client.objects.count()

    # 5. Top 5 des produits les plus vendus
    top_produits = LigneFacture.objects.values(
        'article__nom', 'article__stock_actuel', 'article__stock_minimum'
    ).annotate(
        qty_vendue=Sum('quantite'),
        revenue=Sum(F('quantite') * F('prix_unitaire_ht') * (1 + F('taux_tva')/100))
    ).order_by('-qty_vendue')[:5]

    # 6. Activités récentes (5 dernières factures)
    activites = Facture.objects.select_related('utilisateur').order_by('-date_facture')[:5]

    context = {
        'total_ca': total_ca,
        'total_transactions': total_transactions,
        'stock_critique': stock_critique_count,
        'total_clients': total_clients,
        'top_produits': top_produits,
        'activites': activites,
        'active_menu': 'dashboard', 
    }

    return render(request, 'facturation/dashboard_admin.html', context)

def ventes_admin(request):
    # Sécurité : Vérifier si l'utilisateur est admin dans la session
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # 1. Calcul des indicateurs (KPI)
    stats = Facture.objects.filter(statut='valide').aggregate(
        panier_moyen=Avg('montant_ttc'),
        vente_max=Max('montant_ttc'),
        total_transactions=Count('id')
    )

    # Valeurs par défaut si la BD est vide
    panier_moyen = stats['panier_moyen'] or 0
    vente_max = stats['vente_max'] or 0
    
    # 2. Récupération de l'historique des transactions
    # On utilise select_related pour optimiser la requête (jointure avec User)
    search_query = request.GET.get('search', '')
    if search_query:
        transactions = Facture.objects.filter(numero_facture__icontains=search_query).select_related('utilisateur').order_by('-date_facture')
    else:
        transactions = Facture.objects.select_related('utilisateur').order_by('-date_facture')

    context = {
        'panier_moyen': panier_moyen,
        'vente_max': vente_max,
        'transactions': transactions,
        'active_menu': 'ventes' # Pour mettre en surbrillance le menu dans la sidebar
    }
    
    return render(request, 'facturation/ventes_admin.html', context)

def ventes_admin(request):
    # Sécurité : Vérifier si l'utilisateur est admin dans la session
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # 1. Calcul des indicateurs (KPI)
    stats = Facture.objects.filter(statut='valide').aggregate(
        panier_moyen=Avg('montant_ttc'),
        vente_max=Max('montant_ttc'),
        total_transactions=Count('id')
    )

    # Valeurs par défaut si la BD est vide
    panier_moyen = stats['panier_moyen'] or 0
    vente_max = stats['vente_max'] or 0
    
    # 2. Récupération de l'historique des transactions
    search_query = request.GET.get('search', '')
    if search_query:
        transactions = Facture.objects.filter(numero_facture__icontains=search_query).select_related('utilisateur').order_by('-date_facture')
    else:
        transactions = Facture.objects.select_related('utilisateur').order_by('-date_facture')

    context = {
        'panier_moyen': panier_moyen,
        'vente_max': vente_max,
        'transactions': transactions,
        'active_menu': 'ventes'
    }
    
    return render(request, 'facturation/ventes_admin.html', context)

def stocks_admin(request):
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # 1. Calcul des statistiques réelles du bandeau supérieur
    total_produits = Article.objects.filter(actif=True).count()
    alertes_stock = Article.objects.filter(stock_actuel__lte=F('stock_minimum'), actif=True).count()
    
    stats_valeur = Article.objects.filter(actif=True).aggregate(
        total=Sum(F('stock_actuel') * F('prix_ht'))
    )
    valeur_stock = stats_valeur['total'] or 0

    # 2. Gestion de la recherche (⌘K)
    query = request.GET.get('q', '')
    if query:
        categories = Categorie.objects.prefetch_related(
            prefetch_related_objects('article_set', Article.objects.filter(
                Q(nom__icontains=query) | Q(code_barres__icontains=query)
            ))
        ).distinct()
    else:
        # Sinon on prend tout
        categories = Categorie.objects.prefetch_related('article_set').all()

    context = {
        'total_produits': total_produits,
        'alertes_stock': alertes_stock,
        'valeur_stock': valeur_stock,
        'categories': categories,
        'query': query,
        'active_menu': 'stocks'
    }
    return render(request, 'facturation/stocks_admin.html', context)

def utilisateurs_admin(request):
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # 1. Récupérer tous les utilisateurs
    utilisateurs = User.objects.all().order_by('-date_joined')

    # 2. Récupérer les 5 dernières actions du journal de bord (Admin logs)
    logs = LogEntry.objects.select_related('user', 'content_type').all()[:5]

    context = {
        'utilisateurs': utilisateurs,
        'logs': logs,
        'active_menu': 'utilisateurs',
        'now': now(),
    }
    return render(request, 'facturation/utilisateurs_admin.html', context)

# =========================[ fin du dashboard admin ]============================


# ========================[ Vues pour la gestion des deconnexions ]==============

# def logout_view(request):
#     request.session.flush()
#     return redirect('home')

def logout_user(request):
    django_logout(request)
    request.session.flush()

    return redirect('login')

# =========================[ fin des vues de deconnexion ]=======================


# =========================[ vues pour les caissiers ]===========================

def login_caissier(request):
    error = None
    if request.method == "POST":
        emp_id = request.POST.get('employee-id')
        pin = request.POST.get('pin-code')

        # Test simple des identifiants caissier
        if emp_id == "EMP-001" and pin == "1234":
            
            return redirect('home') 
        else:
            error = "Identifiant ou Code PIN incorrect."

    return render(request, 'facturation/login_caissier.html', {'error': error})


# =========================[ fin des vues pour les caissiers ]====================

# =========================[ vues pour les clients ]==============================

def register_client(request):
    error = None
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm-password')

        if password != confirm_password:
            error = "Les mots de passe ne correspondent pas."
        else:
            return redirect('login') 

    return render(request, 'facturation/register_client.html', {'error': error})

def login_client(request):
    error = None
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        if email == "client@gmail.com" and password == "client1234":
            return redirect('home') 
        else:
            error = "Identifiants client incorrects."

    return render(request, 'facturation/login_client.html', {'error': error})

# =========================[ fin des vues pour les clients ]=======================