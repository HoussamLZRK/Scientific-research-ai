"""Télécharger quatre PDF de test vérifiés par des références bibliographiques.

Exécution depuis la racine du dépôt :
    python scripts/download_sample_documents.py

L'objectif est de constituer une collection locale. Les PDF ne sont pas destinés
à être publiés sur GitHub. Aucun système anti-bot ne doit être contourné.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "config" / "sample_documents.json"
DESTINATION = ROOT / "data" / "sample_documents"
REPORT = ROOT / "data" / "reports" / "sample_documents_report.json"
MAX_BYTES = 30 * 1024 * 1024


def is_pdf(data: bytes) -> bool:
    """Contrôle élémentaire de format, pas une analyse complète du PDF."""
    return len(data) >= 128 and data[:1024].lstrip().startswith(b"%PDF-")


def download_one(entry: dict, output_dir: Path) -> dict:
    path = output_dir / entry["filename"]
    # S'assurer que le nom provient du catalogue et ne permet pas de sortir du dossier.
    if path.name != entry["filename"] or path.suffix.lower() != ".pdf":
        raise ValueError("Nom de fichier PDF invalide")
    result = {
        "id": entry["id"],
        "source": entry["source"],
        "filename": entry["filename"],
        "article_url": entry["article_url"],
        "pdf_url": entry["pdf_url"],
    }
    if path.exists():
        data = path.read_bytes()
        if is_pdf(data):
            return {**result, "status": "already_present", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        return {**result, "status": "invalid_existing_file", "error": "Le fichier local ne ressemble pas à un PDF; aucune suppression automatique."}

    request = Request(entry["pdf_url"], headers={"User-Agent": "ScientificResearchAI-SampleDocuments/1.0 (student research; manual fallback available)", "Accept": "application/pdf"})
    try:
        with urlopen(request, timeout=30) as response:
            if getattr(response, "status", 200) != 200:
                raise RuntimeError(f"HTTP {response.status}")
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("PDF trop volumineux (> 30 Mo)")
        if not is_pdf(data):
            raise ValueError("La réponse n'est pas un PDF (possiblement une page HTML de protection)")
        output_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        try:
            tmp.write_bytes(data)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
        return {**result, "status": "downloaded", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
        return {**result, "status": "failed", "error": str(exc)}


def main() -> int:
    p = argparse.ArgumentParser(description="Prépare les PDF scientifiques pour HDFS")
    p.add_argument("--source", help="Source ciblée : ACL Anthology, PMLR, PLOS ou HAL")
    p.add_argument("--list", action="store_true", help="Affiche seulement les liens")
    args = p.parse_args()
    entries = json.loads(CATALOG.read_text(encoding="utf-8"))
    if args.source:
        entries = [e for e in entries if e["source"].lower() == args.source.lower()]
    if not entries:
        p.error("Aucune source correspondante")
    if args.list:
        for e in entries:
            print(f"{e['source']:14} | {e['filename']}\n  {e['article_url']}\n  PDF : {e['pdf_url']}")
        return 0
    DESTINATION.mkdir(parents=True, exist_ok=True)
    results = []
    for entry in entries:
        result = download_one(entry, DESTINATION)
        results.append(result)
        print(f"{entry['source']:14} : {result['status']:16} {entry['filename']}")
        if result.get("error"):
            print("  ", result["error"])
            print("   Téléchargement manuel possible depuis :", entry["article_url"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"created_at_utc": datetime.now(timezone.utc).isoformat(), "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    good = sum(r["status"] in {"downloaded", "already_present"} for r in results)
    print(f"\nBILAN : {good}/{len(results)} PDF présents et plausibles ; rapport : {REPORT.relative_to(ROOT)}")
    return 0 if good == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
