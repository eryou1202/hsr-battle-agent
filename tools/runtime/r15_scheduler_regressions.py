"""Real IR node regressions with explicitly synthetic wrappers and event bindings."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes,AbilityIR,TaskSequenceIR,Authority,TaskIR
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.action_scheduler import POLICY_ID
from hsr_battle_agent.battle_runtime.behavior_state import ModifierInstance
from r13_reference_fixtures import fixture
from r15_scheduler_probes import read,write,AUDIT,probe_policy


def main():
    graphs=read('data/control/generic_runtime_real_combat_corpus_v2_20261008_001.json')['graphs']
    entries=[]
    for g in graphs:
        if g['stratum'] not in ('ABILITY_CORPUS','PASSIVE_CORPUS','MODIFIER_CORPUS'):continue
        ir=IRNode.from_dict(read(g['IR_artifact']))
        # Only actual executable entry task trees, or the decoded modifier body.
        tree=ir.payload.get('tasks', ir.payload.get('decoded'))
        entries.append((g,ir,list(walk_nodes(tree))))
    nodes=[n for _,_,ns in entries for n in ns]
    state,aliases,policies=fixture({n.payload.get('alias') for n in nodes if n.op=='RPG.GameCore.TargetAlias'},
        {n.payload['key'] for n in nodes if n.op=='lookup'})
    policies[POLICY_ID]=probe_policy()
    a=Authority('REFERENCE_MODEL','r15','SYNTHETIC_REAL_NODE_WRAPPER','',semantic_status='REFERENCE_MODEL')
    finish_entry=next((g,n) for g,_,ns in entries for n in ns if n.op=='RPG.GameCore.SkillPerformFinish')
    results=[]
    for pattern in ['LINEAR_FINISH','TriggerAbility','WaitSecond','WaitAnimState','WaitTimelineFinish','MODIFIER_CALLBACK','DamageByAttackProperty']:
        if pattern=='LINEAR_FINISH':
            source,node=finish_entry
        else:
            wanted=None if pattern=='MODIFIER_CALLBACK' else pattern
            candidates=[(g,n) for g,_,ns in entries for n in ns if (n.op.rsplit('.',1)[-1]==wanted or (wanted is None and n.kind in ('TaskIR','UnsupportedSemanticIR'))) and
                'Natasha' not in g['record_identity'] and (pattern!='MODIFIER_CALLBACK' or g['stratum']=='MODIFIER_CORPUS')]
            if not candidates:
                results.append({'pattern':pattern,'status':'REAL_NODE_NOT_BOUND','native_executable':False});continue
            source,node=next(((g,n) for g,n in candidates if g['skill_joined']),candidates[0])
        if pattern == 'TriggerAbility':
            after = read(AUDIT.relative_to(ROOT) / 'after_probes.json')
            reached_roots = {r['root'] for r in after if r['skill_joined'] and r['metrics']['abilities_invoked'] > 0}
            source, node = next(((g, n) for g, n in candidates if g['record_identity'] in reached_roots), (source, node))
        finish_node=finish_entry[1]
        sequence=[node,finish_node] if pattern!='LINEAR_FINISH' else [node]
        events={}
        local=state.clone()
        if pattern=='MODIFIER_CALLBACK':
            dispatch=TaskIR('synthetic/modifier-event','modifier_event_dispatch',a,{'event_id':901})
            sequence=[dispatch,finish_node]
            local.modifiers['fixture']=ModifierInstance('fixture','REAL_NODE_CALLBACK_REFERENCE','a','a','a',1,1,{},
                event_registrations=[{'event_id':901,'order':0,'callback':node.to_dict(),'mutation_result':'NORMAL_GENERIC_TASK_EXECUTION'}])
        wrapped=AbilityIR('synthetic/'+pattern,'ability',a,{'tasks':TaskSequenceIR('synthetic/'+pattern+'/sequence','immediate_sequence',a,{'tasks':sequence})})
        local_policies=json.loads(json.dumps(policies))
        if pattern=='MODIFIER_CALLBACK':local_policies['r13_reference_v1']['event_callbacks']='ORDERED_OWNER_CONTEXT_REFERENCE_V1'
        catalogs={}
        for g, ir, _ in entries:
            if ir.op == 'ability': catalogs.setdefault(g['record_identity'], []).append(ir)
        catalog={k: values[0] for k, values in catalogs.items() if len(values)==1}
        runtime=BehaviorRuntime(local,actions={'probe':wrapped},abilities=catalog,aliases=aliases,policies=local_policies)
        runtime.start_action('probe');runtime.run_ready(3)
        restored=BehaviorRuntime.from_snapshot(runtime.snapshot())
        result=runtime.run_until_blocked();repeated=restored.run_until_blocked()
        if result!=repeated or runtime.stable_hash()!=restored.stable_hash():raise RuntimeError('real node replay instability')
        d=runtime.state.scheduler.action_execution
        results.append({'pattern':pattern,'root':source['record_identity'],'source_identity':source['source_identity'],
            'IR_artifact':source['IR_artifact'],'node_id':node.node_id,'original_node_hash':node.stable_hash(),
            'skill_joined_source':source['skill_joined'],'scope':'ISOLATED_REAL_IR_NODE_SYNTHETIC_WRAPPER',
            'not_full_root_transition':True,'native_executable':False,'status':result.status.value,
            'first_gap':result.gap.required_capability if result.gap else None,'metrics':d['metrics'],
            'logical_time':d['logical_time'],'determinism':'PASS','replay':'PASS'})
    write(AUDIT.relative_to(ROOT)/'real_node_regressions.json',results)
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
