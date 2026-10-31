# Scientific Research AI — Phase 2C V3 (pilote local)

## Contexte exact

- L'ingestion Scrapy + HDFS est déjà validée.
- 4 PDF, 72 pages, 263 chunks (1200 caractères max avec overlap 180) déjà préparés.
- Les 4 mêmes chunks sont sélectionnés par les modules V1, V2 et V3, pour une comparaison équitable.
- V1 : 13 entités acceptées / 0 relation ; V2 : 18 entités acceptées / 0 relation. **Ces comptes concernent les précédents essais de l'utilisateur, pas V3.**
- Exécuter V3 d'abord comme pilote : pas de traitement automatique des 263 chunks.

## Ce que V3 change

1. Garde exactement les fichiers `extract_scientific_knowledge.py` et `extract_scientific_knowledge_v2.py` existants, utilisés comme dépendances ; n'efface ni V1 ni V2.
2. Corrige un défaut de validation des noms : `Natural` ne peut pas se valider comme sous-chaîne de `NaturalQuestions`. Reconnaît *pour vérification uniquement* les césures OCR/PDF très spécifiques : `Hot- potQA` ≈ `HotpotQA`, `Natural Ques- tions` ≈ `Natural Questions`. Les preuves stockées restent **les textes originaux littéraux**.
3. Fenêtres de preuve de **680 caractères et overlap 320**, au lieu de 380/90 en V2. Une plus grande fenêtre **ne suffit jamais** à accepter une relation.
4. Deux appels LLM par chunk lorsque deux entités au moins sont reconnues : extraction d'entités puis de relations.
5. N'accepte une **candidate** relationnelle que si elle possède des IDs d'entités valides, un sens/type compatible, une fenêtre source existante, **une même phrase** qui contient les deux noms et un indice lexical explicite cohérent avec le prédicat. Détecte quelques négations évidentes.
6. Les relations qui passent ne sont **PAS automatiquement vraies** : elles sont labellisées `LEXICALLY_GROUNDED_CANDIDATE_REQUIRES_HUMAN_REVIEW`.
7. Génère un CSV à réviser humainement, pour la future base Neo4j.

## Installation

Extraire le ZIP dans la racine `Scientific-research-ai`, et fusionner seulement les dossiers `scripts`, `tests`, `docs`. **Ne pas supprimer les anciens scripts ou les données.**

Trois nouveaux fichiers :

- `scripts/extract_scientific_knowledge_v3.py`
- `tests/test_knowledge_extraction_v3.py`
- `docs/LLM_KNOWLEDGE_EXTRACTION_V3.md`

Prérequis déjà installés : Python `.venv`, Ollama, modèle `qwen2.5:3b`, fichiers V1 et V2, `data/processed/chunks/pdf_chunks.jsonl`.

## Exécution dans PowerShell (racine du projet)

```powershell
# 1. Vérifier que le script est présent
Test-Path scripts\extract_scientific_knowledge_v3.py

# 2. Tests unitaires (si Ran 0 tests, ce n'est PAS une réussite)
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_knowledge_extraction_v3.py" -v

# 3. Simulation sans Ollama, sans écriture
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v3.py --dry-run

# 4. Pilote réel sur 4 chunks, un par PDF
.\.venv\Scripts\python.exe scripts/extract_scientific_knowledge_v3.py --model qwen2.5:3b

# 5. Résultats
Get-Content data\reports\llm_knowledge_preview_v3_report.json
Import-Csv data\reports\llm_knowledge_v3_review.csv | Format-Table -AutoSize
```

## Fichiers générés (ne pas pousser sur GitHub)

- `data/processed/llm/knowledge_preview_v3.jsonl` : enregistrements enrichis avec entités, relations candidates, rejets, preuves, identité du modèle, provenance article et page.
- `data/reports/llm_knowledge_preview_v3_report.json` : comptes, rejets et erreurs.
- `data/reports/llm_knowledge_v3_review.csv` : tableau pour validation **humaine**. La colonne `human_decision` vaut toujours `PENDING` ; ne pas importer les relations non approuvées dans Neo4j.

**Le script ne modifie PAS les résultats V1/V2, ni les 263 chunks, ni HDFS, ni Neo4j.** Il contacte uniquement le serveur Ollama local à `127.0.0.1` par l'intermédiaire du validateur d'URL existant.

## Critères de validation pour la soutenance

- Vérifier que les 16 tests unitaires passent sur Windows.
- Contrôler les 4 sorties de modèle réelles, les motifs de rejet et 3 à 5 exemples de preuve.
- Pour une relation `METHOD → EVALUATED_ON → DATASET`, vérifier dans l'article que la méthode a réellement été évaluée sur le dataset, et pas seulement que les deux noms sont mentionnés.
- Les fenêtres et indices lexicaux sont des **filtres**, pas une preuve scientifique suffisante : inspecter les phrases retenues, leurs négations et le contexte.
- Si aucune relation n'est acceptée, rapporter honnêtement 0 ; ne pas affaiblir aveuglément les filtres. Un autre chunk contenant une relation explicite peut alors être ajouté dans une phase ultérieure, en gardant une comparaison équitable séparée.
- Ne **pas** annoncer que l'analyse des 263 chunks ou l'import Neo4j est terminé après ce pilote.

## Commit Git ciblé après validation

```powershell
git add scripts/extract_scientific_knowledge_v3.py tests/test_knowledge_extraction_v3.py docs/LLM_KNOWLEDGE_EXTRACTION_V3.md
git diff --cached --check
git diff --cached --name-only
git commit -m "feat(llm): add grounded V3 scientific extraction pilot"
git push origin main
```

Ne pas utiliser `git add .` : le dépôt contient d'autres fichiers non suivis et des données scientifiques générées.

## Limite importante et plan pour demain

Un modèle `qwen2.5:3b` peut mal interpréter une proposition scientifique. Si les résultats restent insuffisants, sélectionner un petit **jeu d'annotations manuelles** (quelques passages explicites et contre-exemples) et mesurer précision des relations, nombre de preuves vraiment correctes, et taux de rejet. Pour tenir une démonstration demain, privilégier **une chaîne reproductible modeste** à un graphe immense non vérifié. La suite — Spark, Neo4j, GraphRAG, benchmark et Streamlit — n'est pas couverte par cette archive.
