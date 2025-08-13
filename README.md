Quelyos – Dynamic Picking (v2.0)
📌 Description
Ce module Odoo automatise la sélection de l’emplacement source pour les livraisons sortantes (stock.picking) en appliquant une stratégie intelligente et hautement configurable, basée sur un système de règles dynamiques.

Il gère également la création automatique de réassorts internes si nécessaire.

Compatible avec Odoo 18 Community & Enterprise.

🚀 Fonctionnalités principales
Ce module remplace la logique de sélection en cascade par un moteur de règles puissant et flexible, permettant de :

Définir des règles de sélection : Créez des règles avec des conditions et des actions spécifiques pour déterminer l'emplacement source.

Prioriser les règles : Chaque règle possède une séquence qui définit son ordre d'évaluation. La première règle qui s'applique à une commande est utilisée.

Surcharger la stratégie : Les règles peuvent être spécifiques à une catégorie de produits, permettant une gestion fine de la logistique.

Stratégies disponibles par règle :

Priorité au central : Choisit un emplacement central s'il peut couvrir toute la commande.

Ordre strict : Choisit la première boutique dans un ordre prédéfini qui peut couvrir la commande.

Meilleure couverture : Sélectionne l'emplacement offrant la meilleure couverture de la commande, basé sur un score pondéré.

Réassort interne automatique : Si l'emplacement source choisi n'est pas le central, un bon de réassort est créé automatiquement pour transférer le stock manquant.

Paramètres de pondération : Pour les règles de "meilleure couverture", définissez le poids de la couverture de stock par rapport à la disponibilité générale du stock.

Interface intuitive : Gérez toutes les règles depuis un menu dédié dans Odoo, avec des vues Tree et Kanban pour faciliter l'organisation par glisser-déposer.

🛠 Installation
Copier le dossier du module quelyos_ecom_dynamic_picking_v2_0 dans votre répertoire addons ou extra-addons.

Redémarrer le serveur Odoo.

Activer le mode développeur si besoin.

Aller dans Applications et rechercher "Quelyos – Dynamic Picking".

Installer le module.

⚙ Configuration
Allez dans Inventaire > Configuration > Magasin et trouvez le nouveau menu "Règles de Picking Dynamique".

Créez vos règles en leur donnant un nom, une séquence, et un type.

Dans Paramètres > Ventes, trouvez la section "Quelyos – Dynamic Picking" pour activer ou désactiver la stratégie globale et gérer l'application aux commandes eCommerce.

📄 Fichiers principaux
models/quelyos_dynamic_picking_rule.py : Nouveau modèle pour la définition des règles.

models/stock_picking.py : Contient la logique principale qui évalue les règles.

models/res_config_settings.py : Ajout du bouton de gestion des règles.

views/quelyos_dynamic_picking_rule_views.xml : Vues pour gérer les règles.

views/res_config_settings_views.xml : Mise à jour de l'écran de configuration.

📌 Auteur
Quelyos – https://quelyos.com

Licence : LGPL-3