"""Validation indépendante du dataset unifié produit par merge_sources_v3.py."""

import argparse
import json
import re
from pathlib import Path


def norm_doi(value):
    """Validation du format DOI du résultat fusionné, sans import externe."""
    value = str(value or "").strip().lower()
    return value if re.fullmatch(r"10\.\d{4,9}/\S+", value) else None


def validate_merged(path: Path, min_count=1, min_overlap=0):
    errors = []
    if not path.is_file():
        return {"total": 0}, [f"Fichier introuvable : {path}"]
    rows = []
    canonical = set()
    dois = set()
    source_names = set()
    cross_source = 0
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"Ligne {number}: JSON invalide")
            continue
        if not isinstance(item, dict):
            errors.append(f"Ligne {number}: dictionnaire attendu")
            continue
        rows.append(item)
        key = item.get("canonical_id")
        sources = item.get("sources")
        records = item.get("source_records")
        if not isinstance(key, str) or not key or key in canonical:
            errors.append(f"Ligne {number}: canonical_id manquant ou en doublon")
        else:
            canonical.add(key)
        if not item.get("title") or not isinstance(item.get("authors"), list) or not item["authors"]:
            errors.append(f"Ligne {number}: titre ou auteurs manquants")
        if not isinstance(sources, list) or not sources or not set(sources).issubset({"ACL Anthology", "PMLR"}):
            errors.append(f"Ligne {number}: sources incorrectes")
            continue
        source_names.update(sources)
        if not isinstance(records, list) or not records or not all(isinstance(r, dict) and r.get("url") and r.get("source") in sources for r in records):
            errors.append(f"Ligne {number}: source_records incomplets")
        if len(set(sources)) == 2:
            cross_source += 1
        doi = norm_doi(item.get("doi"))
        if doi:
            if doi in dois:
                errors.append(f"Ligne {number}: DOI dupliqué ({doi})")
            dois.add(doi)
    if len(rows) < min_count:
        errors.append(f"Seulement {len(rows)} publications ; minimum demandé : {min_count}")
    if source_names != {"ACL Anthology", "PMLR"}:
        errors.append(f"Deux sources attendues, présentes : {sorted(source_names)}")
    if cross_source < min_overlap:
        errors.append(f"Recoupements entre sources : {cross_source} ; minimum demandé : {min_overlap}")
    return {"total": len(rows), "cross_source": cross_source, "sources": sorted(source_names), "with_doi": len(dois)}, errors


def main():
    parser = argparse.ArgumentParser(description="Validation V3 multisource")
    parser.add_argument("--input", default="data/processed/publications_multisource_v3.jsonl")
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--min-overlap", type=int, default=0)
    args = parser.parse_args()
    if args.min_count < 1 or args.min_overlap < 0:
        parser.error("min-count doit être >=1 et min-overlap >=0")
    report, errors = validate_merged(Path(args.input), args.min_count, args.min_overlap)
    print(f"Publications : {report['total']}")
    print(f"Recoupements confirmés : {report.get('cross_source', 0)}")
    print(f"Sources : {report.get('sources', [])}")
    for problem in errors[:25]:
        print("ERREUR :", problem)
    if errors:
        return 1
    print("VALIDATION MULTISOURCE V3 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
