# Scientific Research AI : Phase 5, Graph Analytics (structurelles)

## Objectif
Analyser le graphe Neo4j issu de Spark **avant** l'enrichissement LLM. Ne pas lancer le ZIP MVP complet. Ce module est indépendant de Streamlit, de GraphRAG et d'Ollama.

## Installation
Extraire le ZIP dans le dépôt et fusionner seulement les dossiers `scripts`, `tests`, `docs`. Ne remplacer aucun ancien script.

## Étapes Windows PowerShell

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_graph_analytics_phase5.py" -v
.\.venv\Scripts\python.exe -m pip show neo4j
.\.venv\Scripts\python.exe scripts/graph_analytics_phase5.py
Get-Content data\reports\graph_analytics_report.json
Import-Csv data\reports\graph_analytics_publications.csv | Select-Object -First 5 | Format-Table
```

Le script demande le mot de passe Neo4j (non affiché) et effectue **uniquement des requêtes de lecture**. Résultats : `graph_analytics_report.json`, `graph_analytics_publications.csv`, `graph_analytics_documents.csv` dans `data/reports/`.

## Vérifications Neo4j Browser

```cypher
MATCH (n) WHERE n.project='scientific-research-ai'
RETURN labels(n) AS type_noeud, count(*) AS nombre ORDER BY nombre DESC;
```

```cypher
MATCH (d:SRAIDocument)-[:HAS_CHUNK]->(c:SRAIChunk)
RETURN d.document_id AS document, count(c) AS chunks ORDER BY chunks DESC;
```

```cypher
MATCH (p:SRAIPublication)-[:HAS_AUTHOR_MENTION]->(a:SRAIAuthorMention)
RETURN p.title AS publication, count(a) AS mentions_auteurs ORDER BY mentions_auteurs DESC LIMIT 10;
```

```cypher
MATCH (d:SRAIDocument)-[:HAS_CHUNK]->(c:SRAIChunk)
RETURN d,c LIMIT 20;
```

## Interprétation scientifique
Ce graphe est une **structure de provenance** avec deux familles de relations, pas encore un réseau de collaborations ni un graphe d'influence scientifique. Les auteurs sont des **mentions** propres à une publication, sans résolution d'identité. PageRank sur les étoiles de provenance serait trompeur et n'est donc pas présenté ici comme influence. Les composantes reflètent les groupes publication/mentions et document/chunks. Les PDF ne sont pas liés artificiellement aux notices du crawler.

Après validation de ces résultats, étape suivante : ajouter des entités scientifiques contrôlées, puis les algorithmes Graph Analytics thématiques pertinents, avant GraphRAG, l'interface et l'évaluation comparative.
