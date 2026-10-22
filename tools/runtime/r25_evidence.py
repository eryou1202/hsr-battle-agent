"""Bounded existing 4.6.51 catalog/metadata pass; no source extraction."""
import collections
import json
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime')]
from r25_checks import AUDIT, write
from r21_checks import read, sha
from r24_evidence import objects
from r16_dependency_closure import load_catalog
from hsr_battle_agent.battle_ir.behavior import stable_hash

def main():
    authoritative = [
        'data/control/generic_runtime_turn_contract_v1_20261011_001.json',
        'data/control/generic_runtime_turn_acceptance_matrix_v1_20261011_001.json',
        'data/control/generic_runtime_turn_execution_census_v1_20261011_001.json',
        'tmp/audit/r22_global_turn_engine_20261011_001/execution_traces.json',
        'docs/agent/handoffs/generic_runtime_real_skill_root_closure_20261012_001.md',
        'data/control/generic_runtime_semantic_gap_ledger_v9_20261012_001.json',
        'data/control/generic_runtime_defense_evidence_v1_20261021_001.json',
        'data/control/generic_runtime_whole_battle_capability_v2_20261021_001.json',
        'tmp/audit/r24_defense_break_shield_20261021_001/functional_scenarios.json',
        'src/hsr_battle_agent/battle_runtime/defense_break.py']
    pins = []
    for name in authoritative:
        data = (ROOT/name).read_text(encoding='utf-8-sig')
        if name.endswith('.json'): json.loads(data)
        pins.append({'artifact': name, 'sha256': sha(ROOT/name), 'bytes': (ROOT/name).stat().st_size})
    from r13_frozen_reader import SNAPSHOT, MANIFEST_SHA
    assert sha(SNAPSHOT/'SNAPSHOT_MANIFEST.json') == MANIFEST_SHA
    observations = []
    catalog = load_catalog()
    for key, record in catalog.records.items():
        graph = record.get('graph')
        if not graph: continue
        assert stable_hash(graph) == record['graph_hash']
        assert record['source_manifest_sha256'] == MANIFEST_SHA
        for pointer, obj in objects(graph):
            concrete = obj.get('type', '')
            if not isinstance(concrete, str): continue
            if not re.search(r'stage|wave|encounter|spawn|victory|defeat|battleend|entitydead', concrete, re.I): continue
            if not concrete.startswith('RPG.') or type(obj.get('start')) is not int: continue
            observations.append({'artifact': record['decoded_artifact'],
                'artifact_sha256': sha(ROOT/record['decoded_artifact']), 'json_pointer': '/graph'+pointer,
                'source_span': [obj['start'], obj.get('end')], 'type': concrete,
                'body_sha256': stable_hash(obj), 'record_identity': record['identity'],
                'source_identity': list(key), 'source_version': '4.6.51',
                'native_semantics': 'UNKNOWN', 'executable_stage_binding': False})
    # Small documented metadata anchor set, at most three exact matching rows per file.
    anchors = []
    folder = ROOT/'tmp/audit/r11_4651_natasha_semantic_closure_20261005_001'
    for name in ('runtime_named_methods.json', 'runtime_core_inventory.json', 'followup_type_inventory.json'):
        path = folder/name
        doc = read(path)
        matches = [(p, o) for p, o in objects(doc) if isinstance(o.get('name'), str) and
            re.search(r'Wave|Stage|BattleEnd|Defeat|Die|Dead|Spawn', o['name'])][:3]
        for pointer, obj in matches:
            anchors.append({'artifact': path.relative_to(ROOT).as_posix(), 'sha256': sha(path),
                'json_pointer': pointer, 'name': obj['name'], 'body_sha256': stable_hash(obj),
                'details': {k: obj[k] for k in ('rva', 'index', 'offset') if k in obj},
                'authority': 'METADATA_CANDIDATE_ONLY', 'source_version': '4.6.51',
                'uncertainty': 'Name/address is not a wave configuration, effective callback, or terminal rule'})
    background = ROOT/'data/control/stage_encounter_product_projection_20260928_001.json'
    if background.exists(): read(background)
    output = {'schema': 'r25_bounded_stage_evidence/1', 'source_version': '4.6.51',
        'trusted_snapshot_manifest_sha256': MANIFEST_SHA, 'authoritative_input_pins': pins,
        'catalog_records': len(catalog.records), 'decoded_records': sum(bool(r.get('graph')) for r in catalog.records.values()),
        'structural_candidates': observations, 'direct_metadata_anchors': anchors,
        'new_native_bodies': 0, 'native_dependency_hops': 0, 'IFix_Lua_excavation': False,
        'native_stage_content_bound': 0,
        'unknown_fields': ['stage configuration', 'enemy group membership', 'wave ordering', 'spawn rules',
            'native defeat/victory rules', 'effective actor callbacks', 'native encounter completion signals'],
        'tickets': [{'id': 'R25-SOURCE-'+str(i+1).zfill(2), 'required_evidence': question,
            'status': 'UNKNOWN', 'authority': 'EXACT_SAME_BUILD_EVIDENCE_REQUIRED'}
            for i, question in enumerate(['Pinned encounter config and complete reader', 'Enemy group and ordered wave/spawn records',
                'Effective life-state callback and completion dispatch binding', 'Terminal objective and mode rule binder'])],
        'product_background': {'source_version': '4.4.54', 'authority': 'BACKGROUND_ONLY_NO_CROSS_VERSION_PROMOTION',
            'artifact': background.relative_to(ROOT).as_posix(), 'sha256': sha(background)} if background.exists() else None,
        'decision': 'Implement explicitly authored REFERENCE encounter; no recovered native stage equivalence'}
    write('stage_evidence.json', output)
    print('bounded stage evidence', len(observations), 'structural candidates,', len(anchors), 'metadata anchors; native binding 0', flush=True)

if __name__ == '__main__': main()
