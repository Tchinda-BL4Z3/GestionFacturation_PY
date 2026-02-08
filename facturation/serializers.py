from rest_framework import serializers
from .models import Article, Facture, LigneFacture, Client

class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['id', 'code_barres', 'nom', 'prix_ht', 'taux_tva', 'prix_ttc', 'stock_actuel']

class LigneFactureSerializer(serializers.ModelSerializer):
    nom_article = serializers.ReadOnlyField(source='article.nom')
    
    class Meta:
        model = LigneFacture
        fields = ['article', 'nom_article', 'quantite', 'prix_unitaire_ht', 'taux_tva']

class FactureSerializer(serializers.ModelSerializer):
    lignes = LigneFactureSerializer(many=True)

    class Meta:
        model = Facture
        fields = ['id', 'numero_facture', 'client', 'mode_paiement', 'montant_ttc', 'lignes', 'date_facture']

    def create(self, validated_data):
        # Logique complexe pour créer la facture et ses lignes en une fois
        lignes_data = validated_data.pop('lignes')
        facture = Facture.objects.create(**validated_data)
        
        total_ht = 0
        total_tva = 0
        
        for ligne in lignes_data:
            # Création de la ligne et calcul automatique
            lf = LigneFacture.objects.create(facture=facture, **ligne)
            # Calculs pour la mise à jour de la facture
            total_ht += lf.prix_unitaire_ht * lf.quantite
            total_tva += (lf.prix_unitaire_ht * lf.quantite) * (lf.taux_tva / 100)
        
        facture.montant_ht = total_ht
        facture.montant_tva = total_tva
        facture.montant_ttc = total_ht + total_tva
        facture.save()
        
        return facture