"""Tests hors ligne : ne contactent aucun site externe."""
import tempfile
import unittest
from pathlib import Path

from scrapy.http import HtmlResponse
from crawler.spiders.pmlr_spider_v3 import PmlrSpider, extract_pmlr_article
from scripts.merge_acl_pmlr_v3 import merge_records
from scripts.validate_acl_pmlr_v3 import validate_merged


def resp(url, html):
    return HtmlResponse(url=url, body=html.encode("utf-8"), encoding="utf-8")


class PmlrTests(unittest.TestCase):
    def test_index_links_limit_and_host(self):
        html = '''<a href="/v235/lin24g.html">abs</a>
        <a href="/v235/rogers24a.html">abs</a><a href="/v235/lin24g.html">duplicate</a>
        <a href="https://example.org/v235/fake24a.html">outside</a><a href="/v238/other24a.html">other</a>'''
        spider = PmlrSpider(limit="2")
        requests = list(spider.parse(resp("https://proceedings.mlr.press/v235/", html)))
        self.assertEqual(len(requests), 2)
        self.assertTrue(requests[0].url.endswith("/v235/lin24g.html"))

    def test_article_metadata(self):
        html = '''<html><head><meta name="citation_title" content="Learning to Model the World With Language">
        <meta name="citation_author" content="Jessy Lin"><meta name="citation_author" content="Yuqing Du">
        <meta name="citation_abstract" content="This is a test abstract."></head></html>'''
        paper = extract_pmlr_article(resp("https://proceedings.mlr.press/v235/lin24g.html", html))
        self.assertEqual(paper["paper_id"], "pmlr-v235-lin24g")
        self.assertEqual(paper["authors"], ["Jessy Lin", "Yuqing Du"])
        self.assertEqual(paper["abstract"], "This is a test abstract.")
        self.assertEqual(paper["source"], "PMLR (page HTML)")
        self.assertIsNone(paper["doi"])

    def test_rejects_bot_page(self):
        spider = PmlrSpider(limit="2")
        response = resp("https://proceedings.mlr.press/v235/", '<h1>Making sure you\'re not a bot!</h1>')
        self.assertEqual(list(spider.parse(response)), [])

    def test_merge_and_validator(self):
        a = {"paper_id":"2024.acl-long.1","title":"Test ACL","authors":["A"],"year":2024,
             "doi":"10.1234/acl","abstract":"ACL abstract","url":"https://aclanthology.org/2024.acl-long.1/",
             "source":"ACL Anthology (page HTML)"}
        b = {"paper_id":"pmlr-v235-lin24g","title":"Test PMLR","authors":["B"],"year":2024,
             "doi":None,"abstract":"PMLR abstract","url":"https://proceedings.mlr.press/v235/lin24g.html",
             "source":"PMLR (page HTML)"}
        merged, report = merge_records([a],[b])
        self.assertEqual(len(merged),2)
        self.assertEqual(report["multi_source_publications"], 0)
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/"merged.jsonl"
            import json
            p.write_text("".join(json.dumps(r)+"\n" for r in merged),encoding="utf-8")
            stats, errors = validate_merged(p,min_count=2,min_overlap=0)
            self.assertEqual(errors, [])
            self.assertEqual(stats["sources"], ["ACL Anthology", "PMLR"])


if __name__ == "__main__":
    unittest.main()
