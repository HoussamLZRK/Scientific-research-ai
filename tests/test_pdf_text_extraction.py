"""Tests isolés : aucun Docker ni téléchargement nécessaire."""
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_pdf_text.py"
spec = importlib.util.spec_from_file_location("srai_extract_pdf", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def sample_pdf(text="Knowledge graphs help organize scientific information."):
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


ENTRY = {
    "id": "test_paper", "source": "Test", "title": "Scientific test paper", "authors": ["Test Author"],
    "article_url": "https://example.org/paper", "filename": "test.pdf", "year": 2024, "doi": None
}


class TextExtractionTests(unittest.TestCase):
    def test_extraction_preserves_provenance(self):
        data = sample_pdf()
        rows, report = mod.extract_document(ENTRY, data, "local")
        self.assertEqual(report["total_pages"], 1)
        self.assertIn("Knowledge graphs", rows[0]["text"])
        self.assertEqual(rows[0]["page_number"], 1)
        self.assertEqual(rows[0]["document_id"], "test_paper")
        self.assertEqual(rows[0]["pdf_sha256"], report["pdf_sha256"])
        self.assertEqual(rows[0]["extraction_status"], "low_text")

    def test_scanned_or_empty_page_flagged(self):
        writer = PdfWriter()
        writer.add_blank_page(width=600, height=800)
        target = io.BytesIO()
        writer.write(target)
        rows, report = mod.extract_document(ENTRY, target.getvalue(), "local")
        self.assertEqual(rows[0]["extraction_status"], "empty_or_scanned")
        self.assertEqual(report["empty_or_scanned_pages"], 1)

    def test_input_name_rejects_traversal(self):
        with self.assertRaises(ValueError):
            mod.pdf_bytes({"filename": "../trick.pdf"}, "local")

    def test_output_is_jsonl_utf8(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(mod, "OUTPUT", Path(temporary) / "out.jsonl"), patch.object(mod, "REPORT", Path(temporary) / "report.json"):
                mod.save_outputs([{"document_id": "énergie", "text": "Évaluation"}], {"documents": 1})
                output = (Path(temporary) / "out.jsonl").read_text(encoding="utf-8")
                self.assertEqual(json.loads(output)["text"], "Évaluation")


if __name__ == "__main__":
    unittest.main()
