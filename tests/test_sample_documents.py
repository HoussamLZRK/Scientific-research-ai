"""Tests hors ligne : exécuter via unittest discover -s tests."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts" / "download_sample_documents.py"
spec = importlib.util.spec_from_file_location("download_sample_documents", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SampleDocumentsTests(unittest.TestCase):
    def test_detects_pdf_bytes(self):
        self.assertTrue(module.is_pdf(b"%PDF-1.7\n" + b"x" * 200))

    def test_rejects_html_challenge_page(self):
        self.assertFalse(module.is_pdf(b"<html>Making sure you're not a bot!</html>" * 5))

    def test_four_distinct_sources_and_files(self):
        import json
        data = json.loads(module.CATALOG.read_text(encoding="utf-8"))
        self.assertEqual({x["source"] for x in data}, {"ACL Anthology", "PMLR", "PLOS", "HAL"})
        self.assertEqual(len({x["filename"] for x in data}), 4)
        self.assertTrue(all(x["pdf_url"].startswith("https://") for x in data))


if __name__ == "__main__":
    unittest.main()
