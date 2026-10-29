"""Crawler pédagogique ACL Anthology, sans API.

Départ : page HTML d'un volume scientifique.
Découverte : URLs des articles affichés sur cette page.
Extraction : métadonnées HTML des pages d'articles.

Exécution :
    python -m scrapy runspider crawler/spiders/acl_spider.py \
        -a limit=10 -O data/raw/publications.jsonl
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy


PAPER_PATH_PATTERN = re.compile(r"^/(?P<id>2024\.acl-long\.(?P<num>\d+))/?$")


def clean(value: str | None) -> str:
    """Supprime les espaces multiples sans modifier le contenu scientifique."""
    return " ".join((value or "").split())


def meta_values(response, name: str) -> list[str]:
    """Récupère les balises HTML <meta name='citation_...'>."""
    values = response.css(f'meta[name="{name}"]::attr(content)').getall()
    return [clean(value) for value in values if clean(value)]


class AclAnthologySpider(scrapy.Spider):
    name = "acl_anthology"
    allowed_domains = ["aclanthology.org"]
    start_urls = ["https://aclanthology.org/volumes/2024.acl-long/"]

    # Réglages prudents pour ne pas surcharger le site.
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 3.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 3.0,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "RETRY_TIMES": 2,
        "FEED_EXPORT_ENCODING": "utf-8",
        "USER_AGENT": (
            "ScientificResearchAI-StudentCrawler/0.1 "
            "(+https://github.com/HoussamLZRK/Scientific-research-ai)"
        ),
        "LOG_LEVEL": "INFO",
    }

    def __init__(self, limit="10", **kwargs):
        super().__init__(**kwargs)
        # Sécurité : ne pas lancer un crawl massif par mégarde.
        self.limit = max(1, min(int(limit), 20))

    def parse(self, response):
        """Découvre au maximum 10 articles, par défaut, depuis le volume."""
        links_by_number = {}
        for href in response.css("a[href]::attr(href)").getall():
            full_url = response.urljoin(href)
            parsed = urlparse(full_url)
            if parsed.netloc.lower().removeprefix("www.") != "aclanthology.org":
                continue
            match = PAPER_PATH_PATTERN.fullmatch(parsed.path)
            if match:
                number = int(match.group("num"))
                canonical = f"https://aclanthology.org/{match.group('id')}/"
                links_by_number[number] = canonical

        if not links_by_number:
            self.logger.error(
                "Aucun lien d'article trouvé. La structure HTML ou l'URL a peut-être changé."
            )
            return

        selected = sorted(links_by_number.items())[: self.limit]
        self.logger.info("%d pages d'articles découvertes", len(selected))
        for _, url in selected:
            yield scrapy.Request(url, callback=self.parse_paper, errback=self.log_failure)

    def parse_paper(self, response):
        """Extrait un article depuis sa page HTML, sans endpoint API."""
        match = PAPER_PATH_PATTERN.fullmatch(urlparse(response.url).path)
        if match is None:
            self.logger.warning("Page inattendue ignorée : %s", response.url)
            return

        titles = meta_values(response, "citation_title")
        title = titles[0] if titles else clean(" ".join(response.css("h2#title ::text").getall()))
        if not title:
            title = clean(response.css("h2#title::text, h1#title::text").get())

        authors = meta_values(response, "citation_author")
        if not authors:
            authors = [
                clean(name)
                for name in response.css(".lead a[href*='/people/']::text").getall()
                if clean(name)
            ]

        abstracts = meta_values(response, "citation_abstract")
        abstract = abstracts[0] if abstracts else clean(
            " ".join(response.css("#abstract ::text, .acl-abstract ::text").getall())
        )
        if not title:
            self.logger.warning("Titre absent, article ignoré : %s", response.url)
            return

        doi_values = meta_values(response, "citation_doi")
        doi = doi_values[0] if doi_values else None
        pdf_values = meta_values(response, "citation_pdf_url")
        pdf_link = pdf_values[0] if pdf_values else response.css(
            'a[href$=".pdf"]::attr(href)'
        ).get()

        yield {
            "paper_id": match.group("id"),
            "title": title,
            "authors": authors,
            "year": 2024,
            "abstract": abstract or None,
            "doi": doi,
            "pdf_url": response.urljoin(pdf_link) if pdf_link else None,
            "url": response.url,
            "source": "ACL Anthology (page HTML)",
            "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def log_failure(self, failure):
        self.logger.error("Échec de téléchargement : %s", failure.request.url)
