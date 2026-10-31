"""Crawler V3 DBLP, HTML uniquement, sans API, ciblé sur ACL 2024 (Long Papers).

Lancement depuis la racine du dépôt :
    python -m scrapy runspider crawler/spiders/dblp_spider.py -a limit=20 \
       -O data/raw/publications_dblp_v3.jsonl

La page de conférence DBLP contient plusieurs notices bibliographiques HTML.
Les résumés ne sont PAS présents dans ces notices ; on ne les invente pas.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy

from crawler.spiders.acl_spider import clean
from crawler.spiders.acl_spider_v2 import normalize_doi, unique_names


ACL_ID = re.compile(r"^2024\.acl-long\.\d+$", flags=re.I)
MAX_PAPERS = 100


def extract_acl_id(url: str) -> str | None:
    """Identifiant ACL explicite depuis un lien ACL ou un DOI (aucune supposition)."""
    parsed = urlparse(url.strip())
    if parsed.hostname in {"aclanthology.org", "www.aclanthology.org"}:
        candidate = parsed.path.strip("/")
    elif parsed.hostname in {"doi.org", "dx.doi.org"}:
        # Les DOI ACL sont de la forme 10.18653/v1/2024.acl-long.123.
        candidate = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    else:
        return None
    return candidate if ACL_ID.fullmatch(candidate) else None


def extract_dblp_record(entry, year: int = 2024) -> dict | None:
    """Lit une notice DBLP HTML. Retourne None quand ce n'est pas un article valide."""
    classes = (entry.attrib.get("class") or "").split()
    if "inproceedings" not in classes:
        return None  # ignore page d'ensemble, proceedings et front matter

    key = clean(entry.attrib.get("id") or entry.attrib.get("data-key") or "")
    if not key.startswith("conf/acl/") or not re.fullmatch(r"conf/acl/[A-Za-z0-9_+-]+", key):
        return None

    title_element = entry.css("span.title")
    title = clean(title_element.xpath("string(.)").get()) if title_element else ""
    authors = unique_names(entry.css('span[itemprop="author"] span[itemprop="name"]::text').getall())
    if not authors:
        # Certains HTML DBLP ont la balise author + lien sans span name.
        authors = unique_names(entry.css('span[itemprop="author"] a::text').getall())
    if not title or not authors:
        return None

    doi = None
    acl_id = None
    for href in entry.css("a[href]::attr(href)").getall():
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.hostname in {"doi.org", "dx.doi.org"}:
            doi = normalize_doi(href) or doi
        if acl_id is None:
            acl_id = extract_acl_id(href)

    if not acl_id and doi and doi.startswith("10.18653/v1/"):
        candidate = doi[len("10.18653/v1/"):]
        if ACL_ID.fullmatch(candidate):
            acl_id = candidate

    return {
        "paper_id": key,
        "title": title,
        "authors": authors,
        "year": year,
        "abstract": None,
        "doi": doi,
        "pdf_url": None,
        "url": f"https://dblp.org/rec/{key}",
        "source": "DBLP (page HTML)",
        "volume_id": "2024.acl-long",
        "acl_paper_id": acl_id,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
    }


class DblpSpider(scrapy.Spider):
    name = "dblp_acl2024_v3"
    allowed_domains = ["dblp.org"]
    start_urls = ["https://dblp.org/db/conf/acl/acl2024-1.html"]
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 3.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 3.0,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "RETRY_TIMES": 0,  # ne pas insister sur 429/403 ; regarder les logs
        "DOWNLOAD_TIMEOUT": 30,
        "COOKIES_ENABLED": False,
        "FEED_EXPORT_ENCODING": "utf-8",
        "USER_AGENT": (
            "ScientificResearchAI-StudentCrawler/0.3 "
            "(+https://github.com/HoussamLZRK/Scientific-research-ai)"
        ),
        "LOG_LEVEL": "INFO",
    }

    def __init__(self, limit="20", **kwargs):
        super().__init__(**kwargs)
        try:
            self.limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit doit être un entier") from exc
        if not 1 <= self.limit <= MAX_PAPERS:
            raise ValueError(f"limit doit être compris entre 1 et {MAX_PAPERS}")

    def parse(self, response):
        """Extrait les notices contenues dans le HTML de la page DBLP.

        Cette V3 lit une page d'index : elle ne télécharge ni PDF ni endpoints API.
        """
        entries = response.css("li.entry.inproceedings")
        if not entries:
            self.logger.error("Aucune notice DBLP trouvée : vérifier HTML et robots.txt (%s)", response.url)
            return

        seen = set()
        emitted = 0
        for entry in entries:
            item = extract_dblp_record(entry)
            if item is None:
                continue
            key = item["paper_id"]
            if key in seen:
                continue
            seen.add(key)
            yield item
            emitted += 1
            if emitted >= self.limit:
                break
        self.logger.info("DBLP V3 : %d notices valides exportées (demandées : %d)", emitted, self.limit)
        if emitted < self.limit:
            self.logger.warning("Moins de notices valides que demandé : %d/%d", emitted, self.limit)
