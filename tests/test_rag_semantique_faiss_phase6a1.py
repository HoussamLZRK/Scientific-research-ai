"""Tests indépendants du modèle Ollama réel; incluent un faux index FAISS pour le protocole d'indexation."""
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import rag_semantique_faiss_phase6a1 as mod

FIXTURE = [
    {"chunk_id": "acl_p001_c001", "document_id": "acl", "page_number": 1,
     "text": "BGM improves retrieval over GTR by better passage selection."},
    {"chunk_id": "hal_p001_c001", "document_id": "hal", "page_number": 1,
     "text": "WiKC and Wikidata taxonomy for entity typing."},
    {"chunk_id": "pmlr_p002_c001", "document_id": "pmlr", "page_number": 2,
     "text": "NaturalQuestions and TriviaQA datasets for evaluating retrieval."},
]

class FakeIndex:
    def __init__(self, d):
        self.d = d
        self.matrix = np.empty((0,d), dtype=np.float32)
        self.ntotal = 0
    def add(self, mat):
        self.matrix = np.vstack([self.matrix, mat])
        self.ntotal = len(self.matrix)
    def search(self, q, n):
        scores = self.matrix @ q.T
        order = np.argsort(-scores[:, 0])[:n]
        return scores[order, 0].reshape(1,-1), order.astype('int64').reshape(1,-1)

class FakeFaiss:
    IndexFlatIP = FakeIndex
    @staticmethod
    def write_index(index, path):
        with open(path, 'wb') as f:
            np.save(f, index.matrix)
    @staticmethod
    def read_index(path):
        with open(path, 'rb') as f:
            mat = np.load(f)
        idx = FakeIndex(mat.shape[1]);idx.add(mat)
        return idx

class Phase6A1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'chunks.jsonl'
        self.source.write_text('\n'.join(json.dumps(row) for row in FIXTURE)+'\n',encoding='utf-8')
        self.folder = self.root/'faiss'

    def test_valid_chunks(self):
        self.assertEqual(len(mod.load_chunks(self.source)),3)
    def test_duplicate_chunk_rejected(self):
        with self.source.open('a', encoding='utf-8') as f: f.write(json.dumps(FIXTURE[0])+'\n')
        with self.assertRaisesRegex(ValueError,'dupliqué'):mod.load_chunks(self.source)
    def test_missing_page_rejected(self):
        r = dict(FIXTURE[0]);r.pop('page_number')
        self.source.write_text(json.dumps(r))
        with self.assertRaises(ValueError):mod.load_chunks(self.source)
    def test_blank_input_rejected(self):
        self.source.write_text(' \n',encoding='utf-8')
        with self.assertRaises(ValueError):mod.load_chunks(self.source)
    def test_normalization(self):
        mat = mod.validate_vectors([[3,4],[1,0]],2)
        np.testing.assert_allclose(np.linalg.norm(mat,axis=1),np.array([1.,1.]),atol=1e-6)
    def test_dimension_mismatch(self):
        with self.assertRaises(ValueError):mod.validate_vectors([[1,0],[0,1]],2,3)
    def test_nan_rejected(self):
        with self.assertRaises(ValueError):mod.validate_vectors([[float('nan'),1.]],1)
    def test_zero_rejected(self):
        with self.assertRaises(ValueError):mod.validate_vectors([[0.,0.]],1)
    def test_embed_request_format(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):return False
        def urlopen(req,timeout):
            payload = json.loads(req.data)
            self.assertEqual(payload['model'],'nomic-embed-text')
            self.assertEqual(payload['input'],['A','B'])
            self.assertIs(payload['truncate'],False)
            self.assertEqual(req.full_url,mod.ENDPOINT)
            return Response()
        with patch.object(mod.urllib.request,'urlopen',side_effect=urlopen), patch.object(mod.json,'load',return_value={'embeddings':[[3,4],[5,12]]}):
            out = mod.embed_texts(['A','B'],'nomic-embed-text',mod.ENDPOINT,5)
        self.assertEqual(out.shape,(2,2))
    def test_embed_missing_key(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):return False
        with patch.object(mod.urllib.request,'urlopen',return_value=Response()), patch.object(mod.json,'load',return_value={'embedding':[1,2]}):
            with self.assertRaises(RuntimeError):mod.embed_texts(['A'],'m',mod.ENDPOINT,5)
    def build_fixture(self):
        array = np.asarray([[1.,0.],[0.,1.],[.8,.6]],dtype=np.float32)
        def fake_embed(texts, model, endpoint, timeout):
            if len(texts)==2: return array[:2]
            if len(texts)==1: return array[2:]
            raise AssertionError('unexpected batch length')
        with patch.object(mod,'get_faiss',return_value=FakeFaiss), patch.object(mod,'embed_texts',side_effect=fake_embed):
            return mod.build_index(self.source,self.folder,'nomic-embed-text',mod.ENDPOINT,2,5)
    def test_build_index_and_check(self):
        meta = self.build_fixture()
        self.assertEqual(meta['chunk_count'],3)
        self.assertTrue((self.folder/'index.faiss').is_file())
        with patch.object(mod,'get_faiss',return_value=FakeFaiss):
            idx, rows, report = mod.read_index(self.source,self.folder,'nomic-embed-text')
        self.assertEqual(idx.ntotal,3)
        self.assertEqual(len(rows),3)
    def test_search_and_document_filter(self):
        self.build_fixture()
        with patch.object(mod,'get_faiss',return_value=FakeFaiss):
            idx,rows,_ = mod.read_index(self.source,self.folder,'nomic-embed-text')
        results = mod.semantic_search(idx,rows,np.array([[1.,0.]],dtype=np.float32),2)
        self.assertEqual(results[0]['chunk_id'],'acl_p001_c001')
        filtered = mod.semantic_search(idx,rows,np.array([[1.,0.]],dtype=np.float32),2,'hal')
        self.assertEqual(len(filtered),1)
        self.assertEqual(filtered[0]['document_id'],'hal')
    def test_stale_index_rejected(self):
        self.build_fixture()
        with self.source.open('a',encoding='utf-8') as f:f.write('\n')
        with self.assertRaisesRegex(ValueError,'changé'):
            mod.read_index(self.source,self.folder,'nomic-embed-text')
    def test_wrong_model_rejected(self):
        self.build_fixture()
        with self.assertRaisesRegex(ValueError,'Modèle'):
            mod.read_index(self.source,self.folder,'other-model')
    def test_bad_index_hash_rejected(self):
        self.build_fixture()
        with (self.folder/'index.faiss').open('ab') as f:f.write(b'X')
        with self.assertRaisesRegex(ValueError,'modifiés'):
            mod.read_index(self.source,self.folder,'nomic-embed-text')
    def test_dry_run_no_ollama_no_files_written(self):
        with patch.object(mod,'embed_texts',side_effect=AssertionError('Ollama forbidden')), patch.object(mod,'get_faiss',side_effect=AssertionError('FAISS forbidden')):
            self.assertEqual(mod.run_cli(['--input',str(self.source),'--index-dir',str(self.folder),'--dry-run']),0)
        self.assertFalse(self.folder.exists())
    def test_search_invalid_k(self):
        idx = FakeIndex(2);idx.add(np.eye(2,dtype=np.float32))
        with self.assertRaises(ValueError):
            mod.semantic_search(idx,FIXTURE,np.asarray([[1,0]],dtype=np.float32),0)

if __name__ == '__main__': unittest.main()
