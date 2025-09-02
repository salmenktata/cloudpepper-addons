# Quelyos – Dynamic Picking

# 📌 Description

Module Odoo qui automatise la sélection de l’emplacement source pour les livraisons sortantes (stock.picking).
Il applique une stratégie intelligente et configurable pour trouver la meilleure source en fonction des stocks disponibles, et gère la création de réassorts internes si nécessaire.

# ✅ Compatible Odoo 18 (Community & Enterprise).
🔗 Dépendances : stock, sale_stock.

# 🚀 Fonctionnalités principales
Stratégie de sélection dynamique et hiérarchisée (évaluée par ligne de picking)

⚠️ Remarque : le terme “commande” dans les priorités ci-dessous désigne chaque ligne (move) de la livraison, pas l’intégralité du picking d’un bloc.

1) Priorité 1 — Central (100 %)
Si l’emplacement central peut couvrir 100 % de la quantité demandée pour la ligne, il est sélectionné.

2) Priorité 2 — Ordre strict activé
Si l’ordre strict est activé, la première boutique de la liste qui couvre 100 % est choisie.

3) Priorité 3 — Ordre strict désactivé
Si l’ordre strict est désactivé, la meilleure boutique (score = stock disponible le plus élevé, avec tie-break sur la meilleure couverture) est sélectionnée si elle couvre 100 %.

4) Priorité 4 — Couverture partielle (nouveau)
Si aucun emplacement (central/boutiques) ne couvre 100 %, le module choisit l’emplacement (central ou boutique) offrant la meilleure couverture partielle pour cette ligne.
Si la meilleure couverture n’est pas le central et qu’un manque subsiste, le module peut créer un réassort interne partiel central → boutique pour combler le manque (voir ci-dessous).

# Réassort interne automatique et finalisé

Lorsqu’un réassort est nécessaire (cas priorité 4, source choisie ≠ central, et central défini) :
- Création d’un picking interne (central → boutique).
- Confirmation, assignation (avec réservation “emplacement exact”) et auto-validation si 100 % des mouvements du réassort sont assignés.
- Nouvelle tentative de réservation de la ligne client après réassort.

Réservation à l’emplacement exact
La réservation est forcée strictement sur l’emplacement choisi (et non ses enfants) grâce à :
- un contexte quelyos_force_exact_location=True lors des assignations,
- une surcharge de stock.move._get_domain_locations() qui remplace le child_of par un in lorsque ce contexte est présent.

Paramétrage complet (Paramètres → Ventes → Quelyos – Dynamic Picking)
- Activation/désactivation de la stratégie.
- Type de stock à utiliser : Quantité libre, Physique (On-Hand), Prévisionnel.
    - Libre = somme des quants – réservé (sur l’arborescence via child_of).
    - On-Hand / Forecast via contexte location (avec compute_child=True).
- Limiter la stratégie aux commandes eCommerce.
- Sélection de l’emplacement central.
- Définition de la liste des boutiques à considérer.
- Ordre strict (liste ordonnée style Gafsa>Sousse>Soukra).
        Note : l’ordre strict par nom est pratique mais sensible aux renommages/traductions. Pour plus de robustesse, envisager un champ code ou une liste d’IDs.

# ⚙️ Installation
1) Copier le dossier du module (p. ex. quelyos_ecom_dynamic_picking) dans votre répertoire addons / extra-addons.
    Si vous utilisez un suffixe de version dans le nom (ex. quelyos_ecom_dynamic_picking_v2_0), vérifiez que le chemin et le nom du module sont cohérents.
2) Redémarrer le serveur Odoo.
3) (Optionnel) Activer le mode développeur.
4) Aller dans Applications et rechercher “Quelyos – Dynamic Picking”.
5) Installer le module.

# 🔧 Configuration
Aller dans Paramètres → Ventes.
Dans la section “Quelyos – Dynamic Picking”, renseigner :
- Activation de la stratégie,
- Limitation eCommerce (si souhaitée),
- Base de stock (Libre / On-Hand / Prévisionnel),
- Emplacement central,
- Boutiques à considérer,
- Ordre strict (et sa liste ordonnée si activé).

# 📂 Fichiers principaux
- models/stock_picking.py : logique principale de sélection & réassort (priorités 1→4, scoring, création/confirmation/assignation/validation des réassorts, réservation “exacte” côté client).
- models/stock_move.py : resserrement du domaine de réservation (emplacement exact) via _get_domain_locations().
- models/res_config_settings.py : paramétrage (écran Configuration / Ventes).
- views/res_config_settings_views.xml : UI du bloc “Quelyos – Dynamic Picking”.
- __manifest__.py : métadonnées du module (dépendances, version, etc.).
- models/__init__.py : imports des modèles du module.

# 🧭 Notes d’usage / bonnes pratiques
La stratégie s’applique aux pickings sortants (code == 'outgoing') et par ligne (move).
En multi-société, si vous stockez la configuration en ir.config_parameter, veillez à la scoper (clé par société) ou migrez vers des champs sur res.company (avec related dans res.config_settings).
Si vous utilisez des lots/séries, adaptez la logique de sélection/réservation en conséquence (exigences de traçabilité).

# 📌 Auteur
Quelyos – https://quelyos.com
Licence : LGPL-3
