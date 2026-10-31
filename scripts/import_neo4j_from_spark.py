"""Import idempotent de donnees Spark verifiees dans Neo4j.

Aucune correspondance Publication <-> Document PDF n'est supposee.
Aucune relation scientifique LLM n'est importee sans validation humaine.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import json
from pathlib import Path

PROJECT = "scientific-research-ai"
EXPECTED = {
    "publications.csv": ("canonical_id", "title", "year", "doi", "abstract", "pdf_url"),
    "publication_authors.csv": ("author_occurrence_id", "canonical_id", "author_order", "author_name"),
    "chunks.csv": ("chunk_id", "document_id", "page_number", "text"),
}


def read_csv(path: Path, columns: tuple[str, ...]):
    """Lire correctement le CSV emis par Spark (guillemets echappes par antislash).

    Interdire les colonnes excedentaires qui deviennent une cle None dans
    csv.DictReader : le pilote Neo4j ne peut pas encoder cette cle.
    """
    if not path.is_file():
        raise ValueError(f"Fichier CSV manquant: {path}")
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            # Spark CSV utilise normalement un antislash pour echapper les guillemets.
            reader = csv.DictReader(handle, escapechar="\\", strict=True)
            fields = reader.fieldnames
            if not fields or not set(columns).issubset(fields):
                raise ValueError(f"Colonnes incorrectes dans {path.name}: {fields}; requis {columns}")
            if len(fields) != len(set(fields)) or any(not f for f in fields):
                raise ValueError(f"En-tetes CSV invalides ou dupliques: {path.name}")
            rows = []
            for row in reader:
                if None in row:
                    raise ValueError(
                        f"CSV mal decoupe ({path.name}, ligne physique {reader.line_num}) : "
                        "champs excedentaires; verifiez le quoting Spark"
                    )
                if any(value is None for value in row.values()):
                    raise ValueError(
                        f"CSV incomplet ({path.name}, ligne physique {reader.line_num})"
                    )
                rows.append(row)
    except csv.Error as exc:
        raise ValueError(f"CSV illisible ou quoting invalide dans {path.name}: {exc}") from exc
    if not rows:
        raise ValueError(f"CSV vide: {path.name}")
    return rows


def validated_tables(directory: Path, report_path: Path):
    if not report_path.is_file():
        raise ValueError(f"Rapport Spark manquant: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    if report.get("status") != "OK":
        raise ValueError("Rapport Spark non valide (status != OK)")
    data = {name: read_csv(directory / name, columns) for name, columns in EXPECTED.items()}
    pubs, authors, chunks = (data[name] for name in EXPECTED)
    pids = [p["canonical_id"].strip() for p in pubs]
    mids = [a["author_occurrence_id"].strip() for a in authors]
    cids = [c["chunk_id"].strip() for c in chunks]
    if any(not p["title"].strip() for p in pubs):
        raise ValueError("Publication(s) sans titre")
    for label, values in (("canonical_id", pids), ("author_occurrence_id", mids), ("chunk_id", cids)):
        if any(not v for v in values) or len(set(values)) != len(values):
            raise ValueError(f"Identifiants vides ou dupliques: {label}")
    if any(a["canonical_id"] not in set(pids) or not a["author_name"].strip() for a in authors):
        raise ValueError("Auteur orphelin ou sans nom")
    if any(not c["document_id"].strip() or not c["text"].strip() for c in chunks):
        raise ValueError("Chunk sans document ou texte")
    for row in chunks:
        try:
            if int(row["page_number"]) <= 0:
                raise ValueError()
        except ValueError:
            raise ValueError(f"Numero de page non valide: {row['chunk_id']}") from None
    reported_pubs = report.get("publications", {}).get("output_rows")
    reported_chunks = report.get("chunks", {}).get("output_rows")
    reported_authors = report.get("outputs", {}).get("publication_author_mentions")
    if (len(pubs), len(chunks), len(authors)) != (reported_pubs, reported_chunks, reported_authors):
        raise ValueError("Les volumes CSV ne correspondent pas au rapport de qualite Spark")
    return data


def chunks_of(rows, size=100):
    for offset in range(0, len(rows), size):
        yield rows[offset:offset + size]


def run_import(driver, tables):
    stmts = [
        "CREATE CONSTRAINT srai_publication_id IF NOT EXISTS FOR (p:SRAIPublication) REQUIRE p.canonical_id IS UNIQUE",
        "CREATE CONSTRAINT srai_author_occurrence_id IF NOT EXISTS FOR (a:SRAIAuthorMention) REQUIRE a.author_occurrence_id IS UNIQUE",
        "CREATE CONSTRAINT srai_document_id IF NOT EXISTS FOR (d:SRAIDocument) REQUIRE d.document_id IS UNIQUE",
        "CREATE CONSTRAINT srai_chunk_id IF NOT EXISTS FOR (c:SRAIChunk) REQUIRE c.chunk_id IS UNIQUE",
    ]
    with driver.session() as s:
        for query in stmts:
            s.run(query).consume()
        for rows in chunks_of(tables["publications.csv"]):
            s.run("""
              UNWIND $rows AS r
              MERGE (p:SRAIPublication {canonical_id:r.canonical_id})
              SET p.project=$project, p.title=r.title, p.year=CASE WHEN trim(r.year)='' THEN null ELSE toInteger(r.year) END,
                  p.doi=r.doi, p.abstract=r.abstract, p.pdf_url=r.pdf_url
            """, rows=rows, project=PROJECT).consume()
        for rows in chunks_of(tables["publication_authors.csv"]):
            s.run("""
              UNWIND $rows AS r
              MATCH (p:SRAIPublication {canonical_id:r.canonical_id})
              MERGE (a:SRAIAuthorMention {author_occurrence_id:r.author_occurrence_id})
              SET a.project=$project, a.name=r.author_name, a.author_order=toInteger(r.author_order)
              MERGE (p)-[:HAS_AUTHOR_MENTION]->(a)
            """, rows=rows, project=PROJECT).consume()
        docs = sorted({c["document_id"] for c in tables["chunks.csv"]})
        s.run("""
          UNWIND $documents AS id
          MERGE (d:SRAIDocument {document_id:id})
          SET d.project=$project
        """, documents=docs, project=PROJECT).consume()
        for rows in chunks_of(tables["chunks.csv"]):
            s.run("""
              UNWIND $rows AS r
              MATCH (d:SRAIDocument {document_id:r.document_id})
              MERGE (c:SRAIChunk {chunk_id:r.chunk_id})
              SET c.project=$project, c.document_id=r.document_id,
                  c.page_number=toInteger(r.page_number), c.text=r.text
              MERGE (d)-[:HAS_CHUNK]->(c)
            """, rows=rows, project=PROJECT).consume()
        counts = s.run("""
            MATCH (p:SRAIPublication {project:$project}) WITH count(p) AS publications
            MATCH (a:SRAIAuthorMention {project:$project}) WITH publications,count(a) AS mentions
            MATCH (d:SRAIDocument {project:$project}) WITH publications,mentions,count(d) AS documents
            MATCH (c:SRAIChunk {project:$project})
            RETURN publications,mentions,documents,count(c) AS chunks
        """, project=PROJECT).single().data()
        counts["author_links"] = s.run("MATCH (:SRAIPublication)-[r:HAS_AUTHOR_MENTION]->(:SRAIAuthorMention) RETURN count(r) AS n").single()["n"]
        counts["chunk_links"] = s.run("MATCH (:SRAIDocument)-[r:HAS_CHUNK]->(:SRAIChunk) RETURN count(r) AS n").single()["n"]
    return counts


def main():
    parser = argparse.ArgumentParser(description="Spark CSV -> Neo4j (sans liens inventes)")
    parser.add_argument("--csv-dir", default="data/processed/spark")
    parser.add_argument("--spark-report", default="data/reports/spark_etl_quality_report.json")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    tables = validated_tables(Path(args.csv_dir), Path(args.spark_report))
    expected = {"publications":len(tables["publications.csv"]),
                "mentions":len(tables["publication_authors.csv"]),
                "documents":len({r["document_id"] for r in tables["chunks.csv"]}),
                "chunks":len(tables["chunks.csv"])}
    print("Validation CSV/Spark OK:", json.dumps(expected, ensure_ascii=False))
    if args.dry_run:
        print("DRY RUN OK: aucune connexion Neo4j, aucune ecriture.")
        return
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise SystemExit("Installer le client : .\\.venv\\Scripts\\python.exe -m pip install neo4j")
    password = getpass.getpass("Mot de passe Neo4j (invisible) : ")
    with GraphDatabase.driver(args.uri, auth=(args.user, password)) as driver:
        driver.verify_connectivity()
        counts = run_import(driver, tables)
    print("NEO4J IMPORT:", json.dumps(counts, ensure_ascii=False))
    for key,value in expected.items():
        if counts.get(key) != value:
            raise SystemExit(f"ANOMALIE nombre {key}: attendu {value}, obtenu {counts.get(key)}")
    if counts["author_links"] != expected["mentions"] or counts["chunk_links"] != expected["chunks"]:
        raise SystemExit("ANOMALIE: relations structurelles manquantes")
    print("NEO4J IMPORT OK : import structurel confirme; relations LLM non importees.")


if __name__ == "__main__":
    main()
