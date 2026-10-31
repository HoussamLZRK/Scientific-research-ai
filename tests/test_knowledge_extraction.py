"""Unit tests that do not download models or call external APIs."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from io import BytesIO

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "extract_scientific_knowledge.py"
spec = importlib.util.spec_from_file_location("extract_scientific_knowledge", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

TEXT = "The RAG method uses a Retriever model to retrieve documents. We evaluate RAG on DatasetAlpha."


class KnowledgeExtractionTests(unittest.TestCase):
    def test_one_chunk_per_document(self):
        inputs = [
            {"document_id": "paper1", "chunk_id": "a1", "page_number": 1, "text": "First page is an introduction."},
            {"document_id": "paper1", "chunk_id": "a2", "page_number": 2, "text": "We evaluate our method and model. " * 30},
            {"document_id": "paper2", "chunk_id": "b1", "page_number": 3, "text": "We propose retrieval methods. " * 30},
        ]
        selected = mod.select_preview(inputs)
        self.assertEqual([x["chunk_id"] for x in selected], ["a2", "b1"])

    def test_accept_grounded_entity_and_relation(self):
        data = {
            "entities": [
                {"name": "RAG", "type": "METHOD", "evidence": "The RAG method uses a Retriever model to retrieve documents."},
                {"name": "Retriever", "type": "MODEL", "evidence": "The RAG method uses a Retriever model to retrieve documents."},
            ],
            "relations": [{"subject": "RAG", "predicate": "USES", "object": "Retriever", "evidence": "The RAG method uses a Retriever model to retrieve documents."}],
        }
        result = mod.validate_extraction(data, TEXT)
        self.assertEqual(len(result["entities"]), 2)
        self.assertEqual(len(result["relations"]), 1)
        self.assertEqual(result["relations"][0]["verification"], "lexically_grounded_needs_semantic_review")

    def test_reject_fabricated_quote(self):
        data = {"entities": [{"name": "GPT-9", "type": "MODEL", "evidence": "GPT-9 dominates every task."}], "relations": []}
        result = mod.validate_extraction(data, TEXT)
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["rejected_entities"][0]["reason"], "evidence_not_in_source")

    def test_reject_relation_without_two_endpoints(self):
        data = {"entities": [
            {"name": "RAG", "type": "METHOD", "evidence": "The RAG method uses a Retriever model to retrieve documents."},
            {"name": "Retriever", "type": "MODEL", "evidence": "The RAG method uses a Retriever model to retrieve documents."},
        ], "relations": [{"subject": "RAG", "predicate": "USES", "object": "Retriever", "evidence": "We evaluate RAG on DatasetAlpha."}]}
        result = mod.validate_extraction(data, TEXT)
        self.assertEqual(result["relations"], [])
        self.assertEqual(result["rejected_relations"][0]["reason"], "endpoints_not_in_evidence")

    def test_reject_non_local_endpoint(self):
        with self.assertRaises(ValueError):
            mod.validate_url("https://remote-ai.example")
        self.assertEqual(mod.validate_url("http://localhost:11434"), "http://localhost:11434")

    def test_model_response_mock(self):
        chunk = {"document_id": "paper1", "chunk_id": "a2", "title": "Test", "page_number": 2, "text": TEXT}
        output = json.dumps({"entities": [{"name": "RAG", "type": "METHOD", "evidence": "The RAG method uses a Retriever model to retrieve documents."}], "relations": []})
        response = json.dumps({"message": {"content": output}}).encode("utf-8")
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, *args): return response
        with patch.object(mod.urllib.request, "urlopen", return_value=FakeResponse()) as client:
            result = mod.extract_one("http://localhost:11434", "qwen2.5:3b", chunk, 10)
            self.assertEqual(result["entities"][0]["name"], "RAG")
            sent_payload = json.loads(client.call_args.args[0].data)
            self.assertFalse(sent_payload["stream"])
            self.assertEqual(sent_payload["format"], mod.OUTPUT_SCHEMA)

    def test_load_chunks_detects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "chunks.jsonl"
            record = {"document_id": "paper1", "chunk_id": "same", "text": "Some text"}
            path.write_text(json.dumps(record) + "\n" + json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate chunk_id"):
                mod.load_chunks(path)


if __name__ == "__main__":
    unittest.main()
