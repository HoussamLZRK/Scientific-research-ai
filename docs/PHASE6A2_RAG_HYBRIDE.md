# Phase 6A.2 - RAG hybride BM25 + FAISS, reranking optionnel

## Objectif

Conserver **BM25 (phase 6A)** et **l'index FAISS (phase 6A.1)**, sans le reconstruire à chaque requête. Pour une question :

1. Recherche BM25 parmi les 263 chunks.
2. Encodage de la question via Ollama `nomic-embed-text`, puis recherche FAISS.
3. Fusion **Reciprocal Rank Fusion** (RRF, k=60), sur les *rangs*, avec dédoublonnage par `chunk_id`.
4. *Facultatif* : reranking de 0 à 3 par `qwen2.5:7b` via schéma JSON contraint. Les candidats notés 0 ne sont pas utilisés pour la génération.
5. *Facultatif* : génération d'une réponse française et de citations via `qwen2.5:7b`, en réutilisant la méthode de la phase 6A.

**Ce module ne contacte pas Neo4j. Il ne constitue pas un GraphRAG.**

## Fichiers

Copier uniquement `scripts/rag_hybride_phase6a2.py` et `tests/test_rag_hybride_phase6a2.py` dans le projet; conserver intactes les phases 6A et 6A.1. Le script importe `rag_classique_phase6.py` et `rag_semantique_faiss_phase6a1.py` déjà installés dans `scripts/`.

## Commandes PowerShell (racine du projet)

1. Tests nouveaux :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_rag_hybride_phase6a2.py" -v
```

2. **Contrôle indispensable** de l'index FAISS (sans Ollama) :

```powershell
.\.venv\Scripts\python.exe scripts/rag_semantique_faiss_phase6a1.py --check
```

Si l'index n'existe pas encore, créer une seule fois :

```powershell
.\.venv\Scripts\python.exe scripts/rag_semantique_faiss_phase6a1.py --build --model nomic-embed-text --batch-size 16
.\.venv\Scripts\python.exe scripts/rag_semantique_faiss_phase6a1.py --check
```

3. Recherche hybride **sans** reranking ni génération :

```powershell
.\.venv\Scripts\python.exe scripts/rag_hybride_phase6a2.py --question "How does BGM improve retrieval compared with GTR?" --top-k 3 --candidates-k 6
```

4. Recherche hybride **avec** reranking Ollama :

```powershell
.\.venv\Scripts\python.exe scripts/rag_hybride_phase6a2.py --question "How does BGM improve retrieval compared with GTR?" --top-k 3 --candidates-k 6 --rerank
```

5. Réponse RAG hybride, avec reranking et citations :

```powershell
.\.venv\Scripts\python.exe scripts/rag_hybride_phase6a2.py --question "How does BGM improve retrieval compared with GTR?" --top-k 3 --candidates-k 6 --rerank --generate
```

Les sorties sont dans `data/reports/rag_hybride_phase6a2_last_query.json`. **Chaque exécution écrase ce rapport**. Pour conserver un benchmark, ajouter `--output data/reports/benchmark_hybride_sans_rerank.json`, etc. Le script ne modifie pas HDFS, les chunks, l'index FAISS ni Neo4j.

## Analyse à réaliser

- Les trois premiers chunks sont-ils pertinents pour la question ?
- Le passage hors sujet (FaZe Clan dans l'ancien top-5) a-t-il disparu ? S'il apparaît, noter le défaut.
- Le reranking améliore-t-il le classement ? Ne pas le supposer sans évaluation.
- Les sources citées appuient-elles vraiment les affirmations de Qwen ? La vérification des identifiants de citation n'est **pas** une vérification sémantique.

## Limites honnêtes

- Avec 263 chunks, `IndexFlatIP` effectue une recherche exacte, aucun gain de vitesse spectaculaire.
- BM25 et les embeddings peuvent récupérer des passages distincts; RRF peut dégrader les résultats dans certains cas.
- Le reranking `qwen2.5:7b` est **LLM-as-reranker**, pas un cross-encoder spécialisé; son évaluation est subjective et peut augmenter la latence. Une alternative spécialisée (cross-encoder) peut être testée plus tard.
- Les documents sont surtout en anglais, donc les requêtes anglaises sont recommandées pour BM25.
- Les résultats expérimentaux sur un exemple ne prouvent pas une amélioration générale. Garder des jeux de questions et mesures `Recall@K`, `MRR`, pertinence humaine et latence.
- Les données de la phase 6A.1 doivent avoir été indexées avant usage, et l'index doit correspondre au SHA256 du corpus.
