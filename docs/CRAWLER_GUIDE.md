# Phase 2 - ACL Anthology HTML crawler (V1)

## Objectif
Récupérer 10 pages HTML d'articles de la conférence ACL 2024 avec Scrapy.
Cette phase **n'appelle aucune API** et ne télécharge pas les PDF.

## Source
- Page de départ : https://aclanthology.org/volumes/2024.acl-long/
- Exemple d'article : https://aclanthology.org/2024.acl-long.1/
- Crédit : ACL Anthology. Conserver la provenance et les URLs dans les données.

## Respect du site
- `ROBOTSTXT_OBEY=True`
- Une requête à la fois par domaine
- Au moins 3 secondes de délai configuré et limitation automatique
- Le crawler limite les pages à 20 maximum tant que la politique n'a pas été vérifiée.
- Vérifier les règles du site et son `robots.txt` avant de monter en volume.
- Si le site interdit la collecte, arrêter et chercher une autre source autorisée.

## Installation (PowerShell dans VS Code)
Dans le dossier racine cloné depuis GitHub :

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-crawler.txt
```

## Tests sans Internet
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Lancer le crawler
```powershell
.\.venv\Scripts\python.exe -m scrapy runspider crawler/spiders/acl_spider.py -a limit=10 -O data/raw/publications.jsonl
```

## Vérifier les résultats
```powershell
.\.venv\Scripts\python.exe scripts/validate_crawl.py
```

La collecte est réussie si le fichier contient des publications réelles avec titre,
auteurs, année et URL, et que la validation ne signale pas d'erreur.

## Points de vigilance
- Si les sélecteurs HTML ne correspondent plus au site, le crawler peut produire 0 résultat.
- Certains articles peuvent ne pas avoir de résumé ou de DOI dans le HTML.
- Les citations et les institutions ne sont pas collectées en V1. Ne pas les inventer.
- L'exécution en conditions réelles doit être validée sur le PC de l'étudiant.
- Ne pas publier les données brutes ou des secrets dans le dépôt GitHub.

## Git
```powershell
git add crawler tests scripts docs/CRAWLER_GUIDE.md requirements-crawler.txt data/raw/.gitignore
git commit -m "feat(crawler): add respectful ACL Anthology HTML spider"
git push -u origin HEAD
```
