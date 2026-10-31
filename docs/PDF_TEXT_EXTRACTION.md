# Phase 2A — Extraction du texte des publications PDF

## Objectif

Extraire le texte **page par page** des 4 articles déjà conservés en HDFS, sans perdre les métadonnées de provenance (source, titre, URL, DOI, nom et hash du PDF, numéro de page). Préparer ainsi les futures étapes d'extraction d'entités et de relations par LLM.

## Pré-requis

- Dossier racine `Scientific-research-ai` dans le terminal VS Code.
- Python 64 bits et `.venv` fonctionnel.
- Catalogue `config/sample_documents.json` et 4 PDF existants.
- Conteneurs NameNode et DataNode opérationnels si on utilise `--source hdfs`.

## Commandes PowerShell

```powershell
.\.venv\Scripts\python.exe -m pip install "pypdf>=5.0,<7"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_pdf_text_extraction.py" -v
.\.venv\Scripts\python.exe scripts/extract_pdf_text.py --source hdfs --upload-hdfs
```

Ce programme **lit les octets PDF directement dans HDFS** via `docker compose exec -T namenode hdfs dfs -cat`. Il ne transforme jamais du binaire PDF en texte dans PowerShell (ce qui l'endommagerait). Le contenu extrait est enregistré sur Windows dans `data/processed/pdf_pages.jsonl` et copié dans HDFS sous `/scientific-research-ai/processed/text/pdf_pages.jsonl`.

**Alternative de diagnostic si Docker est arrêté :**

```powershell
.\.venv\Scripts\python.exe scripts/extract_pdf_text.py --source local
```

Cette variante ne lit pas depuis HDFS et n'y envoie pas les résultats ; elle sert seulement à vérifier la lecture locale des PDF.

## Sorties

- `data/processed/pdf_pages.jsonl` : un objet JSON par **page PDF**, contenant le texte, le numéro de page, la référence bibliographique, SHA-256 et le statut d'extraction.
- `data/reports/pdf_extraction_report.json` : nombre de pages, avertissements, documents qui nécessitent une revue manuelle.
- HDFS : `/scientific-research-ai/processed/text/pdf_pages.jsonl` lorsque `--upload-hdfs` est activé.

Exemple **schématique** d'une ligne :

```json
{"document_id":"exemple","source":"ACL Anthology","page_number":2,"text":"Exemple de texte extrait ...","extraction_status":"ok"}
```

### Contrôles après l'exécution

```powershell
Get-Content data\processed\pdf_pages.jsonl -TotalCount 1
Get-Content data\reports\pdf_extraction_report.json

docker compose -f docker/hdfs/compose.yaml exec -T namenode hdfs dfs -ls /scientific-research-ai/processed/text
```

## Limites importantes

- `pypdf` n'est **pas un outil OCR**. Les pages entièrement scannées peuvent produire un texte vide, d'où `empty_or_scanned`.
- Tableaux, colonnes, formules et figures peuvent être restitués de manière incomplète ou dans un ordre imprécis. Les textes doivent être contrôlés avant d'être considérés comme une vérité scientifique.
- Les avertissements sur les pages (`low_text`, `empty_or_scanned`) ne bloquent pas l'extraction des autres pages. Ils identifient les cas à examiner.
- Aucune extraction d'entités, résolution de doublons, indexation RAG ou analyse LLM n'est encore réalisée. Ce module est uniquement le **prétraitement texte** de la phase 2.
- Les résultats contiennent des textes d'articles dont la redistribution dépend des licences. Ne publie pas automatiquement `data/processed/pdf_pages.jsonl` ni les PDF sur GitHub.
- Ne versionne sur GitHub que `scripts/extract_pdf_text.py`, `tests/test_pdf_text_extraction.py` et `docs/PDF_TEXT_EXTRACTION.md` après validation réelle.
