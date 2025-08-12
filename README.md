# Qelyos – Dynamic Picking (v1.0)

## 📌 Objectif du module
Automatiser le choix de l’emplacement source pour les livraisons sortantes (pickings) en appliquant une **stratégie de sélection intelligente** basée sur les stocks disponibles, tout en déclenchant automatiquement un réassort interne si nécessaire.

---

## 🚀 Fonctionnalités principales

### 1️⃣ Sélection automatique de l’emplacement source
Lorsqu’un picking sortant est créé, le module évalue tous les emplacements configurés (**CENT/Stock** et les boutiques) et applique la stratégie définie dans la configuration.

**Stratégie “Critères personnalisés” :**
1. **Critère 1** – Si **CENT/Stock** a assez de stock libre pour toutes les lignes → on prend CENT comme source pour tout.
2. **Critère 2** – Sinon, choisir la boutique avec **le maximum de stock libre cumulé** (hors CENT), réserver ce qui est dispo et déclencher un **réassort interne** depuis CENT vers cette boutique pour compléter les manquants.
3. **Critère 3 – Ordre strict** (optionnel) – Tester les boutiques dans l’ordre `Gafsa → Sousse → Soukra` et choisir la première qui couvre toute la commande.

---

### 2️⃣ Calcul basé sur différents types de stock
- **Quantité libre (par défaut)** → Physique - Réservé  
- **Physique (On-Hand)** → Quantité physique réelle  
- **Prévisionnel (Forecast)** → Stock disponible après mouvements confirmés

---

### 3️⃣ Réassort interne automatique
Si la source choisie ne couvre pas tout :
- Création d’un picking interne **CENT/Stock → Boutique choisie**
- Quantité transférée = **manquant** pour chaque ligne
- Picking interne créé en **état "À traiter"**

---

### 4️⃣ Paramétrage flexible
Dans **Paramètres > Inventaire > Qelyos – Dynamic Picking** :
- **Stratégie appliquée** : Critères personnalisés ou Désactivé
- **Type de stock** : Libre / Physique / Prévisionnel
- **Boutiques à considérer**
- **Ordre strict activable**
- **Application uniquement aux commandes eCommerce**

---

### 5️⃣ Points forts
- 🚫 Évite les ruptures : priorité à l’entrepôt central si complet
- 🔄 Automatisation du réassort interne
- ⚙️ Paramétrable selon besoin
- 📝 Logs clairs dans le chatter

---

## 📥 Installation
1. Copier le dossier `quelyos_ecom_dynamic_picking_v1_0` dans le répertoire `addons` d’Odoo.
2. Mettre à jour la liste des applications.
3. Installer **Qelyos – Dynamic Picking (v1.0)**.

---

## ⚙️ Configuration
1. Aller dans **Inventaire > Configuration > Paramètres** (onglet Expédition).
2. Dans la section **Qelyos – Dynamic Picking** :
   - Définir l’emplacement central.
   - Choisir les boutiques à inclure.
   - Sélectionner la stratégie et le type de stock.
   - Activer ou non l’ordre strict.
3. Sauvegarder.

---

## 💡 Exemple d’utilisation
- **Commande client de 10 unités**
- CENT/Stock → 6 unités
- Boutique Sousse → 8 unités
- Stratégie choisie : **Critères personnalisés**
- Résultat :
  - Source choisie : **Sousse**
  - Réassort créé automatiquement : **CENT → Sousse (2 unités)**

---

## 🛠️ Compatibilité
- Odoo **v18+**
- Modules requis : `stock`, `sale_management`

---

## 📄 Licence
Ce module est distribué sous licence **LGPL-3.0**.
