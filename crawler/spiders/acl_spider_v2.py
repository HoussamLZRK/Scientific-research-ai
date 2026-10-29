"""Crawler ACL Anthology V2 : pages HTML, sans API.

Depuis la racine du projet :
    python -m scrapy runspider crawler/spiders/acl_spider_v2.py \\
      -a limit=50 -a volume=2024.acl-long \\
      -O data/raw/publications_v2.jsonl

Le volume est explicitement indiqué ; Scrapy contrôle robots.txt.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy

from crawler.spiders.acl_spider import clean, meta_values


VOLUME_PATTERN = re.compile(r"^20\d{2}\.[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_PAPERS = 100  # Garde-fou pour cette étape, à revoir avant toute collecte massive.


def normalize_doi(value: str | None) -> str | None:
    """Normalise un DOI fourni par le site, sans en inventer."""
    if not value:
        return None
    value = clean(value)
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
    value = re.sub(r"^doi\s*:\s*", "", value, flags=re.I)
    return value.lower() if value.lower().startswith("10.") and "/" in value else None


def unique_names(names: list[str]) -> list[str]:
    """Conserve l'ordre et enlève les doublons exacts, sans fusionner des personnes différentes."""
    result = []
    seen = set()
    for name in names:
        name = clean(name)
        if name and name.casefold() not in seen:
            result.append(name)
            seen.add(name.casefold())
    return result


class AclAnthologySpiderV2(scrapy.Spider):
    name = "acl_anthology_v2"
    allowed_domains = ["aclanthology.org"]

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 3.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 3.0,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "RETRY_TIMES": 2,
        "DOWNLOAD_TIMEOUT": 30,
        "COOKIES_ENABLED": False,
        "FEED_EXPORT_ENCODING": "utf-8",
        "ITEM_PIPELINES": {"crawler.pipelines.ValidateAndDeduplicatePipeline": 300},
        "USER_AGENT": (
            "ScientificResearchAI-StudentCrawler/0.2 "
            "(+https://github.com/HoussamLZRK/Scientific-research-ai)"
        ),
        "LOG_LEVEL": "INFO",
    }

    def __init__(self, limit="50", volume="2024.acl-long", **kwargs):
        super().__init__(**kwargs)
        if not VOLUME_PATTERN.fullmatch(volume):
            raise ValueError("volume invalide (exemple attendu : 2024.acl-long)")
        try:
            requested = int(limit)
        except (ValueError, TypeError) as exc:
            raise ValueError("limit doit être un entier") from exc
        if not (1 <= requested <= MAX_PAPERS):
            raise ValueError(f"limit doit être compris entre 1 et {MAX_PAPERS}")
        self.volume = volume
        self.limit = requested
        self.year = int(volume[:4])
        self.start_urls = [f"https://aclanthology.org/volumes/{self.volume}/"]
        self.paper_path = re.compile(
            rf"^/(?P<id>{re.escape(self.volume)}\.(?P<num>\d+))/?$"
        )

    def parse(self, response):
        """Sélectionne des pages d'articles, sans suivre les PDFs ni les liens externes."""
        discovered = {}
        for href in response.css("a[href]::attr(href)").getall():
            parsed = urlparse(response.urljoin(href))
            if parsed.scheme != "https" or parsed.hostname != "aclanthology.org":
                continue
            match = self.paper_path.fullmatch(parsed.path)
            if match:
                n = int(match.group("num"))
                discovered[n] = f"https://aclanthology.org/{match.group('id')}/"

        if not discovered:
            self.logger.error("Aucun lien trouvé dans la page %s", response.url)
            return

        chosen = sorted(discovered.items())[: self.limit]
        self.logger.info("%s articles découverts ; %s sélectionnés", len(discovered), len(chosen))
        if len(chosen) < self.limit:
            self.logger.warning("Moins d'articles disponibles que le nombre demandé")
        for _, url in chosen:
            yield scrapy.Request(
                url,
                callback=self.parse_paper,
                errback=self.log_failure,
                dont_filter=False,
            )

    def parse_paper(self, response):
        """Extrait les informations effectivement disponibles sur la page HTML."""
        parsed = urlparse(response.url)
        match = self.paper_path.fullmatch(parsed.path)
        if parsed.hostname != "aclanthology.org" or not match:
            self.logger.warning("URL d'article inattendue : %s", response.url)
            return

        titles = meta_values(response, "citation_title")
        title = titles[0] if titles else clean(
            " ".join(response.css("h2#title ::text, h1#title ::text").getall())
        )

        authors = unique_names(meta_values(response, "citation_author"))
        if not authors:
            authors = unique_names(response.css(".lead a[href*='/people/']::text").getall())

        abstracts = meta_values(response, "citation_abstract")
        abstract = abstracts[0] if abstracts else clean(
            " ".join(response.css("#abstract ::text, .acl-abstract ::text").getall())
        )
        if not abstract:
            abstract = None

        if not title or not authors:
            self.logger.warning("Article incomplet, ignoré : %s (titre/auteurs)", response.url)
            return

        doi_list = meta_values(response, "citation_doi")
        pdf_list = meta_values(response, "citation_pdf_url")
        pdf = pdf_list[0] if pdf_list else response.css('a[href$=".pdf"]::attr(href)').get()
        pdf_url = response.urljoin(pdf) if pdf else None
        if pdf_url and urlparse(pdf_url).hostname != "aclanthology.org":
            pdf_url = None

        yield {
            "paper_id": match.group("id"),
            "title": title,
            "authors": authors,
            "year": self.year,
            "abstract": abstract,
            "doi": normalize_doi(doi_list[0]) if doi_list else None,
            "pdf_url": pdf_url,
            "url": f"https://aclanthology.org/{match.group('id')}/",
            "source": "ACL Anthology (page HTML)",
            "volume_id": self.volume,
            "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def log_failure(self, failure):
        self.logger.error("Téléchargement impossible : %s", failure.request.url)
