"""Independent serialized-search repeat, complete caller immutability and PV replay."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tools/runtime')]
from r26_checks import AUDIT
from r21_checks import read
from hsr_battle_agent.battle_ir.behavior import stable_hash
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.planner_bridge import PlannerRequest,plan,replay_principal_variation

def write(name,doc):
    (AUDIT/name).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def main():
    expected=read(AUDIT/'P01/result.json')
    if not (AUDIT/'P01/initial_runtime.json').exists():
        from r26_reference_fixtures import encounter
        fixture,_=encounter('choice')
        assert fixture.stable_hash()==expected['starting_runtime_hash']
        write('P01/initial_runtime.json',fixture.snapshot())
    initial=read(AUDIT/'P01/initial_runtime.json')
    runtime=BehaviorRuntime.from_snapshot(initial); before=runtime.snapshot(); prior_hash=runtime.stable_hash()
    q=PlannerRequest.from_dict(json.loads(json.dumps(expected['request'])))
    actual=plan(runtime,q).to_dict(); after=runtime.snapshot()
    assert actual==expected and before==after and runtime.stable_hash()==prior_hash
    assert json.dumps(before,sort_keys=True).encode()==json.dumps(after,sort_keys=True).encode()
    restored=BehaviorRuntime.from_snapshot(json.loads(json.dumps(before)))
    assert plan(restored,q).to_dict()==expected
    end=replay_principal_variation(runtime,expected)
    assert end.snapshot()==expected['chosen_branch']['runtime_snapshot']
    if (AUDIT/'P01/final_runtime.json').exists():
        assert end.snapshot()==read(AUDIT/'P01/final_runtime.json')
    else:write('P01/final_runtime.json',end.snapshot())
    write('original_runtime_before.json',before); write('original_runtime_after.json',after)
    turn=before['state']['mechanics']['battle_turn_v1']
    checks={'complete_snapshot':True,'stable_hash':True,'sorted_JSON_bytes':True,'rng_draw_count':True,
        'R22_permissions':True,'active_R15_ownership':True,'R25_encounter_cursor':True,
        'serialized_search_result_exact':True,'JSON_restored_search_exact':True,'principal_variation_replay':True}
    write('immutability_and_replay.json',{'status':'PASS','checks':checks,'starting_hash':prior_hash,
        'after_hash':runtime.stable_hash(),'before_snapshot_hash':stable_hash(before),'after_snapshot_hash':stable_hash(after),
        'rng_draws_before':before['state']['rng']['draws'],'rng_draws_after':after['state']['rng']['draws'],
        'permissions':turn['permissions'],'active_stack':turn['active_stack'],
        'R15_ownership_hash':stable_hash(before['state']['scheduler']['action_execution']),
        'encounter_cursor_hash':stable_hash(before['state']['mechanics']['reference_encounter_v1']),
        'replayed_branch_hash':end.stable_hash(),'result_hash':expected['result_hash']})
    print('serialized search repeat / immutability / PV replay PASS',flush=True)

if __name__=='__main__':main()
