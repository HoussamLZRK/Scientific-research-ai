# Correctif Neo4j : `Map keys must be strings, not <class 'NoneType'>`

## Cause

Les CSV exportés par Spark peuvent contenir des textes scientifiques avec des guillemets, des virgules et des retours à la ligne. Spark échappe par défaut les guillemets en utilisant `\`. L'ancien `csv.DictReader` ne configurait pas `escapechar`, et pouvait découper le texte en colonnes supplémentaires, créant une clé Python `None`. Le pilote Neo4j refuse ces clés.

Ce correctif configure `escapechar="\\"`, vérifie la structure de toutes les lignes **avant** la connexion, et conserve le reste de l'import structurel. Il ne modifie ni HDFS, ni Spark, ni les versions LLM.

## Installation

Remplacer uniquement `scripts/import_neo4j_from_spark.py` et `tests/test_neo4j_import.py` par les fichiers de cette archive, en fusionnant les dossiers du ZIP avec la racine du projet.

## Exécution dans PowerShell / VS Code

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_neo4j_import.py" -v
.\.venv\Scripts\python.exe scripts/import_neo4j_from_spark.py --dry-run
.\.venv\Scripts\python.exe scripts/import_neo4j_from_spark.py
```

Le script demande le mot de passe Neo4j localement. Ne pas le transmettre dans une capture ou le chat.

## Après l'import, dans Neo4j Browser

```cypher
MATCH (n)
WHERE n.project = 'scientific-research-ai'
RETURN labels(n) AS labels, count(n) AS nombre
ORDER BY nombre DESC;
```

Attendu : 13 publications, 80 mentions d'auteurs, 4 documents, 263 chunks.

```cypher
MATCH (d:SRAIDocument)-[r:HAS_CHUNK]->(c:SRAIChunk)
RETURN count(r) AS chunk_links;
```

Attendu : 263.

## Sécurité des données

- L'import emploie `MERGE` et des contraintes d'unicité. Une nouvelle exécution reprend les éléments manquants sans dupliquer les nœuds existants.
- Aucune commande de suppression, aucun `DETACH DELETE`, aucun reset de la base.
- Les liens scientifiques LLM ne sont pas importés automatiquement.
- Les quatre documents PDF ne sont pas rattachés artificiellement aux treize notices du crawler.
- Si le dry-run échoue avec `CSV mal decoupe`, conserver l'erreur : le CSV en question devra être examiné avant l'import. Ne pas désactiver le contrôle.

## Validation

11 tests unitaires, dont un test de texte contenant des guillemets échappés, virgules, retour à la ligne, et tests de rejet des colonnes excedentaires/incomplètes. Ce sont des tests locaux : l'exécution dans la base Neo4j de l'utilisateur reste à confirmer.
