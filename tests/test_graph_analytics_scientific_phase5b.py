"""Unit tests; no live Neo4j required."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'graph_analytics_scientific_phase5b.py'
spec=importlib.util.spec_from_file_location('phase5b',SCRIPT)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


def sample():
    return [
        {'status':'ok','chunk_id':'d1_p001_c001','document_id':'d1','model':'qwen2.5:7b','entities':[
            {'id':'E1','name':'DPR','type':'MODEL','evidence':'DPR is a model.'},
            {'id':'E2','name':'Natural Questions','type':'DATASET','evidence':'Natural Questions is a dataset.'}],
         'relations':[{'subject':'DPR','predicate':'EVALUATED_ON','object':'Natural Questions'}]},
        {'status':'ok','chunk_id':'d2_p001_c001','document_id':'d2','entities':[
            {'id':'E1','name':'DPR','type':'MODEL','evidence':'DPR is discussed here.'},
            {'id':'E2','name':'TriviaQA','type':'DATASET','evidence':'TriviaQA is a dataset.'}]}
    ]


class Tests(unittest.TestCase):
    def test_entities_and_mentions(self):
        es,ms=mod.build_records(sample());self.assertEqual((len(es),len(ms)),(3,4))
    def test_co_mentions_are_not_facts(self):
        es,ms=mod.build_records(sample());report=mod.measure(es,ms)
        self.assertEqual(report['summary']['co_mention_pairs'],2)
        self.assertIn('not_scientific_facts',report['summary']['scope'])
    def test_entity_ranking(self):
        es,ms=mod.build_records(sample());r=mod.measure(es,ms)
        self.assertEqual(r['entity_ranking'][0]['entity'],'DPR')
        self.assertEqual(r['entity_ranking'][0]['chunks_mentioning'],2)
    def test_duplicate_chunks_rejected(self):
        x=sample();x.append(x[0]);
        with self.assertRaises(ValueError):mod.build_records(x)
    def test_duplicate_entity_ids_rejected(self):
        x=sample();x[0]['entities'][1]['id']='E1'
        with self.assertRaises(ValueError):mod.build_records(x)
    def test_invalid_entity_type_rejected(self):
        x=sample();x[0]['entities'][0]['type']='OTHER'
        with self.assertRaises(ValueError):mod.build_records(x)
    def test_name_without_evidence_rejected(self):
        x=sample();x[0]['entities'][0]['evidence']='No entity here'
        with self.assertRaises(ValueError):mod.build_records(x)
    def test_pdf_hyphenation_is_supported(self):
        x=sample()
        x[0]['entities'][1]['name']='Natural Questions'
        x[0]['entities'][1]['evidence']='Natural Ques- tions is a dataset.'
        self.assertEqual(len(mod.build_records(x)[1]),4)
    def test_empty_extraction_rejected(self):
        with self.assertRaises(ValueError):mod.build_records([])
    def test_dry_run_does_not_touch_neo4j(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'input.jsonl';p.write_text('\n'.join(json.dumps(r) for r in sample()),encoding='utf8')
            self.assertEqual(mod.main(['--dry-run','--input',str(p)]),0)
    def test_no_import_on_dry_run(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'input.jsonl';p.write_text('\n'.join(json.dumps(r) for r in sample()),encoding='utf8')
            with patch.object(mod,'neo4j_import',side_effect=AssertionError('unexpected')):
                self.assertEqual(mod.main(['--dry-run','--input',str(p)]),0)

if __name__=='__main__':unittest.main()
