"""Offline tests for Phase 6B. No live Neo4j, FAISS, or Ollama needed."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import graphrag_phase6b as g

DOCS = [
 {'chunk_id':'a1','document_id':'acl','page_number':7,'text':'BGM improves retrieval compared to GTR.','title':'acl'},
 {'chunk_id':'a2','document_id':'acl','page_number':7,'text':'GTR retrieves passages.','title':'acl'},
 {'chunk_id':'a3','document_id':'acl','page_number':9,'text':'BGM avoids irrelevant contexts.','title':'acl'},
 {'chunk_id':'h1','document_id':'hal','page_number':3,'text':'WiKC studies entity typing.','title':'hal'},
]

ENTITIES=[
 {'entity_key':'METHOD|bgm','name':'BGM','kind':'METHOD','verification':'LEXICAL_ONLY'},
 {'entity_key':'MODEL|gtr','name':'GTR','kind':'MODEL','verification':'LEXICAL_ONLY'},
 {'entity_key':'METHOD|wikc','name':'WiKC','kind':'METHOD','verification':'LEXICAL_ONLY'},
 {'entity_key':'METHOD|unverified','name':'Unverified','kind':'METHOD','verification':'HUMAN_REVIEW_REQUIRED'}
]

LINKS=[
 {'chunk_id':'a1','document_id':'acl','entity_key':'METHOD|bgm'},
 {'chunk_id':'a1','document_id':'acl','entity_key':'MODEL|gtr'},
 {'chunk_id':'a2','document_id':'acl','entity_key':'MODEL|gtr'},
 {'chunk_id':'a3','document_id':'acl','entity_key':'METHOD|bgm'},
 {'chunk_id':'h1','document_id':'hal','entity_key':'METHOD|wikc'},
]

class FakeSession:
 def __init__(self,links=None,ents=None,stats=None):
  self.links=LINKS if links is None else links
  self.entities=ENTITIES if ents is None else ents
  self.stats={'entity_count':3,'enriched_chunks':4,'chunk_entity_links':5} if stats is None else stats
  self.reads=[]
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def run(self, cypher, **params):
  self.reads.append((cypher,params))
  if 'count(e) AS entity_count' in cypher:
   class StatsResult:
    def __init__(self,stats):self.stats=stats
    def single(self):return self.stats
   return StatsResult(self.stats)
  if 'RETURN e.entity_key AS entity_key' in cypher:
   return self.entities
  if 'RETURN c.chunk_id AS chunk_id' in cypher:
   return [r for r in self.links if r['entity_key'] in params['keys']]
  raise AssertionError('Unexpected Cypher')
class FakeDriver:
 def __init__(self,**kwargs):self.obj=FakeSession(**kwargs)
 def session(self):return self.obj


def base_report():
 return {'pipeline':'rag_hybride_phase6a2','reranking':'disabled','generation':None,
         'embedding_model':'nomic-embed-text',
         'fused_candidates':[
          {**DOCS[0],'rrf_score':0.03226},
          {**DOCS[1],'rrf_score':0.03154},
          {**DOCS[3],'rrf_score':0.01613},
         ]}


class GraphRagPhase6BTests(unittest.TestCase):
 def test_01_normalize_pdf_hyphenated_words(self):
  self.assertEqual(g.normalize('Sem- antic'), 'semantic')
 def test_02_lexical_match_correct(self):
  self.assertTrue(g.exact_entity_in_question('BGM','How does BGM improve GTR?'))
 def test_03_no_substring_match(self):
  self.assertFalse(g.exact_entity_in_question('GTR','GTRX retrieval'))
 def test_04_multiword_exact(self):
  self.assertTrue(g.exact_entity_in_question('Natural Questions','natural questions dataset'))
 def test_05_no_nonverified_entities(self):
  found=g.verified_entity_query(ENTITIES,'Unverified BGM')
  self.assertEqual([x['name'] for x in found],['BGM'])
 def test_06_entities_not_in_question(self):
  found=g.verified_entity_query(ENTITIES,'Completely unrelated words')
  self.assertEqual(found,[])
 def test_07_graph_stats(self):
  self.assertEqual(g.graph_stats(FakeDriver())['chunk_entity_links'],5)
 def test_08_graph_stats_missing_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'non enrichi'):
   g.graph_stats(FakeDriver(stats={'entity_count':0,'enriched_chunks':0,'chunk_entity_links':0}))
 def test_09_parameterized_query_only(self):
  d=FakeDriver()
  g.load_graph_matches(d,"BGM'} RETURN everything //",{r['chunk_id']:r for r in DOCS})
  sqls='\n'.join(x[0] for x in d.obj.reads)
  self.assertNotIn("BGM'}",sqls)
  self.assertIn('$keys',sqls)
 def test_10_no_graph_candidate_for_unknown_entity(self):
  es,hits,skip=g.load_graph_matches(FakeDriver(),'We discuss citation quality', {r['chunk_id']:r for r in DOCS})
  self.assertEqual((es,hits,skip),([],[],0))
 def test_11_graph_selects_exact_entity_mentions(self):
  es,hits,_=g.load_graph_matches(FakeDriver(),'BGM and GTR',{r['chunk_id']:r for r in DOCS})
  self.assertEqual([x['chunk_id'] for x in hits],['a1','a2','a3'])
  self.assertEqual(hits[0]['graph_mention_count'],2)
  self.assertEqual({x['name'] for x in es},{'BGM','GTR'})
 def test_12_filter_out_different_documents(self):
  es,hits,_=g.load_graph_matches(FakeDriver(),'BGM and GTR',{r['chunk_id']:r for r in DOCS},document_id='hal')
  self.assertEqual(hits,[])
 def test_13_skip_stale_chunk(self):
  links=LINKS+[{'chunk_id':'unknown','document_id':'acl','entity_key':'METHOD|bgm'}]
  _,hits,skipped=g.load_graph_matches(FakeDriver(links=links),'BGM',{r['chunk_id']:r for r in DOCS})
  self.assertEqual(skipped,1)
  self.assertEqual([r['chunk_id'] for r in hits],['a1','a3'])
 def test_14_skip_doc_id_mismatch(self):
  links=LINKS+[{'chunk_id':'a1','document_id':'hal','entity_key':'METHOD|bgm'}]
  _,_,skipped=g.load_graph_matches(FakeDriver(links=links),'BGM',{r['chunk_id']:r for r in DOCS})
  self.assertEqual(skipped,1)
 def test_15_limits_refuse_truncation(self):
  with self.assertRaisesRegex(RuntimeError,'tronqués'):
   g.load_graph_matches(FakeDriver(), 'BGM and GTR',{r['chunk_id']:r for r in DOCS},max_links=1)
 def test_16_graph_rrf_no_graph_preserves_baseline(self):
  base=base_report()['fused_candidates']
  out=g.graph_rrf(base,[])
  self.assertEqual([r['chunk_id'] for r in out],[r['chunk_id'] for r in base])
 def test_17_graph_rrf_promotes_overlap(self):
  base=base_report()['fused_candidates']
  graph=[{**DOCS[1],'graph_entity_keys':['MODEL|gtr'],'graph_entity_names':['GTR'],'graph_mention_count':1}]
  out=g.graph_rrf(base,graph)
  self.assertEqual(out[0]['chunk_id'],'a2')
  self.assertEqual(out[0]['graph_rank'],1)
 def test_18_graph_only_candidate_has_valid_rerank_score(self):
  base=base_report()['fused_candidates']
  graph=[{**DOCS[2],'graph_entity_keys':['METHOD|bgm'],'graph_entity_names':['BGM'],'graph_mention_count':1}]
  out=g.graph_rrf(base,graph)
  self.assertEqual(next(r['rrf_score'] for r in out if r['chunk_id']=='a3'),0.0)
 def test_19_bad_metadata_rejected(self):
  base=base_report()['fused_candidates']
  graph=[{**DOCS[0],'text':'TAMPERED','graph_entity_keys':[],'graph_entity_names':[],'graph_mention_count':0}]
  with self.assertRaisesRegex(ValueError,'incompatible'):
   g.graph_rrf(base,graph)
 def test_20_duplicate_ids_rejected(self):
  row=base_report()['fused_candidates'][0]
  with self.assertRaisesRegex(ValueError,'dupliqués'):
   g.graph_rrf([row,row],[])
 def test_21_pipeline_works_offline(self):
  r=g.build_graph_pipeline('BGM and GTR',base_report(),DOCS,FakeDriver(),3,False,
   'qwen2.5:7b','qwen2.5:7b',False,'http://fake',1)
  self.assertEqual(r['graph']['matched_entity_count'],2)
  self.assertTrue(r['graph']['graph_used'])
  self.assertEqual(r['retrieval'],'hybrid_BM25_FAISS_RRF + Neo4j_entity_mentions + rank_fusion')
  self.assertIsNone(r['generation'])
 def test_22_pipeline_fallback(self):
  r=g.build_graph_pipeline('Unrelated question',base_report(),DOCS,FakeDriver(),3,False,
   'qwen2.5:7b','qwen2.5:7b',False,'http://fake',1)
  self.assertFalse(r['graph']['graph_used'])
  self.assertEqual(r['graph']['fallback_reason'],'no_entity_in_question')
  self.assertEqual(r['hybrid_baseline_top_chunk_ids'],[x['chunk_id'] for x in r['retrieved']])
 def test_23_pipeline_generation_stub(self):
  with patch.object(g.hybrid.lexical,'ollama_answer',return_value={
      'answer':'BGM beats GTR [1]','citations_used':[1],'citation_warning':False}) as answer:
   r=g.build_graph_pipeline('BGM GTR',base_report(),DOCS,FakeDriver(),3,False,
   'qwen2.5:7b','qwen2.5:7b',True,'http://fake',1)
  self.assertEqual(r['generation']['answer'],'BGM beats GTR [1]')
  self.assertTrue(answer.called)
 def test_24_pipeline_rerank_stub(self):
  def rerank(q, candidates, *args):
   return [{**r,'rerank_relevance':3-i%4} for i,r in enumerate(candidates)]
  with patch.object(g.hybrid,'rerank_with_ollama',side_effect=rerank):
   r=g.build_graph_pipeline('BGM GTR',base_report(),DOCS,FakeDriver(),3,True,
   'qwen2.5:7b','qwen2.5:7b',False,'http://fake',1)
  self.assertTrue(all(x['rerank_relevance']>0 for x in r['retrieved']))
 def test_25_pipeline_invalid_base(self):
  b=base_report(); b['reranking']='Qwen'
  with self.assertRaisesRegex(ValueError,'sans génération'):
   g.build_graph_pipeline('BGM',b,DOCS,FakeDriver(),3,False,'qwen','qwen',False,'http://fake',1)
 def test_26_pipeline_missing_chunk_rejected(self):
  b=base_report();b['fused_candidates'][0]['chunk_id']='not-in-corpus'
  with self.assertRaisesRegex(ValueError,'différente'):
   g.build_graph_pipeline('BGM',b,DOCS,FakeDriver(),3,False,'qwen','qwen',False,'http://fake',1)
 def test_27_pipeline_zero_graph_mentions_but_entities(self):
  d=FakeDriver(links=[])
  r=g.build_graph_pipeline('BGM',base_report(),DOCS,d,3,False,
   'qwen2.5:7b','qwen2.5:7b',False,'http://fake',1)
  self.assertEqual(r['graph']['fallback_reason'],'no_matching_chunks')
 def test_28_no_db_writes_in_queries(self):
  d=FakeDriver()
  g.load_graph_matches(d,'BGM',{r['chunk_id']:r for r in DOCS})
  q=' '.join(x[0] for x in d.obj.reads).upper()
  self.assertNotIn('CREATE ',q)
  self.assertNotIn('MERGE ',q)
  self.assertNotIn('DELETE ',q)
  self.assertNotIn(' SET ',q)

if __name__=='__main__': unittest.main()
