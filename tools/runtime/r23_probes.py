"""Original joined roots through R20 -> R22 permission -> R15; no repairs."""
from __future__ import annotations
import collections
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime')]
from r23_checks import AUDIT
from r23_discovery import write
from r23_reference_fixtures import joined_runtime, content
from r23_census import runtime_class, structural_class
from r21_checks import read
from hsr_battle_agent.battle_ir.behavior import IRNode, walk_nodes
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.battle_turn import KEY


def checkpoint(r,label):
    restored=BehaviorRuntime.from_snapshot(r.snapshot())
    clone=r.clone()
    assert r.stable_hash()==restored.stable_hash()==clone.stable_hash()
    left,right=clone.run_until_next_turn(),restored.run_until_next_turn()
    assert left==right and clone.stable_hash()==restored.stable_hash()
    return {'label':label,'full_hash':r.stable_hash(),'clone_snapshot':'PASS',
        'restored_suffix':'PASS','suffix_boundary':left.kind,'suffix_hash':clone.stable_hash()}


def execute(graph, *, templates=True, template_providers=False, replay=False, stepping=False):
    r,binding,template_receipts=joined_runtime(graph,templates_enabled=templates,template_provider_inputs=template_providers)
    initial=r.clone() if replay else None
    receipts=[];checkpoints=[]
    def command(kind,**args):
        receipt,out=r.record_turn_command(kind,args)
        receipts.append(receipt)
        return out
    decision=command('advance',budget=10000)
    assert decision.kind=='PLAYER_NORMAL_TURN' and decision['actor_id']=='a'
    if replay:checkpoints.append(checkpoint(r,'canonical_skill_decision'))
    permission=r.legal_action_candidates(decision['decision_id'])[0]
    command('submit',permission=permission,targets=['b'],expected_revision=decision['state_revision'])
    if replay:checkpoints.append(checkpoint(r,'before_original_source_entry'))
    before_clock=r.state.mechanics[KEY]['clock']['now'].copy()
    out=None;observed=set()
    for i in range(256 if stepping else 1):
        out=command('complete',budget={'scheduler_work':1,'decision_transitions':1} if stepping else 10000)
        if stepping:
            d=r.state.scheduler.action_execution
            labels=[]
            if any(a['parent_ability_id'] and a['status']=='RUNNING' for a in d['abilities'].values()):labels.append('inside_child_ability')
            if any(b['status']!='RELEASED' for b in d['barriers'].values()):labels.append('at_presentation_or_wait_barrier')
            if r.state.damage_history:labels.append('after_hp_mutation')
            if any(s['cursor']<len(s['nodes']) and s['nodes'][s['cursor']]['op']=='RPG.GameCore.IncludeTaskListTemplate'
                   for s in d['sequences'].values()):labels.append('before_template_call')
            if (d['roots'][d['current_root']]['action_id']=='canonical' and
                    any(v['action_root_id']==d['current_root'] for v in d['completion_requests'].values())):
                labels.append('before_owned_action_completion')
            for label in labels:
                if label not in observed:checkpoints.append(checkpoint(r,label));observed.add(label)
        if out.kind not in ('EXECUTION_YIELD','BUDGET_YIELD'):break
    if stepping and out.kind in ('EXECUTION_YIELD','BUDGET_YIELD'):
        raise RuntimeError('bounded checkpoint traversal did not reach a real boundary')
    assert out is not None
    d=r.state.scheduler.action_execution;s=r.state.mechanics[KEY]
    diag=r.clone().run_until_blocked() if out.kind=='SEMANTIC_GAP' else None
    gap=diag.gap if diag else None
    row={'root':graph['record_identity'],'source_identity':graph['source_identity'],
        'canonical_binding':binding,'canonical_IR_hash':r.actions['canonical'].stable_hash(),
        'templates_enabled':templates,'template_providers_supplied':template_providers,
        'template_bindings':template_receipts,'decision':out.to_dict(),
        'status':'ACTION_REFERENCE_COMPLETE' if s['action_count'] else out.kind,
        'primitive':gap.task_type if gap else None,'required_capability':gap.required_capability if gap else
            (out['failure']['message'] if out['failure'] else out.reason),
        'gap_node':gap.node if gap else None,'metrics':d['metrics'],
        'executed_child_abilities':[{'identity':a['identity'],'source_IR_hash':IRNode.from_dict(a['node']).stable_hash(),
            'status':a['status'],'action_root_id':a['action_root_id'],'parent_ability_id':a['parent_ability_id']}
            for a in d['abilities'].values() if a['parent_ability_id']],
        'template_parameter_contexts':[a['context']['template_call_binding'] for a in d['abilities'].values()
            if 'template_call_binding' in a['context']],
        'runtime_first_gap_class':None,'normal_turns_completed':s['normal_turn_count'],'actions_completed':s['action_count'],
        'original_finish_reached':any(t['node']['op']=='RPG.GameCore.SkillPerformFinish' for t in d['tasks'].values()) or
            bool(gap and gap.task_type=='RPG.GameCore.SkillPerformFinish'),
        'original_finish_completed':sum(t['status']=='TASK_COMPLETE' and t['node']['op']=='RPG.GameCore.SkillPerformFinish' for t in d['tasks'].values()),
        'hp_settlements':len(r.state.damage_history),'resource_history':r.state.mechanics.get('r20_resource_reference_v1',{}).get('history',[]),
        'owned_pending':{k:sum(v.get('status') not in ('TASK_COMPLETE','ABILITY_COMPLETE','SEQUENCE_COMPLETE','RELEASED','CALLBACK_COMPLETE')
            for v in d[k].values()) for k in ('tasks','abilities','sequences','barriers','callbacks')},
        'turn_owner':r.current_turn_owner(),'clock':s['clock']['now'],'rng_draws':r.state.rng.draws,
        'state_hash':r.state.stable_hash(),'full_runtime_hash':r.stable_hash(),'checkpoints':checkpoints,
        'source_finish_added':False,'source_IR_unchanged':r.actions['canonical'].stable_hash()==graph['canonical_IR_hash'],
        'cohort':'PARTIAL_REAL_SKILL_PREFIX' if d['metrics']['tasks_completed'] else 'BLOCKED_REAL_SKILL_ENTRY',
        'native_validated':False}
    row['runtime_first_gap_class']=runtime_class(row)
    if 'missing decoded child catalog reference:' in (row['required_capability'] or ''):
        c=content()[0];ref=row['required_capability'].split(':',1)[1]
        row['runtime_first_gap_class']=structural_class(c.resolve({'reference_type':'ABILITY_REFERENCE','identity':ref}))
    if s['action_count']:
        # Existing scenario presentation assumptions must never inflate source closure.
        abstracted=bool(r.state.presentation.get('r15_reference_nodes'))
        row['cohort']='POLICY_ABSTRACTED_REFERENCE_TRANSITION' if abstracted else 'FULL_SOURCE_CLOSED_REFERENCE_TRANSITION'
        assert s['normal_turn_count'] and out.kind=='PLAYER_NORMAL_TURN'
    elif out.kind=='SEMANTIC_GAP':
        assert r.current_turn_owner()=='a' and s['clock']['now']==before_clock and s['normal_turn_count']==0
        before=r.stable_hash();r.run_until_decision();assert r.stable_hash()==before
    if replay:
        replayed,_=initial.replay_turn_commands(receipts)
        assert replayed.stable_hash()==r.stable_hash() and replayed.snapshot()==r.snapshot()
        restored=BehaviorRuntime.from_snapshot(r.snapshot());clone=r.clone()
        assert clone.stable_hash()==restored.stable_hash()==r.stable_hash()
        row['replay']='PASS'
        write('scenarios/'+binding['binding_hash'][:16]+('_providers' if template_providers else '_template' if templates else '_before')+
              ('_stepped' if stepping else '')+'/commands.json',receipts)
    return row


def main():
    catalog,_,_,_,corpus=content()
    dependency=read(AUDIT/'joined_dependency.json')
    bykey={tuple(g['source_identity']):g for g in corpus['graphs'] if g['skill_joined']}
    # Eight semantic roles + the template caller + two distinct damage/phase paths.
    selected={tuple(c['source_identity']) for c in dependency['diversity_cohort'].values() if c}
    for name in ['Avatar_BlackSwan_00_Skill02_Phase01','Avatar_Natasha_00_Skill02_Phase01',
                 'Avatar_Bailu_00_Skill02_Phase01','Avatar_Serval_Skill02_Phase01']:
        selected.add(tuple(next(g['source_identity'] for g in bykey.values() if g['record_identity']==name)))
    cached=read(AUDIT/'joined_execution_results.json') if '--resume' in sys.argv else []
    cached={tuple(r['source_identity']):r for r in cached}
    rows=[]
    for index,root in enumerate(dependency['roots']):
        key=tuple(root['source_identity']);g=bykey[key]
        row=cached[key] if key in cached else execute(g,templates=True,replay=key in selected)
        if not row['actions_completed']:
            row['cohort']='PARTIAL_REAL_SKILL_PREFIX' if row['metrics']['tasks_completed'] else 'BLOCKED_REAL_SKILL_ENTRY'
        rows.append(row)
        write('joined_execution_results.json',rows)
        print(index+1,row['root'],row['status'],row['required_capability'],flush=True)
    # Same scenario before and after the exact inline scope/dictionary binding.
    comparisons=[]
    for name in ['Avatar_BlackSwan_00_Skill02_Phase01']:
        g=next(g for g in bykey.values() if g['record_identity']==name)
        before=execute(g,templates=False,replay=True)
        after=next(r for r in rows if r['root']==name)
        provider=execute(g,templates=True,template_providers=True,replay=True)
        comparisons.append({'root':name,'before':before,'after_context_binding':after,'after_explicit_provider_input':provider})
        stepped=execute(g,templates=True,template_providers=True,replay=True,stepping=True)
        write('stepped_template_checkpoint.json',stepped)
    write('template_before_after.json',comparisons)
    summary={'roots':len(rows),'owner_rows':161,'source_closed_unique_roots':sum(r['cohort']=='FULL_SOURCE_CLOSED_REFERENCE_TRANSITION' for r in rows),
        'policy_abstracted_unique_roots':sum(r['cohort']=='POLICY_ABSTRACTED_REFERENCE_TRANSITION' for r in rows),
        'partial_real_skill_prefix_roots':sum(r['cohort']=='PARTIAL_REAL_SKILL_PREFIX' for r in rows),
        'blocked_real_skill_entries':sum(r['cohort']=='BLOCKED_REAL_SKILL_ENTRY' for r in rows),
        'native_validated':0,'original_finish_reached_roots':sum(r['original_finish_reached'] for r in rows),
        'original_finish_completed_roots':sum(bool(r['original_finish_completed']) for r in rows),
        'hp_settled_roots':sum(bool(r['hp_settlements']) for r in rows),
        'first_gap_classes':dict(collections.Counter(r['runtime_first_gap_class'] for r in rows)),
        'first_gap_primitives':dict(collections.Counter(r['primitive'] or 'NO_R15_PRIMITIVE' for r in rows)),
        'r22_actions_completed':sum(r['actions_completed'] for r in rows),
        'r22_normal_turns_completed':sum(r['normal_turns_completed'] for r in rows),
        'clone_snapshot_replay_roots':sum(r.get('replay')=='PASS' for r in rows),
        'all_original_IR_hashes_unchanged':all(r['source_IR_unchanged'] for r in rows),
        'frozen_inputs_modified':False,'cohort':'R23_EXPLICIT_SYNTHETIC_ACTOR_INPUTS_NOT_FROZEN_CORPUS'}
    write('execution_summary.json',summary)
    print(summary,flush=True)


if __name__=='__main__':main()
