"""Isolated real resource primitives and modifier-triggered source effects.

These bounded wrappers never count as original graph or joined skill completion.
No SkillPerformFinish is appended.
"""
from __future__ import annotations
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(Path(__file__).parent)]
from r20_checks import AUDIT,read,write
from r20_reference_fixtures import extend,resource_spec
from r18_reference_fixtures import make_runtime
from r19_reference_fixtures import extend as property_extend
from hsr_battle_agent.battle_ir.behavior import IRNode,AbilityIR,TaskSequenceIR,walk_nodes,TaskIR
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE
from tests.battle_runtime.test_behavior_r20 import R20Tests

def main():
    census=read(AUDIT/'resource_instruction_census.json')['instances'];results=[];callbacks=[]
    for index,row in enumerate(census):
        n=IRNode.from_dict(row['node'])
        if n.op!='RPG.GameCore.ModifySPNew':continue
        root=AbilityIR('bounded_real_resource','ability',n.authority,{'tasks':TaskSequenceIR('bounded_resource_seq','immediate_sequence',n.authority,{'tasks':[n]})})
        # Reuse reference initial numeric/providers; damage task map is explicitly
        # emptied because the source here is a resource task, not a damage task.
        from r13_reference_fixtures import fixture
        from r15_scheduler_probes import probe_policy
        from hsr_battle_agent.battle_runtime.action_scheduler import POLICY_ID as SCHEDULER
        from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID as MODIFIER,reference_policy
        nodes=list(walk_nodes(n));lookups={x.payload['key'] for x in nodes if x.op=='lookup'}
        state,aliases,policies=fixture({x.payload['alias'] for x in nodes if x.op=='RPG.GameCore.TargetAlias'},lookups)
        state,policies=property_extend(state,policies,nodes);policies[SCHEDULER]=probe_policy();policies[MODIFIER]=reference_policy()
        r=BehaviorRuntime(state,actions={'probe':root},aliases=aliases,policies=policies)
        b=extend(r,nodes,avatar_id=[1001,1002,1105][index%3])
        before=r.state.actor_resources.copy();r.start_action('probe');r.run_ready(3)
        copies=[r,r.clone(),BehaviorRuntime.from_snapshot(r.snapshot())]
        outcomes=[e.run_until_action_complete() for e in copies]
        assert outcomes[0]==outcomes[1]==outcomes[2] and len({e.state.stable_hash() for e in copies})==1
        result=outcomes[0];history=r.state.mechanics.get(RESOURCE,{}).get('history',[])
        results.append({'root':row['root'],'source':row['source'],'source_task_hash':n.stable_hash(),
            'binding':b.to_dict(),'policies':r.policies,'initial_balance':before,'final_balance':r.state.actor_resources,
            'records':history,'status':result.status.value,'gap':result.gap.required_capability if result.gap else None,
            'clone_snapshot_replay':'PASS','scope':'ISOLATED_ORIGINAL_RESOURCE_TASK_REFERENCE_WRAPPER',
            'full_real_skill_transition':False,'native_validated':False,'finish_nodes_added':False})
        if history and len(callbacks)<3:
            # Explicit R17 listener invoking the same real resource task.
            rr=BehaviorRuntime(state,actions={'probe':AbilityIR('reference_modifier_dispatch','ability',n.authority,
                {'tasks':TaskSequenceIR('event_seq','immediate_sequence',n.authority,{'tasks':[
                    TaskIR('dispatch','modifier_event_dispatch',n.authority,{'event_id':'r20_source_effect','source':'a'})]})})},
                aliases=aliases,policies=policies)
            extend(rr,nodes,avatar_id=[1001,1002,1105][index%3])
            helper=R20Tests();rr.policies[RESOURCE]['bindings']['counter']=resource_spec()
            m=helper.listener(rr,n,event='r20_source_effect')
            rr.policies[RESOURCE]['bindings'][n.stable_hash()]['listener_registrations']=[m.instance_id+'/registration']
            out=rr.step('probe');h=rr.state.mechanics.get(RESOURCE,{}).get('history',[])
            callbacks.append({'root':row['root'],'source_task':n.to_dict(),'status':out.status.value,
                'gap':out.gap.required_capability if out.gap else None,'resource_records':h,
                'modifier_callbacks_completed':rr.state.scheduler.action_execution['metrics'].get('modifier_callbacks_completed',0),
                'scope':'EXPLICIT_REFERENCE_MODIFIER_DISPATCH_REAL_RESOURCE_EFFECT','full_real_skill_transition':False})
    write('isolated_real_resource_results.json',results)
    write('modifier_real_resource_callbacks.json',callbacks)
    # Paired source primitives are a compositional reference probe. Their source
    # envelopes stay real, but the pairing is explicitly synthetic and excluded
    # from original graph/full skill totals.
    from r18_probes import load
    from r18_reference_fixtures import task_binding
    from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE,reference_policy as damage_policy
    roots,_=load()
    damage=IRNode.from_dict(read(ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001/real_damage_fixtures.json')[0]['node'])
    heal=next((n for _,ir in roots for n in walk_nodes(ir) if n.op=='RPG.GameCore.HealHP' and n.payload.get('fields',{}).get('FormulaType')==2),None)
    coupled=[];resource=IRNode.from_dict(next(x['node'] for x in census if x['node']['op']=='RPG.GameCore.ModifySPNew'))
    from hsr_battle_agent.battle_ir.behavior import Authority,TargetSelectorIR
    synthetic_authority=Authority('REFERENCE_MODEL','r20-reference','EXPLICIT_R20_HEAL_RESOURCE_PAIR','',semantic_status='REFERENCE_MODEL')
    reference_heal=TaskIR('explicit_reference_heal','RPG.GameCore.HealHP',synthetic_authority,
        {'fields':{'FormulaType':2,'TargetType':TargetSelectorIR('explicit_heal_target','explicit',synthetic_authority,{'entities':['b']})}})
    for label,primitive in [('damage',damage),('heal',heal),('heal_reference',reference_heal)]:
        if primitive is None:
            coupled.append({'kind':label,'status':'SOURCE_COMPATIBILITY_GAP','full_real_skill_transition':False});continue
        ns=[primitive,resource];nodes=[n for x in ns for n in walk_nodes(x)]
        state,aliases,policies=fixture({x.payload['alias'] for x in nodes if x.op=='RPG.GameCore.TargetAlias'},
                                      {x.payload['key'] for x in nodes if x.op=='lookup'})
        state.properties['b']['hp']=50*(1<<33);state.properties['b']['max_hp']=100*(1<<33)
        state,policies=property_extend(state,policies,nodes);policies[SCHEDULER]=probe_policy();policies[MODIFIER]=reference_policy()
        from hsr_battle_agent.battle_ir.behavior import TargetSelectorIR
        for x in walk_nodes(primitive):
            if x.op=='RPG.GameCore.TargetAlias':aliases[x.payload['alias']]=TargetSelectorIR('coupled-target','explicit',x.authority,{'entities':['b']})
        # Caster in resource graph refers to the bound owner, separately from the
        # primitive's target. No identity inference is performed.
        aliases['Caster']=TargetSelectorIR('resource-caster','Caster',resource.authority)
        root=AbilityIR('paired_'+label,'ability',primitive.authority,{'tasks':TaskSequenceIR('paired_seq','immediate_sequence',primitive.authority,{'tasks':ns})})
        rr=BehaviorRuntime(state,actions={'probe':root},aliases=aliases,policies=policies);extend(rr,nodes,avatar_id=1001)
        if label=='damage':
            rr.policies[DAMAGE]=damage_policy();rr.policies[DAMAGE]['tasks'][primitive.stable_hash()]=task_binding(primitive)
        else:
            rr.policies[MODIFIER]['heal_stages'][primitive.stable_hash()]={
                'formula':'FORMULA_TYPE2_REFERENCE','settlement':'CLAMP_HP_REFERENCE',
                'ordering':['pre_heal','effective_amount','settlement','hp_mutation','post_heal'],
                'events':{s:None for s in ['pre_heal','effective_amount','settlement','hp_mutation','post_heal']},
                'event_source':'a','amount_provider':'supplied','amount_key':'r20_heal','cap_enabled':False,
                'operands':{'d50':1<<33,'d28':1<<33,'d60':0,'dD0':0,'d38':0,'d128':0,'d48':100*(1<<33),'dD8':0}}
        initial=rr.snapshot();before=rr.state.properties['b']['hp'];out=rr.step('probe');replay,replayed=BehaviorRuntime.from_snapshot(initial).replay(['probe'])
        assert replay.stable_hash()==rr.stable_hash() and replayed[0]==out
        coupled.append({'kind':label,'source_primitive':primitive.to_dict(),'source_resource':resource.to_dict(),
            'initial_runtime':initial,'status':out.status.value,'gap':out.gap.required_capability if out.gap else None,
            'hp_before':before,'hp_after':rr.state.properties['b']['hp'],
            'resources':rr.state.mechanics.get(RESOURCE,{}).get('history',[]),
            'scope':'PAIRED_REAL_PRIMITIVES_EXPLICIT_SYNTHETIC_REFERENCE_ORDER','full_real_skill_transition':False,
            'finish_nodes_added':False,'replay':'PASS'})
    write('coupled_damage_heal_resource.json',coupled)
    write('resource_followup_summary.json',{'isolated_source_tasks':len(results),
        'isolated_resource_commits':sum(len(r['records']) for r in results),
        'reference_modifier_callback_probes':len(callbacks),
        'callback_resource_commits':sum(len(r['resource_records']) for r in callbacks),
        'coupled_reference_results':[{'kind':r['kind'],'status':r['status'],'resource_commits':len(r.get('resources',[])),
            'hp_mutated':r.get('hp_after')!=r.get('hp_before')} for r in coupled],
        'clone_snapshot_replay':'PASS','source_completion_added':False,'full_real_skill_transitions':0,
        'excluded_from_original_graph_counts':True})
    print('followups',len(results),sum(len(r['records']) for r in results),callbacks and [c['status'] for c in callbacks],flush=True)

if __name__=='__main__':main()
