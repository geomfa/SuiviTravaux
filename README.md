# Rapports de suivi de chantier

Application locale pour générer, à la demande, deux rapports Word à partir des données déjà synchronisées dans PostGIS par le script Kobo existant :

- **Rapport hebdomadaire** : toutes les soumissions au statut Approuvé sur une période donnée, une ligne par observation.
- **Rapport réserves** : toutes les soumissions marquant une non-conformité (FNC), une fiche par réserve. Le champ "Condition de levée" est laissé vide, à compléter à la main après génération.

## Installation (Windows, avec uv)

1. Installer `uv` si ce n'est pas déjà fait : https://docs.astral.sh/uv/getting-started/installation/
2. Ouvrir un terminal dans ce dossier.
3. Créer l'environnement et installer les dépendances :

   ```
   uv sync
   ```

4. Copier `.env.example` en `.env` et renseigner tes vraies valeurs (connexion PostgreSQL, nom du schéma et de la table, token Kobo si les photos en ont besoin).

## Lancer l'application

```
uv run streamlit run app.py
```

Un onglet de navigateur s'ouvre automatiquement (par défaut sur http://localhost:8501). Choisis l'onglet du rapport voulu, ajuste les dates si besoin, clique sur "Générer", puis télécharge le document.

## Structure du projet

```
reporting_app/
├── app.py              interface Streamlit
├── reporting.py         requêtes SQL, téléchargement des photos, génération des Word
├── templates/            les deux modèles Word tagués (docxtpl)
├── photos_tmp/           cache local des photos téléchargées (créé automatiquement)
├── sorties/              documents générés (créé automatiquement)
├── .env                  ta configuration (à créer depuis .env.example, jamais versionné)
└── pyproject.toml        dépendances du projet
```

## Notes

- Les modèles dans `templates/` sont des versions du hebdo et des réserves envoyés, avec des balises `docxtpl` insérées dans les cellules qui doivent être répétées. Le rendu visuel (mise en forme, couleurs, tableau des parties prenantes) reste identique aux modèles d'origine.
- Le script de synchronisation Kobo → PostGIS (`script de base`) reste indépendant de cette application : il continue de tourner comme avant (manuellement ou via une tâche planifiée), l'application ne fait que lire dans la table déjà alimentée.
- Le mapping "titre" des réserves utilise les champs `prestation` et `activite`. Le mapping "entête" du hebdo utilise `intervenant`. Si ce n'est pas exactement ce que tu veux afficher, ce sont les seules lignes à ajuster dans `reporting.py` (fonctions `generer_hebdo` et `generer_reserves`).
