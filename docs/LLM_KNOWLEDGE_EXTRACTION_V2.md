# Scientific Research AI | Phase 2C, pilot V2

## Pourquoi cette version ?

Le premier test sur 4 chunks a produit 13 entités acceptées, 15 rejetées, **0 relation acceptée et 18 rejetées**. C'est un échec de la **qualité de l'extraction relationnelle**, pas de l'installation d'Ollama ou de HDFS.

La V1 exige que Qwen recopie lui-même de longues citations exactes et réutilise des noms identiques dans toutes les relations. Les césures PDF (`Natural Ques- tions`) et les paraphrases le font échouer. La V2 conserve les contrôles, sans accepter de citations inventées :

1. Découpe chaque chunk en fenêtres **littérales** `P1`, `P2`, ... (petits chevauchements).
2. Demande au LLM **uniquement des entités** avec un nom copié à l'identique et un identifiant de fenêtre.
3. Vérifie en Python que chaque nom figure dans la fenêtre désignée ; **Python extrait la preuve depuis le texte source**, pas depuis une citation inventée par le LLM.
4. Demande au LLM des relations **uniquement entre les entités validées**, référencées par `E1`, `E2`, ...
5. Vérifie qu'une même fenêtre de preuve contient les deux noms, la direction de `EVALUATED_ON`, puis marque les relations retenues comme `needs_semantic_review`.

**Limite fondamentale :** une preuve textuelle contenant les deux noms ne garantit pas que la relation soit vraie. Une validation humaine/sémantique reste obligatoire avant Neo4j. La V2 ne force jamais un résultat non vide.

## Installation

Copier les fichiers dans le projet, **sans supprimer** l'ancienne version `scripts/extract_scientific_knowledge.py`.

Les sorties V1 sont conservées. Aucune écriture vers HDFS ou Neo4j.

## Commandes (PowerShell dans la racine du projet)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_knowledge_extraction_v2.py" -v
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v2.py --dry-run
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v2.py --model qwen2.5:3b
Get-Content data\reports\llm_knowledge_preview_v2_report.json
```

Sorties nouvelles :
- `data/processed/llm/knowledge_preview_v2.jsonl`
- `data/reports/llm_knowledge_preview_v2_report.json`

## À vérifier avant d'aller plus loin

- Nombre d'entités/relation acceptées et rejetées ; motifs de rejet.
- **Chaque relation** : lire le `evidence` complet, vérifier le sens et les types scientifiques.
- Alias à unifier avec prudence (`NQ` = `Natural Ques- tions`) et césures PDF à traiter de manière contrôlée.
- Les quatre chunks restent les mêmes que pour V1 afin de permettre une comparaison équitable.
- Évaluer ensuite quelques annotations humaines comme vérité terrain ; **ne pas optimiser sur un simple nombre de relations**.
- Si le modèle reste peu fiable, envisager un modèle plus robuste, sous réserve de RAM et de temps de calcul.

## Publication Git

Publier uniquement le script V2, les tests et la documentation **après validation réelle**. Aucun `git add .`, aucun JSONL de sorties LLM dans le commit.
