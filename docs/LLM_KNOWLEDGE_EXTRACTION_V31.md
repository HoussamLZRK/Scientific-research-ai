# Phase 2C — V3.1 : robustifier les identifiants de relations

## Pourquoi ?

Le pilote V3 sur quatre chunks a identifié 17 entités, mais rejeté 12 relations
sur 14 à cause de références `subject_id`/`object_id` invalides. Le schéma JSON
de V3 indiquait simplement `type: string` pour ces identifiants. Ollama
pouvait donc proposer des noms de concepts ou des identifiants inexistants.

La V3.1 donne au modèle un schéma JSON **dynamique** dont les valeurs possibles
pour `subject_id`, `object_id` et `evidence_id` correspondent exclusivement
aux entités et fenêtres retenues **dans le chunk traité**.

Elle ne répare **pas** automatiquement les mauvais IDs et conserve **à l'identique**
les validations V3 : existence, types, orientation, preuve littérale,
présence des deux noms dans une phrase avec indice relationnel, négation.
Cela limite une source de rejet technique, sans prétendre valider la vérité.

## Installation

Copier `scripts/extract_scientific_knowledge_v31.py`,
`scripts/diagnose_knowledge_v3.py`, `tests/test_knowledge_extraction_v31.py`
et cette documentation dans leurs dossiers du projet. **Ne rien remplacer.**
Nécessite les scripts V1/V2/V3 déjà installés et Ollama local.

## Commandes PowerShell (racine du projet)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_knowledge_extraction_v31.py" -v
.\.venv\Scripts\python.exe scripts/diagnose_knowledge_v3.py
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v31.py --dry-run
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v31.py --model qwen2.5:3b
Get-Content data\reports\llm_knowledge_preview_v31_report.json
```

## Sorties

- `data/processed/llm/knowledge_preview_v31.jsonl`
- `data/reports/llm_knowledge_preview_v31_report.json`
- `data/reports/llm_knowledge_v31_review.csv`

Aucune modification des sorties V1/V2/V3, aucune écriture dans HDFS,
aucune importation Neo4j, aucun commit Git automatique.

**À vérifier** : les IDs rejetés disparaissent-ils ? Des relations acceptées
représentent-elles réellement ce que disent les articles ? Un score de zéro
reste acceptable lorsque la phrase ne justifie aucun lien.
