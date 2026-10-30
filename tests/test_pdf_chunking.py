"""Offline tests, no Hadoop/Docker service required."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'chunk_pdf_pages.py'
spec = importlib.util.spec_from_file_location('srai_chunk_pdf_pages', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ChunkPDFTests(unittest.TestCase):
    def test_page_provenance_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pages.jsonl'
            page = {'document_id': 'acl_test', 'page_number': 2,
                    'source': 'ACL Anthology', 'doi': '10.1234/example',
                    'hdfs_pdf_path': '/hdfs/a.pdf', 'text': 'This method uses a dataset. ' * 120,
                    'extraction_status': 'ok'}
            path.write_text(json.dumps(page) + '\n', encoding='utf-8')
            chunks, report = mod.process_pages(path, 500, 90)
            self.assertGreater(len(chunks), 1)
            self.assertEqual(report['pages_total'], 1)
            self.assertEqual(len({x['chunk_id'] for x in chunks}), len(chunks))
            self.assertTrue(all(x['doi'] == '10.1234/example' and x['page_number'] == 2 for x in chunks))

    def test_chunks_cover_full_normalized_page_without_gaps(self):
        text = ('Retrieval generation and graph learning are important. ' * 65).strip()
        spans = list(mod.chunk_spans(text, 400, 60))
        self.assertEqual(spans[0][0], 0)
        self.assertEqual(spans[-1][1], len(text))
        for a, b in zip(spans, spans[1:]):
            self.assertLessEqual(b[0], a[1], 'There should be no uncovered text')
            self.assertLessEqual(a[1] - a[0], 400)
        self.assertTrue(all(text[a:b].strip() for a, b in spans))

    def test_empty_page_is_skipped_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pages.jsonl'
            pages = [{'document_id': 'test', 'page_number': 1, 'text': ''},
                     {'document_id': 'test', 'page_number': 2, 'text': 'This is valid text ' * 20}]
            path.write_text(''.join(json.dumps(x) + '\n' for x in pages), encoding='utf-8')
            chunks, report = mod.process_pages(path)
            self.assertEqual(report['pages_empty_skipped'], 1)
            self.assertEqual(report['pages_total'], 2)
            self.assertTrue(all(x['page_number'] == 2 for x in chunks))

    def test_duplicate_document_page_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pages.jsonl'
            page = {'document_id': 'same', 'page_number': 1, 'text': 'Example ' * 30}
            path.write_text((json.dumps(page) + '\n') * 2, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate document/page'):
                mod.process_pages(path)

    def test_invalid_chunking_parameters_fail(self):
        with self.assertRaises(ValueError):
            list(mod.chunk_spans('ABC', 1200, 800))


if __name__ == '__main__':
    unittest.main()
