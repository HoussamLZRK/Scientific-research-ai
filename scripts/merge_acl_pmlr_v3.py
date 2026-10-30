"""Fusion conservatrice ACL V2 + PMLR V3 (JSONL) sans API, sans dépendance externe.

Règles d'identité : DOI commun, sinon identifiant ACL explicite commun.
Un simple titre semblable n'est jamais suffisant pour fusionner deux articles.
Les métadonnées brutes de chaque source sont conservées dans source_records.
"""

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ACL_RE = re.compile(r"^20\d{2}\.[a-z0-9-]+\.\d+$", flags=re.I)


def norm_doi(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi\s*:\s*", "", value)
    return value if re.fullmatch(r"10\.\d{4,9}/\S+", value) else None


def canonical_acl_id(item):
    for value in (item.get("acl_paper_id"), item.get("paper_id") if "ACL Anthology" in str(item.get("source")) else None):
        text = str(value or "").strip()
        if ACL_RE.fullmatch(text):
            return text.lower()
    return None


def read_records(path: Path, source_hint: str) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Fichier introuvable : {path}")
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: JSON invalide") from exc
        if not isinstance(item, dict) or not item.get("paper_id") or not item.get("title") or not isinstance(item.get("authors"), list) or not item["authors"] or not item.get("url"):
            raise ValueError(f"{path}:{line_no}: champs obligatoires manquants")
        if source_hint not in str(item.get("source", "")):
            raise ValueError(f"{path}:{line_no}: source inattendue (attendu : {source_hint})")
        rows.append(item)
    if not rows:
        raise ValueError(f"Aucun article exploitable dans {path}")
    return rows


def similarity_key(item):
    # utilisé UNIQUEMENT pour signaler des collisions possibles, pas pour fusionner
    title = unicodedata.normalize("NFKD", str(item.get("title") or "")).casefold()
    title = " ".join(re.findall(r"[a-z0-9]+", title))
    return (title, str(item.get("year") or ""))


def merge_records(acl_rows, pmlr_rows):
    tagged = [("ACL Anthology", r) for r in acl_rows] + [("PMLR", r) for r in pmlr_rows]
    parent = list(range(len(tagged)))
    doi_sets = [({d} if (d := norm_doi(r.get("doi"))) else set()) for _, r in tagged]
    warnings = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j, cause):
        a, b = find(i), find(j)
        if a == b:
            return
        if doi_sets[a] and doi_sets[b] and doi_sets[a] != doi_sets[b]:
            warnings.append(f"Conflit DOI : refus de fusionner {tagged[i][1]['paper_id']} et {tagged[j][1]['paper_id']} via {cause}")
            return
        parent[b] = a
        doi_sets[a] |= doi_sets[b]

    # Phase DOI, puis phase identifiant ACL ; jamais de fusion basée uniquement sur titre/année.
    for field in ("doi", "acl"):
        known = {}
        for idx, (_, row) in enumerate(tagged):
            key = norm_doi(row.get("doi")) if field == "doi" else canonical_acl_id(row)
            if key is None:
                continue
            if key in known:
                union(known[key], idx, f"{field}={key}")
            else:
                known[key] = idx

    groups = defaultdict(list)
    for idx in range(len(tagged)):
        groups[find(idx)].append(idx)

    result = []
    for _, members in sorted(groups.items(), key=lambda kv: min(kv[1])):
        ordered = sorted(members, key=lambda idx: tagged[idx][0] != "ACL Anthology")
        primary = tagged[ordered[0]][1]
        sources = sorted({tagged[i][0] for i in ordered})
        doi = next((norm_doi(tagged[i][1].get("doi")) for i in ordered if norm_doi(tagged[i][1].get("doi"))), None)
        acl_id = next((canonical_acl_id(tagged[i][1]) for i in ordered if canonical_acl_id(tagged[i][1])), None)
        canonical_id = ("doi:" + doi) if doi else ("acl:" + acl_id) if acl_id else f"{tagged[ordered[0]][0].lower().replace(' ', '_')}:{primary['paper_id']}"
        abstract = next((tagged[i][1]["abstract"] for i in ordered if tagged[i][1].get("abstract")), None)
        pdf_url = next((tagged[i][1]["pdf_url"] for i in ordered if tagged[i][1].get("pdf_url")), None)
        result.append({
            "canonical_id": canonical_id,
            "paper_id": acl_id or str(primary["paper_id"]),
            "title": primary["title"],
            "authors": primary["authors"],
            "year": primary.get("year"),
            "abstract": abstract,
            "doi": doi,
            "pdf_url": pdf_url,
            "sources": sources,
            "source_urls": list(dict.fromkeys(str(tagged[i][1]["url"]) for i in ordered)),
            "source_records": [{
                "source": tagged[i][0],
                "paper_id": tagged[i][1]["paper_id"],
                "url": tagged[i][1]["url"],
                "doi": norm_doi(tagged[i][1].get("doi")),
            } for i in ordered],
        })

    # Examiner les titres similaires de groupes distincts sans en conclure à un doublon.
    similar = defaultdict(list)
    for item in result:
        similar[similarity_key(item)].append(item["canonical_id"])
    possible = [{"title": t, "year": y, "canonical_ids": ids}
                for (t, y), ids in similar.items() if t and len(ids) > 1]
    possible.sort(key=lambda x: (x["year"], x["title"]))
    report = {
        "acl_input": len(acl_rows),
        "pmlr_input": len(pmlr_rows),
        "input_total": len(tagged),
        "unique_publications": len(result),
        "multi_source_publications": sum(len(x["sources"]) > 1 for x in result),
        "acl_only": sum(x["sources"] == ["ACL Anthology"] for x in result),
        "pmlr_only": sum(x["sources"] == ["PMLR"] for x in result),
        "with_doi": sum(bool(x["doi"]) for x in result),
        "with_abstract": sum(bool(x["abstract"]) for x in result),
        "possible_duplicates_not_merged": possible,
        "warnings": warnings,
        "counts_by_source": dict(Counter(s for x in result for s in x["sources"])),
        "method": "DOI identique puis ID ACL explicite ; titres similaires signalés uniquement",
    }
    return result, report


def main():
    parser = argparse.ArgumentParser(description="V3 : fusion ACL + PMLR sans API")
    parser.add_argument("--acl", default="data/raw/publications_v2.jsonl")
    parser.add_argument("--pmlr", default="data/raw/publications_pmlr_v3.jsonl")
    parser.add_argument("--output", default="data/processed/publications_multisource_v3.jsonl")
    parser.add_argument("--report", default="data/reports/multisource_v3_report.json")
    args = parser.parse_args()
    try:
        acl = read_records(Path(args.acl), "ACL Anthology")
        pmlr = read_records(Path(args.pmlr), "PMLR")
        merged, report = merge_records(acl, pmlr)
        out = Path(args.output)
        rep = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        rep.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in merged), encoding="utf-8")
        rep.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"ERREUR V3 : {exc}\n")
    print(f"ACL : {len(acl)} | PMLR : {len(pmlr)} | Uniques : {len(merged)}")
    print(f"Présentes dans les deux sources : {report['multi_source_publications']}")
    print(f"Rapport : {rep}")
    if report["warnings"]:
        print(f"ATTENTION : {len(report['warnings'])} conflit(s) à examiner dans le rapport")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
