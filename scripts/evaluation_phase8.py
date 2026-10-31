"""Scientific Research AI – Phase 8: transparent retrieval / Graph Analytics evaluation.

Uses the exact installed Phase 7 adapter and Phase 6 pipelines. No fake scores.
No new Neo4j writes; no FAISS updates. Generation optional, faithfulness NOT automated.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import statistics
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

import streamlit_phase7_backend as backend

DEFAULT_QUESTIONS = ROOT / 'data' / 'evaluation' / 'questions_phase8.json'
DEFAULT_OUTPUT = ROOT / 'data' / 'reports' / 'evaluation_phase8.json'
MODE_NAMES = backend.MODES


def read_questions(path: Path, corpus_ids: set[str] | None = None) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data, list) or not data:
        raise ValueError('Benchmark doit être une liste JSON non vide')
    ids = set()
    for q in data:
        if not isinstance(q, dict) or not isinstance(q.get('id'), str) or not q['id'].strip():
            raise ValueError('Chaque question doit avoir un identifiant non vide')
        if q['id'] in ids:
            raise ValueError('Identifiant de question dupliqué : ' + q['id'])
        ids.add(q['id'])
        question = q.get('question')
        if not isinstance(question, str) or not question.strip() or len(question) > 700:
            raise ValueError('Question vide ou trop longue : ' + q['id'])
        status = q.get('reference_status', 'none')
        if status not in ('none', 'provisional', 'human_verified'):
            raise ValueError('reference_status inconnu : ' + q['id'])
        gold = q.get('reference_chunk_ids', [])
        if not isinstance(gold, list) or any(not isinstance(x,str) or not x for x in gold) or len(gold) != len(set(gold)):
            raise ValueError('Identifiants de référence invalides : ' + q['id'])
        if (status == 'none' and gold) or (status != 'none' and not gold):
            raise ValueError('État de validation incompatible avec les références : ' + q['id'])
        if corpus_ids is not None and (set(gold) - corpus_ids):
            raise ValueError('Référence absente du corpus : ' + q['id'] + ' : ' + repr(sorted(set(gold) - corpus_ids)))
    return data


def retrieval_scores(retrieved_ids: list[str], reference_ids: list[str], k: int) -> dict[str, float]:
    """Values are well-defined only for questions with explicit, checked reference IDs."""
    if not reference_ids or k < 1 or len(set(reference_ids)) != len(reference_ids):
        raise ValueError('References non vides, uniques, k >= 1')
    at_k = retrieved_ids[:k]
    if len(at_k) != len(set(at_k)):
        raise ValueError('Doublons dans les résultats récupérés')
    gold = set(reference_ids)
    correct = [i for i, cid in enumerate(at_k,1) if cid in gold]
    return {
        'precision_at_k': round(len(correct) / k, 5),
        'recall_at_k': round(len(correct) / len(gold), 5),
        'hit_at_k': int(bool(correct)),
        'reciprocal_rank_at_k': round(1 / correct[0], 5) if correct else 0.0,
    }


def verify_analytics(structural: dict[str, Any] | None, scientific: dict[str, Any] | None,
                     corpus_chunks: int) -> dict[str, Any]:
    checks = []
    snapshot = {}
    if structural:
        s = structural.get('summary', {})
        n, edges = s.get('total_nodes'), s.get('total_relations')
        counts, links = s.get('node_counts', {}), s.get('relation_counts', {})
        validations = {
            'node_count_sum': isinstance(n,int) and sum(counts.values()) == n,
            'relation_count_sum': isinstance(edges,int) and sum(links.values()) == edges,
            'chunks_match_corpus': counts.get('SRAIChunk') == corpus_chunks,
            'chunk_provenance_links': links.get('HAS_CHUNK') == counts.get('SRAIChunk'),
            'author_mention_links': links.get('HAS_AUTHOR_MENTION') == counts.get('SRAIAuthorMention'),
            'components_valid': isinstance(s.get('components'),int) and 1 <= s['components'] <= n,
        }
        checks += [{'check':k, 'passed':v} for k,v in validations.items()]
        snapshot['structural'] = {'total_nodes':n,'total_relations':edges,'components':s.get('components'),
                                  'node_counts':counts,'relation_counts':links}
    if scientific:
        s = scientific.get('summary', {})
        valid = {
            'mention_links_consistent': s.get('chunk_entity_links') == s.get('entity_mentions'),
            'enriched_chunks_within_corpus': isinstance(s.get('input_chunks_with_entities'),int)
                                           and 0 < s['input_chunks_with_entities'] <= corpus_chunks,
            'lexical_scope_disclosed': s.get('scope') == 'exploratory_lexical_mentions_not_scientific_facts',
        }
        checks += [{'check':k,'passed':v} for k,v in valid.items()]
        snapshot['scientific'] = {k:s.get(k) for k in ('unique_entities','entity_mentions','chunk_entity_links',
                                  'input_chunks_with_entities','co_mention_pairs','scope')}
    return {'structural_report_found': bool(structural), 'scientific_report_found': bool(scientific),
            'checks': checks,'checks_passed':sum(x['passed'] for x in checks),'checks_total':len(checks),
            'checks_all_passed': bool(checks) and all(x['passed'] for x in checks),
            'snapshot': snapshot,
            'caution': 'Ces tests vérifient la cohérence des rapports, pas l\'impact scientifique ni la vérité des entités.'}


def calculate_report(questions: list[dict[str,Any]], results: list[dict[str,Any]],
                     methods: list[str], k: int, analytics: dict[str,Any], generation: bool,
                     rerank: bool) -> dict[str,Any]:
    summaries = {}
    byq = {r['id']:r for r in results}
    for method in methods:
        rows = [r['modes'][method] for r in results if r['modes'].get(method,{}).get('status')=='ok']
        reviewed = defaultdict(list)
        for q in questions:
            actual = byq[q['id']]['modes'].get(method, {})
            if actual.get('status')=='ok' and actual.get('metrics'):
                reviewed[q.get('reference_status','none')].append(actual['metrics'])
        groups = {}
        for scope in ('human_verified','provisional'):
            found = reviewed.get(scope,[])
            if found:
                groups[scope] = {'questions':len(found), **{
                    name:round(statistics.mean(a[name] for a in found),5)
                    for name in ('precision_at_k','recall_at_k','hit_at_k','reciprocal_rank_at_k')}}
        summaries[method] = {
            'successful_questions':len(rows),
            'failed_questions':sum(r['modes'].get(method,{}).get('status')=='error' for r in results),
            'avg_elapsed_seconds':round(statistics.mean(r['elapsed_seconds'] for r in rows),3) if rows else None,
            'avg_retrieved_chunks':round(statistics.mean(len(r['retrieved_chunk_ids']) for r in rows),2) if rows else None,
            'avg_distinct_source_documents':round(statistics.mean(r['distinct_documents'] for r in rows),2) if rows else None,
            'reference_metrics':groups,
        }
        if method=='GraphRAG Neo4j' and rows:
            summaries[method]['questions_with_graph_hits'] = sum(r.get('graph_used',False) for r in rows)
            summaries[method]['avg_graph_novel_chunks'] = round(statistics.mean(r.get('graph_novel_chunks',0) for r in rows),2)
    return {'schema':'srai-evaluation-phase8-v1', 'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'question_count':len(questions), 'modes':methods, 'top_k':k, 'reranking_enabled':rerank,
            'generation_enabled':generation, 'summaries':summaries,
            'questions':results, 'analytics':analytics,
            'scientific_validity': {
                'human_verified_labels':sum(q['reference_status']=='human_verified' for q in questions),
                'provisional_labels':sum(q['reference_status']=='provisional' for q in questions),
                'unlabeled_questions':sum(q['reference_status']=='none' for q in questions),
                'note':'Scores sur références provisoires = diagnostics uniquement, pas résultats validés. '
                        'Les réponses générées et leurs citations exigent une vérification humaine de fidélité; '
                        'les temps incluent les appels effectivement effectués. Les configurations GraphRAG '
                        'doivent avoir les mêmes paramètres que la baseline pour comparer.'}}


def evaluate(questions: list[dict[str,Any]], methods: list[str], top_k:int=3,
             candidates_k:int=6, neo4j_password: str='', neo4j_uri: str=backend.NEO4J_URI,
             rerank:bool=False, generate:bool=False, timeout:float=180,
             runner=None) -> dict[str,Any]:
    if not 1 <= top_k <= candidates_k <= 8 or not methods or len(set(methods))!=len(methods):
        raise ValueError('top-k, candidates-k, modes invalides')
    if any(m not in MODE_NAMES for m in methods):
        raise ValueError('Mode inconnu')
    corpus = backend.lexical.load_chunks(backend.CORPUS)
    read_questions_ids = {c['chunk_id'] for c in corpus}
    if len(read_questions_ids) != len(corpus):
        raise ValueError('Corpus : IDs dupliqués')
    for q in questions:
        if any(g not in read_questions_ids for g in q.get('reference_chunk_ids',[])):
            raise ValueError('Reference absente du corpus : '+q['id'])
    structural=backend.load_optional_report(backend.STRUCTURAL_REPORT)
    scientific=backend.load_optional_report(backend.SCIENTIFIC_REPORT)
    analytics=verify_analytics(structural,scientific,len(corpus))
    results=[]
    call=runner or backend.run_query
    for num, q in enumerate(questions,1):
        print(f'[{num}/{len(questions)}] {q["id"]} : {q["question"]}',flush=True)
        record={'id':q['id'],'question':q['question'],
                'reference_status':q.get('reference_status','none'),
                'reference_chunk_ids':q.get('reference_chunk_ids',[]),'modes':{}}
        for m in methods:
            try:
                res=call(mode=m,question=q['question'],top_k=top_k,candidates_k=candidates_k,
                         use_rerank=rerank,generate=generate,neo4j_password=neo4j_password,
                         neo4j_uri=neo4j_uri,timeout=timeout)
                selected=res.get('retrieved') or []
                ids=[c['chunk_id'] for c in selected]
                if len(ids)!=len(set(ids)) or len(ids)>top_k or any(cid not in read_questions_ids for cid in ids):
                    raise ValueError('IDs / provenance incorrects dans les résultats')
                record['modes'][m]={
                    'status':'ok','retrieved_chunk_ids':ids,
                    'sources':[{'chunk_id':r['chunk_id'],'document_id':r['document_id'],
                                'page_number':r['page_number']} for r in selected],
                    'elapsed_seconds':res.get('ui_elapsed_seconds'),
                    'distinct_documents':len({r['document_id'] for r in selected}),
                    'metrics':retrieval_scores(ids,q['reference_chunk_ids'],top_k) if q.get('reference_chunk_ids') else None,
                }
                if m=='GraphRAG Neo4j':
                    g=res.get('graph',{})
                    record['modes'][m].update(graph_used=bool(g.get('graph_used')),
                                             graph_matched_entities=g.get('matched_entity_count',0),
                                             graph_linked_chunks=g.get('eligible_graph_chunks',0),
                                             graph_novel_chunks=g.get('novel_chunk_count',0),
                                             graph_fallback_reason=g.get('fallback_reason'))
                if generate:
                    ans=res.get('generation') or {}
                    record['modes'][m]['answer']=ans.get('answer')
                    record['modes'][m]['citations_used']=ans.get('citations_used',[])
                    record['modes'][m]['answer_human_verified']=False
                print(f'  {m}: OK {len(ids)} chunks | {record["modes"][m]["elapsed_seconds"]} s',flush=True)
            except Exception as exc:
                # Never claim a method was evaluated when an Ollama or Neo4j call failed.
                record['modes'][m]={'status':'error','error_type':type(exc).__name__,'error':str(exc)}
                print(f'  {m}: ERREUR {type(exc).__name__}: {exc}',flush=True)
        results.append(record)
    return calculate_report(questions,results,methods,top_k,analytics,generate,rerank)


def main(argv:list[str] | None=None) -> int:
    p=argparse.ArgumentParser(description='Evaluation reproductible BM25 vs hybride vs GraphRAG (lecture seule)')
    p.add_argument('--questions',type=Path,default=DEFAULT_QUESTIONS)
    p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--top-k',type=int,default=3)
    p.add_argument('--candidates-k',type=int,default=6)
    p.add_argument('--max-questions',type=int,default=0,help='Pour un smoke test rapide ; 0 = toutes')
    p.add_argument('--skip-graph',action='store_true',help='Comparer BM25 et hybride sans Neo4j')
    p.add_argument('--rerank',action='store_true',help='Rerank Qwen sur hybride et GraphRAG (lent)')
    p.add_argument('--generate',action='store_true',help='Generer reponses, sans score automatique de fidelite (lent)')
    p.add_argument('--neo4j-uri',default=backend.NEO4J_URI)
    p.add_argument('--timeout',type=float,default=180)
    args=p.parse_args(argv)
    corpus=backend.lexical.load_chunks(backend.CORPUS)
    questions=read_questions(args.questions,{r['chunk_id'] for r in corpus})
    if args.max_questions < 0: p.error('--max-questions doit etre positif ou nul')
    if args.max_questions: questions=questions[:args.max_questions]
    modes=list(MODE_NAMES if not args.skip_graph else MODE_NAMES[:2])
    password=''
    if 'GraphRAG Neo4j' in modes:
        password=os.environ.get('NEO4J_PASSWORD') or getpass.getpass('Mot de passe Neo4j (invisible) : ')
        if not password: p.error('Mot de passe Neo4j requis (NEO4J_PASSWORD)')
    result=evaluate(questions,modes,args.top_k,args.candidates_k,password,args.neo4j_uri,
                    args.rerank,args.generate,args.timeout)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('\nRAPPORT:',args.output)
    print('STATUT:',json.dumps(result['summaries'],ensure_ascii=False,indent=2))
    print('AVERTISSEMENT: les références provisoires ne sont pas une évaluation scientifique validée.')
    return 1 if any(s['failed_questions'] for s in result['summaries'].values()) else 0

if __name__=='__main__':
    raise SystemExit(main())
