# Phase 6A.1 — Embeddings + FAISS (recherche sémantique uniquement)

Cette phase s'ajoute au RAG lexical BM25 existant, **sans le modifier**. Il n'y a ni génération Qwen, ni reranking, ni GraphRAG dans ce module. Il produit une recherche sémantique indépendante pour une comparaison honnête avec BM25, puis une fusion hybride en phase 6A.2.

## Prérequis

Dans Windows PowerShell à la racine du dépôt :

```powershell
ollama list
.\.venv\Scripts\python.exe -c "import numpy, faiss; print('numpy', numpy.__version__, 'faiss', faiss.__version__)"
```

Le modèle `nomic-embed-text` doit être présent, sinon `ollama pull nomic-embed-text`. Installer si besoin : `.\.venv\Scripts\python.exe -m pip install faiss-cpu numpy`.

## Étape 1 — Valider le corpus sans écrire ni appeler Ollama

```powershell
.\.venv\Scripts\python.exe scripts/rag_semantique_faiss_phase6a1.py --dry-run
```

Le résultat attendu sur le corpus actuel est **263 chunks / 4 documents**.

## Étape 2 — Créer l'index local

```powershell
.\.venv\Scripts\python.exe scripts/rag_semantique_faiss_phase6a1.py --build --model nomic-embed-text --batch-size 16
```

Le script envoie les textes au modèle via `POST /api/embed` en lots de 16, en contrôlant leurs dimensions et valeurs, puis utilise `faiss.IndexFlatIP` et la normalisation L2 pour une recherche en similarité cosinus. Avec seulement 263 chunks, l'index est **exact**, pas approximatif. Les sorties sont exclusivement sous `data/processed/faiss_nomic_v1/` : `index.faiss`, `chunks.json`, `manifest.json`. Les chemins sources ne sont jamais modifiés. Ne pas committer les index binaires dans Git sauf besoin explicite.

## Étape 3 — Vérifier l'index sans Ollama

```powershell
.\.venv\Scripts\python.exe scripts/rag_semantique_faiss_phase6a1.py --check
```

L'index doit contenir 263 vecteurs. Le nombre de dimensions est déterminé par le modèle installé : ne pas inventer cette valeur. Le script compare les sommes SHA-256 pour éviter d'utiliser un index ancien après modification du corpus.

## Étape 4 — Première question, sans générer de réponse

```powershell
.\.venv\Scripts\python.exe scripts/rag_semantique_faiss_phase6a1.py --question "How does BGM improve retrieval compared with GTR?" --top-k 5
```

Comparer les passages obtenus avec la baseline BM25 :

```powershell
.\.venv\Scripts\python.exe scripts/rag_classique_phase6.py --question "How does BGM improve retrieval compared with GTR?" --top-k 5 --retrieval-only
```

FAISS retourne des scores de similarité cosinus, **pas** des scores BM25. Ils ne sont donc pas comparables numériquement. Les sources et les rangs peuvent être comparés à partir des `chunk_id` et des pages.

## Validation

Le modèle d'embeddings effectue une recherche sémantique, tandis que `qwen2.5:7b` reste destiné à générer la réponse dans le pipeline RAG. Il est normal que `nomic-embed-text` ne génère aucun texte. Un meilleur classement n'est pas garanti, et un résultat hors sujet est possible. Il faudra mesurer la pertinence avant de conclure. **Ne jamais confondre FAISS avec un reranker.**

## Dépannage

- `Connection refused` : vérifier qu'Ollama est lancé ; `ollama list` et `ollama ps`.
- `model not found` : vérifier le nom dans `ollama list`, puis `ollama pull nomic-embed-text` si nécessaire.
- `Index incomplet` / `corpus a changé` : relancer `--build` (avec le même modèle) après vérifier les fichiers.
- `faiss` introuvable : installer dans le `.venv` du dépôt, pas dans Python système.
- Modèle/indices : éviter de modifier les fichiers sous `data/processed/faiss_nomic_v1` à la main.
