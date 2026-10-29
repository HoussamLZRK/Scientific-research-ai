"""Tests hors-ligne sur des pages HTML fictives, pas sur le site public."""

import unittest
from pathlib import Path
from scrapy.http import HtmlResponse
from crawler.spiders.acl_spider import AclAnthologySpider

FIXTURES = Path(__file__).parent / "fixtures"


def make_response(fixture, url):
    return HtmlResponse(url=url, body=(FIXTURES / fixture).read_bytes(), encoding="utf-8")


class TestCrawler(unittest.TestCase):
    def test_discovers_only_paper_html_links(self):
        spider = AclAnthologySpider(limit="10")
        response = make_response("volume.html", "https://aclanthology.org/volumes/2024.acl-long/")
        requests = list(spider.parse(response))
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].url, "https://aclanthology.org/2024.acl-long.1/")
        self.assertEqual(requests[1].url, "https://aclanthology.org/2024.acl-long.2/")

    def test_extracts_metadata_from_html(self):
        spider = AclAnthologySpider()
        response = make_response("paper.html", "https://aclanthology.org/2024.acl-long.1/")
        items = list(spider.parse_paper(response))
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "Example Research on Language Models")
        self.assertEqual(item["authors"], ["Example One", "Example Two"])
        self.assertEqual(item["year"], 2024)
        self.assertEqual(item["abstract"], "This is a test abstract.")
        self.assertEqual(item["doi"], "10.1234/example")


if __name__ == "__main__":
    unittest.main()
