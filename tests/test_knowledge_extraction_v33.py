"""V3.3 unit tests: no local Ollama required."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import extract_scientific_knowledge_v33 as m


class ExtractionV33Tests(unittest.TestCase):
    def setUp(self):
        self.chunks=[]
        for doc in ('a','b'):
            for page in range(1,7):
                s='We evaluated Retriever on NaturalQuestions in experiments. '+('Results show accuracy. '*20 if page == 3 else '')
                if page==1: s='References. '+('A citation. '*60)
                self.chunks.append({'document_id':doc,'chunk_id':f'{doc}_p{page}',
                                    'page_number':page,'text':s,'title':'Test'})

    def test_selection_is_deterministic_no_duplicates(self):
        a=m.select_passages(self.chunks,2,3,'expanded')
        b=m.select_passages(self.chunks,2,3,'expanded')
        self.assertEqual([x['chunk_id'] for x in a],[x['chunk_id'] for x in b])
        self.assertEqual(len(a),6)
        self.assertEqual(len({x['chunk_id'] for x in a}),6)

    def test_expanded_includes_exact_v32_baseline(self):
        baseline={x['chunk_id'] for x in m.select_passages(self.chunks,2,3,'baseline')}
        expanded={x['chunk_id'] for x in m.select_passages(self.chunks,2,3,'expanded')}
        self.assertTrue(baseline.issubset(expanded))

    def test_baseline_one_chunk_per_document(self):
        self.assertEqual(len(m.select_passages(self.chunks,2,3,'baseline')),2)

    def test_selection_rejects_oversized_and_invalid(self):
        for n in (0,6):
            with self.assertRaises(ValueError):m.select_passages(self.chunks,2,n)
        with self.assertRaises(ValueError):m.select_passages(self.chunks,2,3,'typo')
        with self.assertRaises(ValueError):m.select_passages(self.chunks,5,3)

    def test_selection_prefers_relevant_passages(self):
        high=m.score_chunk({'text':'We evaluated OurModel on DatasetQ. Results report exact match and accuracy.'})[0]
        low=m.score_chunk({'text':'References. Bibliography. Author and year.'})[0]
        self.assertGreater(high,low)

    def test_output_names_distinct_for_modes_models(self):
        p1=m.output_paths('qwen2.5:7b','baseline')
        p2=m.output_paths('qwen2.5:7b','expanded')
        p3=m.output_paths('qwen2.5:3b','expanded')
        self.assertEqual(len(p1),4)
        self.assertTrue(all(x!=y for x,y in zip(p1,p2)))
        self.assertTrue(all(x!=y for x,y in zip(p2,p3)))

    def test_prompts_retain_type_semantics_and_negative_examples(self):
        self.assertIn('training data',m.ENTITY_PROMPT)
        self.assertIn('NOT evaluated',m.RELATION_PROMPT)
        self.assertIn('EVALUATED_ON',m.RELATION_PROMPT)

    def test_two_stage_extraction_uses_dynamic_evidence_and_ids(self):
        responses=iter([
            {'entities':[{'name':'Retriever','type':'MODEL','evidence_id':'P1'},
                         {'name':'NaturalQuestions','type':'DATASET','evidence_id':'P1'}]},
            {'relations':[{'subject_id':'E1','predicate':'EVALUATED_ON','object_id':'E2','evidence_id':'P1'}]}
        ])
        schemas=[]
        def fake(base,model,schema,prompt,timeout):
            schemas.append(schema)
            return next(responses)
        with patch.object(m.v3,'chat_structured',side_effect=fake):
            out=m.extract_chunk('http://127.0.0.1:11434','mock',
                                {'title':'Mock','text':'We evaluated Retriever on NaturalQuestions.'},2)
        self.assertEqual(len(out['relations']),1)
        self.assertEqual(schemas[0]['properties']['entities']['items']['properties']['evidence_id']['enum'],['P1'])
        self.assertEqual(schemas[1]['properties']['relations']['items']['properties']['subject_id']['enum'],['E1','E2'])

    def test_no_relation_when_cooccurrence_only(self):
        with patch.object(m.v3,'chat_structured',side_effect=[
            {'entities':[{'name':'Retriever','type':'MODEL','evidence_id':'P1'},
                         {'name':'NaturalQuestions','type':'DATASET','evidence_id':'P1'}]},
            {'relations':[{'subject_id':'E1','predicate':'EVALUATED_ON','object_id':'E2','evidence_id':'P1'}]}
        ]):
            out=m.extract_chunk('http://127.0.0.1:11434','mock',
                                {'title':'Mock','text':'Retriever and NaturalQuestions are mentioned.'},2)
        self.assertEqual(len(out['relations']),0)
        self.assertEqual(out['rejected_relations'][0]['reason'],'no_single_sentence_with_both_entities_and_relation_cue')

    def test_dry_run_does_not_call_ollama_or_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.jsonl'
            path.write_text(json.dumps({'chunk_id':'c1','document_id':'d1','text':'We evaluated ModelX on DatasetY.','page_number':2})+'\n',encoding='utf-8')
            with patch.object(m.v3,'check_model',side_effect=AssertionError('Ollama called')):
                code=m.main(['--input',str(path),'--dry-run'])
            self.assertEqual(code,0)
            self.assertEqual(len(list(Path(folder).iterdir())),1)

if __name__ == '__main__':
    unittest.main()
