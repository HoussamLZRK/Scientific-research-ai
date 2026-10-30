# V3 alternative : ACL Anthology + PMLR (HTML sans API)

## Pourquoi ?
Le 30 octobre 2026, la tentative Scrapy sur DBLP a reçu une réponse HTTP 202 contenant une page de vérification Anubis ("Making sure you're not a bot!"). Les **17 tests** hors ligne ont réussi, mais **0 publication** DBLP a été obtenue. Nous ne contournons pas la protection : source alternative PMLR, volume 235 (ICML 2024).

Ce module **n'écrase aucun fichier V1/V2/V3 existant**. DBLP reste dans l'historique comme tentative documentée, non comme une source fonctionnelle.

## Sources
- ACL Anthology : collecte locale `data/raw/publications_v2.jsonl`, déjà validée.
- PMLR : https://proceedings.mlr.press/v235/ . Scrapy parcourt les pages HTML d'articles, pas une API.
- Documentation officielle PMLR : https://proceedings.mlr.press/faq

## Règles de collecte
`ROBOTSTXT_OBEY=True`, 3 secondes entre requêtes par domaine, une seule requête concurrente, limites à 30 publications maximum pour le pilote. Les politiques/robots.txt et conditions du site doivent être vérifiées sur la machine d'exécution avant d'augmenter le volume. En cas de blocage (robots, HTTP 202/403/429), arrêter la collecte. Ni spoofing ni contournement.

## Installation
Copier **le contenu de l'archive** à la racine de `Scientific-research-ai/` (fusion des dossiers existants). Ne remplacer aucun fichier préexistant.

## Commandes PowerShell (racine du projet)

Vérifier les tests existants + 4 nouveaux tests :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Premier essai PMLR limité à **3 articles** :

```powershell
.\.venv\Scripts\python.exe -m scrapy runspider crawler/spiders/pmlr_spider_v3.py -a limit=3 -O data/raw/publications_pmlr_v3.jsonl
```

Contrôler le nombre de lignes et les champs :

```powershell
(Get-Content data/raw/publications_pmlr_v3.jsonl | Where-Object { $_.Trim() -ne '' }).Count
Get-Content data/raw/publications_pmlr_v3.jsonl -TotalCount 1
```

**Si le site autorise cette collecte et 3 lignes valides sont extraites**, augmenter à 10 :

```powershell
.\.venv\Scripts\python.exe -m scrapy runspider crawler/spiders/pmlr_spider_v3.py -a limit=10 -O data/raw/publications_pmlr_v3.jsonl
```

Fusionner **uniquement après succès des deux fichiers sources** :

```powershell
.\.venv\Scripts\python.exe scripts/merge_acl_pmlr_v3.py
.\.venv\Scripts\python.exe scripts/validate_acl_pmlr_v3.py --min-count 2
```

Fichiers produits :
- `data/processed/publications_multisource_v3.jsonl`
- `data/reports/multisource_v3_report.json`

Important : comme ACL Anthology et PMLR couvrent deux conférences différentes, **0 recoupement entre sources n'est pas un échec**. Ne pas demander `--min-overlap 1` artificiellement.

## GitHub, une fois les tests et la collecte réels vérifiés

```powershell
git status
git add crawler/spiders/pmlr_spider_v3.py scripts/merge_acl_pmlr_v3.py scripts/validate_acl_pmlr_v3.py tests/test_pmlr_v3.py docs/CRAWLER_V3_PMLR.md
git commit -m "feat(crawler): add PMLR HTML source after DBLP anti-bot block"
git push origin HEAD
```

Ne pas ajouter automatiquement le dossier `data/` ni publier les fichiers bruts ou un résultat non vérifié.

## Limites scientifiques
La source PMLR n'a pas toujours de DOI. Les auteurs doivent être vérifiés. Les pages d'articles peuvent avoir des structures HTML différentes ; les tests hors ligne ne remplacent pas une collecte réelle. Les graphiques de citations et d'institutions nécessiteront des données supplémentaires plutôt que des chiffres inventés.
