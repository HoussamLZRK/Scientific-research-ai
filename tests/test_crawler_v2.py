"""Tests V2 hors-ligne : aucune requête réseau."""

import json
import tempfile
import unittest
from pathlib import Path

from scrapy.exceptions import DropItem
from scrapy.http import HtmlResponse

from crawler.pipelines import ValidateAndDeduplicatePipeline
from crawler.spiders.acl_spider_v2 import AclAnthologySpiderV2, normalize_doi, unique_names
from scripts.validate_crawl_v2 import validate_file


def response(html: str, url: str) -> HtmlResponse:
    return HtmlResponse(url=url, body=html.encode("utf-8"), encoding="utf-8")


class TestAclCrawlerV2(unittest.TestCase):
    def test_link_discovery_deduplication_sort_and_domain(self):
        spider = AclAnthologySpiderV2(limit="2")
        html = """<a href='/2024.acl-long.12/'>12</a>
        <a href='/2024.acl-long.2/'>2</a>
        <a href='https://evil.test/2024.acl-long.1/'>external</a>
        <a href='/2024.acl-long.2/?ref=dup'>duplicate</a>
        <a href='/2024.acl-long.2.pdf'>pdf</a>
        <a href='/2023.acl-long.1/'>another volume</a>"""
        found = list(spider.parse(response(html, spider.start_urls[0])))
        self.assertEqual([x.url for x in found], [
            "https://aclanthology.org/2024.acl-long.2/",
            "https://aclanthology.org/2024.acl-long.12/",
        ])

    def test_article_extraction(self):
        spider = AclAnthologySpiderV2(limit="3")
        html = """<html><head>
        <meta name='citation_title' content='  Sample    Paper'>
        <meta name='citation_author' content='Ada Researcher'>
        <meta name='citation_author' content='ada researcher'>
        <meta name='citation_author' content='Benoit Scholar'>
        <meta name='citation_abstract' content='A sample abstract.'>
        <meta name='citation_doi' content='https://doi.org/10.1234/ABC'>
        </head><body><h2 id='title'>Different fallback</h2></body></html>"""
        item = list(spider.parse_paper(response(html, "https://aclanthology.org/2024.acl-long.2/")))[0]
        self.assertEqual(item["title"], "Sample Paper")
        self.assertEqual(item["authors"], ["Ada Researcher", "Benoit Scholar"])
        self.assertEqual(item["doi"], "10.1234/abc")
        self.assertEqual(item["volume_id"], "2024.acl-long")

    def test_config_guard(self):
        with self.assertRaises(ValueError):
            AclAnthologySpiderV2(limit="101")
        with self.assertRaises(ValueError):
            AclAnthologySpiderV2(volume="../../outside")

    def test_doi_normalization_and_unique_names(self):
        self.assertEqual(normalize_doi("doi:10.18653/v1/2024.acl-long.1"), "10.18653/v1/2024.acl-long.1")
        self.assertIsNone(normalize_doi("not-a-doi"))
        self.assertEqual(unique_names(["A B", "A  B", "C D"]), ["A B", "C D"])

    def test_pipeline_duplicate(self):
        pipeline = ValidateAndDeduplicatePipeline()
        original = {"paper_id": "2024.acl-long.1", "title": "Example", "authors": ["A"],
                    "url": "https://aclanthology.org/2024.acl-long.1/", "doi": "10.1234/test"}
        pipeline.process_item(original.copy(), None)
        with self.assertRaises(DropItem):
            pipeline.process_item(original.copy(), None)

    def test_validator_detects_duplicate(self):
        entry = {"paper_id": "2024.acl-long.1", "title": "Example", "authors": ["A"],
                 "year": 2024, "url": "https://aclanthology.org/2024.acl-long.1/",
                 "volume_id": "2024.acl-long"}
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "test.jsonl"
            src.write_text(json.dumps(entry) + "\n" + json.dumps(entry) + "\n", encoding="utf-8")
            result, problems = validate_file(src)
            self.assertEqual(result["total"], 2)
            self.assertTrue(any("doublon paper_id" in e for e in problems))

    def test_validator_accepts_clean_file(self):
        entry = {"paper_id": "2024.acl-long.1", "title": "Example", "authors": ["A"],
                 "year": 2024, "url": "https://aclanthology.org/2024.acl-long.1/",
                 "volume_id": "2024.acl-long"}
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "test.jsonl"
            src.write_text(json.dumps(entry) + "\n", encoding="utf-8")
            result, problems = validate_file(src)
            self.assertEqual(result["status"], "OK")
            self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
