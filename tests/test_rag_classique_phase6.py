"""Tests unitaires Phase 6A, hors ligne (Ollama non requis)."""
import json
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import rag_classique_phase6 as rag

FIXTURE=[
 {'chunk_id':'acl_p001_c001','document_id':'acl','page_number':1,'text':'Retrieval augmented generation retrieves passages from a corpus to improve factual answers.'},
 {'chunk_id':'pmlr_p002_c001','document_id':'pmlr','page_number':2,'text':'NaturalQuestions and TriviaQA are datasets used to evaluate retrieval methods.'},
 {'chunk_id':'hal_p003_c001','document_id':'hal','page_number':3,'text':'Wikidata instances are used in entity typing evaluation for WiKC.'},
 {'chunk_id':'acl_p002_c001','document_id':'acl','page_number':2,'text':'The BGM approach improves GTR performance on three datasets.'}
]
class RagClassicTests(unittest.TestCase):
 def test_tokenize_accents_hyphens(self):
  self.assertIn('recherche',rag.tokenize('Recherche basée sur dédoublonnage'))
  self.assertIn('natural',rag.tokenize('Natural-Questions'))
 def test_bm25_find_naturalquestions(self):
  r=rag.BM25(FIXTURE).search('Which datasets evaluate retrieval methods?',k=2)
  self.assertEqual(r[0]['document_id'],'pmlr')
 def test_bm25_find_bgm(self):
  self.assertEqual(rag.BM25(FIXTURE).search('Does BGM improve GTR?',3)[0]['chunk_id'],'acl_p002_c001')
 def test_bm25_no_match(self):
  self.assertEqual(rag.BM25(FIXTURE).search('elephant underwater quantum teleportation'),[])
 def test_bm25_stopwords(self):
  self.assertEqual(rag.BM25(FIXTURE).search('the of with'),[])
 def test_bm25_filter_document(self):
  r=rag.BM25(FIXTURE).search('retrieval',document_id='acl')
  self.assertTrue(all(x['document_id']=='acl' for x in r))
 def test_bm25_reject_invalid_k(self):
  with self.assertRaises(ValueError): rag.BM25(FIXTURE).search('retrieval',k=0)
 def test_context_sources(self):
  s=rag.source_context([FIXTURE[1]])
  self.assertIn('[SOURCE 1]',s)
  self.assertIn('pmlr_p002_c001',s)
 def test_no_generation_on_empty_passages(self):
  out=rag.ollama_answer('test',[],'qwen2.5:7b',rag.OLLAMA_URL,5)
  self.assertIn('insuffisante',out['answer'])
 def test_prompt_disallows_unsourced(self):
  msgs=rag.build_messages('Question',[FIXTURE[0]])
  self.assertIn('N\'invente pas',msgs[0]['content'])
 def test_loader_rejects_duplicate(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c.jsonl';p.write_text('\n'.join(json.dumps(FIXTURE[0]) for _ in range(2)),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'Doublon'):rag.load_chunks(p)
 def test_loader_rejects_missing_page(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c.jsonl';p.write_text(json.dumps({'chunk_id':'x','document_id':'d','text':'hi'}),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'obligatoires'):rag.load_chunks(p)
 def test_loader_valid(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c.jsonl';p.write_text('\n'.join(json.dumps(v) for v in FIXTURE),encoding='utf-8')
   self.assertEqual(len(rag.load_chunks(p)),4)
 def test_cli_retrieval_only_no_ollama(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c.jsonl';p.write_text('\n'.join(json.dumps(v) for v in FIXTURE),encoding='utf-8')
   with patch.object(rag,'ollama_answer',side_effect=AssertionError('Ollama should not be called')):
    self.assertEqual(rag.run_cli(['--input',str(p),'--question','BGM GTR','--retrieval-only']),0)
 def test_fake_citation_rejected(self):
  class Dummy:
   def __enter__(self):return self
   def __exit__(self,*args):pass
  with patch.object(rag.urllib.request,'urlopen',return_value=Dummy()):
   with patch.object(rag.json,'load',return_value={'message':{'content':'False [2]'}}):
    with self.assertRaisesRegex(RuntimeError,'inexistants'):
     rag.ollama_answer('test',[FIXTURE[0]],'qwen2.5:7b',rag.OLLAMA_URL,10)

if __name__=='__main__':unittest.main()
