"""Unit tests for the Phase 7 adapter. No Neo4j/Ollama/FAISS server required."""
from pathlib import Path
import sys
import tempfile
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import streamlit_phase7_backend as core

ROWS=[
 {'chunk_id':'acl_p1_c1','document_id':'acl','page_number':1,'text':'BGM improves retrieval.','title':'ACL'},
 {'chunk_id':'acl_p1_c2','document_id':'acl','page_number':1,'text':'GTR is another method.','title':'ACL'},
 {'chunk_id':'hal_p3_c1','document_id':'hal','page_number':3,'text':'Wikidata typing.','title':'HAL'},
]

class StreamlitBackendTests(unittest.TestCase):
 def test_01_overview_counts(self):
  m=core.corpus_overview(ROWS)
  self.assertEqual((m['chunks'],m['documents'],m['pages_represented']),(3,2,2))
 def test_02_reports_missing(self):
  self.assertIsNone(core.load_optional_report(Path('/xxyyzz/nonexistent.json')))
 def test_03_reports_valid(self):
  with tempfile.TemporaryDirectory() as td:
   file=Path(td)/'a.json';file.write_text('{"summary":{"total_nodes":360}}')
   self.assertEqual(core.load_optional_report(file)['summary']['total_nodes'],360)
 def test_04_reports_wrong_type_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   file=Path(td)/'a.json';file.write_text('[1,2]')
   with self.assertRaises(ValueError):core.load_optional_report(file)
 def test_05_query_rejects_invalid_mode(self):
  with self.assertRaises(ValueError):core.validate_request('Fake','question',3,6,None)
 def test_06_query_rejects_blank(self):
  with self.assertRaises(ValueError):core.validate_request('RAG BM25','  ',3,6,None)
 def test_07_query_rejects_long(self):
  with self.assertRaises(ValueError):core.validate_request('RAG BM25','x'*701,3,6,None)
 def test_08_query_rejects_candidates(self):
  with self.assertRaises(ValueError):core.validate_request('GraphRAG Neo4j','question',7,6,None)
 def test_09_query_accepts_bm25_independent_candidate_k(self):
  self.assertEqual(core.validate_request('RAG BM25',' hi ',3,1,None),'hi')
 def test_10_query_bm25_does_not_contact_neo4j(self):
  with patch.object(core.lexical,'load_chunks',return_value=ROWS),\
       patch.object(core.lexical.BM25,'search',return_value=ROWS[:1]),\
       patch.object(core.lexical,'ollama_answer',return_value={'answer':'BGM [1]','citations_used':[1]}) as llm,\
       patch.object(core.graph,'neo4j_driver',side_effect=AssertionError('Must not call Neo4j')):
   out=core.run_query(mode='RAG BM25',question='BGM?',generate=True)
  self.assertEqual(out['generation']['answer'],'BGM [1]')
  self.assertEqual(len(out['retrieved']),1)
  llm.assert_called_once()
 def test_11_query_bm25_retrieval_only_no_llm(self):
  with patch.object(core.lexical,'load_chunks',return_value=ROWS),\
       patch.object(core.lexical.BM25,'search',return_value=ROWS[:1]),\
       patch.object(core.lexical,'ollama_answer',side_effect=AssertionError('No generation')):
   out=core.run_query(mode='RAG BM25',question='BGM?',generate=False)
  self.assertIsNone(out['generation'])
 def test_12_hybrid_uses_original_pipeline(self):
  out={'retrieved':ROWS[:1],'generation':None,'pipeline':'rag_hybride_phase6a2'}
  with patch.object(core.hybrid,'run_pipeline',return_value=out) as p:
   got=core.run_query(mode='RAG hybride',question='BGM?',generate=False)
  self.assertEqual(got['ui_mode'],'RAG hybride')
  self.assertTrue(p.called)
 def test_13_graph_requires_password(self):
  with self.assertRaisesRegex(ValueError,'Mot de passe'):
   core.run_query(mode='GraphRAG Neo4j',question='BGM?',neo4j_password=None)
 def test_14_graph_executes_existing_pipeline(self):
  drv=MagicMock();drv.__enter__.return_value=drv
  base={'fused_candidates':ROWS,'timing_seconds':{'retrieval':0.17}}
  graph_out={'retrieved':ROWS[:1],'generation':None,'graph':{'matched_entity_count':1},'timing_seconds':{'reranking':0.0,'generation':0.0}}
  with patch.object(core.graph,'neo4j_driver',return_value=drv),\
       patch.object(core.graph,'graph_stats',return_value={'entity_count':46,'enriched_chunks':9,'chunk_entity_links':55}),\
       patch.object(core.hybrid,'run_pipeline',return_value=base),\
       patch.object(core.lexical,'load_chunks',return_value=ROWS),\
       patch.object(core.graph,'build_graph_pipeline',return_value=graph_out) as pipeline:
   result=core.run_query(mode='GraphRAG Neo4j',question='BGM GTR?',neo4j_password='secret',generate=False)
  self.assertEqual(result['graph']['database_counts']['entity_count'],46)
  self.assertTrue(pipeline.called)
 def test_15_source_rows_friendly(self):
  rows=core.source_rows({'retrieved':[{**ROWS[0],'rrf_score':0.032261,'rerank_relevance':3}]})
  self.assertEqual((rows[0]['Score de classement'],rows[0]['Note reranking']),(0.03226,3))
 def test_16_dot_escapes_labels(self):
  label='x"; y -> z; //'
  dot=core.make_dot(label,[{**ROWS[0],'document_id':label}],[])
  self.assertIn('x\\";',dot)
  self.assertIn('HAS_CHUNK',dot)
 def test_17_dot_shows_actual_links(self):
  dot=core.make_dot('acl',ROWS[:2],[{'chunk_id':'acl_p1_c1','entity_key':'METHOD|bgm','name':'BGM','kind':'METHOD'}])
  self.assertIn('MENTIONS_ENTITY',dot)
  self.assertNotIn('IMPROVES',dot)
 def test_18_dot_does_not_invent_links(self):
  dot=core.make_dot('hal',ROWS[:2],[])
  self.assertNotIn('MENTIONS_ENTITY',dot)
 def test_19_faiss_missing(self):
  with tempfile.TemporaryDirectory() as td,patch.object(core.semantic,'INDEX_DIR',Path(td)):
   self.assertFalse(core.faiss_status()['available'])
 def test_20_faiss_manifest(self):
  with tempfile.TemporaryDirectory() as td,patch.object(core.semantic,'INDEX_DIR',Path(td)):
   (Path(td)/'manifest.json').write_text(json.dumps({'chunk_count':263,'dimension':768,'model':'nomic-embed-text'}))
   self.assertEqual(core.faiss_status()['chunks'],263)
 def test_21_preview_parameterized(self):
  class FakeSession:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def run(self, query,**params):
    self.assertQuery(query,params)
    if 'HAS_CHUNK' in query:return ROWS[:2]
    return [{'chunk_id':ROWS[0]['chunk_id'],'name':'BGM','entity_key':'METHOD|bgm','kind':'METHOD'}]
   def assertQuery(self,query,params):
    assert '$document' in query or '$ids' in query
    assert 'acl' not in query
  drv=MagicMock();drv.session.return_value=FakeSession()
  found,mentions=core.graph_preview_rows(drv,'acl')
  self.assertEqual(len(found),2)
  self.assertEqual(mentions[0]['name'],'BGM')
 def test_22_does_not_mutate_report_in_hybrid(self):
  raw={'retrieved':ROWS[:1],'generation':None}
  with patch.object(core.hybrid,'run_pipeline',return_value=raw):
   core.run_query(mode='RAG hybride',question='What is BGM?',generate=False)
  self.assertNotIn('ui_mode',raw)
 def test_23_invalid_filter(self):
  with self.assertRaises(ValueError):core.validate_request('RAG BM25','hi',1,6,' ')
 def test_24_invalid_dot_limit(self):
  with self.assertRaises(ValueError):core.make_dot('acl',ROWS,[],21)

if __name__=='__main__':unittest.main()
