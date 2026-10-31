"""Phase 7 Streamlit adapter: read-only access to the existing Scientific Research AI pipeline.

No Streamlit imports here: functionality can be unit-tested without UI or live services.
Previously validated phase 6A/6A.2/6B scripts remain unchanged.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from typing import Any
import urllib.error
import urllib.request

import rag_classique_phase6 as lexical
import rag_hybride_phase6a2 as hybrid
import graphrag_phase6b as graph
import rag_semantique_faiss_phase6a1 as semantic

ROOT = Path(__file__).resolve().parents[1]
CORPUS = lexical.DEFAULT_INPUT
STRUCTURAL_REPORT = ROOT / 'data' / 'reports' / 'graph_analytics_report.json'
SCIENTIFIC_REPORT = ROOT / 'data' / 'reports' / 'graph_analytics_scientific_phase5b.json'
NEO4J_URI = 'bolt://127.0.0.1:7687'
MODEL = 'qwen2.5:7b'
MODES = ('RAG BM25', 'RAG hybride', 'GraphRAG Neo4j')


def load_optional_report(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('Rapport JSON non objet : ' + str(path))
    return data


def corpus_overview(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    docs = Counter(c['document_id'] for c in chunks)
    pages = {d: set() for d in docs}
    for c in chunks:
        pages[c['document_id']].add(c['page_number'])
    return {'chunks': len(chunks), 'documents': len(docs),
            'pages_represented': sum(len(p) for p in pages.values()),
            'document_rows': [
                {'Document': did, 'Chunks': n, 'Pages représentées': len(pages[did])}
                for did, n in sorted(docs.items())]}


def validate_request(mode: str, question: str, top_k: int, candidates_k: int, document_id: str | None) -> str:
    if mode not in MODES:
        raise ValueError('Mode RAG inconnu')
    question = (question or '').strip()
    if not question or len(question) > 700:
        raise ValueError('Question obligatoire, longueur maximale 700 caractères')
    if not 1 <= top_k <= 8:
        raise ValueError('top-k doit être entre 1 et 8')
    if mode != 'RAG BM25' and not top_k <= candidates_k <= 8:
        raise ValueError('candidates-k doit être entre top-k et 8')
    if document_id is not None and (not isinstance(document_id,str) or not document_id.strip()):
        raise ValueError('document_id invalide')
    return question


def run_query(*, mode: str, question: str, top_k: int = 3, candidates_k: int = 6,
              use_rerank: bool = False, generate: bool = True,
              document_id: str | None = None, neo4j_password: str | None = None,
              timeout: float = 180, neo4j_uri: str = NEO4J_URI,
              model: str = MODEL) -> dict[str, Any]:
    question = validate_request(mode, question, top_k, candidates_k, document_id)
    started = time.perf_counter()
    if mode == 'RAG BM25':
        chunks = lexical.load_chunks(CORPUS)
        if document_id and document_id not in {c['document_id'] for c in chunks}:
            raise ValueError('Document absent du corpus')
        selected = lexical.BM25(chunks).search(question, top_k, document_id)
        retrieval_elapsed = time.perf_counter() - started
        generation_started = time.perf_counter()
        answer = lexical.ollama_answer(question, selected, model, lexical.OLLAMA_URL, timeout) if generate else None
        result = {'pipeline': 'rag_classique_bm25_v1', 'question': question,
                  'retrieved': selected, 'generation': answer,
                  'corpus_chunks': len(chunks),
                  'timing_seconds': {'retrieval': round(retrieval_elapsed,3),
                                     'generation':round(time.perf_counter()-generation_started,3) if generate else 0.0}}
    elif mode == 'RAG hybride':
        result = hybrid.run_pipeline(question, CORPUS, semantic.INDEX_DIR, 'nomic-embed-text',
                   top_k, candidates_k, use_rerank, model, model, generate,
                   semantic.ENDPOINT, hybrid.CHAT_ENDPOINT, timeout, document_id)
    else:
        if not neo4j_password:
            raise ValueError('Mot de passe Neo4j requis pour GraphRAG')
        with graph.neo4j_driver(neo4j_uri, neo4j_password) as driver:
            stats = graph.graph_stats(driver)
            baseline = hybrid.run_pipeline(question, CORPUS, semantic.INDEX_DIR,
                 'nomic-embed-text', top_k, candidates_k, False, model, model, False,
                 semantic.ENDPOINT, hybrid.CHAT_ENDPOINT, timeout, document_id)
            chunks = lexical.load_chunks(CORPUS)
            result = graph.build_graph_pipeline(question, baseline, chunks, driver,
                 top_k, use_rerank, model, model, generate, hybrid.CHAT_ENDPOINT,
                 timeout, document_id)
            result['graph']['database_counts'] = stats
            result['timing_seconds']['hybrid_retrieval'] = baseline['timing_seconds']['retrieval']
    result = dict(result)
    result['ui_mode'] = mode
    result['ui_rerank'] = bool(use_rerank and mode != 'RAG BM25')
    result['ui_generate'] = generate
    result['ui_elapsed_seconds'] = round(time.perf_counter() - started,3)
    result['ui_generated_at_utc'] = datetime.now(timezone.utc).isoformat()
    return result


def source_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for i, row in enumerate(result.get('retrieved') or [],1):
        score = row.get('graphrag_score', row.get('rrf_score', row.get('score')))
        rows.append({'Rang': i, 'Document':row['document_id'],
                    'Page':row['page_number'], 'Chunk':row['chunk_id'],
                    'Score de classement': round(float(score),5) if score is not None else None,
                    'Note reranking':row.get('rerank_relevance'),
                    'Entités graphe': ', '.join(row.get('graph_entity_names') or [])})
    return rows


def check_ollama(url: str = 'http://127.0.0.1:11434/api/tags', timeout:float=2.5) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload=json.load(resp)
        names=[m.get('name') or m.get('model') for m in payload.get('models',[]) if isinstance(m,dict)]
        return {'available':True,'models':[v for v in names if v]}
    except (urllib.error.URLError,TimeoutError,OSError,ValueError,KeyError):
        return {'available':False, 'models':[]}


def faiss_status() -> dict[str, Any]:
    path=semantic.INDEX_DIR / 'manifest.json'
    # Check name used in the released phase 6A.1 script, then fallback to directory listing.
    if not path.is_file():
        for name in ('index_manifest.json','metadata.json'):
            alt=semantic.INDEX_DIR / name
            if alt.is_file(): path=alt; break
    if not path.is_file():
        return {'available':False,'folder':str(semantic.INDEX_DIR)}
    try:
        m=json.loads(path.read_text(encoding='utf-8'))
        return {'available':True, 'model':m.get('model'), 'chunks':m.get('chunk_count'),
                'dimension':m.get('dimension'), 'folder':str(semantic.INDEX_DIR)}
    except (ValueError,OSError):
        return {'available':False,'folder':str(semantic.INDEX_DIR)}


def dot_escape(value: Any) -> str:
    text=str(value).replace('\\','\\\\').replace('"','\\"').replace('\n',' ')
    return text[:140]


def make_dot(document_id: str, chunks: list[dict[str,Any]],
             mentions: list[dict[str,Any]], limit: int = 10) -> str:
    """Graphviz read-only preview; safely quote every label and every ID."""
    if not 1 <= limit <= 20: raise ValueError('Limite d affichage invalide')
    chosen=[r for r in chunks if r['document_id']==document_id][:limit]
    nodes=['digraph G {', '  graph [bgcolor="transparent", rankdir=LR, pad=0.28, nodesep=0.36, ranksep=0.8];',
           '  node [fontname="Arial", fontsize=10, style="filled,rounded", shape=box, penwidth=0];',
           '  edge [color="#7588aa", arrowsize=0.55];',
           f'  "doc" [label="{dot_escape(document_id)}", fillcolor="#d9c9ff", fontcolor="#252344"];']
    valid={r['chunk_id'] for r in chosen}
    for i,c in enumerate(chosen):
        key=f'c{i}'
        label=f'p.{c["page_number"]} | {c["chunk_id"][-14:]}'
        nodes.append(f'  "{key}" [label="{dot_escape(label)}", fillcolor="#b7f1dc", fontcolor="#133b34"];')
        nodes.append(f'  "doc" -> "{key}" [label="HAS_CHUNK"];')
    keys={c['chunk_id']:f'c{i}' for i,c in enumerate(chosen)}
    e_map={}
    for r in mentions:
        cid=r.get('chunk_id'); name=r.get('name'); kind=r.get('kind')
        if cid not in valid or not name: continue
        ek=r.get('entity_key') or f'{kind}|{name}'
        if ek not in e_map:
            e_map[ek]=f'e{len(e_map)}'
            nodes.append(f'  "{e_map[ek]}" [label="{dot_escape(name)}", fillcolor="#bdd3fd", fontcolor="#17345c"];')
        nodes.append(f'  "{keys[cid]}" -> "{e_map[ek]}" [color="#90a5df", label="MENTIONS_ENTITY"];')
    nodes.append('}')
    return '\n'.join(nodes)


def graph_preview_rows(driver, document_id: str, max_chunks:int=8, page_number:int|None=None) -> tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    """Only use real HAS_CHUNK and MENTIONS_ENTITY links, never fake scientific predicates."""
    if not 1<=max_chunks<=16: raise ValueError('max_chunks invalide')
    if page_number is not None and (type(page_number) is not int or page_number < 1):
        raise ValueError('page_number invalide')
    with driver.session() as s:
        chunks=[dict(r) for r in s.run('''
          MATCH (d:SRAIDocument {project:$project, document_id:$document})-[:HAS_CHUNK]->(c:SRAIChunk {project:$project})
          WHERE $page IS NULL OR c.page_number=$page
          RETURN c.chunk_id AS chunk_id, c.document_id AS document_id, c.page_number AS page_number
          ORDER BY c.page_number,c.chunk_id LIMIT $cap
        ''',project=graph.PROJECT,document=document_id,cap=max_chunks,page=page_number)]
        mentions=[dict(r) for r in s.run('''
          MATCH (c:SRAIChunk {project:$project})-[:MENTIONS_ENTITY]->(e:SRAIEntity {project:$project, verification:$scope})
          WHERE c.chunk_id IN $ids
          RETURN c.chunk_id AS chunk_id, e.entity_key AS entity_key, e.name AS name, e.kind AS kind
          ORDER BY c.chunk_id,e.entity_key LIMIT 120
        ''', project=graph.PROJECT,scope=graph.SCOPE,ids=[r['chunk_id'] for r in chunks])]
    return chunks,mentions
