# Crawler V2 — ACL Anthology (HTML, sans API)

## Objectif
La V2 reprend la V1 **sans la modifier** et augmente la capacité maximale de 20 à 100 articles par exécution. Elle ajoute une normalisation du DOI, une suppression des doublons et un contrôle qualité avec rapport JSON.

## Ce que fait le crawler
1. Visite une page de volume HTML (par défaut `2024.acl-long`).
2. Identifie les liens d'articles du même volume.
3. Sélectionne jusqu'à `limit` URLs sans doublons.
4. Visite chaque page autorisée et extrait les métadonnées HTML.
5. Rejette les articles sans titre ou auteurs, ainsi que les doublons de la collecte.
6. Produit un fichier JSONL distinct de la V1.

## Commandes PowerShell dans la racine du dépôt
Tu as **déjà** installé Python 64 bits et Scrapy ; ne réinstalle rien.

### 1. Tests hors-ligne
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### 2. Premier essai (10 articles, dans un fichier V2 distinct)
```powershell
.\.venv\Scripts\python.exe -m scrapy runspider crawler/spiders/acl_spider_v2.py -a limit=10 -O data/raw/publications_v2.jsonl
```

### 3. Validation (10 articles visés)
```powershell
.\.venv\Scripts\python.exe scripts/validate_crawl_v2.py --min-count 10 --max-count 10
```
Le rapport est écrit dans `data/reports/crawler_v2_report.json`.

### 4. Collecte élargie (50 articles visés)
Exécuter seulement si les règles du site le permettent et que le premier essai est concluant :
```powershell
.\.venv\Scripts\python.exe -m scrapy runspider crawler/spiders/acl_spider_v2.py -a limit=50 -O data/raw/publications_v2.jsonl
.\.venv\Scripts\python.exe scripts/validate_crawl_v2.py --min-count 50 --max-count 50
```
Les bornes strictes signalent une collecte incomplète ; lire les logs si le nombre reçu est inférieur au nombre demandé.

`-O` écrase **seulement** le fichier `publications_v2.jsonl`, jamais la V1. Pour préserver chaque essai, utiliser un nom distinct dans `data/raw/`.

## Limitations / points de vigilance
- `ROBOTSTXT_OBEY=True`, une requête à la fois sur le domaine, délai de 3 secondes + auto-throttle. Ne pas contourner un refus, une erreur 403 ou 429.
- Le fichier de `robots.txt` n'a pas pu être vérifié indépendamment pendant la préparation du code. Scrapy le consulte lors de l'exécution ; vérifier également les conditions du site avant d'augmenter le nombre de pages.
- Ni API ni téléchargement de PDF ; pas de citations ou d'institutions inventées.
- Le plafond 100 est intentionnel. Pour dépasser cela, étudier d'abord les limites du site et la qualité des résultats.
- Les doublons sont éliminés **dans une même exécution**, pas entre plusieurs fichiers/runs. La déduplication globale sera traitée lors de la préparation des données Spark.
- La collecte ne garantit pas exactement `limit` articles : des articles peuvent manquer, être inaccessibles ou incomplets. Lire le rapport et les logs Scrapy.

## GitHub
Avant de committer :
```powershell
git status
```
Ajouter seulement les nouveaux fichiers V2 :
```powershell
git add crawler/pipelines.py crawler/spiders/acl_spider_v2.py scripts/validate_crawl_v2.py tests/test_crawler_v2.py docs/CRAWLER_V2.md
```
Puis :
```powershell
git commit -m "feat(crawler): add V2 scaling and data quality checks"
git push origin HEAD
```
Ne pas mettre en dépôt `data/raw/*.jsonl`, `data/reports/*.json` ni `.venv`.
