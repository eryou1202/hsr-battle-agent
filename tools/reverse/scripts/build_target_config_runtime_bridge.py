import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_batch_evidence import NORMALIZED_BASE, iter_records

# Pass 1: parameters by method
param_refs = defaultdict(list)
for rec in iter_records(NORMALIZED_BASE / 'parameters.json'):
    param_refs[rec['method_index']].append(rec['type_reference'])

# Pass 2: types index
types = {}
for rec in iter_records(NORMALIZED_BASE / 'types.json'):
    types[rec['type_index']] = rec

# Pass 3: methods -> config serializer signatures and evaluator ctors
configs = {}   # typeref -> list of config type infos
evaluators = {}  # typeref -> list of evaluator class infos
methods_by_type = defaultdict(list)
for rec in iter_records(NORMALIZED_BASE / 'methods.json'):
    methods_by_type[rec['declaring_type_index']].append(rec)

for ti, ms in methods_by_type.items():
    t = types.get(ti, {})
    name = t.get('full_name', '')
    names = [m['name'] for m in ms]
    if any(m['name'] in ('Transform', 'Evaluate') for m in ms) and 'MGMEGEDLMAK' not in names:
        # generated evaluator class: match ctor param ref
        ctor = next((m for m in ms if m['name'] == '.ctor'), None)
        if ctor is not None and len(param_refs.get(ctor['method_index'], [])) == 1:
            tr = param_refs[ctor['method_index']][0]
            evaluators.setdefault(tr, []).append({
                'type_index': ti,
                'full_name': name,
                'ctor_method_index': ctor['method_index'],
                'ctor_native_rva': ctor.get('native_rva'),
                'exec_methods': [
                    {
                        'method_index': m['method_index'],
                        'name': m['name'],
                        'native_rva': m.get('native_rva'),
                        'parameter_count': m['parameter_count'],
                        'parameter_refs': param_refs.get(m['method_index'], []),
                        'return_type_reference': m['return_type_reference'],
                    }
                    for m in ms if m['name'] in ('Transform', 'Evaluate')
                ],
            })
    if 'MGMEGEDLMAK' in names and 'OJNNBEJLDIJ' in names and 'LJACLBNEEEB' in names:
        # serializer config family; use MGMEGEDLMAK param2 as runtime object type ref
        mg = next(m for m in ms if m['name'] == 'MGMEGEDLMAK')
        refs = param_refs.get(mg['method_index'], [])
        if len(refs) == 2 and not name.endswith('`1'):
            configs.setdefault(refs[1], []).append({
                'type_index': ti,
                'full_name': name,
                'method_index': mg['method_index'],
                'native_rva': mg.get('native_rva'),
            })

print(f"config type_refs={len(configs)} evaluator type_refs={len(evaluators)}")
rows = []
for tr, evs in sorted(evaluators.items()):
    cfs = configs.get(tr, [])
    for ev in evs:
        rows.append({
            'config_type_ref': tr,
            'config_candidates': [c['full_name'] for c in cfs],
            'evaluator_type': ev['full_name'],
            'evaluator_type_index': ev['type_index'],
            'execution_methods': ev['exec_methods'],
        })
        print(f"ref={tr:>7} eval={ev['full_name']:16} <- {[c['full_name'] for c in cfs]} "
              f"exec={[(m['name'], m['native_rva']) for m in ev['exec_methods']]}")

unmatched = [tr for tr in evaluators if tr not in configs]
print(f"\nunmatched evaluator refs: {len(unmatched)} -> {unmatched[:50]}")
out = {
    'schema': 'target_selector_config_runtime_bridge/1',
    'config_type_ref_count': len(configs),
    'evaluator_type_ref_count': len(evaluators),
    'matched_rows': rows,
    'unmatched_evaluator_refs': unmatched,
}
out_path = Path('data/raw/4.4.54/target_config_runtime_bridge_05.json')
out_path.parent.mkdir(parents=True, exist_ok=True)
with out_path.open('w', encoding='utf-8') as f:
    json.dump(out, f, indent=2)
print(f"wrote {out_path} rows={len(rows)}")
