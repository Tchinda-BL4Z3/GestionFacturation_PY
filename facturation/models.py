from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal

class Categorie(models.Model):
    nom = models.CharField(max_length=100)
    def __str__(self): return self.nom

class Article(models.Model):
    UNITE_CHOICES = [('piece', 'Pièce'), ('kg', 'Kilogramme'), ('litre', 'Litre')]
    
    code_barres = models.CharField(max_length=50, unique=True)
    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    prix_ht = models.DecimalField(max_digits=10, decimal_places=2)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=20.0)
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True)
    unite_mesure = models.CharField(max_length=20, choices=UNITE_CHOICES, default='piece')
    stock_actuel = models.IntegerField(default=0)
    stock_minimum = models.IntegerField(default=5)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    @property
    def prix_ttc(self):
        return self.prix_ht * (1 + self.taux_tva / 100)

class Client(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    carte_fidelite = models.CharField(max_length=50, unique=True, null=True, blank=True)
    actif = models.BooleanField(default=True)

class Facture(models.Model):
    MODE_PAIEMENT = [
        ('especes', 'Espèces'), ('cb', 'Carte Bancaire'), 
        ('cheque', 'Chèque'), ('mixte', 'Mixte')
    ]
    STATUT = [('valide', 'Valide'), ('annulee', 'Annulée'), ('avoir', 'Avoir')]

    numero_facture = models.CharField(max_length=50, unique=True)
    date_facture = models.DateTimeField(auto_now_add=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    utilisateur = models.ForeignKey(User, on_delete=models.PROTECT) # Le caissier
    
    montant_ht = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_tva = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_ttc = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_remise = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    mode_paiement = models.CharField(max_length=50, choices=MODE_PAIEMENT)
    statut = models.CharField(max_length=20, choices=STATUT, default='valide')
    facture_origine = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)

class LigneFacture(models.Model):
    facture = models.ForeignKey(Facture, related_name='lignes', on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.PROTECT)
    quantite = models.DecimalField(max_digits=10, decimal_places=2)
    prix_unitaire_ht = models.DecimalField(max_digits=10, decimal_places=2)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2)
    total_ttc = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        # Logique pour décrémenter le stock à la vente
        if not self.pk:
            self.article.stock_actuel -= self.quantite
            self.article.save()
        super().save(*args, **kwargs)