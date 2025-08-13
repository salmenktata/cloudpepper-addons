# Quelyos – Dynamic Picking (v1.0 - Strategy Free Param)

## 📌 Description
Ce module Odoo permet de **sélectionner automatiquement** l’emplacement source pour les livraisons sortantes (`stock.picking`) en appliquant une stratégie intelligente basée sur les stocks disponibles et un ordre de priorité configurable.  
Il gère également la création **automatique de réassorts internes** si nécessaire.

Compatible avec **Odoo 18 Community & Enterprise**.

---

## 🚀 Fonctionnalités principales
- **Critère 1** : utiliser l’**emplacement central** si son stock couvre **toute la commande**.
- **Critère 2** : sinon, sélectionner la **boutique** qui couvre **le plus d’articles** de la commande (maximum de couverture cumulée).
- **Critère 3** : sinon, tester les **boutiques dans l’ordre d’ajout** (défini dans les paramètres) et prendre la première qui couvre tout.
- **Sinon** : déclencher un **réassort interne** du **central → boutique choisie** pour les articles manquants.
- Paramétrage complet depuis **Paramètres > Ventes** :
  - Activation/désactivation du picking dynamique.
  - Choix du **type de stock** utilisé pour le calcul :  
    - `Quantité libre` (stock physique – réservé)  
    - `Physique (On-Hand)`  
    - `Prévisionnel` (inclut les entrées confirmées)
  - Limitation aux **commandes eCommerce** (optionnel).
  - Sélection de l’**emplacement central** (Critère 1).
  - Sélection des **boutiques à considérer** (ordre d’ajout appliqué au Critère 3).

---

## 🛠 Installation
1. Copier le dossier du module `quelyos_ecom_dynamic_picking_v1_0` dans votre répertoire `addons` ou `extra-addons`.
2. Redémarrer le serveur Odoo.
3. Activer le mode développeur si besoin.
4. Aller dans **Applications** et rechercher **"Quelyos – Dynamic Picking"**.
5. Installer le module.

---

## ⚙ Configuration
1. Aller dans **Paramètres > Ventes**.
2. Trouver la section **"Qelyos – Picking dynamique"** (juste après "Livraison").
3. Configurer :
   - **Activer le picking dynamique**.
   - **Type de stock** : libre, physique ou prévisionnel.
   - **Appliquer uniquement eCommerce** : oui/non.
   - **Emplacement central** : choisir le stock prioritaire (ex : `CENT/Stock`).
   - **Boutiques à considérer** : sélectionner et **ordonner l’ajout** (l’ordre sera utilisé pour le Critère 3).

---

## 🔄 Logique détaillée

**Lors de la confirmation d’un transfert sortant** :
1. **Critère 1** : vérifier si l’emplacement central couvre **toute la commande**.
2. Si non, **Critère 2** : calculer la couverture cumulée de chaque boutique → prendre celle avec le **maximum**.
3. Si encore non satisfaisant, **Critère 3** : tester les boutiques dans l’ordre défini dans la configuration → prendre la première qui couvre tout.
4. Si aucun critère ne couvre la commande, créer un **réassort interne** du central vers la boutique qui a déjà le plus d’articles couverts.

---

## 📄 Fichiers principaux
- `models/stock_picking.py` : logique de sélection et réassort.
- `models/res_config_settings.py` : paramètres stockés sur la société.
- `views/res_config_settings_views.xml` : écran de configuration dans Paramètres > Ventes.
- `views/stock_views.xml` : affichage du **log Qelyos** dans les transferts.
- `security/ir.model.access.csv` : droits d’accès aux modèles du module.

---

## 🧪 Tests recommandés
1. **Test Critère 1** : stock central couvrant toute la commande → doit être sélectionné.
2. **Test Critère 2** : central insuffisant, mais une boutique couvre le plus d’articles → doit être sélectionnée.
3. **Test Critère 3** : aucun stock complet, tester l’ordre défini dans la config → doit prendre la première boutique valide.
4. **Test Réassort** : aucun critère ne couvre → création d’un picking interne du central vers la boutique sélectionnée.

---

## 📌 Auteur
- **Quelyos** – [https://quelyos.com](https://quelyos.com)

Licence : **LGPL-3**
