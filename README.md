# Quelyos – Dynamic Picking (v2.0)

# 📌 Description
Ce module Odoo automatise la sélection de l’emplacement source pour les livraisons sortantes (stock.picking). Il applique une stratégie intelligente et configurable pour trouver la meilleure source en fonction des stocks disponibles, tout en gérant la création de réassorts internes si nécessaire.

# Ce module est compatible avec Odoo 18 Community & Enterprise.

# 🚀 Fonctionnalités principales
Stratégie de sélection dynamique et hiérarchisée : Le module évalue les emplacements selon l'ordre de priorité suivant :

- Priorité 1 : L’emplacement central est sélectionné s’il peut couvrir toute la commande.
- Priorité 2 : Sinon, si l’ordre strict est activé, la première boutique de la liste qui peut couvrir la commande est choisie.
- Priorité 3: Si l’ordre strict est désactivé, la meilleure boutique (avec le score de stock disponible le plus élevé) est sélectionnée si elle peut couvrir la commande.
- Priorité 4 (Nouvelle) : Si aucun emplacement ne peut couvrir la commande en entier, le module sélectionne l'emplacement (parmi le central et les boutiques) qui offre la meilleure couverture pour l'ensemble des articles commandés.
- Réassort interne automatique : Si l'emplacement source sélectionné n'est pas l'emplacement central, un bon de réassort interne est automatiquement créé pour transférer le stock manquant de l'emplacement central vers l'emplacement choisi.

# Paramétrage complet depuis Paramètres > Ventes :
- Activation/désactivation de la stratégie de picking.
- Choix du type de stock utilisé pour le calcul : Quantité libre, Physique (On-Hand) ou Prévisionnel.
- Limitation de la stratégie aux commandes eCommerce.
- Sélection de l’emplacement central.
- Définition de la liste des boutiques à considérer.
- Activation de l’ordre strict et spécification de la liste ordonnée des boutiques (Gafsa>Sousse>Soukra).

# 🛠 Installation
- Copier le dossier du module quelyos_ecom_dynamic_picking_v2_0 dans votre répertoire addons ou extra-addons.
- Redémarrer le serveur Odoo.
- Activer le mode développeur si besoin.
- Aller dans Applications et rechercher "Quelyos – Dynamic Picking".
- Installer le module.

# ⚙ Configuration
Aller dans Paramètres > Ventes.
Dans la section "Quelyos – Dynamic Picking", configurer les options souhaitées.

# 📄 Fichiers principaux
models/stock_picking.py : Contient la logique principale de sélection et de réassort.
models/res_config_settings.py : Gère les paramètres de configuration.
views/res_config_settings_views.xml : Définit l'interface de l'écran de configuration.

# 📌 Auteur
Quelyos – https://quelyos.com
Licence : LGPL-3
