"""Scientific Research AI | Graph Analytics structurelles, lecture seule.

Les quatre types de noeuds sont issus de l'ETL Spark/Neo4j. Les auteurs sont
DES MENTIONS, pas des personnes desambiguisees. Ne calcule pas de collaboration.
"""
from __future__ import annotations
import argparse
import csv
import getpass
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT = 'scientific-research-ai'
NODE_TYPES = ('SRAIPublication','SRAIAuthorMention','SRAIDocument','SRAIChunk')
REL_TYPES = ('HAS_AUTHOR_MENTION','HAS_CHUNK')


def calculate_metrics(publications, mentions, documents, chunks, author_links, chunk_links):
    """Pure data function. Raise instead of reporting misleading successes."""
    ps = {r['canonical_id']:r for r in publications}
    ms = {r['author_occurrence_id']:r for r in mentions}
    ds = {r['document_id']:r for r in documents}
    cs = {r['chunk_id']:r for r in chunks}
    counts = [len(publications),len(mentions),len(documents),len(chunks)]
    if counts != [len(ps),len(ms),len(ds),len(cs)]:
        raise ValueError('Identifiants dupliques dans les noeuds')
    if any(not id for dic in (ps,ms,ds,cs) for id in dic):
        raise ValueError('Identifiants vides dans les noeuds')
    if len(author_links) != len(set(author_links)) or len(chunk_links) != len(set(chunk_links)):
        raise ValueError('Relations structurelles dupliquees')
    if any(p not in ps or a not in ms for p,a in author_links):
        raise ValueError('Relation publication/auteur orpheline')
    if any(d not in ds or c not in cs for d,c in chunk_links):
        raise ValueError('Relation document/chunk orpheline')
    author_degree = Counter(p for p,a in author_links)
    doc_degree = Counter(d for d,c in chunk_links)
    reverse_auth = Counter(a for p,a in author_links)
    reverse_chunk = Counter(c for d,c in chunk_links)
    if any(v != 1 for v in reverse_auth.values()) or len(reverse_auth) != len(ms):
        raise ValueError('Mention auteur sans publication ou avec plusieurs publications')
    if any(v != 1 for v in reverse_chunk.values()) or len(reverse_chunk) != len(cs):
        raise ValueError('Chunk sans document ou avec plusieurs documents')
    # Protect against accidental linkage to wrong source document.
    if any(cs[c].get('document_id') != d for d,c in chunk_links):
        raise ValueError('La provenance du chunk contredit HAS_CHUNK')
    per_publication = sorted([{
        'canonical_id':p,'title':str(r.get('title') or ''),'year':r.get('year'),
        'author_mentions':author_degree[p], 'doi':str(r.get('doi') or ''),
    } for p,r in ps.items()], key=lambda r:(-r['author_mentions'],r['canonical_id']))
    per_document = []
    for doc in sorted(ds):
        relevant = [cs[c] for d,c in chunk_links if d == doc]
        pages = sorted({int(x['page_number']) for x in relevant if x.get('page_number') is not None})
        lengths=[len(x.get('text') or '') for x in relevant]
        per_document.append({'document_id':doc,'chunks':len(relevant),'pages_represented':len(pages),
                             'min_page':min(pages) if pages else None,'max_page':max(pages) if pages else None,
                             'avg_chunk_chars':round(sum(lengths)/len(lengths),1) if lengths else 0})
    # Structural graph: distinct stars, no author identity linking, no PDF->crawler identity asserted.
    nodes=set(('p',p) for p in ps) | set(('a',a) for a in ms) | set(('d',d) for d in ds) | set(('c',c) for c in cs)
    edges={frozenset((('p',p),('a',a))) for p,a in author_links} | {frozenset((('d',d),('c',c))) for d,c in chunk_links}
    parent={n:n for n in nodes}
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    for e in edges:
        a,b=tuple(e)
        ra,rb=find(a),find(b)
        if ra!=rb: parent[ra]=rb
    comp=Counter(find(n) for n in nodes)
    n=len(nodes); m=len(edges)
    summary={'node_counts':dict(zip(NODE_TYPES,counts)),
             'relation_counts':{'HAS_AUTHOR_MENTION':len(author_links),'HAS_CHUNK':len(chunk_links)},
             'total_nodes':n,'total_relations':m,'components':len(comp),
             'largest_component_nodes':max(comp.values(),default=0),
             'isolated_nodes':sum(v==1 for v in comp.values()),
             'density_undirected':round(2*m/(n*(n-1)),7) if n>1 else 0,
             'avg_author_mentions_per_publication':round(len(mentions)/len(publications),2) if publications else 0,
             'avg_chunks_per_document':round(len(chunks)/len(documents),2) if documents else 0,
             'interpretation':'Topologie des donnees/provenance seulement; ceci ne mesure ni impact scientifique, ni collaborations, ni communautes thematiques.'}
    return {'summary':summary,'publications':per_publication,'documents':per_document}


def query_data(driver):
    queries={
      'publications':'''MATCH (n:SRAIPublication {project:$project}) RETURN n.canonical_id AS canonical_id, n.title AS title, n.year AS year, n.doi AS doi''',
      'mentions':'''MATCH (n:SRAIAuthorMention {project:$project}) RETURN n.author_occurrence_id AS author_occurrence_id, n.name AS name''',
      'documents':'''MATCH (n:SRAIDocument {project:$project}) RETURN n.document_id AS document_id''',
      'chunks':'''MATCH (n:SRAIChunk {project:$project}) RETURN n.chunk_id AS chunk_id, n.document_id AS document_id, n.page_number AS page_number, n.text AS text''',
      'author_links':'''MATCH (p:SRAIPublication {project:$project})-[:HAS_AUTHOR_MENTION]->(a:SRAIAuthorMention {project:$project}) RETURN p.canonical_id AS left, a.author_occurrence_id AS right''',
      'chunk_links':'''MATCH (d:SRAIDocument {project:$project})-[:HAS_CHUNK]->(c:SRAIChunk {project:$project}) RETURN d.document_id AS left, c.chunk_id AS right''',
    }
    with driver.session() as s:
        data={name:[dict(row) for row in s.run(q,project=PROJECT)] for name,q in queries.items()}
    return data


def save_reports(result, output):
    output.mkdir(parents=True,exist_ok=True)
    path=output/'graph_analytics_report.json'
    result={'generated_at_utc':datetime.now(timezone.utc).isoformat(), 'analysis_scope':'structural', **result}
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name in ('publications','documents'):
        rows=result[name]
        if not rows: continue
        with (output/f'graph_analytics_{name}.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]))
            writer.writeheader();writer.writerows(rows)
    return path


def main():
    parser=argparse.ArgumentParser(description='Phase 5: Graph Analytics structurelles Neo4j, en lecture seule')
    parser.add_argument('--uri',default='bolt://127.0.0.1:7687')
    parser.add_argument('--user',default='neo4j')
    parser.add_argument('--output',default='data/reports')
    args=parser.parse_args()
    from neo4j import GraphDatabase
    password=getpass.getpass('Mot de passe Neo4j (invisible): ')
    with GraphDatabase.driver(args.uri,auth=(args.user,password)) as driver:
        driver.verify_connectivity()
        data=query_data(driver)
    result=calculate_metrics(data['publications'],data['mentions'],data['documents'],data['chunks'],
          [(r['left'],r['right']) for r in data['author_links']],
          [(r['left'],r['right']) for r in data['chunk_links']])
    summary=result['summary']
    print('GRAPH ANALYTICS:',json.dumps(summary,ensure_ascii=False,indent=2))
    if (summary['total_nodes'],summary['total_relations'])!=(360,343):
        print('ATTENTION : volumes differents du premier import attendu. Verifier le rapport avant de conclure.')
    path=save_reports(result,Path(args.output))
    print('RAPPORT:',path)
    print('ANALYSE LECTURE SEULE OK (aucune ecriture Neo4j)')

if __name__=='__main__':main()
