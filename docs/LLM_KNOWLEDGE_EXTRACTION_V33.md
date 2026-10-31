# Scientific Research AI | Phase 2C, version V3.3

## Objectif

Améliorer le **pipeline** d'extraction locale avec `qwen2.5:7b`, sans promettre que les poids du modèle ont changé. V3.3 = nouvelle stratégie de passages + instructions plus précises + provenance + benchmark reproductible. Ce n'est PAS un fine-tuning du LLM.

La V3.2 avait généré, sur quatre chunks, 25 entités lexicalement acceptées et **1 relation candidate** avec Qwen2.5:7b, contre 28 entités et aucune relation candidate avec Qwen2.5:3b. La candidate n'est **pas** une relation validée scientifiquement. Ces chiffres n'établissent pas de précision ou de rappel, qui demandent une annotation de référence.

## Installation

Depuis la racine du dépôt `Scientific-research-ai`, extraire le ZIP puis fusionner les dossiers `scripts/`, `tests/`, `docs/` sans effacer les fichiers existants. Prérequis : `scripts/extract_scientific_knowledge.py`, `_v2.py`, `_v3.py`, `_v32.py` et les 263 chunks dans `data/processed/chunks/pdf_chunks.jsonl`. Ollama installé et modèle `qwen2.5:7b` téléchargé.

## Exécution dans PowerShell (terminal VS Code)

```powershell
# 1. Exécuter les tests V3.3 sans appeler Ollama
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_knowledge_extraction_v33.py" -v

# 2. Prévisualiser les passages sélectionnés sans écriture de fichiers
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v33.py --model qwen2.5:7b --dry-run

# 3. Comparaison directe à V3.2 : EXACTEMENT les quatre chunks de base
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v33.py --model qwen2.5:7b --mode baseline
Get-Content data\reports\llm_knowledge_preview_v33_qwen2_5_7b_baseline_report.json

# 4. Expérience élargie : 3 chunks × 4 documents = max. 12 chunks
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v33.py --model qwen2.5:7b --mode expanded --chunks-per-document 3
Get-Content data\reports\llm_knowledge_preview_v33_qwen2_5_7b_expanded_report.json

# 5. Examen des relations candidates (CSV annotable)
Import-Csv data\reports\llm_knowledge_v33_qwen2_5_7b_expanded_review.csv | Format-List *
```

Les commandes `--mode baseline` et `--mode expanded` enregistrent **des résultats distincts**. La comparaison avec la V3.2 ne se fait QUE sur `baseline`. Les comptes de relations `expanded` sont sur davantage de texte : **ne les comparer pas directement aux comptes V3.2**.

Il est possible de tester Qwen2.5:3b avec les mêmes commandes, en remplaçant `--model`, afin de comparer deux modèles sur un même ensemble.

## Ce que fait la V3.3

1. Réutilise `select_preview` du pipeline antérieur pour garantir que les quatre chunks du benchmark historique sont présents.
2. En mode `expanded`, choisit des passages complémentaires par des indices de pertinence lexicaux (évaluation, benchmark, expérience, dataset, mesures, usage). Elle préfère aussi des pages différentes. C'est un **score heuristique**, pas une vérification scientifique.
3. Fournit des descriptions plus strictes des six types d'entités et des six prédicats, avec exemples **positifs et négatifs**. Les exemples sont clairement séparés des sources et ne doivent jamais être traités comme des faits extraits.
4. Préserve la validation stricte V3 : noms présents dans les fenêtres, IDs valides contraints par schémas JSON dynamiques V3.2, types/directions contrôlés, deux entités et verbe dans une même phrase, garde-fou de négation.
5. Enregistre un fichier JSONL par modèle/mode, un rapport JSON, un CSV de révision humaine et un manifeste de sélection JSON.
6. **N'écrit rien sur HDFS, n'importe rien dans Neo4j, ne modifie pas les fichiers V1 à V3.2.** `--dry-run` ne contacte pas Ollama et n'écrit aucun fichier.

## Comment vérifier les relations

Ouvrir le CSV `..._review.csv` : les colonnes incluent `document_id`, `chunk_id`, `page_number`, `subject`, `predicate`, `object`, `evidence`, `verification`, `human_decision` (initialement `PENDING`) et `review_notes`. Lire la phrase de preuve dans la source et décider explicitement `ACCEPT` ou `REJECT`, avec justification. N'entrer dans le graphe comme relation scientifique confirmée que les relations revues et acceptées. Le validateur lexical ne garantit pas la vérité de la relation, ni le type scientifique exact des entités.

**Limitation importante** : l'échantillon de quatre PDF n'est pas représentatif du corpus scientifique général ; la sélection par mots clés risque de favoriser des passages faciles. Pas de précision/rappel sans jeu annoté manuellement, et des tests unitaires sur des réponses simulées ne prouvent pas les résultats réels d'Ollama.

## En cas d'échec

- `ModuleNotFoundError` : vérifier que `scripts/extract_scientific_knowledge_v32.py` existe.
- `Ollama model missing` : `ollama list`, puis `ollama pull qwen2.5:7b`.
- Réponse JSON invalide : conserver le message d'erreur, ne pas désactiver les contrôles.
- `relations = 0` : ce n'est pas nécessairement une erreur technique. Examiner les chunks choisis, les entités et les rejets.
- Si l'objectif de la soutenance est proche : s'arrêter après baseline + expanded, puis construire le graphe des **publications/sections/auteurs/mentions**, avec les relations scientifiques non validées tenues à l'écart.

## Validation de livraison

Tests unitaires locaux passés (modèles simulés). L'exécution réelle de Qwen2.5:7b sur tes données reste à réaliser sur ton PC : les résultats réels ne sont pas préjugés.
