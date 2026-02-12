
# 🛒 SUPER-FACTU : Système de Gestion de Facturation

**SUPER-FACTU** est une application web moderne de gestion de facturation et d'inventaire conçue pour les supermarchés. Elle offre une interface premium, sombre et réactive, permettant un suivi précis des ventes, des stocks et de la clientèle.

## 🚀 Fonctionnalités Développées

### 🛡️ Authentification Multi-Profils
*   **Espace Administrateur (Patron) :** Accès total aux statistiques, stocks et gestion des comptes.
*   **Espace Caissier :** Interface simplifiée pour l'enregistrement des ventes.

### 📊 Tableau de Bord & Reporting (Admin)
*   **Statistiques en temps réel :** Chiffre d'affaires, volume de transactions et alertes de stock bas.
*   **Centre d'Exportation :** Exportation des rapports de ventes filtrés en trois formats :
    *   **Excel (.xlsx) :** Pour une analyse comptable approfondie.
    *   **PDF :** Pour des rapports officiels prêts à imprimer (via WeasyPrint).
    *   **CSV :** Pour l'importation de données brutes.

### 👥 Gestion de la Clientèle
*   **Répertoire Dynamique :** Recherche instantanée par nom, téléphone ou ID.
*   **Gestion de Comptes :** Possibilité d'activer ou de bloquer un client (Statut actif/inactif).
*   **Fidélité :** Calcul automatique des points de fidélité basés sur le volume d'achat.
*   **Historique Individuel :** Consultation des 10 dernières factures par client via un modal dédié.

### 📦 Gestion des Stocks & Ventes
*   **Inventaire Intelligent :** Suivi des stocks avec indicateurs visuels néon pour les ruptures.
*   **Historique de Facturation :** Filtrage avancé par date, numéro de facture et caissier.
*   **Détails de Vente :** Consultation granulaire des articles vendus pour chaque facture.

---

## 🛠️ Stack Technique & Dépendances

### Backend & Librairies
*   **Python 3.10+ / Django 5.x**
*   **PostgreSQL :** Base de données relationnelle.
*   **WeasyPrint :** Moteur de rendu PDF professionnel.
*   **Openpyxl :** Génération de feuilles de calcul Excel.
*   **Psycopg2-binary :** Connecteur PostgreSQL.

### Frontend
*   **Tailwind CSS :** Design Dark Mode Premium.
*   **Material Symbols :** Bibliothèque d'icônes Google.

---

## ⚙️ Installation et Configuration

### 1. Prérequis Système (Linux/Ubuntu)
Pour générer les rapports PDF, certaines bibliothèques graphiques sont nécessaires sur le système :
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-cffi python3-brotli libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0
```

### 2. Installation du projet
1. **Environnement virtuel :**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
2. **Installation des dépendances Python :**
   ```bash
   pip install -r requirements.txt
   ```

### 3. Base de données PostgreSQL
* Créer une base de données nommée `supermarche_db`.
* Configurer vos accès (User/Password) dans le fichier `config/settings.py`.

### 4. Initialisation
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser  
python manage.py runserver
```

---

## 📝 Contenu du fichier `requirements.txt`
```text
Django>=5.0
psycopg2-binary
djangorestframework
openpyxl
weasyprint
```

---

## 🔑 Identifiants de Test (Développement)

| Profil | Identifiant | Mot de passe / PIN |
| :--- | :--- | :--- |
| **Administrateur** | `admin@gmail.com` | `admin1234` |
| **Caissier** | `EMP-001` | `caissier001` |

---

## 📂 Organisation des fichiers clés
*   `facturation/models.py` : Structure des données (Article, Client, Facture).
*   `facturation/views.py` : Logique d'exportation et calculs statistiques.
*   `templates/facturation/rapport_pdf.html` : Mise en page du document PDF.
*   `facturation/templatetags/` : Filtres personnalisés pour les calculs en template.

---
*Ce document est mis à jour périodiquement suivant l'évolution du projet conformément au Cahier des Charges initial.*