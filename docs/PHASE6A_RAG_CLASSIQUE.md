# Scientific Research AI | Phase 6A : RAG classique

## Pourquoi cette phase ?

Nous préparons un **point de comparaison indépendant** pour la future évaluation RAG classique versus GraphRAG. Ici, **aucun graphe Neo4j n'est consulté** : seuls les chunks provenant des quatre PDF sont utilisés.

Le processus :

1. Charger et vérifier `data/processed/chunks/pdf_chunks.jsonl` (263 chunks attendus dans le corpus actuel).
2. Retrouver les passages avec **BM25**, algorithme lexical (aucun modèle supplémentaire à installer).
3. Afficher le document, la page et `chunk_id` pour chaque passage retenu.
4. Fournir les passages à **Qwen2.5:7b dans Ollama** en lui demandant de ne répondre qu'avec ces preuves.
5. Vérifier les *numéros de citations* utilisés et enregistrer l'exécution dans `data/reports/rag_classique_last_query.json`.

**Attention** : BM25 n'est pas un moteur de similarité sémantique et ne garantit pas de retrouver les passages pour une question française lorsque les PDF sont en anglais. Poser des questions en anglais au moment de la recherche ; le modèle répond en français. L'évaluation scientifique des réponses n'est pas encore faite.

## Installation

Fusionner uniquement les fichiers du ZIP dans le dépôt. **Ne pas écraser** les scripts précédents. Python standard suffit, Ollama est déjà installé.

Tester :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_rag_classique_phase6.py" -v
```

### 1. Recherche seulement, sans LLM

```powershell
.\.venv\Scripts\python.exe scripts/rag_classique_phase6.py --question "How does BGM improve retrieval compared with GTR?" --top-k 5 --retrieval-only
```

Vérifier que les documents et pages affichés sont pertinents. Cette commande ne modifie aucun fichier et n'appelle pas Ollama.

### 2. Recherche + génération locale

```powershell
.\.venv\Scripts\python.exe scripts/rag_classique_phase6.py --question "How does BGM improve retrieval compared with GTR?" --top-k 5 --model qwen2.5:7b
```

Un rapport JSON est enregistré. Vérifier que les citations correspondent bien aux passages affichés. Pour répéter avec une question différente, utiliser `--question` ; le dernier rapport est remplacé (les sources JSONL d'origine ne sont jamais modifiées).

### 3. Autre question

```powershell
.\.venv\Scripts\python.exe scripts/rag_classique_phase6.py --question "How is WiKC evaluated on entity typing with Wikidata instances?" --top-k 5
```

### Vérifications utiles

```powershell
ollama list
ollama ps
Get-Content data\reports\rag_classique_last_query.json
```

Si le serveur Ollama est absent : ouvrir Ollama (ou `ollama serve` si nécessaire) puis relancer.

## Limites et précautions

- Ce RAG est **lexical**, sans embeddings et sans composantes Neo4j. Cela constitue une baseline reproductible, pas une version de production.
- La présence d'une citation ne prouve pas que la phrase générée est scientifiquement correcte. Validation humaine nécessaire.
- Les données de PDF peuvent comporter des césures et fautes d'extraction.
- Si aucun terme de la question ne correspond, le modèle n'est pas appelé et le programme signale un manque de preuves.
- L'index BM25 est recréé en mémoire à chaque lancement (suffisant pour 263 chunks, pas pour des millions de documents).
- Pour comparer équitablement avec le futur GraphRAG, conserver **les mêmes chunks, modèle, paramètres de génération, questions et top-k** ; seul le moteur de récupération doit changer.
- Aucune écriture sur Neo4j ou HDFS, aucun téléchargement de modèle.
