from django.contrib import admin
from .models import Article, Categorie, Facture, LigneFacture, Client

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('code_barres', 'nom', 'prix_ht', 'taux_tva', 'stock_actuel', 'actif')
    search_fields = ('code_barres', 'nom') # Recherche par code-barres ou nom (CDC 2.1.2)
    list_filter = ('categorie', 'actif')
    list_editable = ('stock_actuel', 'actif') # Permet de modifier le stock rapidement

class LigneFactureInline(admin.TabularInline):
    model = LigneFacture
    extra = 1

@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ('numero_facture', 'date_facture', 'montant_ttc', 'statut', 'utilisateur')
    list_filter = ('statut', 'mode_paiement', 'date_facture')
    inlines = [LigneFactureInline] # Permet de voir les articles à l'intérieur de la facture
    readonly_fields = ('date_facture',)

admin.site.register(Categorie)
admin.site.register(Client)