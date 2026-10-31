# Scientific Research AI — Phase 2C : extraction LLM locale

## Objectif

Transformer un **premier échantillon de quatre chunks** (un par PDF) en entités et relations scientifiques **avec preuves textuelles**. Aucun graphe Neo4j n'est créé à ce stade et aucun autre chunk n'est analysé automatiquement.

**Entrée existante :** `data/processed/chunks/pdf_chunks.jsonl` (263 chunks après le chunking).  
**Sortie locale :** `data/processed/llm/knowledge_preview.jsonl`.  
**Rapport :** `data/reports/llm_knowledge_preview_report.json`.

> Les sorties d'un LLM sont des candidats à vérifier. La présence d'une citation mot pour mot ne prouve pas à elle seule que la relation scientifique est correcte.

## Étapes Windows (PowerShell dans la racine du projet)

1. Télécharger Ollama depuis https://ollama.com/download/windows si l'application n'est pas encore installée, puis **ouvrir un nouveau terminal** dans VS Code.
2. Vérifier `ollama --version`.
3. Installer le modèle : `ollama pull qwen2.5:3b` (environ 1,9 Go ; demande aussi de l'espace pour Ollama lui-même).
4. Lancer Ollama depuis le menu Démarrer si le service n'est pas actif ; vérifier `ollama list`.
5. Vérifier les tests : `\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_knowledge_extraction.py" -v`.
6. Voir les chunks sélectionnés sans LLM : `\.venv\Scripts\python.exe scripts/extract_scientific_knowledge.py --dry-run`.
7. Lancer la prévisualisation réelle : `\.venv\Scripts\python.exe scripts/extract_scientific_knowledge.py --model qwen2.5:3b`.
8. Consulter le rapport : `Get-Content data\reports\llm_knowledge_preview_report.json`.
9. Afficher la première réponse : `Get-Content data\processed\llm\knowledge_preview.jsonl -TotalCount 1`.

**Pas de `pip install` supplémentaire** : le module utilise uniquement la bibliothèque standard Python.

## Pourquoi un échantillon de quatre chunks ?

Le jeu de données comprend 263 chunks, mais traiter tout le corpus avant d'évaluer les preuves peut produire beaucoup de faux liens. Le script sélectionne un passage par document, favorisant des pages 2 à 6 et des passages évoquant méthodes, modèles et évaluations. Ce score est une heuristique : il faut examiner les quatre passages retenus.

## Schéma de sortie

Chaque enregistrement conserve : `chunk_id`, `document_id`, `source`, `title`, `doi`, `article_url`, `page_number`, `hdfs_pdf_path`, `pdf_sha256`, `model`, `schema_version`, puis quatre listes : `entities`, `relations`, `rejected_entities`, `rejected_relations`.

Un élément de `entities` contient `name`, `type`, `evidence`. Une relation contient `subject`, `predicate`, `object`, `evidence`, `verification`.

Les types sont `METHOD`, `MODEL`, `DATASET`, `METRIC`, `CONCEPT`, `TASK`. Les prédicats possibles : `USES`, `EVALUATED_ON`, `COMPARED_WITH`, `IMPROVES`, `MEASURES`, `ADDRESSES`.

## Vérifications et limites

- Le LLM utilise l'API **locale** Ollama (`127.0.0.1:11434`) avec schéma JSON et température 0.
- Une entité n'est acceptée que si son nom apparaît dans une citation littérale présente dans le chunk.
- Une relation n'est acceptée que si sa citation apparaît dans le chunk, que les deux extrémités y figurent explicitement et que les deux entités ont été retenues.
- Les propositions rejetées et leurs motifs sont conservés pour audit.
- Les relations acceptées sont marquées `lexically_grounded_needs_semantic_review`. **Elles ne sont pas des faits validés** sans contrôle humain.
- Le modèle 3B peut produire trop peu de relations ou se tromper. Si les résultats sont médiocres, évaluer un modèle plus fort sur les mêmes quatre passages plutôt que changer les données.
- Les PDF sont déjà stockés dans HDFS ; les résultats LLM restent locaux jusqu'à validation. Ne pas les publier sur GitHub sans vérifier les droits de redistribution.
- Ce n'est pas encore RAG : aucune recherche n'est réalisée sur le graphe à ce stade.

## Dépannage

- `ollama n'est pas reconnu` : installer Ollama puis rouvrir VS Code / terminal.
- `Cannot connect to Ollama` : ouvrir Ollama sur Windows ; vérifier `http://localhost:11434/api/tags`.
- `model is missing` : lancer `ollama pull qwen2.5:3b`.
- Le modèle est lent : laisser l'application exécuter le calcul local. Prévisualiser 1 document avec `--max-documents 1` si nécessaire.
- Les tableaux/équations scientifiques issus des PDF peuvent être mal extraits ; aucun LLM ne répare automatiquement cela.
- Pour GitHub après validation : publier seulement le code, les tests et la documentation. Le fichier `.gitignore` empêche de publier le JSONL d'extraction par inadvertance.
