Voici un fichier **README.md** complet et professionnel qui récapitule tout le travail accompli jusqu'à présent. Ce document servira de guide de référence pour ton projet.

---

# 🛒 SUPER-FACTU : Système de Gestion de Facturation

**SUPER-FACTU** est une application web moderne de gestion de facturation et d'inventaire conçue pour les supermarchés. Elle offre une interface premium, sombre et réactive, permettant un suivi précis des ventes et des stocks.

## 🚀 Fonctionnalités Développées

### 🛡️ Authentification Multi-Profils
*   **Espace Administrateur (Patron) :** Connexion sécurisée via E-mail et Mot de passe.
*   **Espace Caissier :** Ouverture de session simplifiée via Identifiant Employé et Code PIN numérique.
*   **Espace Comptable :** (Structure prête pour déploiement).

### 📊 Tableau de Bord Administrateur (Dashboard)
*   **Statistiques en temps réel :** Chiffre d'affaires global, nombre de transactions, et total clients.
*   **Alertes de Stock :** Indicateur visuel immédiat pour les produits en rupture ou sous le seuil critique.
*   **Top 5 Produits :** Affichage des meilleures ventes avec revenus générés.
*   **Journal d'activité :** Flux des dernières factures éditées.

### 💰 Suivi des Ventes
*   **Historique Global :** Liste exhaustive de toutes les transactions avec filtrage par numéro de facture.
*   **Analyse de Performance :** Calcul automatique du panier moyen et de la vente record.
*   **Détails des Paiements :** Identification du mode de paiement (CB, Espèces) et du caissier responsable.

### 📦 Gestion des Stocks (Inventaire)
*   **Vue par Catégories :** Organisation structurée (Alimentaire vs Non-Alimentaire) avec système de dossiers dépliables.
*   **Indicateurs Critiques :** Mise en évidence visuelle (Néon Rouge) des produits nécessitant un réapprovisionnement.
*   **Valeur Marchande :** Calcul automatique de la valeur totale du stock HT.

---

## 🔑 Identifiants de Test

Pour accéder aux différentes interfaces développées, utilisez les comptes suivants :

### 👨‍💼 Profil : Administrateur (Patron)
*   **URL :** `/login/admin/`
*   **E-mail :** `admin@gmail.com`
*   **Mot de passe :** `admin1234`

### 🧑‍ cashier Profil : Caissier
*   **URL :** `/login/caissier/`
*   **ID Employé :** `EMP-123`
*   **Code PIN :** `1234`

---

## 🛠️ Stack Technique
*   **Backend :** Python 3.x, Django 5.x
*   **Base de données :** PostgreSQL (Gestion des transactions et intégrité référentielle)
*   **Frontend :** HTML5, Tailwind CSS (Design Premium Dark Mode)
*   **Icônes :** Google Material Symbols

---

## 📂 Structure du Projet
```text
GestionFacture_PY/
├── config/                  # Configuration Django (settings, urls)
├── facturation/             # Application métier
│   ├── models.py            # Schéma PostgreSQL (Articles, Factures, Clients)
│   ├── views.py             # Logique métier et calculs statistiques
│   └── admin.py             # Configuration du panneau d'administration
├── templates/               
│   ├── layouts/             # adminLayout.html (Base commune avec Sidebar)
│   └── facturation/         # Pages (Dashboard, Ventes, Stocks, Logins)
├── static/                  # Assets (Images de fond, CSS personnalisé)
└── manage.py                # Point d'entrée des commandes
```

---

## ⚙️ Installation Rapide
1.  **Clonage et Environnement :**
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install django psycopg2-binary
    ```
2.  **Base de données :**
    *   Créer une base de données `superfactu_db` dans PostgreSQL.
    *   Configurer les accès dans `settings.py`.
3.  **Migrations et Lancement :**
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    python manage.py runserver
    ```

---

## 📅 Prochaines Étapes
1.  **Interface de Caisse Interactive :** Développement du panier de vente avec scanner de code-barres (JavaScript).
2.  **Génération de PDF :** Impression automatique du ticket de caisse après validation.
3.  **Gestion des Clients :** Système de carte de fidélité et historique par client.

---
*Ce projet suit scrupuleusement le Cahier des Charges "Application de Gestion de la Facturation - Supermarché" version 1.0.*
