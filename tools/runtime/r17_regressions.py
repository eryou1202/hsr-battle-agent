"""Multiple real source graphs; isolated wrappers are explicitly sandbox fixtures."""
from __future__ import annotations
import collections
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r17_checks import read,write,AUDIT
from r17_probes import make_explicit, wrapper, name_of
from r17_reference_fixtures import callback_nodes
from r16_dependency_closure import load_catalog,control
from r13_reference_fixtures import fixture
from r15_scheduler_probes import probe_policy, POLICY_ID as SCHEDULER_POLICY
from hsr_battle_agent.battle_ir.behavior import IRNode,TaskIR,AbilityIR,TaskSequenceIR,walk_nodes
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID

def main():
    corpus=read(control('real_combat_corpus_v2'))
    roots=[(g,IRNode.from_dict(read(ROOT/g['IR_artifact']))) for g in corpus['graphs']]
    nodes=[n for _,r in roots for n in walk_nodes(r)]
    state,aliases,policies=fixture({n.payload.get('alias') for n in nodes if n.op=='RPG.GameCore.TargetAlias'},
        {n.payload['key'] for n in nodes if n.op=='lookup'})
    policies[SCHEDULER_POLICY]=probe_policy()
    catalog=load_catalog();defs=catalog.modifier_definitions();abilities=catalog.executable_abilities();templates=catalog.compiled_templates()
    all_adds=[n for n in nodes if n.op=='RPG.GameCore.AddModifier']
    names=['MAvatar_Argenti_00_Rank02_AttackRatioUp','MAvatar_Bailu_00_PointB3',
           'MAvatar_Robin_00_Skill03_AtkUp','MAvatar_Acheron_00_Rank06_ForceStanceDamage',
           'MAvatar_Seele_Rank06','M_Silwolf_SkillTree01_Buff','MAvatar_Yukong_00_Flower']
    rows=[];fixtures=[]
    for name in names:
        definition=next(d for d in defs.values() if d['config_identity']==name)
        matches=[n for n in all_adds if name_of(n)==name and not n.payload.get('reference_binding',{}).get('unknown_slots')]
        if not matches:
            matches=[n for n in all_adds if name_of(n)==name]
        if not matches:
            rows.append({'config':name,'status':'CONTENT_GRAPH_PRESENT_WITHOUT_OBSERVED_ADDMODIFIER_SITE','native_correct':False});continue
        node=matches[0]
        # These IDs are explicit test triggers. Their native meaning is unknown.
        event_ids=[]
        for f in definition['compiled_decoded'].get('fields',[]):
            if f['mask']==33554432:
                for v in f['values']:
                    for cb in v['children']:
                        for field in cb['fields']:
                            if field['mask']==1:event_ids+=field['values']
        chosen=[53] if 53 in event_ids else event_ids[:1]
        explicit_state,explicit_policies=make_explicit(node,definition,state,policies,aliases,abilities,templates,activation_ids=chosen)
        root=wrapper(node,name+'/reference',node.authority)
        runtime=BehaviorRuntime(explicit_state,actions={'probe':root},aliases=aliases,abilities=abilities,templates=templates,policies=explicit_policies)
        initial=runtime.snapshot();runtime.start_action('probe');runtime.run_ready(5)
        engines=[runtime,runtime.clone(),BehaviorRuntime.from_snapshot(runtime.snapshot())]
        outcomes=[r.run_until_blocked() for r in engines]
        hashes=[r.state.stable_hash() for r in engines]
        if outcomes[0]!=outcomes[1] or outcomes[0]!=outcomes[2] or len(set(hashes))!=1:raise ValueError('modifier callback replay mismatch')
        replay=BehaviorRuntime.from_snapshot(initial);replay.step('probe')
        if replay.state.stable_hash()!=runtime.state.stable_hash():raise ValueError('initial real fixture replay mismatch')
        result=outcomes[0];d=runtime.state.scheduler.action_execution
        receipt={'config':name,'category':'EXPLICIT_MODIFIER_REFERENCE_FIXTURE','scope':'ISOLATED_REAL_ADDMODIFIER_AND_DECODED_CALLBACKS',
            'definition_id':definition['definition_id'],'definition_source':definition['source_identity'],
            'node_source':node.authority.to_dict(),'event_ids':event_ids,'explicit_activation_ids':chosen,
            'status':result.status.value,'gap':result.gap.required_capability if result.gap else None,
            'metrics':copy.deepcopy(d['metrics']),'boundaries':copy.deepcopy(runtime.state.modifier_history),
            'determinism':'PASS','replay':'PASS','native_correct':False,'legal_native_actor':False}
        fixtures.append({'config':name,'node':node.to_dict(),'definition':definition,
            'policy':explicit_policies[POLICY_ID],'initial_state':explicit_state.snapshot()})
        # Completion of first action leaves the installed modifier persistent. Exercise
        # other explicit opaque event IDs and refresh/replacement/removal on new roots.
        if result.status.value=='ACTION_REFERENCE_COMPLETE':
            lifecycle=[]
            for i,mode in enumerate(['REFRESH_EXISTING_REFERENCE','INCREMENT_STACK_REFERENCE','REPLACE_EXISTING_REFERENCE']):
                new=TaskIR(node.node_id+'/'+mode,node.op,node.authority,node.payload)
                binding=copy.deepcopy(runtime.policies[POLICY_ID]['applications'][node.stable_hash()])
                binding.update(application_policy=mode,source_ability='ability:'+root.node_id)
                # Source ability remains the first explicit wrapper identity across actions.
                binding['match_identity']=['definition_id','owner','caster','original_caster','target']
                binding['cross_source_update']='PRESERVE_EXISTING_IDENTITIES_REFERENCE'
                runtime.policies[POLICY_ID]['applications'][new.stable_hash()]=binding
                aid='lifecycle'+str(i);runtime.actions[aid]=wrapper(new,aid,node.authority)
                result2=runtime.step(aid)
                lifecycle.append({'operation':mode,'status':result2.status.value,'gap':result2.gap.required_capability if result2.gap else None,
                    'metrics':runtime.state.scheduler.action_execution['metrics']})
                if result2.status.value!='ACTION_REFERENCE_COMPLETE':break
            if lifecycle and lifecycle[-1]['status']=='ACTION_REFERENCE_COMPLETE':
                for ordinal,eid in enumerate(event_ids[:3]):
                    event=TaskIR(node.node_id+'/explicit_event/'+str(eid),'modifier_event_dispatch',node.authority,{'event_id':eid,'source':'a','payload':{'explicit_reference_trigger':True}})
                    aid='event'+str(ordinal);runtime.actions[aid]=wrapper(event,aid,node.authority)
                    result2=runtime.step(aid)
                    lifecycle.append({'operation':'EXPLICIT_OPAQUE_EVENT_DISPATCH','event_id':eid,'status':result2.status.value,
                        'gap':result2.gap.required_capability if result2.gap else None,'metrics':runtime.state.scheduler.action_execution['metrics']})
                    if result2.status.value!='ACTION_REFERENCE_COMPLETE':break
            if lifecycle and lifecycle[-1]['status']=='ACTION_REFERENCE_COMPLETE':
                remove=TaskIR(node.node_id+'/remove','modifier_remove_reference',node.authority)
                for instance in list(runtime.state.modifiers.values()):
                    runtime.policies[POLICY_ID]['removals'][remove.stable_hash()]={'selection':'INSTANCE_REFERENCE',
                        'instance_id':instance.instance_id,'reason':'REGRESSION_REFERENCE_REMOVAL','pending_callbacks':'RETAIN_ENQUEUED_REFERENCE'}
                    runtime.actions['remove']=wrapper(remove,'remove',node.authority);result2=runtime.step('remove')
                    lifecycle.append({'operation':'EXPLICIT_INSTANCE_REMOVAL','status':result2.status.value,
                        'gap':result2.gap.required_capability if result2.gap else None,'metrics':runtime.state.scheduler.action_execution['metrics']})
            receipt['subsequent_actions']=lifecycle
        rows.append(receipt);print(name,receipt['status'],receipt['gap'],flush=True)
    write('real_modifier_regressions.json',rows)
    write('real_modifier_reference_fixtures.json',fixtures)
    natasha=[r for r in read(AUDIT/'after_probes.json') if 'Natasha' in r['root']]
    write('natasha_regression.json',{'rows':natasha,'actor_progression_preserved':any('progression' in (r['required_capability'] or '') for r in natasha),
          'native_actor_supplied':False,'character_specific_production_branches':False})
    summary=collections.Counter()
    for row in rows:
        summary.update(row.get('metrics',{}))
        for action in row.get('subsequent_actions',[]):summary.update(action['metrics'])
    write('regression_summary.json',{'fixture_count':len(fixtures),'initial_statuses':dict(collections.Counter(r['status'] for r in rows)),
        'metrics':dict(summary),'determinism':'PASS','replay':'PASS','native_correct':False,
        'action_reference_completions':sum(r['status']=='ACTION_REFERENCE_COMPLETE' for r in rows)+sum(
            a['status']=='ACTION_REFERENCE_COMPLETE' for r in rows for a in r.get('subsequent_actions',[])),
        'synthetic_nested_event_tests':'tests/battle_runtime/test_behavior_r17.py','R18_oracle_followups_required':True})

if __name__=='__main__':main()
