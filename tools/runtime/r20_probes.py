"""Frozen R19 comparisons and separately labelled R20 original graph probes."""
from __future__ import annotations
import collections
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r20_checks import AUDIT,read,write
from r18_probes import load,R17
from r19_probes import context,annotate,summarize
from r16_probes import run_probe
from r19_reference_fixtures import extend as r19_extend
from r20_reference_fixtures import extend,JOINS
from hsr_battle_agent.battle_ir.behavior import walk_nodes,IRNode
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState
from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE
from hsr_battle_agent.battle_runtime.actor_binding import POLICY_ID as ACTOR
R18=ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001'
R19=ROOT/'tmp/audit/r19_damage_continuation_20261010_001'

def comparisons(roots,frozen=False):
    # Reuse the exact previous runner, but redirect every receipt to R20.
    import r19_probes as previous
    previous.write=lambda name,value:write('r19_comparison/'+name,value)
    if frozen:
        previous.frozen(roots)
        receipt=read(AUDIT/'r19_comparison/frozen_summary.json')
        old=read(R19/'frozen_summary.json')
        assert receipt['combat']==old['combat'] and receipt['joined']==old['joined']
        write('frozen_regression.json',{'before':old,'after':receipt,'all_original_state_hashes_equal':True})
    else:
        previous.joined(roots)
        receipt=read(AUDIT/'r19_comparison/joined_summary.json');old=read(R19/'joined_summary.json')
        assert receipt==old
        write('r19_damage_regression.json',{'before':old,'after':receipt,'status':'PASS','denominator':15})

def actor_cohort(roots):
    allnodes,aliases,abilities,templates=context(roots)
    inputs=read(R18/'joined_explicit_inputs.json');base=BehaviorBattleState.from_snapshot(inputs['state'])
    state,policies=r19_extend(base,inputs['policies'],allnodes,expressions=True,ranks=False)
    joins=read(JOINS)['rows'];owners={}
    for j in joins:
        exact=j.get('exact_root_identity')
        if exact:
            key=tuple(exact[k] for k in ('source_shard_sha256','record_start','record_end'))
            owners.setdefault(key,[]).append(j)
    selected=[]
    reference15={tuple(r['source_identity']) for r in read(R18/'joined_explicit_prefix_results.json')}
    for g,ir in roots:
        ops={n.op for n in walk_nodes(ir)}
        if tuple(g['source_identity']) in reference15 or ops & {'RPG.GameCore.ModifySPNew','RPG.GameCore.ByRankActivated','RPG.GameCore.BySkillPointActivated'}:
            selected.append((g,ir))
    rows=[];initializations=[];replays=[]
    for index,(g,ir) in enumerate(selected):
        key=tuple(g['source_identity']);joined=owners.get(key,[])
        # Unjoined ability contexts are explicit fixture owners; never name-derived.
        aid=joined[0]['avatar_id'] if joined else [1001,1002,1105][index%3]
        r=BehaviorRuntime(state,actions={'probe':ir},aliases=aliases,abilities=abilities,templates=templates,policies=policies)
        binding=extend(r,allnodes,avatar_id=aid,level=1 if index%2==0 else 70,promotion=0 if index%2==0 else 5,rank=index%3,activation=True)
        initializations.append({'root':g['record_identity'],'source_identity':g['source_identity'],'binding':binding.to_dict(),
            'graph_owner_join':joined,'owner_authority':'EXACT_SOURCE_SKILL_OWNER_JOIN' if joined else 'EXPLICIT_SCENARIO_ABILITY_OWNER_ONLY'})
        row,r,result=run_probe(g,ir,r.state,aliases,r.policies,abilities,templates);annotate(row,r,result)
        data=r.state.mechanics.get(RESOURCE,{})
        history=data.get('history',[]);d=r.state.scheduler.action_execution
        row.update(actor_id=aid,graph_owner_join=bool(joined),reference15=key in reference15,
            resource_records=history,resource_mutations_attempted=d['metrics'].get('resource_mutations_attempted',0)+int(bool(result.gap and
                (result.gap.task_type=='RPG.GameCore.ModifySPNew' or result.gap.task_type.startswith('resource_')))),
            resource_mutations_committed=d['metrics'].get('resource_mutations_committed',0),
            resource_callbacks=sum(len(h['callbacks_processed']) for h in history),
            actor_balances=r.state.actor_resources,team_balances=r.state.team_resources,
            actor_state_constructed=True,activation_rows=len(binding.fields['activated_skill_tree_rows']['value']),
            completed_skill_tree_predicates=sum(h.get('op')=='RPG.GameCore.BySkillPointActivated' for h in r.trace),
            completed_rank_predicates=sum(h.get('op')=='RPG.GameCore.ByRankActivated' for h in r.trace),
            full_joined_skill_transition=bool(g['skill_joined'] and result.status.value=='ACTION_REFERENCE_COMPLETE'),
            real_graph_resource_prefix=bool(history),scope='EXPLICIT_R20_ACTOR_REFERENCE_ORIGINAL_GRAPH',native_executable=False)
        # Original inputs and policies are serialized; replay a bounded pending checkpoint.
        if history or key in reference15 or 'Natasha' in g['record_identity']:
            rr=BehaviorRuntime.from_snapshot(r.snapshot())
            assert rr.state.stable_hash()==r.state.stable_hash()
            replays.append({'root':g['record_identity'],'state_roundtrip':True})
        rows.append(row)
        if (index+1)%10==0:print('actor cohort',index+1,'/',len(selected),flush=True)
    write('actor_cohort_inputs.json',initializations)
    write('actor_cohort_results.json',rows)
    write('actor_cohort_summary.json',summarize(rows)|{
        'initialized_actor_contexts':len(initializations),'unique_real_avatars':len({r['actor_id'] for r in rows}),
        'exact_source_owner_join_contexts':sum(r['graph_owner_join'] for r in rows),
        'bound_activation_rows':sum(r['activation_rows'] for r in rows),
        'skill_tree_predicates_completed':sum(r['completed_skill_tree_predicates'] for r in rows),
        'rank_predicates_completed':sum(r['completed_rank_predicates'] for r in rows),
        'resource_mutations_attempted':sum(r['resource_mutations_attempted'] for r in rows),
        'resource_mutations_committed':sum(r['resource_mutations_committed'] for r in rows),
        'real_graph_resource_prefix_roots':sum(r['real_graph_resource_prefix'] for r in rows),
        'resource_callbacks':sum(r['resource_callbacks'] for r in rows),
        'full_joined_skill_transitions':sum(r['full_joined_skill_transition'] for r in rows),
        'r20_selected15':summarize([r for r in rows if r['reference15']]),
        'first_gaps':dict(collections.Counter(r['required_capability'] for r in rows if r['required_capability'])),
        'native_validated':0,'source_graphs_modified':False,'finish_nodes_inserted':False})
    write('actor_cohort_snapshot_receipt.json',replays)
    # Natasha exact root identity is looked up solely for this named regression.
    natasha=[(g,ir) for g,ir in roots if 'Natasha' in g['record_identity'] and '_Skill02_' in g['record_identity']]
    regression=[]
    for g,ir in natasha:
        frozen=read(R17/'frozen_reference_policy.json')
        before,_,_=run_probe(g,ir,BehaviorBattleState.from_snapshot(frozen['state']),aliases,frozen['policies'],abilities,templates)
        own=next((j for j in owners.get(tuple(g['source_identity']),[]) if j['avatar_id']==1105),None)
        rr=BehaviorRuntime(state,actions={'probe':ir},aliases=aliases,abilities=abilities,templates=templates,policies=policies)
        extend(rr,allnodes,avatar_id=1105,activation=True)
        after,_,_=run_probe(g,ir,rr.state,aliases,rr.policies,abilities,templates)
        regression.append({'root':g['record_identity'],'unchanged_inputs':before,'explicit_actor_inputs':after,
                           'owner_source_join':own,'source_graph_modified':False})
    write('natasha_regression.json',regression)

if __name__=='__main__':
    roots,_=load()
    if '--frozen' in sys.argv: comparisons(roots,True)
    elif '--r19' in sys.argv: comparisons(roots)
    else: actor_cohort(roots)
