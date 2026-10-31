# Correctif V3.2 : comparatif Qwen 3B / 7B sans fausser la validation

## Diagnostic

Le benchmark 7B sous V3.1 a produit 7 entités retenues, 24 entités rejetées pour `unknown_evidence_id`, 0 relation retenue et 5 relations rejetées pour types/direction. Ces sorties ne permettent PAS de classer la qualité des deux modèles : l'identification des preuves est techniquement défaillante.

**Cause inspectée dans le code** : V3.1 limitait par JSON Schema les identifiants de relations (`subject_id`, `object_id`, `evidence_id`) mais laissait `evidence_id` d'entité en texte libre. Le 7B pouvait donc produire des références n'existant pas dans les fenêtres `P1`, `P2`, `P3`.

La V3.2 construit un JSON Schema dynamique **dès l'extraction des entités**, avec l'enum exact des fenêtres disponibles. **Les validations V3 restent strictes et identiques.** Aucun ID n'est converti/accepté automatiquement. Il est encore possible qu'un modèle produise une mauvaise réponse ou des classifications scientifiques incorrectes.

La V3.2 crée des fichiers distincts pour chaque nom de modèle. Elle n'écrase donc ni V3.1 ni les autres benchmarks.

## Installation

À la racine du projet, copier les nouveaux dossiers `scripts`, `tests`, `docs` du ZIP dans le projet. **Ne remplacer aucun fichier existant.** V1, V2 et V3 doivent être déjà présents. Aucun accès Internet nécessaire après téléchargement du modèle Ollama.

## Commandes (PowerShell VS Code)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_knowledge_extraction_v32.py' -v
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v32.py --model qwen2.5:7b --dry-run
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v32.py --model qwen2.5:7b
Get-Content data\reports\llm_knowledge_preview_v32_qwen2_5_7b_report.json
```

Comparer sur EXACTEMENT les mêmes chunks via :

```powershell
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v32.py --model qwen2.5:3b
Get-Content data\reports\llm_knowledge_preview_v32_qwen2_5_3b_report.json
```

Les sorties sont :
- `data/processed/llm/knowledge_preview_v32_qwen2_5_7b.jsonl`
- `data/reports/llm_knowledge_preview_v32_qwen2_5_7b_report.json`
- `data/reports/llm_knowledge_v32_qwen2_5_7b_review.csv`
- Même structure avec suffixe `_qwen2_5_3b` pour le 3B.

## Interprétation correcte

1. Chercher si `rejected_entities:unknown_evidence_id` diminue; un `0` indiquerait la résolution du problème technique d'ID.
2. Comparer la qualité et les types des entités dans le JSONL, pas seulement le nombre.
3. Chaque relation retenue reste une **candidate à valider sur le texte source** avant Neo4j.
4. Si `invalid_types_or_direction` domine encore, inspecter les erreurs d'étiquetage d'entités et choisir des passages plus riches en relations explicites. Ne pas affaiblir les garde-fous.
5. Ne pas assimiler 0 relation retenue à un crash : le pipeline peut fonctionner normalement et ne pas trouver de relation documentée dans ce petit échantillon.

**Limitation du test** : les unit tests utilisent des réponses simulées, sans appeler le modèle local. La confirmation sur Ollama exige les commandes réelles ci-dessus.
