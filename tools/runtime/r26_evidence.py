"""Pin authoritative runtime/contract inputs; inventory frozen search adapters."""
import json
import sys
import time
from pathlib import Path
from r26_checks import AUDIT
from r21_checks import ROOT, sha, read
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tools/runtime')]


def main():
    names = [f'data/control/generic_runtime_{n}_v1_20261021_001.json' for n in
        ('encounter_contract','stage_objective_policy','wave_lifecycle','encounter_execution_census','stage_semantic_gaps')]
    names += ['data/control/generic_runtime_whole_battle_capability_v3_20261021_001.json',
        'data/control/generic_runtime_turn_contract_v1_20261011_001.json',
        'data/control/generic_runtime_global_turn_engine_v1_20261011_001.json',
        'data/control/generic_runtime_turn_execution_census_v1_20261011_001.json',
        'data/control/generic_runtime_whole_battle_capability_v2_20261021_001.json',
        'docs/agent/handoffs/generic_runtime_reference_encounter_lifecycle_20261021_001.md',
        'tmp/audit/r25_reference_encounter_20261021_001/functional_scenarios.json',
        'tmp/audit/r22_global_turn_engine_20261011_001/execution_traces.json']
    names += ['src/hsr_battle_agent/battle_runtime/'+n+'.py' for n in
        ('behavior','action_scheduler','battle_turn','encounter_runtime','resource_engine','damage_pipeline','defense_break')]
    names += ['src/hsr_battle_agent/'+n for n in ('reference_battle_planner/search.py','reference_battle_planner/adapter.py',
        'planner_search/search.py','battle_sandbox/sandbox.py')]
    pins=[]
    for name in names:
        p=ROOT/name; body=p.read_text(encoding='utf-8-sig')
        if p.suffix=='.json': json.loads(body)
        pins.append({'path':name,'sha256':sha(p),'bytes':p.stat().st_size})
    data={'authoritative_inputs':pins,'historical_search_inventory':{
        'reference_battle_planner':'Bounded source-order DFS over immutable M10 ReferenceBattleSession',
        'planner_search':'Bounded DFS over SANDBOX_RESOURCE_V1/TerraBattleState',
        'battle_sandbox':'Sandbox clone/execute; StrictSandbox step; frozen, different transition system',
        'beam_or_mcts_implementation_found':False,
        'decision':'Separate R26 adapter calls BehaviorRuntime public R22/R25 APIs; historical implementations unchanged'},
        'source_boundary':{'combat_roots':632,'decoded_joined_skill_roots':160,'joined_rows':161,
                           'source_closed_joined_transitions':0,'stable_nonempty_prefixes':72,'historical_nonempty_prefixes':73},
        'R22_target_constraint':'Candidate retrieval validates the full target pool; use min=1/max=pool_size for multi-target subset enumeration. No R22 modification.'}
    (AUDIT/'authoritative_input_inventory.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    from r26_reference_fixtures import encounter
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
    runtime,_=encounter('resource'); before=runtime.snapshot(); rows=[]
    for _ in range(3):
        start=time.perf_counter_ns(); branch=runtime.clone(); clone_ns=time.perf_counter_ns()-start
        start=time.perf_counter_ns(); snapshot=branch.snapshot(); snapshot_ns=time.perf_counter_ns()-start
        encoded=json.dumps(snapshot,sort_keys=True).encode('utf-8')
        start=time.perf_counter_ns(); restored=BehaviorRuntime.from_snapshot(json.loads(encoded)); restore_ns=time.perf_counter_ns()-start
        assert restored.snapshot()==before and runtime.snapshot()==before
        rows.append({'clone_ns':clone_ns,'snapshot_ns':snapshot_ns,'JSON_restore_ns':restore_ns,'snapshot_bytes':len(encoded)})
    (AUDIT/'clone_snapshot_profile.json').write_text(json.dumps({'samples':rows,'starting_hash':runtime.stable_hash(),
        'parent_unchanged':True,'timing_scope':'External diagnostic only. Timing never enters request, scores, search ordering, result hashes or reproducibility checks.'},indent=2)+'\n',encoding='utf-8')
    print('authoritative inputs pinned',len(pins),flush=True)

if __name__=='__main__':main()
