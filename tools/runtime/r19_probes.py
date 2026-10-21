"""R19 original joined roots, separate additive cohorts, and frozen comparisons."""
from __future__ import annotations
import collections
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r19_checks import AUDIT,read,write
from r18_probes import load,R17
from r16_dependency_closure import load_catalog
from r16_probes import run_probe
from r15_scheduler_probes import summary
from r13_reference_fixtures import fixture
from r19_reference_fixtures import extend,finish_binding
from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes,AbilityIR,TaskSequenceIR
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState
from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE
R18=ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001'

def context(roots):
    catalog=load_catalog();abilities=catalog.executable_abilities();templates=catalog.compiled_templates()
    nodes=[n for _,ir in roots for n in walk_nodes(ir)]
    nodes.extend(n for ir in abilities.values() for n in walk_nodes(ir))
    _,aliases,_=fixture({n.payload.get('alias') for n in nodes if n.op=='RPG.GameCore.TargetAlias'},
                        {n.payload['key'] for n in nodes if n.op=='lookup'})
    return nodes,aliases,abilities,templates

def annotate(row,r,result):
    d=r.state.scheduler.action_execution
    finishes=[t for t in d['tasks'].values() if t['node']['op']=='RPG.GameCore.DamagePerformFinish']
    reached=bool(finishes) or bool(result.gap and result.gap.task_type=='RPG.GameCore.DamagePerformFinish')
    completed=[t for t in finishes if t['status']=='TASK_COMPLETE']
    next_tasks=[]
    for t in completed:
        seq=d['sequences'][t['sequence_frame_id']];index=next(i for i,n in enumerate(seq['nodes']) if n==t['node'])
        next_tasks.extend(seq['nodes'][index+1:index+2])
    reached_hashes={IRNode.from_dict(t['node']).stable_hash() for t in d['tasks'].values()}
    settlement=[h for h in r.state.damage_history if h['boundary']=='REFERENCE_DAMAGE_HP_SETTLED']
    row.update(hp_mutated=bool(settlement),settlements=settlement,
        damage_finish_reached=reached,damage_finish_completed=bool(completed),damage_finish_completion_count=len(completed),
        next_source_tasks=next_tasks,next_task_reached=any(IRNode.from_dict(n).stable_hash() in reached_hashes for n in next_tasks),
        source_sequence_drained_after_finish=any(d['sequences'][t['sequence_frame_id']]['status']=='SEQUENCE_COMPLETE' for t in completed),
        damage_lifecycle_complete=bool(settlement) and bool(completed),
        full_real_skill_reference_transition=result.status.value=='ACTION_REFERENCE_COMPLETE',
        final_battle_state_hash=r.state.stable_hash(),
        source_finish_nodes_added=False,native_correctness=False)
    return row

def joined(roots):
    nodes,aliases,abilities,templates=context(roots);bykey={tuple(g['source_identity']):(g,ir) for g,ir in roots}
    original=read(R18/'joined_explicit_prefix_results.json');inputs=read(R18/'joined_explicit_inputs.json')
    base=BehaviorBattleState.from_snapshot(inputs['state']);before=[]
    for old in original:
        g,ir=bykey[tuple(old['source_identity'])]
        row,r,result=run_probe(g,ir,base,aliases,inputs['policies'],abilities,templates)
        assert row['status']==old['status'] and row['required_capability']==old['required_capability']
        assert r.state.damage_history and old['hp_mutated'] or not r.state.damage_history and not old['hp_mutated']
        before.append(annotate(row,r,result))
    write('r18_comparison_rerun.json',before)
    cohorts={}
    for name,expressions,ranks in [('finish_only',False,False),('continuation_expression',True,False),('explicit_rank',True,True)]:
        state,policies=extend(base,inputs['policies'],nodes,expressions=expressions,ranks=ranks)
        write(name+'_inputs.json',{'state':state.snapshot(),'policies':policies,'baseline':'unchanged R18 joined_explicit_inputs.json',
              'source_graphs_modified':False,'additional_rank_input':ranks,'additional_dynamic_values':False})
        rows=[]
        for index,old in enumerate(original):
            g,ir=bykey[tuple(old['source_identity'])]
            row,r,result=run_probe(g,ir,state,aliases,policies,abilities,templates)
            annotate(row,r,result);row['category']=name
            assert r.state.stable_hash()==r.state.clone().stable_hash()==BehaviorBattleState.from_snapshot(r.state.snapshot()).stable_hash()
            # Real root replay includes source graphs, catalogs, policies, and ownership.
            replay=BehaviorRuntime(state,actions={'probe':ir},abilities=abilities,templates=templates,aliases=aliases,policies=policies)
            replay.state.target_context['current_ability']=g['record_identity']
            replay.start_action('probe');replay.run_ready(7)
            if name=='continuation_expression':
                resumed=[replay,replay.clone(),BehaviorRuntime.from_snapshot(replay.snapshot())]
                outcomes=[e.run_until_action_complete() for e in resumed]
                assert outcomes[0]==outcomes[1]==outcomes[2]
                assert len({e.state.stable_hash() for e in resumed})==1 and resumed[0].state.stable_hash()==r.state.stable_hash()
                if index==0:
                    assert len({e.stable_hash() for e in resumed})==1
                row['clone_snapshot_replay']='PASS; runtime checkpoint restore and result/state equality; full catalog hash on first root'
            else:
                out=replay.run_until_action_complete()
                assert replay.state.stable_hash()==r.state.stable_hash() and out.status==result.status
                row['clone_snapshot_replay']='PASS; state clone/restore plus independent root replay'
            rows.append(row)
            print(name,g['record_identity'],result.status.value,row['damage_finish_completion_count'],row['required_capability'],flush=True)
        write(name+'_results.json',rows);cohorts[name]=summarize(rows)
    write('joined_summary.json',{'denominator':15,'before':summarize(before),'cohorts':cohorts})

def summarize(rows):
    return summary(rows)|{'hp_mutated':sum(r['hp_mutated'] for r in rows),
        'settlements':sum(len(r['settlements']) for r in rows),
        'damage_finish_reached':sum(r['damage_finish_reached'] for r in rows),
        'damage_finish_completed':sum(r['damage_finish_completed'] for r in rows),
        'damage_finish_completions':sum(r['damage_finish_completion_count'] for r in rows),
        'damage_lifecycle_complete':sum(r['damage_lifecycle_complete'] for r in rows),
        'unknown_dynamic_program_first_gaps':sum(r['primitive']=='unknown_opcode' for r in rows)}

def frozen(roots):
    nodes,aliases,abilities,templates=context(roots)
    inputs=read(R17/'frozen_reference_policy.json');state=BehaviorBattleState.from_snapshot(inputs['state'])
    previous={tuple(r['source_identity']):r for r in read(R18/'frozen_probes.json')};rows=[];drift=[]
    for i,(g,ir) in enumerate(roots):
        row,r,result=run_probe(g,ir,state,aliases,inputs['policies'],abilities,templates)
        changes={k:{'before':previous[tuple(g['source_identity'])][k],'after':row[k]} for k in
                 ['status','metrics','first_gap_family','primitive','required_capability','state_hash'] if row[k]!=previous[tuple(g['source_identity'])][k]}
        if changes:drift.append({'root':g['record_identity'],'changes':changes})
        annotate(row,r,result);rows.append(row)
        if (i+1)%50==0:print('frozen',i+1,flush=True)
    write('frozen_results.json',rows)
    write('frozen_summary.json',{'combat':summarize(rows),'joined':summarize([r for r in rows if r['skill_joined']]),
        'damage_attempts':sum(r['metrics'].get('damage_operations_attempted',0)+int(r['primitive']=='RPG.GameCore.DamageByAttackProperty') for r in rows),
        'drift':drift,'inputs_modified':False,'historical_denominators':[632,160,161]})
    assert not drift and len(rows)==632 and sum(r['skill_joined'] for r in rows)==160

def broader(roots):
    nodes,aliases,abilities,templates=context(roots)
    inputs=read(R18/'joined_explicit_inputs.json');base=BehaviorBattleState.from_snapshot(inputs['state'])
    state,policies=extend(base,inputs['policies'],nodes)
    instances=read(R18/'damage_perform_finish_evidence.json')['instances'];bykey={tuple(g['source_identity']):(g,ir) for g,ir in roots}
    graph_results={};rows=[]
    for instance in instances:
        key=tuple(instance['source_identity']);g,ir=bykey[key]
        if key not in graph_results:
            row,r,result=run_probe(g,ir,state,aliases,policies,abilities,templates)
            graph_results[key]=(annotate(row,r,result),r)
        graph,r=graph_results[key];source=IRNode.from_dict(instance['decoded_fields'])
        # Prefer the executable pointer for the same exact source span.
        candidates=[n for n in [*walk_nodes(ir.payload.get('tasks')),*walk_nodes(ir)]
                    if n.op==source.op and n.payload.get('span')==source.payload.get('span')]
        source=candidates[0] if candidates else source
        p=__import__('copy').deepcopy(policies);p[DAMAGE]['finish_tasks'][source.stable_hash()]=finish_binding()
        root=AbilityIR('bounded_finish_probe','ability',source.authority,{'tasks':TaskSequenceIR('bounded_seq','immediate_sequence',source.authority,{'tasks':[source]})})
        probe=BehaviorRuntime(state,actions={'probe':root},policies=p);out=probe.step('probe')
        count=probe.state.scheduler.action_execution['metrics'].get('damage_perform_finish_completed',0)
        assert count==1 and out.status.value=='WAITING_SCHEDULER'
        tasks=[t for t in r.state.scheduler.action_execution['tasks'].values() if t['node']['op']==source.op
               and t['node']['payload'].get('span')==source.payload.get('span')
               and t['node']['authority']['source_sha256']==source.authority.source_sha256]
        rows.append({'root':instance['root'],'source_identity':instance['source_identity'],'source_span':instance['source_span'],
            'source_hash':source.stable_hash(),'source_evidence':source.authority.to_dict(),
            'reachable':bool(tasks) or bool(graph['gap_node'] and graph['gap_node']==source.to_dict()),
            'context_ready':bool(tasks),'reference_supported':count==1,'oracle_blocked':True,
            'structure_only_in_original_graph':not bool(tasks),
            'original_graph_completed':any(t['status']=='TASK_COMPLETE' for t in tasks),
            'graph_status':graph['status'],'graph_gap':graph['required_capability'],
            'bounded_probe_status':out.status.value,'bounded_probe_hash':probe.state.stable_hash(),
            'probe_scope':'ISOLATED_REAL_FINISH_LOCAL_DRAIN_ASSERTION; no damage injected; not lifecycle/full-skill completion',
            'finish_node_added':False,'native_correctness':False})
    write('broader_finish_instances.json',rows)
    write('broader_summary.json',{'structural_instances':len(rows),'classification_overlap':True,
        **{k:sum(r[k] for r in rows) for k in ('reachable','context_ready','reference_supported','oracle_blocked','structure_only_in_original_graph','original_graph_completed')},
        'distinct_original_roots':len(graph_results),'synthetic_skill_finish_inserted':False})
    assert len(rows)==118

if __name__=='__main__':
    roots,_=load()
    if '--frozen-only' in sys.argv:frozen(roots)
    elif '--broader-only' in sys.argv:broader(roots)
    else:joined(roots)
