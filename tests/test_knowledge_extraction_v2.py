"""Tests for the Phase 2C V2 local pilot, no Ollama calls."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import extract_scientific_knowledge_v2 as mod

TEXT = "The RAG method uses Retriever model to retrieve documents. We evaluate RAG on DatasetAlpha."

class ExtractionV2Tests(unittest.TestCase):
    def test_windows_are_literal_and_cover_source(self):
        text = "This is an example sentence. " * 35
        segments = mod.evidence_windows(text, size=120, overlap=20)
        self.assertGreater(len(segments), 2)
        for segment in segments.values():
            self.assertIn(segment, text)

    def test_empty_text_is_rejected(self):
        with self.assertRaises(ValueError):
            mod.evidence_windows(" ")

    def test_accept_entity_with_source_evidence(self):
        result = mod.accept_entities({"entities":[{"name":"RAG", "type":"METHOD", "evidence_id":"P1"}]}, {"P1":TEXT})
        self.assertEqual(result['entities'][0]['evidence'], "The RAG method uses Retriever model to retrieve documents.")

    def test_accept_pdf_hyphenated_exact_name(self):
        text = "We used Natural Ques- tions (NQ) for evaluation."
        r = mod.accept_entities({"entities":[{"name":"Natural Ques- tions", "type":"DATASET", "evidence_id":"P1"}]}, {"P1":text})
        self.assertEqual(len(r['entities']),1)

    def test_reject_nonexistent_entity(self):
        result = mod.accept_entities({"entities":[{"name":"GPT-99", "type":"MODEL", "evidence_id":"P1"}]}, {"P1":TEXT})
        self.assertEqual(result['rejected_entities'][0]['reason'],'name_not_in_source_window')

    def test_reject_nonexistent_passage(self):
        result = mod.accept_entities({"entities":[{"name":"RAG", "type":"METHOD", "evidence_id":"P99"}]}, {"P1":TEXT})
        self.assertEqual(result['rejected_entities'][0]['reason'],'unknown_evidence_id')

    def test_accept_grounded_relation(self):
        entities = [{"id":"E1","name":"RAG","type":"METHOD"}, {"id":"E2","name":"Retriever","type":"MODEL"}]
        payload = {"relations":[{"subject_id":"E1", "predicate":"USES", "object_id":"E2", "evidence_id":"P1"}]}
        output = mod.accept_relations(payload, entities, {"P1":TEXT})
        self.assertEqual(len(output['relations']),1)
        self.assertIn('RAG method uses Retriever', output['relations'][0]['evidence'])
        self.assertEqual(output['relations'][0]['verification'],'source_span_confirmed_needs_semantic_review')

    def test_reject_wrong_evaluated_on_direction(self):
        entities = [{"id":"E1","name":"DatasetAlpha","type":"DATASET"}, {"id":"E2","name":"RAG","type":"METHOD"}]
        payload = {"relations":[{"subject_id":"E1", "predicate":"EVALUATED_ON", "object_id":"E2", "evidence_id":"P1"}]}
        r = mod.accept_relations(payload, entities, {"P1":TEXT})
        self.assertEqual(r['rejected_relations'][0]['reason'],'invalid_evaluated_on_types_or_direction')

    def test_reject_missing_endpoint_in_evidence(self):
        entities = [{"id":"E1","name":"RAG","type":"METHOD"}, {"id":"E2","name":"Retriever","type":"MODEL"}]
        payload = {"relations":[{"subject_id":"E1", "predicate":"USES", "object_id":"E2", "evidence_id":"P1"}]}
        r = mod.accept_relations(payload, entities, {"P1":"We evaluate RAG on DatasetAlpha."})
        self.assertEqual(r['rejected_relations'][0]['reason'],'entities_not_together_in_evidence_window')

    def test_end_to_end_two_calls_with_mock_model(self):
        chunk = {"text":TEXT, "title":"Example", "page_number":2}
        answers = iter([
            {"entities":[
                {"name":"RAG", "type":"METHOD", "evidence_id":"P1"},
                {"name":"Retriever", "type":"MODEL", "evidence_id":"P1"},
            ]},
            {"relations":[{"subject_id":"E1", "predicate":"USES", "object_id":"E2", "evidence_id":"P1"}]},
        ])
        with patch.object(mod, 'chat_structured', side_effect=lambda *args,**kwargs: next(answers)) as mock_chat:
            result=mod.extract_chunk('http://127.0.0.1:11434', 'qwen2.5:3b', chunk, 10)
        self.assertEqual(mock_chat.call_count,2)
        self.assertEqual(len(result['entities']),2)
        self.assertEqual(len(result['relations']),1)

if __name__ == '__main__':
    unittest.main()
