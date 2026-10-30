"""Phase 2B-1 : decouper les pages PDF en passages tracables.

Depuis la racine du projet :
  python scripts/chunk_pdf_pages.py
  python scripts/chunk_pdf_pages.py --upload-hdfs

Aucun LLM n'est appele. Aucune information scientifique n'est inventee.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'data' / 'processed' / 'pdf_pages.jsonl'
OUTPUT = ROOT / 'data' / 'processed' / 'chunks' / 'pdf_chunks.jsonl'
REPORT = ROOT / 'data' / 'reports' / 'pdf_chunking_report.json'
COMPOSE = ROOT / 'docker' / 'hdfs' / 'compose.yaml'
HDFS_OUT_DIR = '/scientific-research-ai/processed/chunks'
HDFS_OUT_FILE = HDFS_OUT_DIR + '/pdf_chunks.jsonl'
METADATA_KEYS = ('document_id', 'source', 'title', 'authors', 'year', 'doi',
                 'article_url', 'pdf_filename', 'hdfs_pdf_path', 'pdf_sha256',
                 'page_number', 'page_count', 'extraction_status', 'extraction_method')


def normalize_text(text):
    """Normalize whitespace only; never alter semantic or scientific content."""
    if not isinstance(text, str):
        return ''
    return re.sub(r'\s+', ' ', text.replace('\x00', '')).strip()


def chunk_spans(text, max_chars=1200, overlap=180):
    """Yield (start,end) spans in normalized page, with overlap and no gaps."""
    if max_chars < 100 or overlap < 0 or overlap >= max_chars // 2:
        raise ValueError('Invalid max_chars/overlap (need 0 <= overlap < max_chars / 2)')
    n = len(text)
    start = 0
    while start < n:
        end = min(n, start + max_chars)
        if end < n:
            # Prefer breaking at a space near the end of the window.
            boundary = text.rfind(' ', start + max_chars // 2, end + 1)
            if boundary > start:
                end = boundary
        if end <= start:
            raise ValueError('Chunker did not make forward progress')
        yield start, end
        if end == n:
            break
        candidate = max(start + 1, end - overlap)
        # Move forward to the next word boundary; do not exceed prior chunk end.
        if candidate > 0 and text[candidate - 1] != ' ':
            next_space = text.find(' ', candidate, end)
            if next_space >= 0:
                candidate = next_space + 1
        start = candidate
        while start < n and text[start].isspace():
            start += 1


def process_pages(input_file, max_chars=1200, overlap=180):
    """Parse validated page records and return chunks plus an explicit report."""
    if not input_file.is_file():
        raise FileNotFoundError(f'Missing input: {input_file}')
    chunks, warnings = [], []
    page_keys = set()
    counts = Counter()
    doc_ids = set()
    with input_file.open('r', encoding='utf-8-sig') as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                page = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f'Invalid JSON at line {line_no}: {e}') from e
            if not isinstance(page, dict):
                raise ValueError(f'Expected JSON object on line {line_no}')
            doc_id, page_number = page.get('document_id'), page.get('page_number')
            if not isinstance(doc_id, str) or not doc_id or not isinstance(page_number, int) or page_number < 1:
                raise ValueError(f'Missing document_id or invalid page_number on line {line_no}')
            key = doc_id, page_number
            if key in page_keys:
                raise ValueError(f'Duplicate document/page: {key}')
            page_keys.add(key)
            doc_ids.add(doc_id)
            counts['pages_total'] += 1
            if page.get('extraction_status') != 'ok':
                counts['pages_flagged_from_pdf_extraction'] += 1
            text = normalize_text(page.get('text'))
            if not text:
                counts['pages_empty_skipped'] += 1
                warnings.append({'document_id': doc_id, 'page_number': page_number, 'reason': 'no_text'})
                continue
            counts['pages_chunked'] += 1
            spans = list(chunk_spans(text, max_chars, overlap))
            for i, (start, end) in enumerate(spans, start=1):
                fragment = text[start:end].strip()
                if not fragment:
                    continue
                record = {field: page.get(field) for field in METADATA_KEYS}
                record.update({
                    'chunk_id': f'{doc_id}_p{page_number:03d}_c{i:03d}',
                    'chunk_number_on_page': i,
                    'chunks_on_page': len(spans),
                    'char_start_on_page': start,
                    'char_end_on_page': end,
                    'text': fragment,
                    'char_count': len(fragment),
                    'word_count': len(fragment.split()),
                    'chunking_method': 'whitespace-window-overlap-v1',
                })
                chunks.append(record)
    if not chunks:
        raise ValueError('No chunks: every page is empty, or input is empty')
    chunk_ids = [chunk['chunk_id'] for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError('Duplicate chunk_id; refusing to write output')
    report = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'input': str(input_file.relative_to(ROOT)) if input_file.is_relative_to(ROOT) else str(input_file),
        'documents': len(doc_ids), 'pages_total': counts['pages_total'],
        'pages_chunked': counts['pages_chunked'],
        'pages_empty_skipped': counts['pages_empty_skipped'],
        'pages_flagged_from_pdf_extraction': counts['pages_flagged_from_pdf_extraction'],
        'chunks': len(chunks), 'max_chars': max_chars, 'overlap_chars': overlap,
        'warnings': warnings,
        'note': 'Text remains automatically extracted and unverified. Chunking is character-based, not LLM token counting.',
    }
    return chunks, report


def write_outputs(chunks, report, output=OUTPUT, report_file=REPORT):
    output.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_name(output.name + '.part')
    temp_report = report_file.with_name(report_file.name + '.part')
    try:
        with temp_output.open('w', encoding='utf-8', newline='\n') as handle:
            for chunk in chunks:
                handle.write(json.dumps(chunk, ensure_ascii=False) + '\n')
        temp_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(temp_output, output)
        os.replace(temp_report, report_file)
    finally:
        temp_output.unlink(missing_ok=True)
        temp_report.unlink(missing_ok=True)


def docker_hdfs(*hdfs_args):
    command = ['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T', 'namenode',
               'hdfs', 'dfs', *hdfs_args]
    result = subprocess.run(command, cwd=ROOT, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip() or str(command))
    return result.stdout


def upload_hdfs():
    if not COMPOSE.is_file():
        raise FileNotFoundError(f'HDFS configuration missing: {COMPOSE}')
    docker_hdfs('-mkdir', '-p', HDFS_OUT_DIR)
    # Docker mount: host data/ -> container /project-data (read-only).
    docker_hdfs('-put', '-f', '/project-data/processed/chunks/pdf_chunks.jsonl', HDFS_OUT_FILE)
    docker_hdfs('-test', '-e', HDFS_OUT_FILE)
    actual = subprocess.run(['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T',
                             'namenode', 'bash', '-c',
                             f'hdfs dfs -cat {HDFS_OUT_FILE} | sha256sum'],
                            cwd=ROOT, capture_output=True)
    if actual.returncode:
        raise RuntimeError('Unable to verify HDFS SHA-256: ' + actual.stderr.decode(errors='replace'))
    remote_hash = actual.stdout.decode('ascii').split()[0]
    local_hash = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    if remote_hash != local_hash:
        raise RuntimeError('HDFS content differs from local file (SHA-256 mismatch)')
    print(f'HDFS upload and SHA-256 verified: {HDFS_OUT_FILE}')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build traceable scientific paper text chunks')
    parser.add_argument('--max-chars', type=int, default=1200)
    parser.add_argument('--overlap', type=int, default=180)
    parser.add_argument('--upload-hdfs', action='store_true')
    args = parser.parse_args(argv)
    try:
        chunks, report = process_pages(INPUT, args.max_chars, args.overlap)
        write_outputs(chunks, report)
        print(f"CHUNKING OK: {report['documents']} documents, {report['pages_total']} pages, {len(chunks)} passages")
        print(f"Pages sans texte : {report['pages_empty_skipped']} ; pages avec avertissement pypdf : {report['pages_flagged_from_pdf_extraction']}")
        print(f'JSONL: {OUTPUT.relative_to(ROOT)}')
        print(f'Rapport: {REPORT.relative_to(ROOT)}')
        if args.upload_hdfs:
            upload_hdfs()
    except (ValueError, FileNotFoundError, RuntimeError, OSError) as error:
        print(f'ERREUR : {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
