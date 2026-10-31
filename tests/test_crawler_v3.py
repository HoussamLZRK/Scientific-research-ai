"""Tests V3 hors ligne. Ne contacte jamais ACL ou DBLP."""

import tempfile
import unittest
from pathlib import Path

from scrapy.http import HtmlResponse

from crawler.spiders.dblp_spider import DblpSpider, extract_acl_id
from scripts.merge_sources_v3 import merge_records
from scripts.validate_multisource_v3 import validate_merged

FIXTURE = Path(__file__).parent / "fixtures" / "dblp_volume_v3.html"


def response():
    return HtmlResponse(
        url="https://dblp.org/db/conf/acl/acl2024-1.html",
        body=FIXTURE.read_bytes(), encoding="utf-8"
    )


class TestDblpSpiderV3(unittest.TestCase):
    def test_html_extraction_and_limit(self):
        spider = DblpSpider(limit="2")
        data = list(spider.parse(response()))
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["paper_id"], "conf/acl/Alpha24")
        self.assertEqual(data[0]["authors"], ["Ada Researcher", "Benoit Scholar"])
        self.assertEqual(data[0]["acl_paper_id"], "2024.acl-long.1")
        self.assertEqual(data[0]["doi"], "10.1234/example")
        self.assertEqual(data[1]["acl_paper_id"], "2024.acl-long.2")
        self.assertEqual(data[1]["title"], "Another Article with HTML Markup")
        self.assertIsNone(data[0]["abstract"])

    def test_limit_validation(self):
        for n in ("0", "101", "hello"):
            with self.assertRaises(ValueError):
                DblpSpider(limit=n)

    def test_extract_acl_id_does_not_guess(self):
        self.assertEqual(extract_acl_id("https://aclanthology.org/2024.acl-long.2/"), "2024.acl-long.2")
        self.assertIsNone(extract_acl_id("https://other.example/2024.acl-long.2/"))


class TestMergeV3(unittest.TestCase):
    def setUp(self):
        self.acl = [{"paper_id": "2024.acl-long.1", "title": "Example Research on Language Models",
                     "authors": ["Ada Researcher"], "year": 2024, "doi": "10.1234/example",
                     "abstract": "Reference abstract", "url": "https://aclanthology.org/2024.acl-long.1/",
                     "source": "ACL Anthology (page HTML)"}]
        self.dblp = [{"paper_id": "conf/acl/Alpha24", "title": "Example Research on Language Models",
                      "authors": ["Ada Researcher"], "year": 2024, "doi": "10.1234/example",
                      "abstract": None, "acl_paper_id": "2024.acl-long.1",
                      "url": "https://dblp.org/rec/conf/acl/Alpha24", "source": "DBLP (page HTML)"}]

    def test_doi_overlap_and_provenance(self):
        merged, report = merge_records(self.acl, self.dblp)
        self.assertEqual(len(merged), 1)
        self.assertEqual(report["multi_source_publications"], 1)
        self.assertEqual(merged[0]["sources"], ["ACL Anthology", "DBLP"])
        self.assertEqual(len(merged[0]["source_records"]), 2)
        self.assertEqual(merged[0]["abstract"], "Reference abstract")

    def test_explicit_acl_id_without_doi(self):
        a = dict(self.acl[0], doi=None)
        b = dict(self.dblp[0], doi=None)
        merged, _ = merge_records([a], [b])
        self.assertEqual(len(merged), 1)

    def test_similar_titles_do_not_force_merge(self):
        b = dict(self.dblp[0], doi="10.5555/other", acl_paper_id=None)
        merged, report = merge_records(self.acl, [b])
        self.assertEqual(len(merged), 2)
        self.assertEqual(len(report["possible_duplicates_not_merged"]), 1)

    def test_conflicting_dois_are_not_merged(self):
        b = dict(self.dblp[0], doi="10.5555/other")
        merged, report = merge_records(self.acl, [b])
        self.assertEqual(len(merged), 2)
        self.assertTrue(report["warnings"])

    def test_validator(self):
        import json
        merged, _ = merge_records(self.acl, self.dblp)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "merge.jsonl"
            path.write_text(json.dumps(merged[0], ensure_ascii=False) + "\n", encoding="utf-8")
            report, errors = validate_merged(path, min_count=1, min_overlap=1)
            self.assertEqual(report["cross_source"], 1)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
