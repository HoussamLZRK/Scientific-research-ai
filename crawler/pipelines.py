"""Validation et suppression des doublons par exécution Scrapy V2."""

from urllib.parse import urlparse

from scrapy.exceptions import DropItem

from crawler.spiders.acl_spider_v2 import normalize_doi


class ValidateAndDeduplicatePipeline:
    def __init__(self):
        self.ids = set()
        self.dois = set()

    def process_item(self, item, spider):
        paper_id = str(item.get("paper_id") or "").strip()
        title = str(item.get("title") or "").strip()
        authors = item.get("authors")
        url = str(item.get("url") or "")

        if not paper_id or not title or not isinstance(authors, list) or not authors:
            raise DropItem(f"article incomplet : {paper_id or url}")
        if urlparse(url).hostname != "aclanthology.org":
            raise DropItem(f"domaine inattendu : {url}")
        if paper_id in self.ids:
            raise DropItem(f"identifiant dupliqué : {paper_id}")

        doi = normalize_doi(item.get("doi"))
        if doi and doi in self.dois:
            raise DropItem(f"DOI dupliqué : {doi}")

        self.ids.add(paper_id)
        if doi:
            self.dois.add(doi)
        item["doi"] = doi
        return item
