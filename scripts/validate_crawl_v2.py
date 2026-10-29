"""Valide les données V2 et produit un rapport JSON de qualité.

Exemple :
    python scripts/validate_crawl_v2.py --input data/raw/publications_v2.jsonl \\
      --min-count 1 --max-count 100
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


def validate_file(path: Path, min_count: int = 1, max_count: int = 100) -> tuple[dict, list[str]]:
    problems = []
    valid_items = []
    ids = set()
    dois = set()
    if not path.exists():
        return {"file": str(path), "total": 0}, [f"Fichier introuvable : {path}"]
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as e:
            problems.append(f"Ligne {line_number} : JSON invalide ({e.msg})")
            continue
        if not isinstance(item, dict):
            problems.append(f"Ligne {line_number} : objet JSON attendu")
            continue
        valid_items.append(item)
        pid = str(item.get("paper_id") or "").strip()
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        authors = item.get("authors")
        year = item.get("year")
        doi = str(item.get("doi") or "").lower().strip()
        volume = str(item.get("volume_id") or "").strip()

        if not pid or not title or not isinstance(authors, list) or not authors:
            problems.append(f"Ligne {line_number} : champ obligatoire absent (id/titre/auteurs)")
        if not isinstance(year, int) or isinstance(year, bool) or year < 1900:
            problems.append(f"Ligne {line_number} : année invalide")
        if pid and pid in ids:
            problems.append(f"Ligne {line_number} : doublon paper_id {pid}")
        ids.add(pid)
        if doi and doi in dois:
            problems.append(f"Ligne {line_number} : doublon DOI {doi}")
        if doi:
            dois.add(doi)
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "aclanthology.org" or parsed.path.strip("/") != pid:
            problems.append(f"Ligne {line_number} : URL incohérente")
        if volume and not pid.startswith(volume + "."):
            problems.append(f"Ligne {line_number} : volume incohérent")

    total = len(valid_items)
    if not (min_count <= total <= max_count):
        problems.append(f"Nombre d'articles {total} hors limites [{min_count}, {max_count}]")
    report = {
        "file": str(path),
        "total": total,
        "with_abstract": sum(bool(i.get("abstract")) for i in valid_items),
        "with_doi": sum(bool(i.get("doi")) for i in valid_items),
        "unique_ids": len(ids),
        "total_authorships": sum(len(i.get("authors") or []) for i in valid_items if isinstance(i.get("authors"), list)),
        "by_year": dict(sorted(Counter(str(i.get("year", "unknown")) for i in valid_items).items())),
        "errors": problems,
        "status": "OK" if not problems else "ERROR",
    }
    return report, problems


def main():
    parser = argparse.ArgumentParser(description="Contrôle qualité du crawler V2")
    parser.add_argument("--input", default="data/raw/publications_v2.jsonl")
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--max-count", type=int, default=100)
    parser.add_argument("--report", default="data/reports/crawler_v2_report.json")
    args = parser.parse_args()
    if args.min_count < 1 or args.max_count < args.min_count:
        parser.error("bornes invalides : 1 <= min-count <= max-count")

    report, problems = validate_file(Path(args.input), args.min_count, args.max_count)
    dest = Path(args.report)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Publications : {report.get('total', 0)}")
    print(f"Résumés : {report.get('with_abstract', 0)}")
    print(f"DOI : {report.get('with_doi', 0)}")
    print(f"Rapport : {dest}")
    if problems:
        for p in problems[:20]:
            print("ERREUR :", p)
        return 1
    print("VALIDATION V2 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
