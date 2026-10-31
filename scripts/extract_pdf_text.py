"""Phase 2A : extraire le texte des PDF scientifiques, page par page.

Depuis la racine du projet :
  python scripts/extract_pdf_text.py --source hdfs --upload-hdfs
  python scripts/extract_pdf_text.py --source local

Aucune donnée brute n'est modifiée. Pas d'OCR ni d'extraction d'entités par LLM.
"""

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    raise SystemExit("pypdf manque : .\\.venv\\Scripts\\python.exe -m pip install pypdf")

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "config" / "sample_documents.json"
PDF_DIR = ROOT / "data" / "sample_documents"
OUTPUT = ROOT / "data" / "processed" / "pdf_pages.jsonl"
REPORT = ROOT / "data" / "reports" / "pdf_extraction_report.json"
COMPOSE = ROOT / "docker" / "hdfs" / "compose.yaml"
HDFS_INPUT = "/scientific-research-ai/raw/sample_documents"
HDFS_OUTPUT = "/scientific-research-ai/processed/text"
MIN_TEXT_CHARS = 80
MAX_PDF_BYTES = 50 * 1024 * 1024


def normalized_text(raw: str | None) -> str:
    """Nettoyage léger, sans modification sémantique ni invention de texte."""
    if not raw:
        return ""
    text = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def invoke_docker_hdfs(*args: str, binary: bool = False) -> bytes | str:
    """Évite PowerShell pour les octets binaires des PDF."""
    if not COMPOSE.is_file():
        raise RuntimeError(f"Configuration HDFS absente : {COMPOSE}")
    command = ["docker", "compose", "-f", str(COMPOSE), "exec", "-T", "namenode", "hdfs", "dfs", *args]
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        err = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"HDFS : {err or 'échec de la commande'}")
    return result.stdout if binary else result.stdout.decode("utf-8", errors="replace")


def pdf_bytes(entry: dict, source: str) -> bytes:
    name = entry.get("filename")
    if not isinstance(name, str) or Path(name).name != name or not name.lower().endswith(".pdf"):
        raise ValueError("Nom de PDF non sécurisé dans le catalogue")
    if source == "local":
        data = (PDF_DIR / name).read_bytes()
    else:
        data = invoke_docker_hdfs("-cat", f"{HDFS_INPUT}/{name}", binary=True)
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF trop volumineux (> 50 Mo)")
    if not data[:1024].lstrip().startswith(b"%PDF-"):
        raise ValueError("Le fichier n'a pas d'en-tête PDF valide")
    return data


def extract_document(entry: dict, data: bytes, source_mode: str) -> tuple[list[dict], dict]:
    """Une ligne JSONL par page, même lorsque cette page n'a pas de texte exploitable."""
    reader = PdfReader(io.BytesIO(data), strict=False)
    if reader.is_encrypted:
        raise ValueError("PDF chiffré non pris en charge")
    count = len(reader.pages)
    if count == 0:
        raise ValueError("PDF sans page")
    sha256 = hashlib.sha256(data).hexdigest()
    records = []
    blank_pages = 0
    low_text_pages = 0
    for index, page in enumerate(reader.pages, start=1):
        extraction_error = None
        try:
            text = normalized_text(page.extract_text())
        except Exception as exc:
            text = ""
            extraction_error = f"{type(exc).__name__}: {str(exc)[:200]}"
        if not text:
            status = "empty_or_scanned"
            blank_pages += 1
        elif len(text) < MIN_TEXT_CHARS:
            status = "low_text"
            low_text_pages += 1
        else:
            status = "ok"
        record = {
            "document_id": entry["id"],
            "source": entry["source"],
            "title": entry["title"],
            "authors": entry.get("authors", []),
            "year": entry.get("year"),
            "doi": entry.get("doi"),
            "article_url": entry["article_url"],
            "pdf_filename": entry["filename"],
            "hdfs_pdf_path": f"{HDFS_INPUT}/{entry['filename']}",
            "pdf_sha256": sha256,
            "page_number": index,
            "page_count": count,
            "text": text,
            "char_count": len(text),
            "word_count": len(text.split()),
            "extraction_status": status,
            "extraction_method": "pypdf",
        }
        if extraction_error:
            record["extraction_error"] = extraction_error
        records.append(record)
    summary = {
        "document_id": entry["id"],
        "source": entry["source"],
        "pdf_filename": entry["filename"],
        "source_mode": source_mode,
        "pdf_sha256": sha256,
        "total_pages": count,
        "empty_or_scanned_pages": blank_pages,
        "low_text_pages": low_text_pages,
        "total_chars": sum(r["char_count"] for r in records),
        "status": "needs_review" if blank_pages or low_text_pages else "ok",
    }
    return records, summary


def save_outputs(records: list[dict], report: dict) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    jsonl_temp = OUTPUT.with_suffix(".jsonl.part")
    report_temp = REPORT.with_suffix(".json.part")
    try:
        with jsonl_temp.open("w", encoding="utf-8", newline="\n") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        report_temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        jsonl_temp.replace(OUTPUT)
        report_temp.replace(REPORT)
    finally:
        jsonl_temp.unlink(missing_ok=True)
        report_temp.unlink(missing_ok=True)


def upload_hdfs() -> None:
    # Le volume monté /project-data est en lecture seule : HDFS écrit dans son propre espace.
    invoke_docker_hdfs("-mkdir", "-p", HDFS_OUTPUT)
    invoke_docker_hdfs("-put", "-f", "/project-data/processed/pdf_pages.jsonl", HDFS_OUTPUT + "/")
    invoke_docker_hdfs("-test", "-e", HDFS_OUTPUT + "/pdf_pages.jsonl")
    print(f"Données extraites envoyées dans HDFS : {HDFS_OUTPUT}/pdf_pages.jsonl")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extrait les pages des 4 PDF scientifiques")
    parser.add_argument("--source", choices=("hdfs", "local"), default="hdfs", help="Provenance du PDF (défaut : HDFS)")
    parser.add_argument("--upload-hdfs", action="store_true", help="Copie le JSONL généré dans HDFS")
    args = parser.parse_args(argv)
    if not CATALOG.is_file():
        parser.error(f"Catalogue introuvable : {CATALOG}")
    entries = json.loads(CATALOG.read_text(encoding="utf-8"))
    if len(entries) != 4:
        parser.error(f"Quatre documents attendus dans le catalogue, trouvé : {len(entries)}")
    all_records, summaries = [], []
    for entry in entries:
        try:
            data = pdf_bytes(entry, args.source)
            page_records, summary = extract_document(entry, data, args.source)
        except Exception as exc:
            print(f"ERREUR : {entry.get('filename', 'PDF inconnu')} : {exc}", file=sys.stderr)
            print("Aucun nouveau résultat JSONL ne sera enregistré.", file=sys.stderr)
            return 1
        all_records.extend(page_records)
        summaries.append(summary)
        print(f"{entry['source']:14} | {summary['total_pages']:3} pages | {summary['total_chars']:7} caractères | {summary['status']}")
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_source": args.source,
        "documents": len(summaries),
        "pages": len(all_records),
        "pages_with_text": sum(bool(r["text"]) for r in all_records),
        "warnings": sum(r["extraction_status"] != "ok" for r in all_records),
        "documents_detail": summaries,
        "notes": "Texte extrait automatiquement, non corrigé. Les tableaux, équations, images et PDF scannés peuvent nécessiter une analyse spécifique.",
    }
    save_outputs(all_records, report)
    print(f"\nEXTRACTION : {len(summaries)}/4 documents, {len(all_records)} pages, {report['warnings']} avertissement(s).")
    print(f"Sortie : {OUTPUT.relative_to(ROOT)}")
    print(f"Rapport : {REPORT.relative_to(ROOT)}")
    if args.upload_hdfs:
        try:
            upload_hdfs()
        except Exception as exc:
            print(f"ERREUR de transfert du JSONL extrait vers HDFS : {exc}", file=sys.stderr)
            return 1
    print("Phase 2A - extraction PDF terminée. Pas encore d'extraction d'entités par LLM.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
