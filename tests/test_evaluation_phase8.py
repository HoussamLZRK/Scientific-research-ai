from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluation_phase8 as ev

ROWS = [
 {'chunk_id':'a','document_id':'acl','page_number':1,'text':'BGM vs GTR.'},
 {'chunk_id':'b','document_id':'acl','page_number':2,'text':'BGM lowers costs.'},
 {'chunk_id':'c','document_id':'hal','page_number':3,'text':'Wikidata entity typing.'},
]
QUESTIONS = [
 {'id':'q1','question':'How does BGM compare to GTR?','reference_status':'provisional','reference_chunk_ids':['a']},
 {'id':'q2','question':'What is the role of Wikidata?','reference_status':'none','reference_chunk_ids':[]}
]

class EvalPhase8Tests(unittest.TestCase):
 def _load(self,obj):
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/'questions.json'
   f.write_text(json.dumps(obj),encoding='utf-8')
   return ev.read_questions(f,{'a','b','c'})
 def test_01_questions_valid(self):self.assertEqual(len(self._load(QUESTIONS)),2)
 def test_02_duplicate_questions(self):
  with self.assertRaisesRegex(ValueError,'dupliqué'):self._load(QUESTIONS+[QUESTIONS[0]])
 def test_03_empty(self):
  with self.assertRaises(ValueError):self._load([])
 def test_04_bad_reference(self):
  q=[{**QUESTIONS[0],'reference_chunk_ids':['missing']}]
  with self.assertRaisesRegex(ValueError,'absente'):self._load(q)
 def test_05_no_label_with_ref(self):
  q=[{**QUESTIONS[0],'reference_status':'none'}]
  with self.assertRaises(ValueError):self._load(q)
 def test_06_human_label_without_ref(self):
  q=[{**QUESTIONS[0],'reference_status':'human_verified','reference_chunk_ids':[]}]
  with self.assertRaises(ValueError):self._load(q)
 def test_07_bad_reference_status(self):
  q=[{**QUESTIONS[0],'reference_status':'excellent'}]
  with self.assertRaises(ValueError):self._load(q)
 def test_08_metric_all_hit(self):
  out=ev.retrieval_scores(['a','b','c'],['a'],3)
  self.assertEqual((out['precision_at_k'],out['recall_at_k'],out['hit_at_k'],out['reciprocal_rank_at_k']),(.33333,1.0,1,1.0))
 def test_09_metric_second(self):
  self.assertEqual(ev.retrieval_scores(['b','a','c'],['a'],3)['reciprocal_rank_at_k'],0.5)
 def test_10_metric_missing(self):
  self.assertEqual(ev.retrieval_scores(['b','c'],['a'],3)['hit_at_k'],0)
 def test_11_metric_multiple_references(self):
  out=ev.retrieval_scores(['b','a','c'],['a','c'],3)
  self.assertEqual(out['recall_at_k'],1.0)
 def test_12_metric_no_gold_rejected(self):
  with self.assertRaises(ValueError):ev.retrieval_scores(['a'],[],3)
 def test_13_duplicate_retrieval_rejected(self):
  with self.assertRaises(ValueError):ev.retrieval_scores(['a','a'],['a'],3)
 def test_14_analytics_consistent(self):
  structural={'summary':{'total_nodes':7,'total_relations':5,'components':2,
    'node_counts':{'SRAIPublication':1,'SRAIAuthorMention':1,'SRAIDocument':2,'SRAIChunk':3},
    'relation_counts':{'HAS_AUTHOR_MENTION':1,'HAS_CHUNK':3,'something':1}}}
  # Inconsistent because sum relations=5 but provenance layout includes an unknown edge.
  summary=ev.verify_analytics(structural,None,3)
  self.assertTrue(summary['checks_all_passed'])
 def test_15_analytics_bad_chunks(self):
  s={'summary':{'total_nodes':1,'total_relations':0,'components':1,'node_counts':{'SRAIChunk':1},'relation_counts':{}}}
  result=ev.verify_analytics(s,None,3)
  self.assertFalse(result['checks_all_passed'])
 def test_16_analytics_missing(self):
  self.assertFalse(ev.verify_analytics(None,None,3)['checks_all_passed'])
 def test_17_diagnostic_provisional_is_separate(self):
  result=[{'id':'q1','modes':{'RAG BM25':{'status':'ok','elapsed_seconds':1.1,'retrieved_chunk_ids':['a'],
           'distinct_documents':1,'metrics':ev.retrieval_scores(['a'],['a'],3)}}}]
  out=ev.calculate_report(QUESTIONS[:1],result,['RAG BM25'],3,{},False,False)
  self.assertIn('provisional',out['summaries']['RAG BM25']['reference_metrics'])
  self.assertNotIn('human_verified',out['summaries']['RAG BM25']['reference_metrics'])
 def test_18_no_fake_scores_on_unlabeled(self):
  result=[{'id':'q2','modes':{'RAG BM25':{'status':'ok','elapsed_seconds':1.1,'retrieved_chunk_ids':['a'],
           'distinct_documents':1,'metrics':None}}}]
  out=ev.calculate_report(QUESTIONS[1:],result,['RAG BM25'],3,{},False,False)
  self.assertEqual(out['summaries']['RAG BM25']['reference_metrics'],{})
 def test_19_offline_integration(self):
  def fake_runner(**kwargs):
   return {'retrieved':ROWS[:2],'generation':None,'ui_elapsed_seconds':0.02,'graph':{'graph_used':True,'novel_chunk_count':0}}
  with patch.object(ev.backend.lexical,'load_chunks',return_value=ROWS),\
       patch.object(ev.backend,'load_optional_report',return_value=None):
   output=ev.evaluate(QUESTIONS,list(ev.MODE_NAMES),3,6,'pw',runner=fake_runner)
  self.assertEqual(len(output['questions']),2)
  self.assertEqual(output['summaries']['GraphRAG Neo4j']['questions_with_graph_hits'],2)
 def test_20_partial_failure_not_hidden(self):
  def broken(**kw):
   if kw['mode']=='GraphRAG Neo4j':raise ConnectionError('offline')
   return {'retrieved':ROWS[:1],'ui_elapsed_seconds':0.01}
  with patch.object(ev.backend.lexical,'load_chunks',return_value=ROWS),\
       patch.object(ev.backend,'load_optional_report',return_value=None):
   out=ev.evaluate(QUESTIONS[:1],list(ev.MODE_NAMES),runner=broken)
  self.assertEqual(out['summaries']['GraphRAG Neo4j']['failed_questions'],1)
 def test_21_unknown_modes_rejected(self):
  with self.assertRaises(ValueError):ev.evaluate(QUESTIONS,['FAKE'],runner=lambda **kw:None)
 def test_22_bad_k_rejected(self):
  with self.assertRaises(ValueError):ev.evaluate(QUESTIONS,['RAG BM25'],5,3,runner=lambda **kw:None)
 def test_23_source_ids_unique(self):
  def wrong(**kw):return {'retrieved':[ROWS[0],ROWS[0]],'ui_elapsed_seconds':0.1}
  with patch.object(ev.backend.lexical,'load_chunks',return_value=ROWS),\
       patch.object(ev.backend,'load_optional_report',return_value=None):
   out=ev.evaluate(QUESTIONS[:1],['RAG BM25'],runner=wrong)
  self.assertEqual(out['summaries']['RAG BM25']['failed_questions'],1)
 def test_24_no_answers_marked_human_verified(self):
  def fake(**kw):return {'retrieved':ROWS[:1], 'ui_elapsed_seconds':0.01,'generation':{'answer':'BGM [1]','citations_used':[1]}}
  with patch.object(ev.backend.lexical,'load_chunks',return_value=ROWS),\
       patch.object(ev.backend,'load_optional_report',return_value=None):
   out=ev.evaluate(QUESTIONS[:1],['RAG BM25'],generate=True,runner=fake)
  self.assertFalse(out['questions'][0]['modes']['RAG BM25']['answer_human_verified'])

if __name__=='__main__':unittest.main()
