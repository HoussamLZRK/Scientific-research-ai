"""Vérification élémentaire du fichier généré par le crawler."""

import json
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/publications.jsonl")
    if not path.is_file():
        print(f"ERREUR : fichier introuvable : {path}")
        return 1

    errors = []
    rows = []
    ids = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"ligne {line_number} : JSON invalide")
            continue
        rows.append(item)
        for key in ("paper_id", "title", "year", "url"):
            if not item.get(key):
                errors.append(f"ligne {line_number} : champ {key} manquant")
        if not isinstance(item.get("authors"), list) or not item["authors"]:
            errors.append(f"ligne {line_number} : auteurs absents")
        if item.get("paper_id") in ids:
            errors.append(f"ligne {line_number} : doublon {item.get('paper_id')}")
        ids.add(item.get("paper_id"))

    print(f"Publications collectées : {len(rows)}")
    print(f"Résumés disponibles : {sum(bool(r.get('abstract')) for r in rows)}")
    for row in rows[:3]:
        print(" -", row.get("paper_id"), "|", row.get("title"))
    if not rows:
        errors.append("aucune publication trouvée")
    if errors:
        print("\nPROBLÈMES DÉTECTÉS :")
        for error in errors:
            print(" -", error)
        return 1
    print("\nVALIDATION OK : structure élémentaire vérifiée.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
