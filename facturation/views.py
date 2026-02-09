from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.utils.timezone import now
from django.contrib.auth import logout as django_logout
from django.db.models import Avg, Sum, Max, Count, F, Q, Prefetch 
from .models import Article, Categorie, Facture, LigneFacture, Client
from .models import Facture, User
from django.db.models import Count 


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

    # 7. Statistiques des produits par catégories
    stats_categories = Categorie.objects.annotate(
        nb_produits=Count('article')
    ).order_by('-nb_produits')

    context = {
        'total_ca': total_ca,
        'total_transactions': total_transactions,
        'stock_critique': stock_critique_count,
        'total_clients': total_clients,
        'top_produits': top_produits,
        'activites': activites,
        'stats_categories': stats_categories,
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
    """
    Gère l'affichage de l'inventaire, la recherche de produits 
    et l'ajout, la modification OU la suppression d'articles en base de données.
    """
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # --- 1. TRAITEMENT DES ACTIONS (POST) ---
    if request.method == "POST":
        
        # --- 1.1 LOGIQUE DE SUPPRESSION ---
        delete_id = request.POST.get('delete_article_id')
        if delete_id:
            try:
                article_a_supprimer = get_object_or_404(Article, id=delete_id)
                nom_supprime = article_a_supprimer.nom
                article_a_supprimer.delete()
                messages.success(request, f"Le produit '{nom_supprime}' a été définitivement supprimé de l'inventaire.")
                return redirect('stocks_admin')
            except Exception as e:
                messages.error(request, f"Erreur lors de la suppression : {e}")
                return redirect('stocks_admin')

        # --- 1.2 LOGIQUE D'AJOUT OU DE MODIFICATION ---
        article_id = request.POST.get('article_id')
        
        try:
            # Récupération des données brutes du formulaire
            nom = request.POST.get('nom')
            code_barres = request.POST.get('code_barres')
            categorie_id = request.POST.get('categorie')
            unite = request.POST.get('unite_mesure')
            prix_ht_raw = request.POST.get('prix_ht')
            tva_raw = request.POST.get('taux_tva')
            stock_init_raw = request.POST.get('stock_actuel')
            stock_min_raw = request.POST.get('stock_minimum')

            # Nettoyage et conversion des types numériques (sécurité PostgreSQL)
            prix_ht = float(prix_ht_raw.replace(',', '.')) if prix_ht_raw else 0.0
            taux_tva = float(tva_raw.replace(',', '.')) if tva_raw else 19.25
            stock_actuel = int(stock_init_raw) if stock_init_raw else 0
            stock_minimum = int(stock_min_raw) if stock_min_raw else 5

            if article_id:
                # --- LOGIQUE DE MODIFICATION ---
                article = get_object_or_404(Article, id=article_id)
                article.nom = nom
                article.code_barres = code_barres
                article.categorie_id = categorie_id
                article.unite_mesure = unite
                article.prix_ht = prix_ht
                article.taux_tva = taux_tva
                article.stock_actuel = stock_actuel
                article.stock_minimum = stock_minimum
                article.save()
                messages.success(request, f"Produit '{nom}' mis à jour avec succès !")
            else:
                # --- LOGIQUE D'AJOUT ---
                Article.objects.create(
                    nom=nom,
                    code_barres=code_barres,
                    categorie_id=categorie_id,
                    unite_mesure=unite,
                    prix_ht=prix_ht,
                    taux_tva=taux_tva,
                    stock_actuel=stock_actuel,
                    stock_minimum=stock_minimum
                )
                messages.success(request, f"Nouveau produit '{nom}' enregistré !")
            
            return redirect('stocks_admin')

        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement : {e}")

    # --- 2. LOGIQUE DE RECHERCHE ET AFFICHAGE (GET) ---
    query = request.GET.get('q', '').strip()
    all_categories = Categorie.objects.all()
    
    # Préparation de la liste principale avec filtrage intelligent
    if query:
        articles_filtres = Article.objects.filter(
            Q(nom__icontains=query) | Q(code_barres__icontains=query)
        )
        categories_list = Categorie.objects.filter(
            article__in=articles_filtres
        ).prefetch_related(
            Prefetch('article_set', queryset=articles_filtres)
        ).distinct()
    else:
        categories_list = Categorie.objects.prefetch_related('article_set').all()
    
    # --- 3. CALCUL DES STATISTIQUES GLOBALES ---
    
    # Nombre total de références actives
    total_produits = Article.objects.filter(actif=True).count()
    
    # Nombre d'alertes (Stock actuel <= Seuil de sécurité)
    alertes_stock = Article.objects.filter(
        stock_actuel__lte=F('stock_minimum'), 
        actif=True
    ).count()
    
    # Valeur marchande totale du stock (Prix HT * Quantité en stock)
    valeur_stock_data = Article.objects.filter(actif=True).aggregate(
        total=Sum(F('stock_actuel') * F('prix_ht'))
    )
    valeur_stock = valeur_stock_data['total'] or 0

    # Construction du contexte pour le template HTML
    context = {
        'total_produits': total_produits,
        'alertes_stock': alertes_stock,
        'valeur_stock': valeur_stock,
        'categories': categories_list,    
        'all_categories': all_categories, 
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


def clients_admin(request):
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # Recherche
    query = request.GET.get('q', '')
    
    # Récupération des clients avec calculs dynamiques
    clients = Client.objects.annotate(
        total_depense=Sum('facture__montant_ttc'),
        dernier_achat=Max('facture__date_facture'),
        nb_factures=Count('facture')
    ).order_by('-total_depense')

    if query:
        clients = clients.filter(nom__icontains=query) | clients.filter(prenom__icontains=query)

    # Statistiques globales pour les boutons de filtre
    total_clients_count = Client.objects.count()

    context = {
        'clients': clients,
        'total_clients_count': total_clients_count,
        'active_menu': 'clients'
    }
    return render(request, 'facturation/clients_admin.html', context)


def facturations_admin(request):
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # 1. Récupération des filtres depuis l'URL
    query = request.GET.get('q', '')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    caissier_id = request.GET.get('caissier')

    # 2. Construction de la requête de base
    factures_qs = Facture.objects.select_related('client', 'utilisateur').all()

    # Application des filtres
    if query:
        factures_qs = factures_qs.filter(numero_facture__icontains=query)
    
    if date_debut and date_fin:
        factures_qs = factures_qs.filter(date_facture__date__range=[date_debut, date_fin])
    
    if caissier_id and caissier_id != 'Tous':
        factures_qs = factures_qs.filter(utilisateur_id=caissier_id)

    # 3. Calcul des statistiques (basé sur le QuerySet filtré)
    total_factures = factures_qs.count()
    ca_periode = factures_qs.filter(statut='valide').aggregate(total=Sum('montant_ttc'))['total'] or 0
    total_annulees = factures_qs.filter(statut='annulée').count()

    # Liste des caissiers pour le menu déroulant
    caissiers = User.objects.all()

    context = {
        'factures': factures_qs.order_by('-date_facture'),
        'total_factures': total_factures,
        'ca_periode': ca_periode,
        'total_annulees': total_annulees,
        'caissiers': caissiers,
        'active_menu': 'facturations'
    }
    return render(request, 'facturation/facturations_admin.html', context)


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
    success = False
    
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm-password')

        # 1. Vérification des mots de passe
        if password != confirm_password:
            error = "Les mots de passe ne correspondent pas."
        
        # 2. Tentative de création du compte
        else:
            try:
                # On utilise l'email comme nom d'utilisateur (username)
                if User.objects.filter(username=email).exists():
                    error = "Cet e-mail est déjà utilisé pour un compte."
                else:
                    # Création de l'utilisateur dans la table Auth de Django
                    new_user = User.objects.create_user(
                        username=email, 
                        email=email, 
                        password=password
                    )
                    
                    # Création du profil dans notre table Client (PostgreSQL)
                    # On extrait une partie de l'email pour le nom par défaut
                    default_name = email.split('@')[0]
                    Client.objects.create(
                        nom=default_name.upper(),
                        prenom="Client",
                        email=email
                    )
                    # Déclenchera le modal de confirmation
                    success = True 
                    
            except Exception as e:
                error = "Une erreur technique est survenue. Veuillez réessayer."

    return render(request, 'facturation/register_client.html', {
        'error': error,
        'success': success
    })


def login_client(request):
    error = None
    success = False
    
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Authentification de l'utilisateur
        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            success = True 
        else:
            error = "Identifiants invalides. Veuillez vérifier votre e-mail et mot de passe."

    return render(request, 'facturation/login_client.html', {
        'error': error,
        'success': success
    })


# =========================[ fin des vues pour les clients ]=======================