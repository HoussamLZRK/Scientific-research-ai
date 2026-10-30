"""V3 source HTML PMLR (ICML 2024, v235) sans API ni téléchargement PDF."""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy

VOL = "235"
INDEX_URL = f"https://proceedings.mlr.press/v{VOL}/"
ARTICLE_PATH = re.compile(r"^/v235/([A-Za-z0-9_-]+)\.html$")


def clean(value):
    return " ".join(str(value or "").split())


def metadata(response, name):
    return [clean(x) for x in response.css(f'meta[name="{name}"]::attr(content)').getall() if clean(x)]


def extract_pmlr_article(response):
    """Métadonnées de page de publication; jamais de champ inventé."""
    match = ARTICLE_PATH.fullmatch(urlparse(response.url).path)
    if not match:
        return None
    titles = metadata(response, "citation_title")
    title = titles[0] if titles else clean(" ".join(response.css("h1::text, h1 *::text").getall()))
    authors = metadata(response, "citation_author") or metadata(response, "DC.creator")
    if not authors:
        authors = [clean(x) for x in response.css(".authors a::text, #authors a::text, .author::text").getall() if clean(x)]
    authors = list(dict.fromkeys(authors))
    abstracts = metadata(response, "citation_abstract") or metadata(response, "description")
    abstract = abstracts[0] if abstracts else clean(" ".join(response.css("#abstract ::text, .abstract ::text, section.abstract ::text").getall()))
    pdfs = metadata(response, "citation_pdf_url")
    if not pdfs:
        pdfs = [response.urljoin(x) for x in response.css('a[href$=".pdf"]::attr(href)').getall()]
    # Les publications PMLR n'ont pas systématiquement un DOI.
    dois = metadata(response, "citation_doi")
    if not title or not authors:
        return None
    return {
        "paper_id": f"pmlr-v{VOL}-{match.group(1)}",
        "title": title,
        "authors": authors,
        "year": 2024,
        "abstract": abstract or None,
        "doi": dois[0] if dois else None,
        "pdf_url": pdfs[0] if pdfs else None,
        "url": response.url,
        "source": "PMLR (page HTML)",
        "volume_id": f"v{VOL}",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
    }


class PmlrSpider(scrapy.Spider):
    name = "pmlr_icml2024_v3"
    allowed_domains = ["proceedings.mlr.press"]
    start_urls = [INDEX_URL]
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 3.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 3.0,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "RETRY_TIMES": 0,
        "DOWNLOAD_TIMEOUT": 30,
        "COOKIES_ENABLED": False,
        "FEED_EXPORT_ENCODING": "utf-8",
        "USER_AGENT": "ScientificResearchAI-StudentCrawler/0.3 (+https://github.com/HoussamLZRK/Scientific-research-ai)",
        "LOG_LEVEL": "INFO",
    }

    def __init__(self, limit="10", **kwargs):
        super().__init__(**kwargs)
        try:
            self.limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit doit etre un entier") from exc
        if not 1 <= self.limit <= 30:
            raise ValueError("limit doit etre entre 1 et 30 pendant ce pilote")
        self.count = 0

    def parse(self, response):
        if response.status != 200 or "making sure you're not a bot" in response.text.lower():
            self.logger.error("Page PMLR inaccessible / verification anti-bot : HTTP %s", response.status)
            return
        discovered = {}
        for href in response.css("a[href]::attr(href)").getall():
            url = response.urljoin(href)
            parsed = urlparse(url)
            if parsed.hostname != "proceedings.mlr.press":
                continue
            if ARTICLE_PATH.fullmatch(parsed.path):
                discovered[parsed.path] = f"https://proceedings.mlr.press{parsed.path}"
        if not discovered:
            self.logger.error("Aucun lien d'article PMLR reconnu dans l'index : verifier le HTML")
            return
        self.logger.info("PMLR : %d liens, %d pages demandees", len(discovered), self.limit)
        for url in list(discovered.values())[:self.limit]:
            yield response.follow(url, callback=self.parse_article)

    def parse_article(self, response):
        if response.status != 200 or "making sure you're not a bot" in response.text.lower():
            self.logger.warning("Article indisponible HTTP %s : %s", response.status, response.url)
            return
        paper = extract_pmlr_article(response)
        if paper is None:
            self.logger.warning("Titre ou auteurs introuvables : %s", response.url)
            return
        self.count += 1
        yield paper
