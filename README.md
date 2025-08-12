# cloudpepper-addons
- Logique picking complète :
- Critère 1 → CENTRAL si dispo
- Critère 2 → Max dispo boutiques (liste paramétrée)
- Critère 3 → Ordre strict configurable
- Sinon → Réassort interne (type d’opération interne existant)

# Gestion dynamique des étapes :
- Lecture de delivery_steps de l’entrepôt pour livraisons
- Lecture de reception_steps si on veut aussi l’adapter aux réceptions
- Adapte automatiquement le flux 1, 2 ou 3 étapes (OUT seul, PICK+OUT, PICK+PACK+OUT)
- Quantité disponible uniquement (réservations exclues)

# Dual log texte pur :
- Posté dans picking
- Posté aussi dans commande client
- Bloc de configuration complet dans Paramètres Ventes :
- Emplacements sources possibles (critère 2)
- Ordre strict configurable (critère 3)
- Stratégie (fixée ou extensible)
- Site web optionnel
