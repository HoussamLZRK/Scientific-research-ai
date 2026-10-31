# Scientific Research AI — Phase 6B : GraphRAG avec Neo4j

## 1. Ce que fait précisément ce module

**RAG hybride déjà existant** : BM25 + embeddings `nomic-embed-text` indexés par FAISS + fusion RRF ; reranking Qwen2.5:7b optionnel ; génération Qwen2.5:7b optionnelle.

**Enrichissement GraphRAG** :
1. Exécuter le RAG hybride existant sans génération/reranking pour obtenir sa liste de candidats.
2. Rechercher dans Neo4j les entités `SRAIEntity` portant `verification='LEXICAL_ONLY'` dont les noms apparaissent **en toutes lettres** dans la question. Pas de matching par sous-chaîne.
3. Trouver les chunks reliés à ces entités par `MENTIONS_ENTITY` dans le même projet.
4. Vérifier les `chunk_id` et `document_id` contre le JSONL local des 263 chunks : le contenu original des PDF est l'unique contexte textuel utilisé pour la réponse.
5. Fusionner les deux listes par rangs (RRF), dédupliquer, reranker facultativement avec Qwen, puis générer la réponse et les références si demandé.

**LIMITES** : `MENTIONS_ENTITY` est une mention *lexicalement* étayée, non une relation causale démontrée. Il n'existe actuellement aucune base vérifiée pour inférer que « BGM IMPROVES GTR » à partir du graphe seul. Les relations LLM candidates de la phase V3.3 ne sont pas utilisées. La phase 5B n'avait enrichi que certains chunks (environ 12 chunks candidats V3.3), et **non les 263**. GraphRAG peut donc n'apporter aucun nouveau chunk pour certaines questions. C'est une observation valable, pas un succès artificiel. Le terme « GraphRAG » désigne ici **graph-augmented retrieval fondé sur des mentions**, pas un knowledge graph sémantique validé ou des communautés scientifiques inférées.

Le script lit Neo4j **sans écriture**. Il ne remplace **aucun** module ni fichier de phase antérieure. Le mot de passe Neo4j est demandé de manière invisible et n'est **jamais** enregistré dans le JSON de rapport.

## 2. Installation

Extraire le ZIP **à la racine** du projet `C:\Users\houss\Documents\Scientific-research-ai` pour ajouter :

- `scripts/graphrag_phase6b.py`
- `tests/test_graphrag_phase6b.py`
- `docs/PHASE6B_GRAPHRAG_NEO4J.md`

Les scripts des phases 6A, 6A.1, 6A.2 **doivent déjà être dans `scripts/`** :

- `scripts/rag_classique_phase6.py`
- `scripts/rag_semantique_faiss_phase6a1.py`
- `scripts/rag_hybride_phase6a2.py`

Les bibliothèques `neo4j`, `faiss-cpu`, `numpy` et Ollama sont nécessaires sur la machine. Si besoin :

```powershell
.\.venv\Scripts\python.exe -m pip install neo4j
```

**Ne relancez pas `--build` FAISS : l'index a déjà été construit et vérifié pour 263 vecteurs 768 dimensions.**

## 3. Étapes PowerShell : une par une

### A — Tests sans aucun service externe

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_graphrag_phase6b.py" -v
```

Résultat attendu : `Ran 28 tests ... OK`.

### B — Vérifier les relations réellement présentes dans Neo4j

Ouvrir Docker Desktop, vérifier `srai-neo4j` en cours d'exécution, puis :

```powershell
.\.venv\Scripts\python.exe scripts/graphrag_phase6b.py --check
```

Saisir le mot de passe Neo4j dans le terminal (il ne s'affiche pas). Le résultat dépend des données réellement importées. Il doit indiquer un nombre **strictement positif** d'entités, de chunks enrichis et de liens. Sinon : revisiter `graph_analytics_scientific_phase5b.py --import`.

### C — GraphRAG retrieval seulement : même question que le RAG hybride

```powershell
.\.venv\Scripts\python.exe scripts/graphrag_phase6b.py --question "How does BGM improve retrieval compared with GTR?" --top-k 3 --candidates-k 6
```

Afficher dans la sortie :
- `BASE HYBRIDE` = chunks du RAG hybride avant enrichissement.
- `GRAPH` = nombre d'entités reconnues dans la question, nombre de chunks liés et nombre de passages nouveaux dans le top final.
- `ENTITES` = noms reconnus dans la question.
- Pour chaque passage : le score GraphRAG et la/les entités trouvées par une vraie arête `MENTIONS_ENTITY`.

### D — Tester le reranking et la génération GraphRAG

```powershell
.\.venv\Scripts\python.exe scripts/graphrag_phase6b.py --question "How does BGM improve retrieval compared with GTR?" --top-k 3 --candidates-k 6 --rerank --generate
```

Cette commande utilise Ollama `nomic-embed-text` pour la question puis Qwen2.5:7b pour le reranking et la génération. Le texte de la réponse utilise toujours les extraits PDF sources, **pas** les arêtes du graphe comme affirmations scientifiques.

Le rapport JSON est : `data/reports/graphrag_phase6b_last_query.json`.

### E — Comparer avec le RAG hybride à paramètres comparables

```powershell
.\.venv\Scripts\python.exe scripts/rag_hybride_phase6a2.py --question "How does BGM improve retrieval compared with GTR?" --top-k 3 --candidates-k 6 --rerank --generate
```

Les deux systèmes partagent les mêmes corpus, modèle d'embeddings, BM25, FAISS, RRF, reranker et LLM. GraphRAG a **en plus** la récupération d'entités Neo4j. Comme le reranker Qwen est contextuel, il faut plusieurs questions annotées pour prouver une amélioration, et contrôler fidélité des citations, pertinence et temps de réponse.

## 4. Inspecter le graphe dans Neo4j Browser (http://localhost:7474)

```cypher
MATCH path=(d:SRAIDocument)-[:HAS_CHUNK]->(c:SRAIChunk)-[:MENTIONS_ENTITY]->(e:SRAIEntity)
WHERE e.name IN ['BGM','GTR'] AND e.verification='LEXICAL_ONLY'
RETURN path LIMIT 20;
```

Pour vérifier les comptages de mentions :

```cypher
MATCH (c:SRAIChunk)-[:MENTIONS_ENTITY]->(e:SRAIEntity)
WHERE e.verification='LEXICAL_ONLY'
RETURN e.name AS entite, count(DISTINCT c) AS passages
ORDER BY passages DESC LIMIT 15;
```

## 5. Si l'enrichissement du graphe est nul

Si la commande affiche `FALLBACK: no_entity_in_question`, le graphe ne contient aucune entité dont le nom correspond exactement à une expression de la question. Le système reprend normalement le RAG hybride. Cela n'est **pas** une erreur de connexion ; ne prétendez simplement pas que le graphe a amélioré ce cas.

Si `FALLBACK: no_matching_chunks`, les entités ont été reconnues mais aucun chunk correspondant au corpus local n'a été trouvé (ou le filtrage documentaire les exclut).

Si Neo4j n'est pas connecté ou contient zéro lien `MENTIONS_ENTITY`, le programme s'arrête explicitement : **ne pas présenter un RAG hybride de secours comme du GraphRAG**.

Si `GraphRAG` retourne les mêmes 3 chunks que l'hybride, il a potentiellement influencé leur **rang**, mais pas augmenté la couverture du contexte. Il faudra tester d'autres questions pour quantifier son apport.

## 6. Suite après cette étape

**Phase 7** : interface Streamlit des 3 recherches, Graph Analytics et navigation dans le graphe. **Phase 8** : évaluation factuelle sur jeu de questions annotées, avec comparaison BM25 vs hybride vs GraphRAG, et analyse des coûts, latence et source-grounding.
