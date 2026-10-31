"""Phase 2C V3 isolated unit tests; no Ollama calls or web requests."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import extract_scientific_knowledge_v3 as m

TEXT='We evaluate the Retriever model on NaturalQuestions (NQ) using exact-match accuracy.'


class ExtractionV3Tests(unittest.TestCase):
    def test_hyphenation_joins_broken_words_for_checking_only(self):
        self.assertTrue(m.contains_name('We study Natural Ques- tions (NQ).','Natural Questions'))
        self.assertTrue(m.contains_name('We study Hot- potQA.','HotpotQA'))

    def test_partial_entity_not_a_word_match(self):
        self.assertFalse(m.contains_name('We study NaturalQuestions.','Natural'))
        self.assertFalse(m.contains_name('Retrieval model.', 'Retrieve'))

    def test_entity_has_source_evidence(self):
        out=m.validate_entities({'entities':[
            {'name':'Retriever','type':'MODEL','evidence_id':'P1'},
            {'name':'NaturalQuestions','type':'DATASET','evidence_id':'P1'}]}, {'P1':TEXT})
        self.assertEqual(len(out['entities']),2)
        self.assertEqual(out['entities'][1]['name'],'NaturalQuestions')

    def test_reject_fabricated_entity(self):
        out=m.validate_entities({'entities':[{'name':'ImaginaryNet','type':'MODEL','evidence_id':'P1'}]}, {'P1':TEXT})
        self.assertEqual(out['rejected_entities'][0]['reason'],'name_not_in_evidence_window')

    def test_reject_missing_window_and_duplicate(self):
        out=m.validate_entities({'entities':[
            {'name':'Retriever','type':'MODEL','evidence_id':'P1'},
            {'name':'Retriever','type':'MODEL','evidence_id':'P1'},
            {'name':'NaturalQuestions','type':'DATASET','evidence_id':'P12'}]}, {'P1':TEXT})
        self.assertEqual([i['reason'] for i in out['rejected_entities']], ['duplicate_entity','unknown_evidence_id'])

    def test_windows_are_literal_and_cover_source(self):
        source='A word appears in an article. '*70
        windows=m.evidence_windows(source)
        self.assertGreaterEqual(len(windows),2)
        for w in windows.values():
            self.assertIn(w,source)

    def test_accept_evaluation_with_explicit_cue_and_both_entities(self):
        entities=[{'id':'E1','name':'Retriever','type':'MODEL'}, {'id':'E2','name':'NaturalQuestions','type':'DATASET'}]
        response={'relations':[{'subject_id':'E1','predicate':'EVALUATED_ON','object_id':'E2','evidence_id':'P1'}]}
        out=m.validate_relations(response,entities,{'P1':TEXT})
        self.assertEqual(len(out['relations']),1)
        self.assertIn('evaluate',out['relations'][0]['evidence'])
        self.assertIn('HUMAN_REVIEW',out['relations'][0]['verification'])

    def test_reject_type_or_direction(self):
        entities=[{'id':'E1','name':'NaturalQuestions','type':'DATASET'}, {'id':'E2','name':'Retriever','type':'MODEL'}]
        payload={'relations':[{'subject_id':'E1','predicate':'EVALUATED_ON','object_id':'E2','evidence_id':'P1'}]}
        out=m.validate_relations(payload,entities,{'P1':TEXT})
        self.assertEqual(out['rejected_relations'][0]['reason'],'invalid_types_or_direction')

    def test_reject_cooccurrence_without_semantic_cue(self):
        passage='The Retriever and NaturalQuestions were mentioned in an overview.'
        entities=[{'id':'E1','name':'Retriever','type':'MODEL'}, {'id':'E2','name':'NaturalQuestions','type':'DATASET'}]
        payload={'relations':[{'subject_id':'E1','predicate':'EVALUATED_ON','object_id':'E2','evidence_id':'P1'}]}
        out=m.validate_relations(payload,entities,{'P1':passage})
        self.assertEqual(out['rejected_relations'][0]['reason'], 'no_single_sentence_with_both_entities_and_relation_cue')

    def test_obvious_negation_is_not_a_positive_relation(self):
        passage='We did not evaluate the Retriever on NaturalQuestions.'
        entities=[{'id':'E1','name':'Retriever','type':'MODEL'}, {'id':'E2','name':'NaturalQuestions','type':'DATASET'}]
        payload={'relations':[{'subject_id':'E1','predicate':'EVALUATED_ON','object_id':'E2','evidence_id':'P1'}]}
        out=m.validate_relations(payload,entities,{'P1':passage})
        self.assertEqual(out['relations'],[])
        self.assertEqual(out['rejected_relations'][0]['reason'], 'no_single_sentence_with_both_entities_and_relation_cue')

    def test_reject_cross_sentence_cooccurrence(self):
        passage='We evaluated the Retriever in an experiment. NaturalQuestions appears in the references.'
        entities=[{'id':'E1','name':'Retriever','type':'MODEL'}, {'id':'E2','name':'NaturalQuestions','type':'DATASET'}]
        payload={'relations':[{'subject_id':'E1','predicate':'EVALUATED_ON','object_id':'E2','evidence_id':'P1'}]}
        out=m.validate_relations(payload,entities,{'P1':passage})
        self.assertEqual(out['rejected_relations'][0]['reason'], 'no_single_sentence_with_both_entities_and_relation_cue')

    def test_reject_bad_ids(self):
        payload={'relations':[{'subject_id':'Retriever','predicate':'EVALUATED_ON','object_id':'E2','evidence_id':'P1'}]}
        out=m.validate_relations(payload,[{'id':'E1','name':'Retriever','type':'MODEL'},{'id':'E2','name':'NaturalQuestions','type':'DATASET'}],{'P1':TEXT})
        self.assertEqual(out['rejected_relations'][0]['reason'],'invalid_entity_ids')

    def test_two_stage_mocked_ollama(self):
        chunk={'text':TEXT,'title':'Test paper','page_number':1}
        responses=iter([
            {'entities':[{'name':'Retriever','type':'MODEL','evidence_id':'P1'},
                         {'name':'NaturalQuestions','type':'DATASET','evidence_id':'P1'}]},
            {'relations':[{'subject_id':'E1','predicate':'EVALUATED_ON','object_id':'E2','evidence_id':'P1'}]}
        ])
        with patch.object(m,'chat_structured',side_effect=lambda *a,**k:next(responses)) as mock:
            out=m.extract_chunk('http://127.0.0.1:11434','qwen2.5:3b',chunk,10)
        self.assertEqual(mock.call_count,2)
        self.assertEqual(len(out['entities']),2)
        self.assertEqual(len(out['relations']),1)

    def test_no_relations_is_legitimate(self):
        out=m.validate_relations({'relations':[]},[],{'P1':'Scientific text.'})
        self.assertEqual(out['relations'],[])

    def test_review_csv_keeps_pending(self):
        rows=[{'document_id':'d1','chunk_id':'c1','page_number':2,
               'relations':[{'subject':'Retriever','predicate':'EVALUATED_ON','object':'NaturalQuestions',
                             'evidence':TEXT,'verification':'LEXICALLY_GROUNDED_CANDIDATE_REQUIRES_HUMAN_REVIEW'}]}]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'review.csv'
            m.write_review_csv(rows,path)
            with path.open(encoding='utf-8-sig',newline='') as f:
                items=list(csv.DictReader(f))
            self.assertEqual(len(items),1)
            self.assertEqual(items[0]['human_decision'],'PENDING')

    def test_dry_run_from_fixture_no_ollama(self):
        # Reuses the real shared V1 loader and selector on a tiny, isolated input file.
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'chunks.jsonl'
            rec={'chunk_id':'example_p001_c001','document_id':'example','text':TEXT,
                 'title':'Test article','source':'test','page_number':1}
            file.write_text(json.dumps(rec)+'\n',encoding='utf-8')
            with patch.object(m,'check_model',side_effect=AssertionError('Should not call Ollama')):
                result=m.main(['--input',str(file),'--dry-run','--max-documents','1'])
            self.assertEqual(result,0)


if __name__=='__main__':
    unittest.main()
