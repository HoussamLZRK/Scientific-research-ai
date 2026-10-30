# Phase 2B, étape 1 : découpage des textes scientifiques

## Objectif

Lire `data/processed/pdf_pages.jsonl` produit en phase 2A et produire des passages (chunks) JSONL pour une future extraction LLM.

**Aucune extraction par LLM n'a lieu à cette étape.** Les passages doivent être contrôlés avant d'être utilisés comme preuves scientifiques.

## Installation

Fusionner les dossiers `scripts`, `tests`, `docs`, `data` du ZIP avec le projet. Ne pas écraser les fichiers existants hors de ces nouveaux chemins.

## Exécution depuis la racine du projet (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_pdf_chunking.py" -v
.\.venv\Scripts\python.exe scripts/chunk_pdf_pages.py --upload-hdfs
Get-Content data\reports\pdf_chunking_report.json
```

## Sorties

- Local : `data/processed/chunks/pdf_chunks.jsonl`
- Rapport : `data/reports/pdf_chunking_report.json`
- HDFS : `/scientific-research-ai/processed/chunks/pdf_chunks.jsonl`

Chaque ligne conserve les métadonnées de provenance (`document_id`, `source`, `title`, `doi`, `page_number`, `hdfs_pdf_path`, `pdf_sha256`) et ajoute `chunk_id`, `char_start_on_page`, `char_end_on_page`, `text`.

Les offsets font référence au texte de page **normalisé en espaces uniques**, pas aux positions originales dans le PDF.

Le découpage utilise des fenêtres de **1 200 caractères maximum et un chevauchement ciblé de 180 caractères**, sans compter de tokens. Il ne comprend pas encore la structure scientifique des paragraphes, tableaux ou formules. La qualité des extractions pypdf doit être contrôlée séparément.

## GitHub

Le `.gitignore` fourni protège le JSONL des passages, qui peut reproduire du texte protégé. Ne pas publier les textes complets ou les PDF. Après vérification, versionner uniquement le code, les tests, la documentation et le `.gitignore`.
