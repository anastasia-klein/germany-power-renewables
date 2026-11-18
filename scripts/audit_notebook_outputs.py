"""Inventory authentic notebook outputs separately from source-only Git exports."""
import ast
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def inspect(path):
    document=json.loads(path.read_text())
    code=[c for c in document['cells'] if c['cell_type']=='code']
    reference=ROOT/'notebooks'/path.name
    parity=None
    if 'fabric_runs/2026-11-18' in str(path) and reference.exists():
        def syntax(p):
            d=json.loads(p.read_text())
            text='\n\n'.join(''.join(c['source']) for c in d['cells'] if c['cell_type']=='code')
            return ast.dump(ast.parse(text))
        parity=syntax(path)==syntax(reference)
    return {'path':str(path.relative_to(ROOT)), 'code_matches_versioned_source':parity, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'code_cells':len(code),'cells_with_output':sum(bool(c.get('outputs')) for c in code),
        'executed_cells':sum(c.get('execution_count') is not None for c in code),
        'error_outputs':sum(o.get('output_type')=='error' for c in code for o in c.get('outputs',[]))}

if __name__=='__main__':
    paths=sorted((ROOT/'notebooks').glob('*.ipynb'))+sorted((ROOT/'evidence').rglob('*.ipynb'))
    report={'audited_on':'2026-11-18','policy':'Source-only exports, Fabric execution exports and independent local EDA evidence are inventoried separately; no execution outputs are fabricated.','notebooks':[inspect(p) for p in paths]}
    (ROOT/'evidence/fabric_runs/output_inventory.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
