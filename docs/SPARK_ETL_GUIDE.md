# Étape 3 : Apache Spark ETL (Scientific Research AI)

## Objectif
Lire avec **Spark** les métadonnées des publications depuis **HDFS**, nettoyer et dédoublonner les données, vérifier les IDs/DOI, puis produire **Parquet sur HDFS**, **CSV locaux pour Neo4j** et un **rapport de qualité**.

Les **263 chunks PDF** sont lus depuis le JSONL local de l'étape précédente, normalisés puis enregistrés aussi en Parquet HDFS. Ils n'ont **pas** encore été traités par le LLM en masse.

## Compatibilité et sécurité
- Compatible avec les fichiers de la phase HDFS précédente : `docker/hdfs/compose.yaml`, `docker/hdfs/config/*.xml`.
- Extension `docker/hdfs/compose.spark.yaml` : n'altère pas le YAML HDFS original et ne supprime aucun volume Docker.
- Image `apache/spark:3.5.7-python3` ; Spark démarre ponctuellement en mode `local[2]` dans un conteneur. Ce n'est **pas** un cluster Spark multinoeuds.
- Hadoop est joint via `hdfs://namenode:8020` sur le réseau Docker Compose existant.
- Le job n'écrase que ses propres sorties dérivées : `/scientific-research-ai/curated/spark_etl_v1/*` et `data/processed/spark/*`. Les fichiers sources HDFS et les versions du LLM sont conservés.
- Les auteurs sont représentés par mentions dans chaque publication. Aucun rapprochement d'identités personnelles n'est présumé.

## Prérequis
1. Docker Desktop fonctionne.
2. Les conteneurs HDFS `namenode` et `datanode` existent / sont démarrables.
3. Le fichier local `data/processed/chunks/pdf_chunks.jsonl` existe.
4. HDFS contient `/scientific-research-ai/processed/publications_multisource_v3.jsonl`.

## Depuis PowerShell, à la racine du dépôt

**1. Tester les règles pures (ne lance pas Spark)**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_spark_etl_utils.py" -v
```

**2. Vérifier les sources**

```powershell
Test-Path data\processed\chunks\pdf_chunks.jsonl
docker compose -f docker/hdfs/compose.yaml ps
docker compose -f docker/hdfs/compose.yaml exec -T namenode hdfs dfs -ls /scientific-research-ai/processed/publications_multisource_v3.jsonl
```

**3. Vérifier la configuration du service Spark**

```powershell
docker compose -f docker/hdfs/compose.yaml -f docker/hdfs/compose.spark.yaml config --quiet
```

**4. Exécuter Spark ETL (premier lancement : télécharge une image)**

```powershell
docker compose -f docker/hdfs/compose.yaml -f docker/hdfs/compose.spark.yaml run --rm spark-etl
```

L'indicateur de succès doit être explicitement `SPARK ETL OK`, sans erreur Docker/PySpark. Exécuter les tests unitaires ne prouve pas que ce job réel ait fonctionné.

**5. Examiner le rapport et HDFS**

```powershell
Get-Content data\reports\spark_etl_quality_report.json
docker compose -f docker/hdfs/compose.yaml exec -T namenode hdfs dfs -ls -R /scientific-research-ai/curated/spark_etl_v1
Get-ChildItem data\processed\spark
```

## Structure des sorties

```text
data/reports/spark_etl_quality_report.json

data/processed/spark/
  publications.csv                  # prêt pour Neo4j (métadonnées)
  publication_authors.csv           # lien entre publication et mention d'auteur
  chunks.csv                        # passages avec provenance
  publications_csv/part-*.csv       # dossier natif Spark
  publication_authors_csv/part-*.csv
  chunks_csv/part-*.csv

HDFS /scientific-research-ai/curated/spark_etl_v1/
  publications_parquet/part-*.parquet
  chunks_parquet/part-*.parquet
```

### À lire dans le rapport
- `input_rows` : nombre de lignes d'entrée (pas nombre d'articles de toute la littérature).
- `invalid_rows` : valeurs rejetées pour titre/auteur/identifiant manquant ; chunks sans texte/ID/page.
- `duplicates_removed` : doublons par ID explicite seulement.
- `doi_conflict_rows` : publications conservées hors du jeu final en cas de conflit d'identifiants et DOI.
- `output_rows` : lignes après traitement, à vérifier avec Parquet.

## Explication à l'oral
> Scrapy récupère les métadonnées ; HDFS les conserve ; Spark les lit, vérifie leur qualité, élimine les doublons sûrs et produit des tables Parquet ; Neo4j pourra ensuite importer les publications et leurs passages. L'extraction de relations scientifiques par le LLM est indépendante et nécessite une validation humaine.

## Dépannage
- `pull access denied` ou `manifest unknown` : vérifier l'image Docker, utiliser le tag référencé dans `compose.spark.yaml`.
- `Connection refused namenode:8020` : vérifier les conteneurs HDFS et leur même projet Compose ; ne pas mettre `localhost` depuis le conteneur Spark.
- `Input ... not found` : contrôler le fichier HDFS via `hdfs dfs -ls` et l'existence locale des chunks.
- `Permission denied` sur `data/processed/spark` : vérifier que Docker Desktop peut écrire dans le dossier projet.
- `NameError`, `AnalysisException` ou échec du job : copier la sortie complète, et **ne pas déclarer ETL terminé** avant de relancer et de vérifier les Parquet.
- `CSV` de sortie en plusieurs fichiers : les dossiers Spark `part-*.csv` sont normaux ; le script copie aussi chaque fichier unique vers un nom fixe.

## Limites méthodologiques
- `local[2]` démontre un vrai traitement Spark mais **pas** un cluster Spark distribué.
- Le pipeline traite uniquement les publications disponibles et les chunks de quatre PDFs, sans augmenter artificiellement le volume des données.
- Une publication n'est pas fusionnée à une autre sur le seul titre ; DOI/identifiant canonique servent de clés.
- Les candidats LLM V3.3 ne sont pas importés ici ; leur validation sémantique est un travail séparé.
