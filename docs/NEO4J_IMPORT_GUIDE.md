# Phase 4 - Import structurel Spark -> Neo4j

## But

Importer les **13 publications**, **80 mentions d'auteurs**, **4 documents PDF** et **263 chunks** des sorties de Spark. **Ne pas** créer de lien Publication-Document sans correspondance vérifiée. **Ne pas** importer les relations LLM V3.3 non validées.

### 1. Installation

Copier `scripts/import_neo4j_from_spark.py` et `tests/test_neo4j_import.py` dans les dossiers correspondants du dépôt.

### 2. Vérifier les CSV sans accéder à Neo4j

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_neo4j_import.py" -v
.\.venv\Scripts\python.exe scripts/import_neo4j_from_spark.py --dry-run
```

### 3. Installer le client Neo4j et importer

```powershell
.\.venv\Scripts\python.exe -m pip install neo4j
.\.venv\Scripts\python.exe scripts/import_neo4j_from_spark.py
```

Le script demande le mot de passe en mode masqué. Aucun mot de passe ne figure dans le code, les commandes ou les journaux. Le port Bolt `7687` du conteneur doit être exposé sur `localhost`.

### 4. Explorer avec Neo4j Browser

```cypher
MATCH (n) WHERE n.project = 'scientific-research-ai'
RETURN labels(n) AS labels, count(*) AS nombre ORDER BY nombre DESC;
```

```cypher
MATCH (d:SRAIDocument)-[:HAS_CHUNK]->(c:SRAIChunk)
RETURN d.document_id AS document, count(c) AS chunks ORDER BY chunks DESC;
```

```cypher
MATCH (p:SRAIPublication)-[:HAS_AUTHOR_MENTION]->(a:SRAIAuthorMention)
RETURN p.title AS publication, collect(a.name)[0..5] AS auteurs LIMIT 5;
```

### Notes de qualité

- `SRAIAuthorMention` modélise une mention d'auteur, **pas** une personne désambiguïsée.
- Les documents PDF sont distincts des notices du crawler jusqu'à preuve d'un rapprochement fiable (DOI ou autre identifiant confirmé).
- Les relations LLM ne sont jamais importées automatiquement.
- Le script est **idempotent** : relancer n'ajoute pas de doublons grâce à `MERGE` et aux contraintes d'unicité.
- Le script ne supprime aucun nœud existant et ne modifie pas HDFS.
