"""Read V3 results only; print invalid reference fields and valid ID inventory."""
from pathlib import Path
import json

root=Path(__file__).resolve().parents[1]
file=root/'data'/'processed'/'llm'/'knowledge_preview_v3.jsonl'
if not file.is_file():
    raise SystemExit(f'Missing V3 output: {file}')
for line in file.open(encoding='utf-8'):
    if not line.strip():
        continue
    row=json.loads(line)
    entities={e['id']:f"{e['name']} ({e['type']})" for e in row.get('entities',[])}
    print(f"\n{row.get('document_id')} | Validated IDs:")
    for ident,name in entities.items():
        print(' ',ident,'=',name)
    for r in row.get('rejected_relations',[]):
        item=r.get('item') or {}
        print(' REJECT:',r.get('reason'), 'subject_id=',repr(item.get('subject_id')),
              'object_id=',repr(item.get('object_id')),
              'predicate=',repr(item.get('predicate')),
              'evidence_id=',repr(item.get('evidence_id')))
