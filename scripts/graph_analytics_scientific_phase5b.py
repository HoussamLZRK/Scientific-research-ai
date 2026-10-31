"""Phase 5B: enrichissement lexical prudent et Graph Analytics exploratoire.

Aucune relation scientifique candidate n'est importee comme fait.
Les mentions sont des sorties LLM lexicalement ancrees, NON validees scientifiquement.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import re
import unicodedata

PROJECT = "scientific-research-ai"
SOURCE = Path("data/processed/llm/knowledge_preview_v33_qwen2_5_7b_expanded.jsonl")
REPORT = Path("data/reports/graph_analytics_scientific_phase5b.json")
CSV_OUT = Path("data/reports/graph_analytics_scientific_entities.csv")
TYPES = {"MODEL", "METHOD", "DATASET", "TASK", "CONCEPT", "METRIC"}


def normalize(name: str) -> str:
    value = unicodedata.normalize("NFKC", name)
    value = re.sub(r"(?<=[^\W\d_])-\s+(?=[^\W\d_])", "", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip().casefold()


def build_records(rows):
    """Pure transformation with strict ID/provenance and lexical safeguards."""
    entities, mentions, chunks = {}, [], set()
    for row in rows:
        if row.get("status") != "ok":
            continue
        chunk = str(row.get("chunk_id") or "").strip()
        document = str(row.get("document_id") or "").strip()
        if not chunk or not document or chunk in chunks:
            raise ValueError("Chunk/document vide ou chunk duplique")
        chunks.add(chunk)
        used_ids = set()
        for e in row.get("entities", []):
            name, kind = str(e.get("name") or "").strip(), str(e.get("type") or "").strip()
            evidence, eid = str(e.get("evidence") or ""), str(e.get("id") or "").strip()
            if not name or kind not in TYPES or not eid or eid in used_ids or not evidence:
                raise ValueError("Entite ou preuve non conforme dans " + chunk)
            if not re.search(r"(?<!\w)" + re.escape(normalize(name)) + r"(?!\w)", normalize(evidence)):
                raise ValueError("Nom absent de sa preuve : " + name)
            used_ids.add(eid)
            key = kind + "|" + normalize(name)
            entities.setdefault(key, {"entity_key": key, "name": name, "kind": kind})
            mentions.append({
                "mention_id": chunk + "|" + eid,
                "chunk_id": chunk, "document_id": document,
                "entity_key": key, "kind": kind, "name": name,
                "model": row.get("model") or "qwen2.5:7b",
                "evidence": evidence[:1200],
            })
    if not mentions:
        raise ValueError("Aucune mention d'entite disponible")
    return list(entities.values()), mentions


def load_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def measure(entities, mentions):
    """Graph Analytics on chunk-entity incidence and co-mentions, not causal claims."""
    ref = {e["entity_key"]: e for e in entities}
    by_chunk, by_entity, by_document = defaultdict(set), defaultdict(set), defaultdict(set)
    docs_by_entity = defaultdict(set)
    for m in mentions:
        c, e = m["chunk_id"], m["entity_key"]
        if e not in ref:
            raise ValueError("Mention orpheline")
        by_chunk[c].add(e)
        by_entity[e].add(c)
        docs_by_entity[e].add(m["document_id"])
        by_document[m["document_id"]].add(c)
    pairs = Counter()
    for es in by_chunk.values():
        ss = sorted(es)
        for i, a in enumerate(ss):
            for b in ss[i+1:]:
                pairs[(a, b)] += 1
    # Connected components in bipartite chunk-entity graph.
    graph = defaultdict(set)
    for c, es in by_chunk.items():
        for e in es:
            a, b = "C:" + c, "E:" + e
            graph[a].add(b); graph[b].add(a)
    unseen = set(graph); components = []
    while unseen:
        seed = unseen.pop(); seen = {seed}; stack = [seed]
        while stack:
            cur = stack.pop()
            for next_node in graph[cur] - seen:
                seen.add(next_node); unseen.discard(next_node); stack.append(next_node)
        components.append(len(seen))
    ranking = sorted([
        {"entity_key": k, "entity": ref[k]["name"], "type": ref[k]["kind"],
         "chunks_mentioning": len(cs), "documents_mentioning": len(docs_by_entity[k])}
        for k, cs in by_entity.items()
    ], key=lambda r: (-r["chunks_mentioning"],-r["documents_mentioning"],r["entity_key"]))
    co = sorted([{
        "entity_a": ref[a]["name"], "type_a": ref[a]["kind"],
        "entity_b": ref[b]["name"], "type_b": ref[b]["kind"], "shared_chunks": n
    } for (a,b),n in pairs.items()], key=lambda r:(-r["shared_chunks"],r["entity_a"],r["entity_b"]))
    summary = {
        "input_chunks_with_entities": len(by_chunk), "documents": len(by_document),
        "unique_entities": len(entities), "entity_mentions": len(mentions),
        "chunk_entity_links": sum(map(len, by_chunk.values())),
        "co_mention_pairs": len(pairs), "connected_components": len(components),
        "largest_component_nodes": max(components,default=0),
        "scope": "exploratory_lexical_mentions_not_scientific_facts",
        "warning": "LLM types and names are not human-verified. Co-mention is not a semantic relationship."
    }
    return {"summary": summary, "entity_ranking": ranking, "co_mentions": co[:100]}


def neo4j_import(driver, entities, mentions):
    with driver.session() as s:
        real = {r["id"] for r in s.run(
            "MATCH (c:SRAIChunk {project:$p}) WHERE c.chunk_id IN $ids RETURN c.chunk_id AS id",
            p=PROJECT, ids=sorted({m["chunk_id"] for m in mentions}))}
        missing = sorted({m["chunk_id"] for m in mentions} - real)
        if missing:
            raise ValueError("Chunks absents de Neo4j : " + ", ".join(missing[:5]))
        s.run("CREATE CONSTRAINT srai_entity_key IF NOT EXISTS FOR (e:SRAIEntity) REQUIRE e.entity_key IS UNIQUE").consume()
        s.run("CREATE CONSTRAINT srai_mention_key IF NOT EXISTS FOR (m:SRAIEntityMention) REQUIRE m.mention_id IS UNIQUE").consume()
        s.run("""UNWIND $rows AS r
            MERGE (e:SRAIEntity {entity_key:r.entity_key})
            SET e.name=r.name,e.kind=r.kind,e.project=$p,e.verification='LEXICAL_ONLY'""",
            rows=entities,p=PROJECT).consume()
        for offset in range(0,len(mentions),75):
            s.run("""UNWIND $rows AS r
                MATCH (c:SRAIChunk {chunk_id:r.chunk_id,project:$p})
                MATCH (e:SRAIEntity {entity_key:r.entity_key})
                MERGE (m:SRAIEntityMention {mention_id:r.mention_id})
                SET m.name=r.name,m.kind=r.kind,m.evidence=r.evidence,
                    m.model=r.model,m.project=$p,m.verification='LEXICAL_ONLY'
                MERGE (c)-[:HAS_ENTITY_MENTION]->(m)
                MERGE (m)-[:REFERS_TO]->(e)
                MERGE (c)-[:MENTIONS_ENTITY]->(e)""",
                rows=mentions[offset:offset+75],p=PROJECT).consume()
    return len(entities),len(mentions)


def analyze_neo4j(driver):
    with driver.session() as s:
        ents = [dict(r) for r in s.run("""MATCH (e:SRAIEntity {project:$p})
            RETURN e.entity_key AS entity_key,e.name AS name,e.kind AS kind""",p=PROJECT)]
        refs = [dict(r) for r in s.run("""MATCH (c:SRAIChunk {project:$p})-[:HAS_ENTITY_MENTION]->(m:SRAIEntityMention {project:$p})-[:REFERS_TO]->(e:SRAIEntity {project:$p})
            RETURN m.mention_id AS mention_id,c.chunk_id AS chunk_id,c.document_id AS document_id,
              e.entity_key AS entity_key, m.kind AS kind, m.name AS name""",p=PROJECT)]
    if not refs: raise ValueError("Aucune mention dans Neo4j : executer --import d'abord")
    return measure(ents,refs)


def write_report(result):
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    payload={"generated_at_utc": datetime.now(timezone.utc).isoformat(),**result}
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with CSV_OUT.open("w",encoding="utf-8-sig",newline="") as f:
        fields=["entity_key","entity","type","chunks_mentioning","documents_mentioning"]
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(result["entity_ranking"])


def main(argv=None):
    p=argparse.ArgumentParser(description="Graph Analytics scientifiques exploratoires, phase 5B")
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run",action="store_true")
    modes.add_argument("--import",dest="do_import",action="store_true")
    modes.add_argument("--analyze",action="store_true")
    p.add_argument("--input",type=Path,default=SOURCE)
    p.add_argument("--uri",default="bolt://127.0.0.1:7687")
    args=p.parse_args(argv)
    if args.dry_run or args.do_import:
        entities,mentions=build_records(load_jsonl(args.input))
        result=measure(entities,mentions)
        print("VALIDATION LOCALE:",json.dumps(result["summary"],ensure_ascii=False,indent=2))
        if args.dry_run:
            print("DRY RUN OK: aucune connexion ni ecriture Neo4j")
            return 0
    from neo4j import GraphDatabase
    pwd=getpass.getpass("Mot de passe Neo4j (invisible): ")
    with GraphDatabase.driver(args.uri,auth=("neo4j",pwd)) as driver:
        driver.verify_connectivity()
        if args.do_import:
            n,m=neo4j_import(driver,entities,mentions)
            print(f"IMPORT OK: {n} entites distinctes, {m} mentions LLM (NON validees)")
        result=analyze_neo4j(driver)
    write_report(result)
    print("GRAPH ANALYTICS SCIENTIFIQUE:",json.dumps(result["summary"],ensure_ascii=False,indent=2))
    print("RAPPORT:", REPORT)
    print("CSV:",CSV_OUT)
    print("Les relations LLM candidates ne sont PAS importees comme faits.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
