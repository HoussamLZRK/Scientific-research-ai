# Phase 5B — Graph Analytics des mentions scientifiques (prototype exploratoire)

## Finalité et limites
Les 360 nœuds et 343 relations issus de Spark restent inchangés.
Cette étape ajoute des **mentions lexicales** extraites par Qwen2.5:7b (V3.3, expanded), associées à leurs chunks.
Les `SRAIEntity` / `SRAIEntityMention` ont `verification='LEXICAL_ONLY'`.
**Aucun lien causal `IMPROVES` / `USES` / `EVALUATED_ON` n'est importé**. Une cooccurrence dans un même chunk n'est **pas** une relation scientifique démontrée. Les classes d'entités du LLM ne sont pas encore validées par une personne.

## Installation
Copier `scripts/`, `tests/`, `docs/` dans `Scientific-research-ai` sans remplacer les anciens scripts.
Le paquet Python `neo4j` a déjà été installé pendant la phase 4.

## Exécution PowerShell
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_graph_analytics_scientific_phase5b.py" -v
.\.venv\Scripts\python.exe scripts/graph_analytics_scientific_phase5b.py --dry-run
.\.venv\Scripts\python.exe scripts/graph_analytics_scientific_phase5b.py --import
Get-Content data\reports\graph_analytics_scientific_phase5b.json
```
`--dry-run` ne se connecte pas à Neo4j. `--import` contrôle les chunks existants et ajoute les mentions de façon idempotente. Pour analyser à nouveau sans écrire :
```powershell
.\.venv\Scripts\python.exe scripts/graph_analytics_scientific_phase5b.py --analyze
```

## Neo4j Browser : visualisations avec lignes
Exécuter **une seule requête à la fois**, onglet **Graph** :

```cypher
MATCH path=(d:SRAIDocument)-[:HAS_CHUNK]->(c:SRAIChunk)-[:MENTIONS_ENTITY]->(e:SRAIEntity)
WHERE d.document_id='acl_2024_rag_retrievers'
RETURN path LIMIT 12;
```

Classement du nombre de chunks contenant une entité (et non importance scientifique) :
```cypher
MATCH (e:SRAIEntity)<-[:MENTIONS_ENTITY]-(c:SRAIChunk)
RETURN e.name AS entity, e.kind AS type, count(DISTINCT c) AS chunks
ORDER BY chunks DESC LIMIT 15;
```

Cooccurrence (les deux entités sont citées dans au moins un même chunk) :
```cypher
MATCH (a:SRAIEntity)<-[:MENTIONS_ENTITY]-(c:SRAIChunk)-[:MENTIONS_ENTITY]->(b:SRAIEntity)
WHERE a.entity_key < b.entity_key
RETURN a.name AS entite_a, b.name AS entite_b, count(DISTINCT c) AS passages_communs
ORDER BY passages_communs DESC LIMIT 15;
```

## Fichiers produits
- `data/reports/graph_analytics_scientific_phase5b.json`
- `data/reports/graph_analytics_scientific_entities.csv`

Les chiffres attendus ne sont pas fixés artificiellement : ils dépendent du contenu réel de V3.3.
Ne pas mélanger les métriques des 12 chunks sélectionnés par le LLM avec celles de tous les 263 chunks.
