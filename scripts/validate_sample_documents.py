"""Vérifie les fichiers locaux et leur SHA256, sans accès réseau."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRIES = json.loads((ROOT / "config" / "sample_documents.json").read_text(encoding="utf-8"))
DIRECTORY = ROOT / "data" / "sample_documents"


def pdf_header_ok(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 128:
        return False
    with path.open("rb") as f:
        return f.read(1024).lstrip().startswith(b"%PDF-")


def main():
    good = 0
    for entry in ENTRIES:
        path = DIRECTORY / entry["filename"]
        if not pdf_header_ok(path):
            print(f"MANQUANT OU INVALIDE : {entry['source']:14} -> {path.relative_to(ROOT)}")
            continue
        with path.open("rb") as f:
            sha = hashlib.file_digest(f, "sha256").hexdigest()
        print(f"OK {entry['source']:14} | {path.stat().st_size:>8} octets | SHA256 {sha[:16]}... | {entry['filename']}")
        good += 1
    print(f"\nVALIDATION : {good}/{len(ENTRIES)} PDF présents et avec en-tête PDF valide.")
    print("N.B. Ce contrôle ne garantit pas que tout le contenu est lisible.")
    return 0 if good == len(ENTRIES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
