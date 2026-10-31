"""Unit tests offline, no real Ollama, FAISS, or Neo4j connection."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import rag_hybride_phase6a2 as m

ROWS = [
 {'chunk_id':'a1','document_id':'acl','page_number':1,'text':'BGM improves GTR using better passage selection.','title':'acl'},
 {'chunk_id':'a2','document_id':'acl','page_number':2,'text':'GTR retrieves passages for QA tasks.','title':'acl'},
 {'chunk_id':'h1','document_id':'hal','page_number':3,'text':'WiKC uses Wikidata for taxonomy entity typing.','title':'hal'},
 {'chunk_id':'p1','document_id':'pmlr','page_number':1,'text':'NaturalQuestions and TriviaQA datasets.','title':'pmlr'},
]

def hits(ids,method):
 return [{**next(r for r in ROWS if r['chunk_id']==cid), 'score':2.5 if method=='bm25' else 0.8} for cid in ids]

class PipelineTests(unittest.TestCase):
 def test_rrf_ranks_only(self):
  out=m.rrf_fusion(hits(['a1','a2'],'bm25'),hits(['a2','h1'],'faiss'))
  self.assertEqual(out[0]['chunk_id'],'a2')
  self.assertEqual(out[0]['bm25_rank'],2)
  self.assertEqual(out[0]['faiss_rank'],1)
  self.assertIsNotNone(out[0]['bm25_score'])
  self.assertIsNotNone(out[0]['cosine_score'])
 def test_rrf_tie_deterministic(self):
  out=m.rrf_fusion(hits(['a1'],'bm25'),hits(['h1'],'faiss'))
  self.assertEqual([r['chunk_id'] for r in out],['a1','h1'])
 def test_rrf_deduplicates_overlap(self):
  self.assertEqual(len(m.rrf_fusion(hits(['a1'],'bm25'),hits(['a1'],'faiss'))),1)
 def test_rrf_rejects_duplicate_within_method(self):
  with self.assertRaisesRegex(ValueError,'dupliqué'):
   m.rrf_fusion(hits(['a1','a1'],'bm25'),[])
 def test_rrf_rejects_inconsistent_text(self):
  bad=hits(['a1'],'faiss');bad[0]['text']='UNRELATED'
  with self.assertRaisesRegex(ValueError,'contradictoires'):
   m.rrf_fusion(hits(['a1'],'bm25'),bad)
 def test_rrf_invalid_limits(self):
  with self.assertRaises(ValueError):m.rrf_fusion([],[],limit=0)
 def test_rerank_schema_has_dynamic_ids(self):
  payload=m.make_rerank_payload('Which method?',hits(['a1','h1'],'bm25'),'qwen2.5:7b')
  schema=payload['format']['properties']['scores']['items']['properties']['chunk_id']
  self.assertEqual(schema['enum'],['a1','h1'])
  self.assertEqual(payload['options']['temperature'],0)
 def test_rerank_reorders_by_relevance(self):
  items=m.rrf_fusion(hits(['a1','h1'],'bm25'),[])
  reply={'message':{'content':json.dumps({'scores':[{'chunk_id':'h1','relevance':3},{'chunk_id':'a1','relevance':0}]})}}
  ranked=m.parse_reranking(reply,items)
  self.assertEqual(ranked[0]['chunk_id'],'h1')
  self.assertEqual(ranked[-1]['rerank_relevance'],0)
 def test_rerank_rejects_wrong_id(self):
  reply={'message':{'content':json.dumps({'scores':[{'chunk_id':'unknown','relevance':3}]})}}
  with self.assertRaises(ValueError):m.parse_reranking(reply,hits(['a1'],'bm25'))
 def test_rerank_rejects_duplicate_id(self):
  reply={'message':{'content':json.dumps({'scores':[{'chunk_id':'a1','relevance':3},{'chunk_id':'a1','relevance':0}]})}}
  with self.assertRaises(ValueError):m.parse_reranking(reply,hits(['a1','h1'],'bm25'))
 def test_rerank_rejects_missing_id(self):
  reply={'message':{'content':json.dumps({'scores':[{'chunk_id':'a1','relevance':3}]})}}
  with self.assertRaises(ValueError):m.parse_reranking(reply,hits(['a1','h1'],'bm25'))
 def test_rerank_rejects_float_score(self):
  reply={'message':{'content':json.dumps({'scores':[{'chunk_id':'a1','relevance':2.5}]})}}
  with self.assertRaises(ValueError):m.parse_reranking(reply,hits(['a1'],'bm25'))
 def test_rerank_rejects_bad_json(self):
  with self.assertRaises(ValueError):m.parse_reranking({'message':{'content':'not json'}},hits(['a1'],'bm25'))
 def test_query_mismatch_disallowed(self):
  class Idx: d=2;ntotal=4
  with patch.object(m.lexical,'load_chunks',return_value=ROWS),patch.object(m.semantic,'read_index',return_value=(Idx(),ROWS[:-1],{'dimension':2})):
   with self.assertRaisesRegex(ValueError,'incohérents'):
    self._run()
 def test_pipeline_offline_hybrid(self):
  with self.patched_sources():
   with patch.object(m,'rerank_with_ollama',side_effect=AssertionError('rerank called')) as reranker,patch.object(m.lexical,'ollama_answer',side_effect=AssertionError('generation called')):
    report=self._run()
  self.assertEqual(report['corpus_chunks'],4)
  self.assertEqual(len(report['retrieved']),2)
  self.assertEqual(report['retrieval_methods'],['BM25','FAISS_cosine'])
  self.assertIsNone(report['generation'])
 def test_pipeline_offline_rerank(self):
  with self.patched_sources():
   with patch.object(m,'rerank_with_ollama',side_effect=lambda q,c,*args:[{**row,'rerank_relevance':3-i} for i,row in enumerate(c[::-1])]):
    report=self._run(rerank=True)
  self.assertEqual(report['reranking'],'Qwen relevance 0..3')
  self.assertIn('rerank_relevance',report['retrieved'][0])
 def test_pipeline_generation_stub(self):
  with self.patched_sources():
   with patch.object(m.lexical,'ollama_answer',return_value={'answer':'BGM [1]','citations_used':[1],'citation_warning':False}):
    report=self._run(gen=True)
  self.assertEqual(report['generation']['answer'],'BGM [1]')
 def test_pipeline_rejects_k_exceed_candidates(self):
  with self.assertRaises(ValueError):self._run(top_k=5,candidates_k=4)
 def _run(self,rerank=False,gen=False,top_k=2,candidates_k=2):
  return m.run_pipeline('BGM compared with GTR',Path('/fake/source'),Path('/fake/index'),'nomic-embed-text',top_k,candidates_k,rerank,'qwen2.5:7b','qwen2.5:7b',gen,'http://fake/embed','http://fake/chat',5)
 from contextlib import contextmanager
 @contextmanager
 def patched_sources(self):
  class Idx: d=2;ntotal=4
  with patch.object(m.lexical,'load_chunks',return_value=ROWS),\
       patch.object(m.semantic,'read_index',return_value=(Idx(),ROWS,{'dimension':2})),\
       patch.object(m.lexical.BM25,'search',return_value=hits(['a1','a2'],'bm25')),\
       patch.object(m.semantic,'embed_texts',return_value=np.array([[1.,0.]],dtype=np.float32)),\
       patch.object(m.semantic,'semantic_search',return_value=hits(['a2','h1'],'faiss')):
    yield

if __name__=='__main__':unittest.main()
