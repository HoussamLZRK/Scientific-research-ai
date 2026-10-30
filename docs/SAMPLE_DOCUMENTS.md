# Échantillon documentaire pour le pipeline d'ingestion

## Objectif

En complément des publications HTML recueillies par les crawlers ACL et PMLR,
préparer quatre **documents PDF** issus de **quatre sources** pour démontrer la
variété des formats et des sources du futur pipeline HDFS -> extraction LLM.

Les PDF ne sont **pas** téléchargés depuis une API. Ils sont récupérés depuis
les liens officiels de publication. Ceci constitue un échantillon documentaire
contrôlé, pas une nouvelle version du crawler Scrapy.

## Articles retenus

| Plateforme | Article | Année | Lien officiel |
| --- | --- | --- | --- |
| ACL Anthology | Bridging the Preference Gap between Retrievers and LLMs | 2024 | https://aclanthology.org/2024.acl-long.562/ |
| PMLR | A Statistical Framework for Data-dependent Retrieval-Augmented Models | 2024 | https://proceedings.mlr.press/v235/basu24a.html |
| PLOS | Ten simple rules for using large language models in science, version 1.0 | 2024 | https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1011767 |
| HAL | Refining Wikidata Taxonomy using Large Language Models | 2024 | https://hal.science/hal-04687258 |

Les références, auteurs, DOI éventuels, URL PDF et conditions sont dans
`config/sample_documents.json` (ce fichier doit être suivi par Git).

## Instructions (PowerShell sous Windows, à la racine du dépôt)

```powershell
.\.venv\Scripts\python.exe scripts/download_sample_documents.py --list
.\.venv\Scripts\python.exe scripts/download_sample_documents.py
.\.venv\Scripts\python.exe scripts/validate_sample_documents.py
```

Si une source refuse les téléchargements automatiques, **ne pas** contourner
ses protections. Ouvrir son `article_url` dans le navigateur, télécharger
manuellement le PDF lorsque c'est autorisé et le placer dans
`data/sample_documents/` avec le nom indiqué dans le catalogue. Relancer la
validation. **HAL peut présenter une page de protection anti-bot**.

L'application conserve un rapport local dans `data/reports/sample_documents_report.json`.

## GitHub et droits

- **Ne pas publier les PDF** dans le dépôt par défaut. Leur droit de
  redistribution dépend de la source, même si le téléchargement est libre.
- Suivre uniquement le catalogue, les scripts, les tests et cette documentation.
- Garder DOI, URL de l'article, titre, auteurs, année et source pour la traçabilité.
- `data/sample_documents` sera stocké dans HDFS au prochain jalon.

## Limites

Le script vérifie un en-tête `%PDF-` et calcule un SHA256. Ce n'est **pas**
une extraction du texte, un contrôle de la licence ni une preuve de conformité
scientifique. Les relations extraites par LLM seront validées plus tard.
