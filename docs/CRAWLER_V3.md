# Crawler V3 — collecte multisource ACL Anthology + DBLP

## Objectif
Réunir des données bibliographiques issues **de deux sites HTML** (pas d'API), avec une traçabilité de chaque source. Le module DBLP exploite les notices d'une **page de conférence**, non les pages PDF. Les résumés absents restent `null`.

## Pré-requis
- Dossier Git local `Scientific-research-ai`, Windows / PowerShell et environnement `.venv` avec Scrapy déjà installé.
- La V1 et la V2 **restent inchangées** ; conserver `crawler/spiders/acl_spider_v2.py`, `crawler/pipelines.py` et `scripts/validate_crawl_v2.py`.
- À faire avant V3 : vérifier que `publications_v2.jsonl` contient réellement des notices ACL valides (la présence d'un commit ne suffit pas).

## Nouvelle source
- DBLP : https://dblp.org/db/conf/acl/acl2024-1.html
- Règles officielles de crawling : https://dblp.org/faq/1474706.html . DBLP autorise l'exploration en respectant robots.txt et des délais raisonnables, suggérant 1–2 secondes au minimum. Notre configuration applique un délai de 3 s et une seule requête à la fois.
- **La politique robots.txt et la structure HTML actuelles doivent être vérifiées lors du premier lancement réel** ; aucune collecte sur DBLP n'a été exécutée pendant la préparation de cette archive.
- Ne pas contourner `403`, `429`, ni robots.txt. Éviter les téléchargements massifs.

## Installation V3
Copier le **contenu** de cette archive à la racine de `Scientific-research-ai` ; ne pas créer un deuxième dossier racine. Pour les dossiers déjà présents (`crawler`, `docs`, `scripts`, `tests`, `data`), copier leur contenu pour fusionner les dossiers. Ne remplacer aucun fichier V1/V2.

## Commandes PowerShell, à la racine du dépôt

### 1. Tests hors ligne (toutes versions)
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### 2. Contrôle de la collecte ACL V2 déjà faite
```powershell
.\.venv\Scripts\python.exe scripts/validate_crawl_v2.py --min-count 1 --max-count 100
```

### 3. Collecte DBLP (10 notices pour la première exécution)
```powershell
.\.venv\Scripts\python.exe -m scrapy runspider crawler/spiders/dblp_spider.py -a limit=10 -O data/raw/publications_dblp_v3.jsonl
```
`-O` remplace **uniquement** `publications_dblp_v3.jsonl`. Il ne modifie ni `publications_v2.jsonl` ni la V1. Si aucune notice n'est exportée, contrôler les logs Scrapy, les directives robots.txt et les sélecteurs HTML.

### 4. Fusion multisource (sans perte des données d'origine)
```powershell
.\.venv\Scripts\python.exe scripts/merge_sources_v3.py
```
Sorties :
- `data/processed/publications_multisource_v3.jsonl` : publications unifiées, provenance conservée.
- `data/reports/multisource_v3_report.json` : comptages, recoupements, erreurs potentielles.

### 5. Validation du jeu de données unifié
```powershell
.\.venv\Scripts\python.exe scripts/validate_multisource_v3.py --min-count 2
```
Quand les deux sites couvrent suffisamment d'articles communs, essayer `--min-overlap 1` pour exiger au moins un recoupement confirmé. Ne pas inventer une correspondance si le rapport indique zéro.

### 6. Amélioration progressive
Après un test réussi et vérification des règles du site, augmenter à 20 puis 50 notices :
```powershell
.\.venv\Scripts\python.exe -m scrapy runspider crawler/spiders/dblp_spider.py -a limit=20 -O data/raw/publications_dblp_v3.jsonl
.\.venv\Scripts\python.exe scripts/merge_sources_v3.py
.\.venv\Scripts\python.exe scripts/validate_multisource_v3.py --min-count 2
```

## Logique de déduplication
1. Si le DOI est identique, on fusionne les fiches.
2. Sinon, si un identifiant ACL **explicitement attesté** est commun, on peut fusionner.
3. Si deux DOI différents sont présents, on signale le conflit et on **ne fusionne pas**.
4. Un même titre/année ne suffit pas ; ces cas sont seulement signalés dans `possible_duplicates_not_merged`.
5. Les informations d'origine restent conservées dans `source_records` et `source_urls`.

## Limites et qualité
- La présence de plusieurs sources est garantie si les fichiers de chaque source existent et contiennent des résultats valides. Une **correspondance** entre sources n'est pas garantie.
- DBLP n'apporte pas systématiquement de résumé ; ne jamais inventer ce champ.
- Les références de citations entre articles et les affiliations institutionnelles ne sont pas encore extraites. Elles nécessiteront un module distinct.
- Les tests livrés utilisent des pages HTML fictives. Si le site réel change, il faudra adapter `extract_dblp_record` aux éléments HTML observés.
- Les données brutes et les rapports doivent rester locaux tant qu'une publication n'a pas été approuvée.

## GitHub (committer seulement le code vérifié)
```powershell
git status
git add crawler/spiders/dblp_spider.py scripts/merge_sources_v3.py scripts/validate_multisource_v3.py tests/test_crawler_v3.py tests/fixtures/dblp_volume_v3.html docs/CRAWLER_V3.md data/processed/.gitignore
git commit -m "feat(crawler): add DBLP HTML source and multisource reconciliation"
git push -u origin HEAD
```
Si vous travaillez sur `feat/crawler-v3-multisource`, le push envoie sur cette branche, **pas sur main**. Après vérification, ouvrir une pull request vers main pour conserver une revue du travail.
