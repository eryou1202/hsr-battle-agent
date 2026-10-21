"""Real joined skill prefixes and explicit R17 callback checkpoint, separately scoped."""
from __future__ import annotations
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r18_checks import read,write,AUDIT
from r18_probes import R17,load
from r18_reference_fixtures import make_runtime,reference_listener,task_binding
from r16_dependency_closure import load_catalog
from r16_probes import run_probe
from r13_reference_fixtures import fixture
from hsr_battle_agent.battle_ir.behavior import Authority,TaskIR,ExpressionIR,IRNode,walk_nodes
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID,reference_policy
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID as MODIFIER,reference_policy as modifier_policy

def events():
    row=read(AUDIT/'real_damage_fixtures.json')[0];node=IRNode.from_dict(row['node'])
    r=make_runtime([node]);a=Authority('SANDBOX_EXTENSION','r18-reference','R18_EXPLICIT_AMOUNT_CALLBACK','',semantic_status='REFERENCE_MODEL')
    callback=TaskIR('explicit_amount_callback','reference_damage_amount_modify',a,
        {'value':ExpressionIR('explicit_callback_operand','literal',a,{'raw':5*SCALE})})
    reference_listener(r,callback,operation='add')
    initial=r.snapshot();r.start_action('probe');r.run_ready(9)
    clone=r.clone();restored=BehaviorRuntime.from_snapshot(r.snapshot())
    results=[e.run_until_action_complete() for e in (r,clone,restored)]
    assert results[0]==results[1]==results[2] and r.stable_hash()==clone.stable_hash()==restored.stable_hash()
    assert r.state.properties['b']['hp']==75*SCALE
    replay,out=BehaviorRuntime.from_snapshot(initial).replay(['probe'])
    assert out[0].status==results[0].status and replay.stable_hash()==r.stable_hash()
    write('event_damage_checkpoint.json',{'category':'EXPLICIT_DAMAGE_EVENT_REFERENCE_CHECKPOINT',
        'source_task_id':node.stable_hash(),'real_source_root':row['root'],'source_span':node.payload['span'],
        'damage_node_replaced':False,'listener_authority':'EXPLICIT_SYNTHETIC_SANDBOX_REFERENCE',
        'callback_authority':'EXPLICIT_SYNTHETIC_SANDBOX_REFERENCE','initial_runtime':initial,
        'status':results[0].status.value,'settlements':r.state.damage_history,
        'metrics':r.state.scheduler.action_execution['metrics'],'state_hash':r.state.stable_hash(),
        'clone_restore':'PASS','replay':'PASS','native_correctness':False})
    print('real damage + R17 amount callback + HP + owned drain checkpoint PASS',flush=True)
def joined():
    roots,damage=load();bykey={tuple(g['source_identity']):(g,ir) for g,ir in roots}
    previous=[r for r in read(R17/'after_probes.json') if r['skill_joined'] and r['first_gap_family']=='DAMAGE']
    assert len(previous)==15
    frozen=read(R17/'frozen_reference_policy.json');base=BehaviorBattleState.from_snapshot(frozen['state'])
    nodes=[n for g,ir in roots for n in walk_nodes(ir)]
    _,aliases,_=fixture({n.payload.get('alias') for n in nodes if n.op=='RPG.GameCore.TargetAlias'},
                        {n.payload['key'] for n in nodes if n.op=='lookup'})
    catalog=load_catalog();abilities=catalog.executable_abilities();templates=catalog.compiled_templates()
    all_damage=[n for g,ir in roots for n in walk_nodes(ir) if n.op=='RPG.GameCore.DamageByAttackProperty']
    all_damage.extend(n for ir in abilities.values() for n in walk_nodes(ir) if n.op=='RPG.GameCore.DamageByAttackProperty')
    policies=copy.deepcopy(frozen['policies']);policies[MODIFIER]=modifier_policy();policies[POLICY_ID]=reference_policy()
    policies[POLICY_ID]['tasks']={n.stable_hash():task_binding(n) for n in all_damage}
    for eid in base.entities:
        base.properties[eid]['reference_atk']=10*SCALE
    # Every reference coefficient is recorded explicitly. Other original frozen
    # properties/context are retained; no progression/resource/modifier defaults.
    for n in all_damage:
        for expr in walk_nodes(n):
            if expr.op=='lookup':base.dynamic_values['supplied'][str(expr.payload['key'])]=2*SCALE
    write('joined_explicit_inputs.json',{'category':'EXPLICIT_JOINED_DAMAGE_REFERENCE_PREFIX',
        'state':base.snapshot(),'policies':policies,'roots':[r['source_identity'] for r in previous],
        'damage_nodes_replaced':False,'source_finish_nodes_added':False,
        'native_actor':False,'provider_values':'EXPLICIT_SANDBOX_DAMAGE_OPERAND_VALUES'})
    output=[]
    for i,old in enumerate(previous):
        g,ir=bykey[tuple(old['source_identity'])]
        row,r,result=run_probe(g,ir,base,aliases,policies,abilities,templates)
        row.update(category='EXPLICIT_JOINED_DAMAGE_REFERENCE_PREFIX',hp_mutated=bool(r.state.damage_history),
            settlements=r.state.damage_history,full_real_skill_reference_transition=result.status.value=='ACTION_REFERENCE_COMPLETE',
            source_finish_nodes_added=False,native_correctness=False)
        output.append(row);print('joined damage prefix',i+1,result.status.value,len(r.state.damage_history),flush=True)
    write('joined_explicit_prefix_results.json',output)
    import collections
    write('joined_explicit_summary.json',{'denominator':len(output),'hp_mutated':sum(r['hp_mutated'] for r in output),
        'full_real_skill_reference_transitions':sum(r['full_real_skill_reference_transition'] for r in output),
        'status_distribution':dict(collections.Counter(r['status'] for r in output)),
        'gap_distribution':dict(collections.Counter(r['required_capability'] for r in output if r['required_capability'])),
        'committed_settlements':sum(len(r['settlements']) for r in output),
        'category':'EXPLICIT_JOINED_DAMAGE_REFERENCE_PREFIX'})
if __name__=='__main__': events();joined()
