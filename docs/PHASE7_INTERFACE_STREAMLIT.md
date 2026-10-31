# Scientific Research AI — Phase 7 : interface Streamlit

## Objectif

Exposer le pipeline réel validé dans les phases précédentes :

- **Vue d'ensemble** : décompte des PDF, chunks, publications et topologie du graphe à partir des fichiers existants.
- **Assistant scientifique** : BM25, hybride BM25 + embeddings FAISS + RRF, ou GraphRAG Neo4j ; génération Qwen2.5:7b ; affichage des passages avec leurs pages et IDs.
- **Graph Analytics** : métriques structurelles et entités exploratoires, sous-graphe de provenance interrogé en lecture seule dans Neo4j.
- **Explorateur** : lecture du corpus PDF chunké.
- **Évaluation : protocole** : comparaisons prévues, **sans scores inventés** (la mesure multi-questions arrive en phase 8).

Cette phase ne remplace ni ne modifie les scripts 6A, 6A.1, 6A.2, 6B ou leurs index.

## Installation Windows PowerShell (depuis la racine du projet)

1. Extraire le ZIP **dans le dossier** `C:\Users\houss\Documents\Scientific-research-ai`. Le nouveau fichier principal se nomme **`app_phase7.py`** pour éviter d'écraser un éventuel `app.py` existant. Les autres fichiers nouveaux sont `scripts/streamlit_phase7_backend.py`, `tests/test_streamlit_phase7.py`, `docs/PHASE7_INTERFACE_STREAMLIT.md`, `.streamlit/config.toml`, `requirements_streamlit_phase7.txt`.

2. Installer Streamlit et assurer les dépendances déjà utilisées :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_streamlit_phase7.txt
```

3. Exécuter les tests de la nouvelle phase :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_streamlit_phase7.py" -v
```

**Attendu :** `Ran 24 tests` puis `OK`. Tests **hors ligne** et simulés, qui ne prouvent pas à eux seuls la connexion à ton Ollama, Neo4j ou FAISS.

4. Lancer Streamlit :

```powershell
.\.venv\Scripts\python.exe -m streamlit run app_phase7.py
```

Le terminal doit proposer `Local URL: http://localhost:8501`. Ouvrir cette adresse dans le navigateur. Pour arrêter : `Ctrl+C` dans le terminal.

## Avant de présenter

- Docker Desktop démarré, conteneur Neo4j existant (`docker ps --filter "name=srai-neo4j"`).
- Ollama en cours d'exécution, modèles `qwen2.5:7b` et `nomic-embed-text` déjà installés (`ollama list`).
- Index FAISS **déjà créé** sous `data/processed/faiss_nomic_v1/`, `--check` réussi (263 vecteurs, dimension 768). **Pas besoin de refaire `--build`**.
- Chunking PDF : `data/processed/chunks/pdf_chunks.jsonl` (263 chunks).
- Neo4j : 46 entités, 9 chunks enrichis et 55 relations `MENTIONS_ENTITY` lors de ta dernière vérification ; l'UI lira les données présentes au moment de l'exécution. Pas de relation scientifique causale inventée.
- Rapports Graph Analytics : `data/reports/graph_analytics_report.json` et `data/reports/graph_analytics_scientific_phase5b.json` pour les métriques. Leur absence produit un message de diagnostic, pas des chiffres fabriqués.

## Démonstration conseillée

1. **Vue d'ensemble** : montrer 4 PDF, 263 chunks et le rapport de structure Neo4j.
2. **Graph Analytics → Sous-graphe Neo4j** : dans la barre latérale, déplier **Connexion Neo4j** et saisir le mot de passe (il n'est ni écrit dans le code ni exporté). Choisir `acl_2024_rag_retrievers`, **page 7**, et cliquer **Charger le sous-graphe depuis Neo4j**. Montrer `HAS_CHUNK` et `MENTIONS_ENTITY`.
3. **Assistant scientifique** : question `How does BGM improve retrieval compared with GTR?`, choisir **RAG hybride**, top-k 3, candidats 6, case **Générer une réponse** cochée. Lancer, vérifier les sources et leur page.
4. Refaire **la même question** avec **GraphRAG Neo4j**, mêmes top-k, candidats et paramètre de reranking. Montrer « entités dans la question », « chunks liés » et « nouveaux chunks » ; ne pas conclure à une supériorité sans évaluation multi-questions.
5. **Explorateur de corpus** : montrer l'extrait exact correspondant à une citation.
6. **Évaluation : protocole** : présenter honnêtement les métriques à exécuter en phase 8.

## Points critiques

- Le tableau de bord reprend **uniquement des métriques calculées** par le corpus et les rapports existants.
- Les rapports RAG sont proposés au **téléchargement JSON**. Aucune écriture permanente automatique n'est ajoutée : les originaux et les index restent intacts.
- L'interface affichera une erreur si les services ou la connexion sont indisponibles. Elle ne produit pas de réponse simulée.
- Seuls les passages effectivement récupérés sont transmis à Qwen. Les numéros `[1]`, `[2]` sont des *références de passage*, pas une preuve de véracité de chaque affirmation.
- Si Neo4j ne retrouve aucune entité dans une question, GraphRAG se replie vers la recherche hybride ; cet état est affiché.
- Le graphe scientifique actuel est un **graphe de mentions lexicales**, pas une ontologie de relations causales vérifiées.
- Les articles PDF ne sont **pas** automatiquement associés aux 13 métadonnées de publications extraites par le crawler.
- Les tests et la compilation ont été exécutés lors de la fabrication du ZIP, mais **l'interface live Streamlit n'a pas pu être testée dans l'environnement de génération**. Le démarrage de ton PC constitue le test d'intégration réel.

## Dépannage

- `No module named streamlit` → installer via `python -m pip install -r requirements_streamlit_phase7.txt` avec l'interpréteur `.venv`.
- `FileNotFoundError ... pdf_chunks.jsonl` → lancer depuis la racine de ton projet avec la bonne arborescence ; les 263 chunks doivent être présents.
- Ollama inaccessible → vérifier que l'application Windows Ollama est active et que `ollama list` fonctionne ; ne pas réinstaller le modèle pour rien.
- Neo4j `Unauthorized` → ressaisir le mot de passe via la barre latérale, ne jamais le copier ici.
- FAISS manquant → `python scripts/rag_semantique_faiss_phase6a1.py --check` dans `.venv`; reconstruire l'index seulement si `--check` échoue.
- Tableau Graph Analytics incomplet → lire les rapports sur disque ; les indicateurs non disponibles sont masqués, pas substitués.

## Fichiers fournis

```text
app_phase7.py
requirements_streamlit_phase7.txt
.streamlit/config.toml
scripts/streamlit_phase7_backend.py
tests/test_streamlit_phase7.py
docs/PHASE7_INTERFACE_STREAMLIT.md
```
