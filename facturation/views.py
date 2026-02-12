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
from django.http import HttpResponse, JsonResponse 
import csv
import datetime 
from django.http import HttpResponse
from openpyxl import Workbook
from weasyprint import HTML
from django.template.loader import render_to_string


def home(request):
    return render(request, 'facturation/homePage.html')

def login_selection(request):
    return render(request, 'facturation/LogIn.html')

def login_admin(request):
    error = None
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        # 1. On cherche l'utilisateur par son email
        try:
            user_obj = User.objects.get(email=email)
            # 2. On vérifie si le mot de passe est correct via Django
            user = authenticate(request, username=user_obj.username, password=password)
            
            if user is not None and user.is_superuser:
                # 3. On connecte OFFICIELLEMENT l'utilisateur pour tout le site
                login(request, user) 
                request.session['role'] = 'admin'
                return redirect('dashboard_admin')
            else:
                error = "Identifiants incorrects ou accès refusé."
        except User.DoesNotExist:
            error = "Cet administrateur n'existe pas."

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
    """
    Gestion du personnel et des utilisateurs via l'interface Admin Premium.
    Gère l'ajout, la modification, le changement de statut et la suppression sécurisée.
    """
    # 1. SÉCURITÉ : Vérification du rôle dans la session
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # 2. SÉCURITÉ ANTI-CRASH : Si l'utilisateur n'est pas authentifié par Django
    # on empêche l'exécution des fonctions de mot de passe pour éviter le NotImplementedError
    if not request.user.is_authenticated:
        messages.error(request, "Votre session Django a expiré. Veuillez vous reconnecter sur la page admin.")
        return redirect('login_admin')

    # --- LOGIQUE DE TRAITEMENT DES ACTIONS (POST) ---
    if request.method == "POST":
        action = request.POST.get('action_type')
        user_id = request.POST.get('user_id')

        # 1. AJOUT D'UN UTILISATEUR
        if action == "add_user":
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            role = request.POST.get('role')

            if User.objects.filter(username=username).exists():
                messages.error(request, "Erreur : Ce nom d'utilisateur existe déjà.")
            else:
                new_user = User.objects.create_user(username=username, email=email, password=password)
                if role == 'admin':
                    new_user.is_superuser = True
                    new_user.is_staff = True
                elif role == 'caissier':
                    new_user.is_staff = True
                new_user.save()
                messages.success(request, f"L'utilisateur {username} ({role}) a été créé avec succès.")

        # 2. SUSPENSION / ACTIVATION
        elif action == "toggle_status":
            u = get_object_or_404(User, id=user_id)
            if u == request.user:
                messages.warning(request, "Action impossible : Vous ne pouvez pas suspendre votre propre compte.")
            else:
                u.is_active = not u.is_active
                u.save()
                status_text = "activé" if u.is_active else "suspendu"
                messages.success(request, f"L'utilisateur {u.username} a été {status_text} avec succès.")

        # 3. MISE À JOUR DES INFORMATIONS
        elif action == "update_user":
            u = get_object_or_404(User, id=user_id)
            new_username = request.POST.get('username')
            new_email = request.POST.get('email')

            if User.objects.filter(username=new_username).exclude(id=user_id).exists():
                messages.error(request, f"Le nom d'utilisateur '{new_username}' est déjà utilisé.")
            else:
                u.username = new_username
                u.email = new_email
                u.save()
                messages.success(request, f"Les informations de {u.username} ont été mises à jour.")

        # 4. SUPPRESSION DÉFINITIVE SÉCURISÉE (Correction de l'erreur NotImplementedError)
        elif action == "delete_user_secure":
            admin_password = request.POST.get('admin_password')
            u = get_object_or_404(User, id=user_id)
            
            # Vérification sécurisée du mot de passe
            # Comme on a vérifié is_authenticated en haut, request.user est forcément un objet User réel ici
            if not request.user.check_password(admin_password):
                messages.error(request, "Échec de suppression : Mot de passe administrateur incorrect.")
            elif u == request.user:
                messages.error(request, "Action refusée : Vous ne pouvez pas supprimer votre propre compte.")
            elif u.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
                messages.error(request, "Sécurité : Impossible de supprimer le dernier administrateur.")
            else:
                nom_supprime = u.username
                u.delete()
                messages.success(request, f"L'utilisateur {nom_supprime} a été supprimé définitivement.")

        return redirect('utilisateurs_admin')

    # --- LOGIQUE D'AFFICHAGE (GET) ---
    query = request.GET.get('q', '')
    if query:
        utilisateurs = User.objects.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        ).order_by('-date_joined')
    else:
        utilisateurs = User.objects.all().order_by('date_joined')
    
    logs = LogEntry.objects.select_related('user', 'content_type').all().order_by('-action_time')[:50]

    context = {
        'utilisateurs': utilisateurs,
        'logs': logs,
        'query': query,
        'active_menu': 'utilisateurs',
    }
    return render(request, 'facturation/utilisateurs_admin.html', context)


def toggle_user_status(request, user_id):
    """Fonction pour suspendre ou activer un utilisateur rapidement"""
    if request.session.get('role') != 'admin':
        return redirect('login_admin')
    
    user_to_change = get_object_or_404(User, id=user_id)
    # Empêcher de se désactiver soi-même ou un autre superadmin par erreur
    if not user_to_change.is_superuser:
        user_to_change.is_active = not user_to_change.is_active
        user_to_change.save()
        
    return redirect('utilisateurs_admin')


def clients_admin(request):
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # Traitement des actions POST (Désactivation / Suppression)
    if request.method == "POST":
        action = request.POST.get('action')
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, id=client_id)

        if action == "toggle_status":
            # On suppose que tu as un champ 'actif' dans ton modèle Client (comme dans le CDC)
            client.actif = not client.actif
            client.save()
            status_msg = "activé" if client.actif else "désactivé"
            messages.success(request, f"Le compte de {client.prenom} a été {status_msg}.")

        elif action == "delete_client":
            admin_password = request.POST.get('admin_password')
            # Vérification du mot de passe de l'admin actuellement connecté
            user = authenticate(username=request.user.username, password=admin_password)
            
            if user is not None:
                client.delete()
                messages.success(request, f"Le compte client a été définitivement supprimé.")
            else:
                messages.error(request, "Mot de passe administrateur incorrect. Suppression annulée.")

        return redirect(request.path)

    # Logique de recherche et filtrage
    query = request.GET.get('q', '')
    filter_type = request.GET.get('filter', 'all')

    clients_list = Client.objects.annotate(
        total_depense=Sum('facture__montant_ttc'),
        dernier_achat=Max('facture__date_facture'),
        nb_achats=Count('facture')
    )

    if query:
        clients_list = clients_list.filter(
            Q(nom__icontains=query) | 
            Q(prenom__icontains=query) | 
            Q(telephone__icontains=query)
        )

    if filter_type == 'top':
        clients_list = clients_list.filter(total_depense__gt=100000).order_by('-total_depense')
    elif filter_type == 'inactive':
        clients_list = clients_list.filter(total_depense__isnull=True)
    else:
        clients_list = clients_list.order_by('-id')

    context = {
        'clients': clients_list,
        'total_clients_count': Client.objects.count(),
        'filter_type': filter_type,
        'active_menu': 'clients'
    }
    return render(request, 'facturation/clients_admin.html', context)


def facturations_admin(request):
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # 1. Récupération des filtres
    query = request.GET.get('q', '')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    caissier_id = request.GET.get('caissier')

    # Base de la requête
    factures = Facture.objects.all().order_by('-date_facture')

    # 2. Application des filtres
    if query:
        factures = factures.filter(numero_facture__icontains=query)
    
    if date_debut:
        factures = factures.filter(date_facture__date__gte=parse_date(date_debut))
    
    if date_fin:
        factures = factures.filter(date_facture__date__lte=parse_date(date_fin))
    
    if caissier_id and caissier_id != 'Tous':
        factures = factures.filter(utilisateur_id=caissier_id)

    # 3. Calcul des statistiques sur les données FILTRÉES
    stats = factures.aggregate(
        total_ca=Sum('montant_ttc', filter=Q(statut='valide')),
        nb_total=Sum(1), # Count
        nb_annulees=Sum(1, filter=Q(statut='annulée'))
    )

    context = {
        'factures': factures,
        'caissiers': User.objects.all(),
        'total_factures': factures.count(),
        'ca_periode': stats['total_ca'] or 0,
        'total_annulees': stats['nb_annulees'] or 0,
        'active_menu': 'factures'
    }
    return render(request, 'facturation/facturations_admin.html', context)

# VUE POUR L'EXPORT CSV
def export_factures_csv(request):
    # On récupère les mêmes filtres que la vue principale pour n'exporter que ce qu'on voit
    factures = Facture.objects.all()
    # (Appliquer les mêmes filtres que ci-dessus ici...)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="rapport_factures.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['N° Facture', 'Date', 'Client', 'Caissier', 'Montant TTC', 'Statut'])
    
    for f in factures:
        writer.writerow([f.numero_facture, f.date_facture, f.client, f.utilisateur.username, f.montant_ttc, f.statut])
        
    return response

def export_factures(request, format):
    # 1. Récupérer les données de base
    factures = Facture.objects.all().order_by('-date_facture')

    # 2. Appliquer les MÊMES FILTRES que la page de visualisation
    query = request.GET.get('q', '')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    caissier_id = request.GET.get('caissier')

    if query:
        factures = factures.filter(numero_facture__icontains=query)
    if date_debut:
        factures = factures.filter(date_facture__date__gte=date_debut)
    if date_fin:
        factures = factures.filter(date_facture__date__lte=date_fin)
    if caissier_id and caissier_id != 'Tous':
        factures = factures.filter(utilisateur_id=caissier_id)

    # 3. CALCULER le total (C'est ici qu'on règle ton NameError)
    total_ttc = sum(f.montant_ttc for f in factures)
    
    filename = f"rapport_ventes_{datetime.date.today()}"

    # --- FORMAT CSV ---
    if format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        writer = csv.writer(response)
        writer.writerow(['N° Facture', 'Date', 'Client', 'Caissier', 'Montant TTC', 'Statut'])
        for f in factures:
            writer.writerow([
                f.numero_facture, 
                f.date_facture.strftime('%d/%m/%Y'), 
                f"{f.client.prenom if f.client else 'Passage'} {f.client.nom if f.client else ''}",
                f.utilisateur.username,
                f.montant_ttc, 
                f.statut
            ])
        return response

    # --- FORMAT EXCEL (XLSX) ---
    elif format == 'excel':
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        wb = Workbook()
        ws = wb.active
        ws.title = "Rapport Ventes"
        ws.append(['N° Facture', 'Date', 'Client', 'Caissier', 'Montant TTC', 'Statut'])
        for f in factures:
            nom_client = f"{f.client.prenom if f.client else 'Passage'} {f.client.nom if f.client else ''}"
            ws.append([
                f.numero_facture, 
                f.date_facture.strftime('%d/%m/%Y'), 
                nom_client,
                f.utilisateur.username, 
                float(f.montant_ttc), 
                f.statut
            ])
        wb.save(response)
        return response

    # --- FORMAT PDF ---
    elif format == 'pdf':
        context = {
            'factures': factures,
            'total_ttc': total_ttc, 
            'date': datetime.date.today(),
            'caissier': request.GET.get('caissier', 'Tous')
        }
        
        # Transformer le template HTML en texte
        html_string = render_to_string('facturation/rapport_pdf.html', context)
        
        # Créer la réponse PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        
        # Générer le PDF avec WeasyPrint
        HTML(string=html_string).write_pdf(response)
        return response

    return redirect('facturations_admin')

# VUE POUR LES DÉTAILS (AJAX)
def facture_detail_api(request, facture_id):
    facture = get_object_or_404(Facture, id=facture_id)
    lignes = LigneFacture.objects.filter(facture=facture)
    data = {
        'numero': facture.numero_facture,
        'date': facture.date_facture.strftime('%d/%m/%Y %H:%M'),
        'client': str(facture.client) if facture.client else "Passage",
        'caissier': facture.utilisateur.username,
        'total_ht': float(facture.montant_ht),
        'total_tva': float(facture.montant_tva),
        'total_ttc': float(facture.montant_ttc),
        'lignes': [
            {'article': l.article.nom, 'qty': float(l.quantite), 'prix': float(l.prix_unitaire_ht), 'total': float(l.quantite * l.prix_unitaire_ht)}
            for l in lignes
        ]
    }
    return JsonResponse(data)

# VUE POUR L'IMPRESSION (HTML)
def imprimer_facture(request, facture_id):
    # Récupère la facture ou affiche une erreur 404 si elle n'existe pas
    facture = get_object_or_404(Facture, id=facture_id)
    # Récupère tous les articles liés à cette facture
    lignes = LigneFacture.objects.filter(facture=facture)
    
    context = {
        'facture': facture,
        'lignes': lignes,
    }
    # On utilise un template spécial pour l'impression (sans sidebar ni menus)
    return render(request, 'facturation/facture_print.html', context)


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