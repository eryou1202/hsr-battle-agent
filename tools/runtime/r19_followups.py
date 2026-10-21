"""Original R18 isolated and six ability-root fixtures; no graph edits."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r19_checks import read,write
from r19_reference_fixtures import extend,effective_binding
from r19_probes import R18,annotate
from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes,stable_hash
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState
from hsr_battle_agent.battle_runtime.dynamic_property import POLICY_ID,reference_policy
from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE

def ability_runtime(row):
    inputs=row['initial_runtime'];root=IRNode.from_dict(inputs['source_root'])
    state,policies=extend(BehaviorBattleState.from_snapshot(inputs['state']),inputs['policies'],list(walk_nodes(root)))
    return BehaviorRuntime(state,actions={'probe':root},aliases={k:IRNode.from_dict(v) for k,v in inputs['aliases'].items()},policies=policies)

def main():
    isolated=[]
    for row in read(R18/'explicit_damage_results.json'):
        raw=row['initial_runtime']
        r=BehaviorRuntime(BehaviorBattleState.from_snapshot(raw['state']),
            **{key:{k:IRNode.from_dict(v) for k,v in raw[key].items()} for key in ('actions','aliases','abilities','templates')},
            policies=raw['policies'])
        out=r.step('probe');assert out.status.value=='ACTION_REFERENCE_COMPLETE'
        isolated.append({'root':row['root'],'category':'ISOLATED_REAL_DAMAGE_PRIMITIVE','status':out.status.value,
            'settlements':r.state.damage_history,'hash':r.state.stable_hash(),'wrapper_finish':'R18 EXPLICIT_SYNTHETIC_WRAPPER_ONLY'})
    write('isolated_results.json',isolated)
    ability=[]
    for original in read(R18/'real_graph_prefix_results.json'):
        r=ability_runtime(original);initial=r.snapshot();r.start_action('probe');r.run_ready(7)
        resumed=[r,r.clone(),BehaviorRuntime.from_snapshot(r.snapshot())]
        results=[e.run_until_action_complete() for e in resumed]
        assert results[0]==results[1]==results[2] and len({e.stable_hash() for e in resumed})==1
        replay,out=BehaviorRuntime.from_snapshot(initial).replay(['probe']);assert replay.stable_hash()==r.stable_hash()
        row={'root':original['root'],'source_identity':original['source_identity'],'source_graph_hash':IRNode.from_dict(original['initial_runtime']['source_root']).stable_hash(),
            'category':'ORIGINAL_REAL_ABILITY_ROOT_REFERENCE_ACTION; not a joined whole-skill transition',
            'status':results[0].status.value,'gap_node':results[0].gap.node if results[0].gap else None,
            'required_capability':results[0].gap.required_capability if results[0].gap else None,
            'clone_snapshot_hash_replay':'PASS','original_source_graph_retained':True}
        annotate(row,r,results[0]);ability.append(row)
        print('real ability action',row['root'],row['status'],row['required_capability'],flush=True)
    write('real_ability_results.json',ability)
    # Demonstrate real decoded damage driven by explicit EFFECTIVE_PROPERTY source.
    # This separate reference fixture does not add a modifier to real skill cohorts.
    from r18_reference_fixtures import make_runtime,reference_listener
    from hsr_battle_agent.battle_ir.behavior import Authority,TaskIR,ExpressionIR,TargetSelectorIR
    from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID as MODIFIER,property_contribution
    from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
    n=IRNode.from_dict(read(R18/'real_damage_fixtures.json')[0]['node']);r=make_runtime([n])
    a=Authority('SANDBOX_EXTENSION','r19','EXPLICIT_PROPERTY_CONTRIBUTION_FIXTURE','',semantic_status='REFERENCE_MODEL')
    cb=TaskIR('reference_callback','property_write',a,{'owner':'a','key':'reference_atk','operation':'set','value':ExpressionIR('noop','literal',a,{'raw':13*SCALE})})
    reference_listener(r,cb)
    task=TaskIR('reference_contribution','RPG.GameCore.StackProperty',a,{'roles':{'target':TargetSelectorIR('caster','explicit',a,{'entities':['a']}),
        'property':'reference_atk','value':ExpressionIR('contribution','literal',a,{'raw':3*SCALE})}})
    r.policies[MODIFIER]['property_tasks'][task.stable_hash()]={'aggregation':'ADDITIVE_REVERSIBLE_REFERENCE','properties':{'reference_atk':'reference_atk'}}
    r.policies[POLICY_ID]=reference_policy();r.state.target_context['modifier_instance_id']='sandbox_listener';r.start_action('probe')
    property_contribution(r,task)
    r.policies[POLICY_ID]['property_bindings']['attack']=effective_binding(r.state,'a')
    r.policies[DAMAGE]['tasks'][n.stable_hash()]['formula']['args'][0]['binding']='attack'
    checkpoint=r.snapshot();clone=r.clone();restored=BehaviorRuntime.from_snapshot(checkpoint)
    results=[e.run_until_action_complete() for e in (r,clone,restored)]
    assert results[0]==results[1]==results[2] and r.stable_hash()==clone.stable_hash()==restored.stable_hash()
    assert r.state.properties['b']['hp']==74*SCALE
    write('property_pipeline_checkpoint.json',{'category':'EXPLICIT_R17_CONTRIBUTION_REAL_DAMAGE_REFERENCE',
        'real_damage_source':n.to_dict(),'reference_contribution_source':task.to_dict(),'initial_checkpoint':checkpoint,
        'base_atk':10*SCALE,'contribution_atk':3*SCALE,'effective_atk':13*SCALE,'damage':26*SCALE,'hp_after':74*SCALE,
        'settlements':r.state.damage_history,'final_hash':r.state.stable_hash(),'clone_snapshot_hash':'PASS','native_correctness':False})
    write('followup_summary.json',{'isolated':{'completed':len(isolated),'denominator':6},
        'real_ability_roots':{'denominator':6,'hp_mutated':sum(r['hp_mutated'] for r in ability),
            'damage_lifecycle_complete':sum(r['damage_lifecycle_complete'] for r in ability),
            'reference_actions_complete':sum(r['status']=='ACTION_REFERENCE_COMPLETE' for r in ability)},
        'property_pipeline':'PASS; reference modifier contribution + original decoded damage task',
        'joined_skill_transition_denominator_changed':False})

if __name__=='__main__':main()
