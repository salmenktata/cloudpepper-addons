# cloudpepper-addons **synthèse fonctionnelle** claire et complète du module **Quelyos Dynamic Picking (v8.3.9)** :

---

## 1️⃣ Objectif du module

Automatiser le choix de l’emplacement source pour les livraisons sortantes (*pickings*) en appliquant **une stratégie de sélection intelligente** basée sur les stocks disponibles, tout en déclenchant automatiquement un **réassort interne** si nécessaire.

---

## 2️⃣ Fonctionnalités principales

### 🔹 A. Sélection automatique de l’emplacement source

Lorsqu’un picking est créé, le module évalue **tous les emplacements configurés** (CENT/Stock et les boutiques) et applique la stratégie définie dans la configuration.

**Stratégie “Custom Criteria”** :

1. **Critère 1** – Si **CENT/Stock** a assez de stock libre pour toutes les lignes → on prend CENT comme source pour tout.
2. **Critère 2** – Sinon, rechercher la **boutique** avec le **maximum de stock libre cumulé** (hors CENT) → réserver ce qui est dispo et **déclencher un réassort interne depuis CENT vers cette boutique** pour compléter les manquants.
3. **Critère 3 (ordre strict)** – Si activé, tester les boutiques dans l’ordre *Gafsa → Sousse → Soukra* et choisir la première qui couvre toute la commande.

---

### 🔹 B. Calcul basé sur différents types de stock

Le calcul des disponibilités peut se baser sur :

* **Free Quantity** (*par défaut*) → quantité physique **moins** la quantité réservée.
* **On-Hand** → quantité physique réelle, sans tenir compte des réservations.
* **Forecast** → stock prévisionnel après mouvements confirmés (inclut entrées à venir).

---

### 🔹 C. Réassort interne automatique

Si la source choisie ne couvre pas tout :

* Création d’un picking interne **CENT/Stock → Boutique choisie**
* Quantité transférée = **manquant** pour chaque ligne.
* Picking interne mis en état *à traiter* pour compléter la livraison.

---

### 🔹 D. Paramétrage flexible

Via **Paramètres > Inventaire > Qelyos Dynamic Picking** :

* **Applied Strategy** :

  * *Custom Criteria* (logique décrite ci-dessus)
  * *Disabled* (pas de sélection auto)
* **Stock Basis** : *Free Quantity*, *On-Hand*, *Forecast*
* **Order strict** (Gafsa → Sousse → Soukra) activable/désactivable
* Liste des boutiques à prendre en compte dans le calcul.

---

## 3️⃣ Points forts

* **Évite les ruptures** : priorité à l’entrepôt central si complet, sinon à la meilleure boutique.
* **Automatise le réassort** interne en cas de stock insuffisant.
* **Paramétrable** : choix de la stratégie, du type de stock, de l’ordre des boutiques.
* **Compatible Odoo 18+** : code sans `attrs`/`states`, basé sur OWL.
* **Logs clairs** dans le chatter : le critère appliqué et la boutique choisie sont enregistrés.

---

📌 **Cas d’usage typiques** :

* E-commerce multi-boutiques avec un entrepôt central.
* Scénarios où il faut optimiser le lieu d’expédition pour réduire les transferts.
* Besoin d’un réassort interne automatique si le stock local est insuffisant.

Veux-tu que je te prépare ça ?
