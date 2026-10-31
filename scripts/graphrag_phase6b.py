"""Phase 6B: Graph-augmented RAG (Neo4j lexical mentions + BM25/FAISS/RRF).

READ ONLY in Neo4j. No scientifically unverified predicate is used as a fact.
Dependency: the original phase 6A, 6A.1, and 6A.2 scripts remain unchanged.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
from typing import Any

import rag_hybride_phase6a2 as hybrid

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'data' / 'reports' / 'graphrag_phase6b_last_query.json'
PROJECT = 'scientific-research-ai'
# The graph only contains lexical entity mentions produced by an exploratory LLM pass.
SCOPE = 'LEXICAL_ONLY'


def normalize(text: str) -> str:
    # Compatibility with 5B's normalization for split PDF words.
    value = unicodedata.normalize('NFKC', text or '')
    value = re.sub(r'(?<=[^\W\d_])-\s+(?=[^\W\d_])', '', value, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', value).strip().casefold()


def exact_entity_in_question(name: str, question: str) -> bool:
    """Avoid substring matching: 'GTR' must not match e.g. 'GTRX'."""
    needle = normalize(name)
    haystack = normalize(question)
    return bool(needle and re.search(r'(?<!\w)' + re.escape(needle) + r'(?!\w)', haystack))


def verified_entity_query(entities: list[dict[str, Any]], question: str) -> list[dict[str, Any]]:
    """Name match is lexical evidence only, NOT entity scientific validation."""
    selected = {}
    for item in entities:
        if (item.get('verification') != SCOPE or
            not isinstance(item.get('entity_key'), str) or not item['entity_key'] or
            not isinstance(item.get('name'), str) or not item['name'].strip()):
            continue
        if exact_entity_in_question(item['name'], question):
            selected[item['entity_key']] = dict(item)
    return [selected[k] for k in sorted(selected)]


def neo4j_driver(uri: str, password: str, user: str = 'neo4j'):
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError('Module neo4j manquant : .\\.venv\\Scripts\\python.exe -m pip install neo4j') from exc
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=10)
    try:
        driver.verify_connectivity()
    except Exception:
        driver.close()
        raise
    return driver


def graph_stats(driver) -> dict[str, int]:
    """Check actual graph state; refuses to treat missing Phase 5B as a GraphRAG run."""
    with driver.session() as s:
        row = s.run('''
            OPTIONAL MATCH (e:SRAIEntity {project:$project, verification:$scope})
            WITH count(e) AS entity_count
            OPTIONAL MATCH (c:SRAIChunk {project:$project})-[r:MENTIONS_ENTITY]->
                (e2:SRAIEntity {project:$project, verification:$scope})
            RETURN entity_count, count(DISTINCT c) AS enriched_chunks,
                   count(r) AS chunk_entity_links
        ''', project=PROJECT, scope=SCOPE).single()
    if row is None:
        raise RuntimeError('Impossible de lire le graphe Neo4j')
    counts = {k: int(row[k]) for k in ('entity_count', 'enriched_chunks', 'chunk_entity_links')}
    if not all(counts.values()):
        raise RuntimeError('Graphe 5B non enrichi (entités / MENTIONS_ENTITY manquants). Exécuter la phase 5B --import avant GraphRAG.')
    return counts


def load_graph_matches(driver, question: str, allowed_chunks: dict[str, dict[str, Any]],
                       document_id: str | None = None,
                       max_links: int = 3000) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Read only; query->exact entity name->chunks that mention it; local corpus remains authority.

    Returns entities matched in question, ranked graph candidate chunks, stale/out-of-corpus links skipped.
    """
    with driver.session() as s:
        entities = [dict(r) for r in s.run('''
            MATCH (e:SRAIEntity {project:$project, verification:$scope})
            RETURN e.entity_key AS entity_key, e.name AS name, e.kind AS kind,
                   e.verification AS verification
            ORDER BY e.entity_key
        ''', project=PROJECT, scope=SCOPE)]
    matches = verified_entity_query(entities, question)
    if not matches:
        return [], [], 0
    keys = [e['entity_key'] for e in matches]
    with driver.session() as s:
        # Read only; all Cypher inputs use typed parameters, never interpolated user text.
        links = [dict(r) for r in s.run('''
            MATCH (c:SRAIChunk {project:$project})-[:MENTIONS_ENTITY]->
                  (e:SRAIEntity {project:$project, verification:$scope})
            WHERE e.entity_key IN $keys
            RETURN c.chunk_id AS chunk_id, c.document_id AS document_id,
                   e.entity_key AS entity_key
            ORDER BY c.chunk_id, e.entity_key
            LIMIT $link_limit
        ''', project=PROJECT, scope=SCOPE, keys=keys, link_limit=max_links+1)]
    if len(links) > max_links:
        raise RuntimeError('Trop de liens Neo4j; refuser des résultats tronqués (limite de sûreté).')
    mentions: dict[str, set[str]] = {}
    skipped = 0
    keys_set = set(keys)
    for r in links:
        cid = r.get('chunk_id')
        row = allowed_chunks.get(cid)
        if (row is None or r.get('document_id') != row.get('document_id') or
            (document_id and row.get('document_id') != document_id) or
            r.get('entity_key') not in keys_set):
            skipped += 1
            continue
        mentions.setdefault(cid, set()).add(r['entity_key'])
    graph_hits=[]
    name_by_key = {e['entity_key']:e['name'] for e in matches}
    for cid, keys_here in mentions.items():
        graph_hits.append({**allowed_chunks[cid],
                           'graph_entity_keys':sorted(keys_here),
                           'graph_entity_names':[name_by_key[k] for k in sorted(keys_here)],
                           'graph_mention_count':len(keys_here)})
    graph_hits.sort(key=lambda r:(-r['graph_mention_count'],r['chunk_id']))
    return matches, graph_hits, skipped


def graph_rrf(base: list[dict[str, Any]], graph_hits: list[dict[str, Any]],
              limit: int = 16, k: int = 60) -> list[dict[str, Any]]:
    """RRF over hybrid rank and graph rank, never BM25/cosine raw scores.

    If graph hits are empty, return baseline rankings EXACTLY as-is (no fake graph gain).
    """
    if not 1 <= limit <= 16 or k < 1:
        raise ValueError('limit doit être dans [1,16], k>=1')
    if len({r['chunk_id'] for r in base}) != len(base) or len({r['chunk_id'] for r in graph_hits}) != len(graph_hits):
        raise ValueError('IDs de chunks dupliqués dans la fusion')
    if not graph_hits:
        return [{**r,'graph_rank':None,'hybrid_rank':i,'graphrag_score':r['rrf_score'],
                 'graph_entity_names':[], 'graph_entity_keys':[], 'graph_mention_count':0}
                for i,r in enumerate(base[:limit],1)]
    combined = {}
    for i, r in enumerate(base,1):
        combined[r['chunk_id']] = {**r, 'hybrid_rank':i, 'graph_rank':None,
                                 'graphrag_score':1/(k+i),
                                 'graph_entity_names':[], 'graph_entity_keys':[], 'graph_mention_count':0}
    for i, r in enumerate(graph_hits,1):
        cid = r['chunk_id']
        if cid in combined:
            prev=combined[cid]
            if any(prev.get(x)!=r.get(x) for x in ('document_id','page_number','text')):
                raise ValueError('Chunk Neo4j incompatible avec le corpus FAISS/BM25')
            prev.update(graph_entity_names=r['graph_entity_names'],
                        graph_entity_keys=r['graph_entity_keys'],
                        graph_mention_count=r['graph_mention_count'])
            prev['graph_rank']=i
            prev['graphrag_score']+=1/(k+i)
        else:
            combined[cid] = {**r,'hybrid_rank':None,'graph_rank':i,
                             'rrf_score':0.0, 'graphrag_score':1/(k+i)}
    return sorted(combined.values(),key=lambda r:(-r['graphrag_score'],
          r['hybrid_rank'] is None, r['hybrid_rank'] or 10**6,r['chunk_id']))[:limit]


def build_graph_pipeline(question: str, base_report: dict[str, Any], chunks: list[dict[str, Any]],
                         driver, top_k:int, use_rerank:bool, rerank_model:str,
                         model:str, generate:bool, chat_endpoint:str, timeout:float,
                         document_id:str|None=None, graph_limit:int=8) -> dict[str,Any]:
    """Separated from I/O so offline tests can stub the hybrid retrieval and graph."""
    if not 1 <= top_k <= 10 or not 1 <= graph_limit <= 16:
        raise ValueError('top_k dans [1,10]; graph_limit dans [1,16]')
    if base_report.get('generation') is not None or base_report.get('reranking') != 'disabled':
        raise ValueError('Le rapport de base doit contenir la récupération hybride sans génération ni reranking')
    allowed_chunks={r['chunk_id']:r for r in chunks}
    if len(allowed_chunks) != len(chunks):
        raise ValueError('Corpus local : chunks dupliqués')
    base_pool=base_report['fused_candidates']
    for r in base_pool:
        local = allowed_chunks.get(r['chunk_id'])
        if local is None or any(local.get(k)!=r.get(k) for k in ('document_id','page_number','text')):
            raise ValueError('Récupération hybride différente du corpus local')
    graph_entities, graph_hits, stale_links=load_graph_matches(driver,question,allowed_chunks,document_id)
    hits=graph_rrf(base_pool,graph_hits[:graph_limit],limit=16)
    t_rerank=0.0
    if use_rerank and hits:
        start=time.perf_counter()
        hits=hybrid.rerank_with_ollama(question,hits,rerank_model,chat_endpoint,timeout)
        t_rerank=time.perf_counter()-start
    selected=([r for r in hits if r['rerank_relevance']>0] if use_rerank else hits)[:top_k]
    t_generation=0.0
    answer=None
    if generate:
        start=time.perf_counter()
        answer=hybrid.lexical.ollama_answer(question,selected,model,chat_endpoint,timeout)
        t_generation=time.perf_counter()-start
    baseline_ids=[r['chunk_id'] for r in base_pool[:top_k]]
    selected_ids=[r['chunk_id'] for r in selected]
    novel=[cid for cid in selected_ids if cid not in {r['chunk_id'] for r in base_pool}]
    return {
        'pipeline':'graphrag_neo4j_phase6b',
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'question':question, 'document_id_filter':document_id,
        'embedding_model':base_report.get('embedding_model'),
        'generation_model':model if generate else None,
        'rerank_model':rerank_model if use_rerank else None,
        'retrieval':'hybrid_BM25_FAISS_RRF + Neo4j_entity_mentions + rank_fusion',
        'graph_type':'entity_mention_graph_NOT_validated_scientific_relations',
        'graph_relation':'MENTIONS_ENTITY',
        'entity_validation':'LEXICAL_ONLY_not_human_verified',
        'corpus_chunks':len(chunks),
        'graph':{
            'question_entities':graph_entities,
            'matched_entity_count':len(graph_entities),
            'eligible_graph_chunks':len(graph_hits),
            'stale_or_filtered_links':stale_links,
            'graph_candidate_chunk_ids':[r['chunk_id'] for r in graph_hits[:graph_limit]],
            'graph_used':bool(graph_hits),
            'fallback_reason':None if graph_hits else ('no_entity_in_question' if not graph_entities else 'no_matching_chunks'),
            'novel_chunk_ids':novel,
            'novel_chunk_count':len(novel),
        },
        'hybrid_baseline_top_chunk_ids':baseline_ids,
        'graph_ranking':hits,
        'retrieved':selected,
        'generation':answer,
        'timing_seconds':{'reranking':round(t_rerank,3),'generation':round(t_generation,3)},
        'limitations':[
            'The graph encodes only LEXICAL_ONLY mention links, not validated scientific relationships.',
            'The corpus has 263 chunks, but only a small subset of chunks is enriched with entities.',
            'A valid [n] citation proves source identity, not the factual correctness of the answer.',
            'A single question cannot demonstrate GraphRAG beats hybrid RAG.',
            'Do not treat GraphRAG ranking scores as probabilities.',
        ]
    }


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description='Phase 6B: GraphRAG sur mentions lexicales Neo4j, sans mutation du graphe')
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true',help='Vérifier le graphe Neo4j Phase 5B sans Ollama')
    mode.add_argument('--question',help='Question scientifique pour le GraphRAG')
    p.add_argument('--input',type=Path,default=hybrid.lexical.DEFAULT_INPUT)
    p.add_argument('--index-dir',type=Path,default=hybrid.semantic.INDEX_DIR)
    p.add_argument('--embedding-model',default='nomic-embed-text')
    p.add_argument('--top-k',type=int,default=3)
    p.add_argument('--candidates-k',type=int,default=6)
    p.add_argument('--graph-limit',type=int,default=8)
    p.add_argument('--document-id')
    p.add_argument('--rerank',action='store_true')
    p.add_argument('--generate',action='store_true')
    p.add_argument('--model',default='qwen2.5:7b')
    p.add_argument('--rerank-model',default='qwen2.5:7b')
    p.add_argument('--neo4j-uri',default='bolt://127.0.0.1:7687')
    p.add_argument('--neo4j-user',default='neo4j')
    p.add_argument('--timeout',type=float,default=180)
    p.add_argument('--embed-endpoint',default=hybrid.semantic.ENDPOINT)
    p.add_argument('--chat-endpoint',default=hybrid.CHAT_ENDPOINT)
    p.add_argument('--output',type=Path,default=REPORT)
    args=p.parse_args(argv)
    if args.question is not None and not args.question.strip():
        p.error('Question non vide requise')
    if args.question is not None and not 1 <= args.top_k <= args.candidates_k <= 8:
        p.error('1 <= top-k <= candidates-k <= 8 requis')
    secret=os.environ.get('NEO4J_PASSWORD') or getpass.getpass('Mot de passe Neo4j (saisie invisible) : ')
    if not secret:
        p.error('Mot de passe Neo4j requis (variable NEO4J_PASSWORD ou invite interactive)')
    with neo4j_driver(args.neo4j_uri,secret,args.neo4j_user) as driver:
        stats=graph_stats(driver)
        print('NEO4J CHECK OK:', json.dumps(stats,ensure_ascii=False))
        if args.check:
            print('Lecture Neo4j uniquement. Aucun appel Ollama, aucun index modifié.')
            return 0
        # Reuse exactly the same 6A.2 hybrid RRF method; do NOT rerank here yet.
        base=hybrid.run_pipeline(args.question,args.input,args.index_dir,args.embedding_model,
            args.top_k,args.candidates_k,False,args.rerank_model,args.model,False,
            args.embed_endpoint,args.chat_endpoint,args.timeout,args.document_id)
        chunks=hybrid.lexical.load_chunks(args.input)
        report=build_graph_pipeline(args.question,base,chunks,driver,args.top_k,args.rerank,
            args.rerank_model,args.model,args.generate,args.chat_endpoint,args.timeout,
            args.document_id,args.graph_limit)
    report['graph']['database_counts']=stats
    report['timing_seconds']['hybrid_retrieval']=base['timing_seconds']['retrieval']
    print('BASE HYBRIDE:', ', '.join(report['hybrid_baseline_top_chunk_ids']) or '(vide)')
    print('GRAPH:', 'entités dans question =',report['graph']['matched_entity_count'],
          '| passages liés =',report['graph']['eligible_graph_chunks'],
          '| nouveaux passages sélectionnés =',report['graph']['novel_chunk_count'])
    if report['graph']['question_entities']:
        print('ENTITES:', ', '.join(x['name'] for x in report['graph']['question_entities']))
    if report['graph']['fallback_reason']:
        print('FALLBACK:',report['graph']['fallback_reason'],
              '(le graphe ne fournit pas de preuve pour cette question)')
    for i,r in enumerate(report['retrieved'],1):
        print(f'[{i}] {r["document_id"]} | p.{r["page_number"]} | {r["chunk_id"]}'
              f' | score GraphRAG {r["graphrag_score"]:.5f}'
              + (f' | rerank {r["rerank_relevance"]}' if args.rerank else ''))
        print('    '+' '.join(r['text'].split())[:150]+'...')
        if r['graph_entity_names']:
            print('    MENTIONS_ENTITY:', ', '.join(r['graph_entity_names']))
    if report['generation']:
        print('\n=== REPONSE GRAPHRAG ===\n'+report['generation']['answer'])
        print('\n=== SOURCES DISPONIBLES ===')
        for i,r in enumerate(report['retrieved'],1):
            print(f'[{i}] {r["document_id"]}, page {r["page_number"]}, {r["chunk_id"]}')
        if report['generation']['citation_warning']:
            print('ATTENTION: génération sans citations explicites, à vérifier.')
    hybrid.semantic.atomic_json(args.output,report)
    print('RAPPORT:',args.output)
    return 0


if __name__=='__main__':
    try:
        sys.exit(main())
    except (ValueError,RuntimeError,OSError,KeyError,json.JSONDecodeError) as exc:
        print('ERREUR:',str(exc),file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # Database drivers can raise numerous provider-specific exceptions.
        if exc.__class__.__module__.startswith('neo4j.'):
            print('ERREUR Neo4j:', str(exc),file=sys.stderr)
            sys.exit(1)
        raise
