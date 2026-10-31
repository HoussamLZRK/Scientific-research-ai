r"""Diagnostic prudent d'une seule page HTML DBLP, sans contournement d'accès.

Depuis la racine du projet :
    .\.venv\Scripts\python.exe -m scrapy runspider scripts/diagnose_dblp_v3.py

La classe réutilise les paramètres de politesses / robots.txt du spider V3.
"""
from crawler.spiders.dblp_spider import DblpSpider


class DblpDiagnosticSpider(DblpSpider):
    name = "dblp_v3_diagnostic"

    def parse(self, response):
        title = response.css("title::text").get() or "(aucun titre)"
        count = len(response.css("li.entry.inproceedings"))
        body_text = " ".join(response.css("body ::text").getall())
        excerpt = " ".join(body_text.split())[:230]

        self.logger.warning("DIAGNOSTIC HTTP_STATUS = %s", response.status)
        self.logger.warning("DIAGNOSTIC BODY_BYTES = %s", len(response.body))
        self.logger.warning("DIAGNOSTIC HTML_TITLE = %r", title.strip())
        self.logger.warning("DIAGNOSTIC DBLP_ENTRIES = %s", count)
        self.logger.warning("DIAGNOSTIC BODY_EXCERPT = %r", excerpt)
        self.logger.warning("Aucune publication n'est collectee par ce diagnostic.")
