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
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import TruncDate, TruncHour
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
        'active_menu': 'facturations'
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


def analyse_admin(request):
    if request.session.get('role') != 'admin':
        return redirect('login_admin')

    # 1. Chiffre d'Affaires Total (Invoices Validated)
    total_ca = Facture.objects.filter(statut='valide').aggregate(Sum('montant_ttc'))['montant_ttc__sum'] or 0

    # 1.b Panier Moyen (Moyenne des factures valides)
    panier_moyen = Facture.objects.filter(statut='valide').aggregate(Avg('montant_ttc'))['montant_ttc__avg'] or 0

    # 1.c Taux de retour (Annulations + Avoirs / Total)
    total_factures = Facture.objects.count()
    factures_retour = Facture.objects.filter(statut__in=['annulée', 'avoir']).count()
    taux_retour = (factures_retour / total_factures * 100) if total_factures > 0 else 0
    # ---------------------------------

    # 2. Ventes des 7 derniers jours (pour le graphique linéaire)
    sept_jours_derniers = timezone.now() - timedelta(days=7)
    ventes_evolution = Facture.objects.filter(statut='valide', date_facture__gte=sept_jours_derniers) \
        .annotate(jour=TruncDate('date_facture')) \
        .values('jour') \
        .annotate(total=Sum('montant_ttc')) \
        .order_by('jour')

    # 3. Répartition par Catégorie (pour le graphique camembert)
    stats_categories = LigneFacture.objects.filter(facture__statut='valide') \
        .values('article__categorie__nom') \
        .annotate(total=Sum('total_ttc')) \
        .order_by('-total')

    # 4. Top 5 des produits les plus vendus
    top_produits = LigneFacture.objects.filter(facture__statut='valide') \
        .values('article__nom') \
        .annotate(quantite=Sum('quantite')) \
        .order_by('-quantite')[:5]

    # 5. Modes de paiement
    modes_paiement = Facture.objects.filter(statut='valide') \
        .values('mode_paiement') \
        .annotate(count=Count('id'))

    context = {
        'total_ca': total_ca,
        'panier_moyen': panier_moyen,        
        'taux_retour': taux_retour,          
        'total_factures': total_factures,     
        'ventes_evolution': ventes_evolution,
        'stats_categories': stats_categories,
        'top_produits': top_produits,
        'modes_paiement': modes_paiement,
        'active_menu': 'analyse',
    }
    return render(request, 'facturation/analyse_admin.html', context)


# =========================[ fin du dashboard admin ]============================

# =========================[ vues pour la gestion caissiers ]====================

def login_caissier(request):
    if request.method == "POST":
        identifiant = request.POST.get('username')
        password = request.POST.get('password')
        
        print(f"--- TENTATIVE DE CONNEXION CAISSIER ---")
        print(f"Identifiant saisi : {identifiant}")
        
        user = authenticate(request, username=identifiant, password=password)
        
        if user is not None:
            # On connecte l'utilisateur
            login(request, user)
            
            # On définit le rôle APRES le login (car login() peut réinitialiser la session)
            request.session['role'] = 'caissier'
            request.session['is_caissier'] = True
            
            # On force l'enregistrement immédiat en base de données
            request.session.modified = True
            request.session.save() 
            
            print(f"SUCCÈS: {user.username} est authentifié.")
            print(f"SESSION: Rôle défini sur -> {request.session.get('role')}")
            print(f"REDIRECTION: Vers dashboard_caissier...")
            
            return redirect('dashboard_caissier')
        else:
            print("ÉCHEC: Identifiants incorrects.")
            messages.error(request, "Identifiant ou Code PIN invalide.")
            
    return render(request, 'facturation/login_caissier.html')

def logout_view(request):
    logout(request) 
    request.session.flush()
    return redirect('login_caissier')


def dashboard_caissier(request):
    # VERIFICATION DE LA SESSION
    user_role = request.session.get('role')
    print(f"--- ACCÈS DASHBOARD CAISSIER ---")
    print(f"Rôle en session détecté : {user_role}")
    print(f"Utilisateur connecté : {request.user.username}")

    if user_role != 'caissier':
        print("ALERTE: Accès refusé (Rôle incorrect ou session expirée). Redirection login...")
        return redirect('login_caissier')

    # LOGIQUE METIER
    caissier = request.user
    aujourdhui = timezone.now().date()

    # 1. Récupérer les factures du caissier pour aujourd'hui
    factures_session = Facture.objects.filter(
        utilisateur=caissier, 
        date_facture__date=aujourdhui
    ).order_by('-date_facture')

    # 2. Calcul des statistiques de session
    stats = factures_session.aggregate(total_ca=Sum('montant_ttc'))
    ca_session = stats['total_ca'] or 0
    nb_clients = factures_session.count()
    
    # 3. Alertes stocks (Articles sous le seuil minimum)
    alertes_stocks = Article.objects.filter(
        stock_actuel__lte=F('stock_minimum'), 
        actif=True
    ).count()

    print(f"DONNÉES: CA={ca_session}, Clients={nb_clients}, Alertes={alertes_stocks}")

    context = {
        'factures': factures_session,
        'ca_session': ca_session,
        'nb_clients': nb_clients,
        'alertes_stocks': alertes_stocks,
        'caissier': caissier,
        'active_menu': 'dashboard',
        'date_now': timezone.now(),
    }
    return render(request, 'facturation/dashboard_caissier.html', context)

def nouvelle_vente(request):
    if request.session.get('role') != 'caissier':
        return redirect('login_caissier')

    # Initialiser le panier s'il n'existe pas
    if 'panier' not in request.session:
        request.session['panier'] = {}
    
    panier = request.session.get('panier')
    
    # Traitement du scan de code-barres (POST)
    if request.method == "POST":
        barcode = request.POST.get('barcode')
        action = request.POST.get('action')

        if action == "add":
            article = Article.objects.filter(code_barres=barcode, actif=True).first()
            if article:
                art_id = str(article.id)
                if art_id in panier:
                    panier[art_id]['quantite'] += 1
                else:
                    panier[art_id] = {
                        'nom': article.nom,
                        'prix': float(article.prix_ht),
                        'tva': float(article.taux_tva),
                        'quantite': 1,
                        'code': article.code_barres
                    }
                request.session.modified = True
            else:
                messages.error(request, "Article introuvable ou inactif.")

        elif action == "update":
            art_id = request.POST.get('article_id')
            op = request.POST.get('op')
            if art_id in panier:
                if op == "plus": panier[art_id]['quantite'] += 1
                elif op == "moins" and panier[art_id]['quantite'] > 1: panier[art_id]['quantite'] -= 1
                request.session.modified = True

        elif action == "delete":
            art_id = request.POST.get('article_id')
            if art_id in panier:
                del panier[art_id]
                request.session.modified = True

    # Calculs des totaux
    sous_total_ht = sum(item['prix'] * item['quantite'] for item in panier.values())
    total_tva = sum((item['prix'] * item['quantite']) * (item['tva'] / 100) for item in panier.values())
    total_ttc = sous_total_ht + total_tva

    context = {
        'panier': panier,
        'sous_total': sous_total_ht,
        'total_tva': total_tva,
        'total_ttc': total_ttc,
        'active_menu': 'ventes'
    }
    return render(request, 'facturation/ventes_caissier.html', context)

# Vue pour finaliser l'encaissement
def valider_encaissement(request):
    panier = request.session.get('panier', {})
    if not panier:
        return redirect('nouvelle_vente')

    # Création de la facture
    facture = Facture.objects.create(
        utilisateur=request.user,
        mode_paiement="ESPÈCES",
        statut="valide"
    )

    total_ht = 0
    total_tva = 0

    for art_id, data in panier.items():
        article = Article.objects.get(id=art_id)
        ligne_ht = Decimal(data['prix']) * data['quantite']
        ligne_tva = ligne_ht * (Decimal(data['tva']) / 100)
        
        LigneFacture.objects.create(
            facture=facture,
            article=article,
            quantite=data['quantite'],
            prix_unitaire_ht=data['prix'],
            taux_tva=data['tva']
        )
        total_ht += ligne_ht
        total_tva += ligne_tva

    # Mise à jour des totaux de la facture
    facture.montant_ht = total_ht
    facture.montant_tva = total_tva
    facture.montant_ttc = total_ht + total_tva
    facture.save()

    # Vider le panier
    request.session['panier'] = {}
    messages.success(request, f"Vente #{facture.numero_facture} validée avec succès !")
    return redirect('dashboard_caissier')

# API pour chercher un article par code-barres ou nom (AJAX)
def chercher_article(request):
    q = request.GET.get('q', '')
    articles = Article.objects.filter(
        models.Q(code_barres=q) | models.Q(nom__icontains=q),
        actif=True
    ).values('id', 'nom', 'code_barres', 'prix_ht', 'taux_tva', 'stock_actuel')
    
    return JsonResponse(list(articles), safe=False)

def nouvelle_vente(request):
    if request.session.get('role') != 'caissier':
        return redirect('login_caissier')

    # Initialiser le panier s'il n'existe pas
    if 'panier' not in request.session:
        request.session['panier'] = {}
    
    panier = request.session.get('panier')
    
    # Traitement du scan de code-barres (POST)
    if request.method == "POST":
        barcode = request.POST.get('barcode')
        action = request.POST.get('action')

        if action == "add":
            article = Article.objects.filter(code_barres=barcode, actif=True).first()
            if article:
                art_id = str(article.id)
                if art_id in panier:
                    panier[art_id]['quantite'] += 1
                else:
                    panier[art_id] = {
                        'nom': article.nom,
                        'prix': float(article.prix_ht),
                        'tva': float(article.taux_tva),
                        'quantite': 1,
                        'code': article.code_barres
                    }
                request.session.modified = True
            else:
                messages.error(request, "Article introuvable ou inactif.")

        elif action == "update":
            art_id = request.POST.get('article_id')
            op = request.POST.get('op')
            if art_id in panier:
                if op == "plus": panier[art_id]['quantite'] += 1
                elif op == "moins" and panier[art_id]['quantite'] > 1: panier[art_id]['quantite'] -= 1
                request.session.modified = True

        elif action == "delete":
            art_id = request.POST.get('article_id')
            if art_id in panier:
                del panier[art_id]
                request.session.modified = True

    # Calculs des totaux
    sous_total_ht = sum(item['prix'] * item['quantite'] for item in panier.values())
    total_tva = sum((item['prix'] * item['quantite']) * (item['tva'] / 100) for item in panier.values())
    total_ttc = sous_total_ht + total_tva

    context = {
        'panier': panier,
        'sous_total': sous_total_ht,
        'total_tva': total_tva,
        'total_ttc': total_ttc,
        'active_menu': 'ventes'
    }
    return render(request, 'facturation/ventes_caissier.html', context)

# Vue pour traiter la validation de la vente (Appelée en AJAX)
def valider_vente(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            panier = data.get('panier')
            client_id = data.get('client_id')
            mode_paiement = data.get('mode_paiement')

            if not panier:
                return JsonResponse({'success': False, 'message': 'Le panier est vide'})

            # Utilisation d'une transaction pour garantir que tout est sauvegardé ou rien du tout
            with transaction.atomic():
                facture = Facture.objects.create(
                    utilisateur=request.user,
                    client_id=client_id if client_id else None,
                    mode_paiement=mode_paiement,
                    statut='valide'
                )

                total_ht = 0
                total_tva = 0
                total_ttc = 0

                for item in panier:
                    article = Article.objects.get(id=item['id'])
                    quantite = int(item['quantite'])
                    
                    # Calculs
                    p_unit_ht = article.prix_ht
                    l_total_ttc = float(article.prix_ttc) * quantite
                    
                    # Création de la ligne
                    LigneFacture.objects.create(
                        facture=facture,
                        article=article,
                        quantite=quantite,
                        prix_unitaire_ht=p_unit_ht,
                        taux_tva=article.taux_tva
                    )

                    total_ht += float(p_unit_ht) * quantite
                    total_ttc += l_total_ttc

                # Mise à jour finale de la facture
                facture.montant_ht = total_ht
                facture.montant_ttc = total_ttc
                facture.montant_tva = total_ttc - total_ht
                facture.save()

            return JsonResponse({'success': True, 'facture_id': facture.id})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'})

def clients_caissier(request):
    if request.session.get('role') != 'caissier':
        return redirect('login_caissier')

    query = request.GET.get('q', '')
    
    # On annote chaque client avec ses stats réelles
    clients_list = Client.objects.filter(actif=True).annotate(
        total_achats=Sum('facture__montant_ttc'),
        derniere_fac=Max('facture__numero_facture'),
        date_dernier=Max('facture__date_facture')
    ).order_by('-id')

    if query:
        clients_list = clients_list.filter(
            Q(nom__icontains=query) | Q(telephone__icontains=query)
        )

    context = {
        'clients': clients_list,
        'active_menu': 'clients'
    }
    return render(request, 'facturation/clients_caissier.html', context)

def caissier_achat_rapide(request):
    if request.session.get('role') != 'caissier':
        return redirect('login_caissier')

    # Récupération des articles pour la liste de sélection
    articles = Article.objects.filter(actif=True).order_by('nom')

    if request.method == "POST":
        article_id = request.POST.get('product')
        quantite = request.POST.get('quantity')
        prix_achat = request.POST.get('price')
        fournisseur = request.POST.get('supplier')

        try:
            article = Article.objects.get(id=article_id)
            # Mise à jour du stock réel en BD
            article.stock_actuel += int(quantite)
            article.save()

            messages.success(request, f"Stock mis à jour ! +{quantite} {article.nom} ajoutés.")
            return redirect('caissier_achat_rapide')
            
        except Exception as e:
            messages.error(request, "Erreur lors de l'enregistrement de l'achat.")

    context = {
        'articles': articles,
        'active_menu': 'achat',
        'ref_achat': f"ACH-{timezone.now().strftime('%M%S')}" 
    }
    return render(request, 'facturation/achat_caissier.html', context)

def caissier_stocks(request):
    if request.session.get('role') != 'caissier':
        return redirect('login_caissier')

    # Récupération des filtres
    query = request.GET.get('q', '')
    cat_id = request.GET.get('category', '')

    # Requête de base
    articles = Article.objects.filter(actif=True).select_related('categorie')

    # Recherche
    if query:
        articles = articles.filter(
            Q(nom__icontains=query) | 
            Q(code_barres__icontains=query)
        )

    # Filtre catégorie
    if cat_id and cat_id != 'all':
        articles = articles.filter(categorie_id=cat_id)

    context = {
        'articles': articles,
        'categories': Categorie.objects.all(),
        'active_menu': 'stocks',
        'query': query,
        'cat_id': cat_id,
    }
    return render(request, 'facturation/stocks_caissier.html', context)

def caissier_facturations(request):
    if request.session.get('role') != 'caissier':
        return redirect('login_caissier')

    # Récupération des filtres
    query = request.GET.get('q', '')
    mode_filtre = request.GET.get('mode', '')

    # On récupère les factures du caissier connecté
    factures = Facture.objects.filter(utilisateur=request.user).order_by('-date_facture')

    # Logique de recherche
    if query:
        factures = factures.filter(
            Q(numero_facture__icontains=query) | 
            Q(client__nom__icontains=query) |
            Q(client__prenom__icontains=query)
        )

    # Filtre par mode de paiement
    if mode_filtre and mode_filtre != 'Tous':
        factures = factures.filter(mode_paiement__icontains=mode_filtre)

    # Statistiques de la session (Ventes du jour même)
    aujourdhui = timezone.now().date()
    ventes_du_jour = Facture.objects.filter(utilisateur=request.user, date_facture__date=aujourdhui, statut='valide')
    
    total_especes = ventes_du_jour.filter(mode_paiement='espèces').aggregate(Sum('montant_ttc'))['montant_ttc__sum'] or 0
    total_carte = ventes_du_jour.filter(mode_paiement='cb').aggregate(Sum('montant_ttc'))['montant_ttc__sum'] or 0
    total_cheque = ventes_du_jour.filter(mode_paiement='chèque').aggregate(Sum('montant_ttc'))['montant_ttc__sum'] or 0
    net_session = total_especes + total_carte + total_cheque

    context = {
        'factures': factures,
        'count_session': ventes_du_jour.count(),
        'total_especes': total_especes,
        'total_carte': total_carte,
        'total_cheque': total_cheque,
        'net_session': net_session,
        'active_menu': 'facturations',
        'query': query,
        'mode_filtre': mode_filtre,
    }
    return render(request, 'facturation/facturations_caissier.html', context)

def caissier_graphiques(request):
    if request.session.get('role') != 'caissier':
        return redirect('login_caissier')

    aujourdhui = timezone.now().date()
    # On filtre tout par l'utilisateur connecté et la date du jour
    base_query = Facture.objects.filter(utilisateur=request.user, date_facture__date=aujourdhui, statut='valide')

    # 1. Calcul des indicateurs (Cards)
    stats = base_query.aggregate(
        panier_moyen=Avg('montant_ttc'),
        total_ventes=Sum('montant_ttc'),
        nb_factures=Count('id'),
        nb_clients_fidele=Count('client', filter=Q(client__isnull=False))
    )

    # Calcul du taux de fidélité
    taux_fidelite = 0
    if stats['nb_factures'] > 0:
        taux_fidelite = (stats['nb_clients_fidele'] / stats['nb_factures']) * 100

    # 2. Ventes par Heure (Histogramme)
    ventes_par_heure = base_query.annotate(heure=TruncHour('date_facture')) \
        .values('heure') \
        .annotate(total=Sum('montant_ttc')) \
        .order_by('heure')

    # Préparation des données pour l'affichage (on cherche le max pour l'échelle relative)
    max_vente_heure = max([v['total'] for v in ventes_par_heure], default=1)
    for v in ventes_par_heure:
        v['percent'] = (v['total'] / max_vente_heure) * 100

    # 3. Répartition par Catégorie (Donut)
    repartition_cat = LigneFacture.objects.filter(
        facture__utilisateur=request.user, 
        facture__date_facture__date=aujourdhui
    ).values('article__categorie__nom').annotate(total=Sum('total_ttc')).order_by('-total')

    total_cat = sum([c['total'] for c in repartition_cat])
    for c in repartition_cat:
        c['percent'] = (c['total'] / total_cat * 100) if total_cat > 0 else 0

    context = {
        'stats': stats,
        'taux_fidelite': taux_fidelite,
        'ventes_par_heure': ventes_par_heure,
        'repartition_cat': repartition_cat,
        'total_session': total_cat,
        'active_menu': 'graphiques',
    }
    return render(request, 'facturation/graphiques_caissier.html', context)


# ========================[ fin vue gestion des caissiers ]=====================

# ========================[ Vues pour la gestion des deconnexions ]==============

# def logout_view(request):
#     request.session.flush()
#     return redirect('home')

def logout_user(request):
    django_logout(request)
    request.session.flush()

    return redirect('login')

# =========================[ fin des vues de deconnexion ]=======================


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

        # --- Recherche du username via l'email ---
        try:
            # On cherche l'utilisateur qui possède cet e-mail en base de données
            user_db = User.objects.get(email=email)
            username_to_authenticate = user_db.username
        except User.DoesNotExist:
            # Si l'e-mail n'existe pas, authenticate() renverra None plus bas
            username_to_authenticate = email

        # --- Authentification ---
        user = authenticate(request, username=username_to_authenticate, password=password)

        if user is not None:
            # --- VERIFICATION : Est-ce un client, un admin ou un staff ? ---
            if hasattr(user, 'client') or user.is_superuser or user.is_staff:
                login(request, user)
                
                # On définit le rôle pour les accès aux pages
                request.session['role'] = 'client' 
                
                success = True
                return render(request, 'facturation/login_client.html', {
                    'error': error,
                    'success': success
                })
            else:
                # Cas où le mot de passe est juste, mais le compte n'est lié à rien
                error = "Cet utilisateur n'est pas enregistré comme un client."
        else:
            # Mauvais email ou mauvais mot de passe
            error = "Identifiants invalides. Veuillez vérifier votre e-mail et mot de passe."

    # Retour classique en cas de chargement simple ou d'erreur
    return render(request, 'facturation/login_client.html', {
        'error': error,
        'success': success
    })


def client_dashboard(request):
    if request.session.get('role') != 'client':
        return redirect('login_client')

    # Récupérer l'objet Client lié à l'utilisateur connecté
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return HttpResponse("Profil client non trouvé. Veuillez contacter l'administration.")

    # Statistiques réelles basées sur la base de données
    factures = Facture.objects.filter(client=client).order_by('-date_facture')
    total_depense = factures.aggregate(Sum('montant_ttc'))['montant_ttc__sum'] or 0
    
    # 1 point de fidélité tous les 100 FCFA dépensés
    points_fidelite = int(total_depense / 100) 
    
    # On considère ici les factures 'en_attente' (si tu as ce statut)
    factures_a_regler = factures.filter(statut='en_attente').count()

    context = {
        'client': client,
        'factures_recentes': factures[:5], 
        'total_depense': total_depense,
        'points': points_fidelite,
        'factures_a_regler': factures_a_regler,
        'today': timezone.now(), 
        'active_menu': 'dashboard'
    }
    return render(request, 'facturation/dashboard_client.html', context)

def achats_client(request):
    if request.session.get('role') != 'client':
        return redirect('login_client')

    # On récupère les infos du client et tous les articles actifs
    client = Client.objects.get(user=request.user)
    articles = Article.objects.filter(actif=True).select_related('categorie')

    return render(request, 'facturation/achats_client.html', {
        'client': client,
        'articles': articles,
        'active_menu': 'achats' 
    })


def client_stocks(request):
    if request.session.get('role') != 'client':
        return redirect('login_client')

    client = Client.objects.get(user=request.user)

    # On récupère tous les produits achetés par ce client
    # On groupe par article pour avoir le total des quantités et la date du dernier achat
    mes_produits = LigneFacture.objects.filter(facture__client=client)\
        .values('article__nom', 'article__code_barres', 'article__categorie__nom', 'article__unite_mesure')\
        .annotate(
            quantite_totale=Sum('quantite'),
            dernier_achat=Max('facture__date_facture')
        ).order_by('-dernier_achat')

    return render(request, 'facturation/stocks_client.html', {
        'client': client,
        'stocks': mes_produits,
        'active_menu': 'stocks'
    })

def facturations_client(request):
    if request.session.get('role') != 'client':
        return redirect('login_client')
    
    # On récupère les infos du client réel
    client = Client.objects.get(user=request.user)
    
    # Filtrage par recherche
    query = request.GET.get('q')
    factures = Facture.objects.filter(client=client).order_by('-date_facture')
    if query:
        factures = factures.filter(numero_facture__icontains=query)

    # Calcul des points (1 point par 1000 FCFA par exemple)
    total_achats = factures.aggregate(Sum('montant_ttc'))['montant_ttc__sum'] or 0
    points = int(total_achats / 1000)

    # Création du contexte pour le template
    context = {
        'client': client,
        'factures': factures,
        'points': points,
        'active_menu': 'facturations', 
        'query': query
    }
    
    return render(request, 'facturation/facturations_client.html', context)


# =========================[ fin des vues pour les clients ]=======================