"""Petits helpers purs, indépendants de PySpark, testables sans Docker."""
from __future__ import annotations

import re
from pathlib import Path

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def normalize_doi(value: object) -> str | None:
    value = str(value or "").strip().lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi\s*:\s*", "", value)
    return value if DOI_RE.fullmatch(value) else None


def canonical_fallback(doi: object, paper_id: object, source: object) -> str | None:
    """Ne fusionne JAMAIS deux publications sur titre seul."""
    normalized_doi = normalize_doi(doi)
    if normalized_doi:
        return "doi:" + normalized_doi
    pid = str(paper_id or "").strip().lower()
    origin = re.sub(r"[^a-z0-9]+", "_", str(source or "").lower()).strip("_")
    if not pid or not origin:
        return None
    return f"{origin}:{pid}"


def verify_derived_path(path: str, *, kind: str) -> None:
    """Protection anti-effacement accidentel des sources lors d'un overwrite Spark."""
    normalized = path.rstrip("/")
    if kind == "hdfs":
        expected = "/scientific-research-ai/curated/spark_etl_v1"
        if not normalized.endswith(expected) or not normalized.startswith("hdfs://"):
            raise ValueError(f"Destination HDFS interdite : {path!r} (attendu : {expected})")
    elif kind == "local":
        if not normalized.endswith("/data/processed/spark"):
            raise ValueError(f"Destination locale interdite : {path!r}")
    else:
        raise ValueError("Type de destination inconnu")


def verify_report_path(path: str) -> None:
    if not path.replace("\\", "/").endswith("/data/reports/spark_etl_quality_report.json"):
        raise ValueError(f"Chemin de rapport inattendu : {path}")


def report_success(report: dict) -> bool:
    return (
        report.get("status") == "OK"
        and report.get("publications", {}).get("output_rows", 0) > 0
        and report.get("chunks", {}).get("output_rows", 0) > 0
    )
