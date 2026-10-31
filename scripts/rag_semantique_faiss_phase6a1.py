"""Phase 6A.1 : embeddings Ollama + recherche vectorielle FAISS (sans Neo4j ni LLM génératif).

Prérequis: pip install numpy faiss-cpu ; modèle: ollama pull nomic-embed-text.
Ne modifie pas les données sources. Usage: --dry-run, --build, --check, --question.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.request
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed" / "chunks" / "pdf_chunks.jsonl"
INDEX_DIR = ROOT / "data" / "processed" / "faiss_nomic_v1"
REPORT = ROOT / "data" / "reports" / "faiss_semantic_last_query.json"
ENDPOINT = "http://127.0.0.1:11434/api/embed"
SCHEMA = "srai-faiss-semantic-v1"


def sha256(path: Path) -> str:
    d = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            d.update(chunk)
    return d.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Same directory, so os.replace is atomic on the same filesystem.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".tmp_", suffix=".json", delete=False) as f:
        t = Path(f.name)
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(t, path)


def load_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"Fichier chunks absent: {path}")
    rows, seen = [], set()
    with path.open("r", encoding="utf-8-sig") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON invalide, ligne {lineno}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Ligne {lineno}: objet JSON attendu")
            cid, did, txt, pg = (row.get(k) for k in ("chunk_id", "document_id", "text", "page_number"))
            if (not isinstance(cid, str) or not cid.strip() or cid in seen or
                not isinstance(did, str) or not did.strip() or
                not isinstance(txt, str) or not txt.strip() or
                type(pg) is not int or pg < 1):
                raise ValueError(f"Ligne {lineno}: chunk invalide ou identifiant dupliqué ({cid!r})")
            seen.add(cid)
            rows.append({"chunk_id": cid, "document_id": did, "page_number": pg,
                         "text": txt, "title": row.get("title") or did})
    if not rows:
        raise ValueError("Aucun chunk dans le corpus")
    return rows


def validate_vectors(data: Any, expected_rows: int, expected_dim: int | None = None) -> np.ndarray:
    try:
        mat = np.asarray(data, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise ValueError("Embeddings non numériques") from exc
    if mat.ndim != 2 or mat.shape[0] != expected_rows or mat.shape[1] < 2:
        raise ValueError(f"Dimensions embeddings incorrectes: {mat.shape}, attendu {expected_rows} lignes")
    if expected_dim is not None and mat.shape[1] != expected_dim:
        raise ValueError(f"Dimension du modèle modifiée: {mat.shape[1]} au lieu de {expected_dim}")
    if not np.isfinite(mat).all():
        raise ValueError("Embeddings contiennent NaN ou Inf")
    norms = np.linalg.norm(mat, axis=1)
    if np.any(norms <= 1e-12):
        raise ValueError("Embedding nul")
    return mat / norms[:, None]


def embed_texts(texts: list[str], model: str, endpoint: str, timeout: float) -> np.ndarray:
    if not texts or any(not isinstance(x, str) or not x.strip() for x in texts):
        raise ValueError("Textes d'embeddings vides ou invalides")
    payload = {"model": model, "input": texts, "truncate": False}
    req = urllib.request.Request(endpoint, method="POST",
             data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
             headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Ollama /api/embed inaccessible ({endpoint}): {exc}") from exc
    if not isinstance(result, dict) or "embeddings" not in result:
        raise RuntimeError("Ollama n'a pas retourné le champ 'embeddings'")
    return validate_vectors(result["embeddings"], len(texts))


def get_faiss():
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError("FAISS absent: .\\.venv\\Scripts\\python.exe -m pip install faiss-cpu") from exc
    return faiss


def build_index(input_path: Path, index_dir: Path, model: str, endpoint: str,
                batch_size: int, timeout: float) -> dict[str, Any]:
    if batch_size < 1 or batch_size > 64:
        raise ValueError("--batch-size doit être entre 1 et 64")
    rows = load_chunks(input_path)
    faiss = get_faiss()
    mats = []
    dim = None
    for start in range(0, len(rows), batch_size):
        batch = rows[start:start+batch_size]
        arr = embed_texts([r["text"] for r in batch], model, endpoint, timeout)
        if dim is None:
            dim = arr.shape[1]
        arr = validate_vectors(arr, len(batch), dim)
        mats.append(arr)
        print(f"EMBEDDINGS: {min(start+batch_size, len(rows))}/{len(rows)} chunks", flush=True)
    vectors = np.ascontiguousarray(np.concatenate(mats, axis=0), dtype=np.float32)
    idx = faiss.IndexFlatIP(vectors.shape[1])
    idx.add(vectors)
    if idx.ntotal != len(rows):
        raise RuntimeError("Le nombre de vecteurs FAISS ne correspond pas au nombre de chunks")
    index_dir.mkdir(parents=True, exist_ok=True)
    # Écritures préparées puis manifeste final comme marqueur d'une construction complète.
    tmp_index = index_dir / ".index_building.faiss"
    faiss.write_index(idx, str(tmp_index))
    index_path = index_dir / "index.faiss"
    os.replace(tmp_index, index_path)
    atomic_json(index_dir / "chunks.json", rows)
    manifest = {"schema": SCHEMA, "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "model": model, "dimension": int(vectors.shape[1]),
                "chunk_count": len(rows), "document_count": len({r['document_id'] for r in rows}),
                "input_sha256": sha256(input_path),
                "index_sha256": sha256(index_path),
                "metadata_sha256": sha256(index_dir / "chunks.json"),
                "similarity": "cosine (L2-normalized embeddings; FAISS inner product)",
                "index_type": "IndexFlatIP_exact"}
    atomic_json(index_dir / "manifest.json", manifest)
    return manifest


def read_index(input_path: Path, index_dir: Path, expected_model: str):
    manifest_path = index_dir / "manifest.json"
    metadata_path = index_dir / "chunks.json"
    index_path = index_dir / "index.faiss"
    if not (manifest_path.is_file() and metadata_path.is_file() and index_path.is_file()):
        raise ValueError("Index incomplet. Lancer --build pour le construire")
    meta = json.loads(manifest_path.read_text(encoding="utf-8"))
    if meta.get("schema") != SCHEMA or meta.get("model") != expected_model:
        raise ValueError("Modèle ou schéma d'index différent: relancer --build avec le même modèle")
    if sha256(input_path) != meta.get("input_sha256"):
        raise ValueError("Le corpus JSONL a changé depuis la création de l'index : reconstruire avec --build")
    if (sha256(index_path) != meta.get("index_sha256") or
        sha256(metadata_path) != meta.get("metadata_sha256")):
        raise ValueError("Index ou métadonnées FAISS modifiés / corrompus : reconstruire avec --build")
    rows = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != meta["chunk_count"] or not rows:
        raise ValueError("Métadonnées FAISS incohérentes")
    # IMPORTANT : faiss.read_index charge un fichier natif; uniquement nos fichiers locaux vérifiés par SHA256.
    faiss = get_faiss()
    idx = faiss.read_index(str(index_path))
    if idx.ntotal != len(rows) or idx.d != meta["dimension"]:
        raise ValueError("Index FAISS incohérent avec le manifeste")
    return idx, rows, meta


def semantic_search(index, rows: list[dict[str, Any]], query_vector: np.ndarray,
                    k: int, document_id: str | None = None) -> list[dict[str, Any]]:
    if k < 1 or k > 50:
        raise ValueError("top-k doit être dans [1, 50]")
    q = validate_vectors(query_vector, 1, index.d)
    # Le filtrage par document est fait après une recherche exhaustive sur notre petit corpus.
    distances, ids = index.search(np.ascontiguousarray(q, dtype=np.float32), index.ntotal)
    results = []
    for score, rowid in zip(distances[0], ids[0]):
        if rowid < 0:
            continue
        row = rows[int(rowid)]
        if document_id and row["document_id"] != document_id:
            continue
        results.append({**row, "score": round(float(score), 6), "retrieval": "FAISS_COSINE"})
        if len(results) == k:
            break
    return results


def run_cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Phase 6A.1 - Recherche sémantique avec Ollama et FAISS")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Valider le corpus sans Ollama ni écriture")
    group.add_argument("--build", action="store_true", help="Créer les embeddings et l'index FAISS")
    group.add_argument("--check", action="store_true", help="Vérifier les index existants sans Ollama")
    group.add_argument("--question", help="Question de recherche sémantique, sans génération")
    p.add_argument("--input", type=Path, default=INPUT)
    p.add_argument("--index-dir", type=Path, default=INDEX_DIR)
    p.add_argument("--model", default="nomic-embed-text")
    p.add_argument("--endpoint", default=ENDPOINT)
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--document-id")
    p.add_argument("--output", type=Path, default=REPORT)
    args = p.parse_args(argv)
    if args.dry_run:
        rows = load_chunks(args.input)
        print(f"DRY RUN OK: {len(rows)} chunks / {len({r['document_id'] for r in rows})} documents, aucun appel Ollama, aucune écriture.")
        return 0
    if args.build:
        meta = build_index(args.input, args.index_dir, args.model, args.endpoint, args.batch_size, args.timeout)
        print("INDEX FAISS OK:", json.dumps(meta, ensure_ascii=False, indent=2))
        return 0
    index, rows, meta = read_index(args.input, args.index_dir, args.model)
    if args.check:
        print(f"INDEX CHECK OK: {index.ntotal} vecteurs, dimension {index.d}, modèle {meta['model']}")
        return 0
    if not args.question.strip():
        raise ValueError("La question ne doit pas être vide")
    vec = embed_texts([args.question], args.model, args.endpoint, args.timeout)
    hits = semantic_search(index, rows, vec, args.top_k, args.document_id)
    print(f"RECHERCHE FAISS: {len(hits)} passages | modèle={args.model} | corpus={len(rows)} chunks")
    import re
    for i, r in enumerate(hits, 1):
        print(f"[{i}] {r['document_id']} | page {r['page_number']} | {r['chunk_id']} | cosinus={r['score']:.3f}")
        print("    " + re.sub(r"\s+", " ", r["text"])[:180] + "...")
    atomic_json(args.output, {"pipeline": "semantic_faiss_6a1", "model": args.model,
             "question": args.question, "retrieved": hits, "chunks_in_corpus": len(rows),
             "note": "Recherche sémantique seule. Ni génération LLM ni GraphRAG ni reranking."})
    print(f"RAPPORT: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run_cli())
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print("ERREUR:", str(exc), file=sys.stderr)
        sys.exit(1)
