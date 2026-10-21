"""Same R15 denominators and fixture; expanded roots measured separately."""
from __future__ import annotations
import collections
import copy
import time
from r16_dependency_closure import *
from r15_scheduler_probes import summary, family, probe_policy, POLICY_ID
from r13_reference_fixtures import fixture
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime

def run_probe(g, ir, state, aliases, policies, abilities, templates):
    runtime=BehaviorRuntime(state,actions={'probe':ir},abilities=abilities,templates=templates,aliases=aliases,policies=policies)
    runtime.state.target_context['current_ability']=g['record_identity']
    result=runtime.step('probe')
    gap=result.gap
    d=runtime.state.scheduler.action_execution
    counts=collections.Counter(d['metrics'])
    occurrences=collections.Counter(h['node']['op'].rsplit('.',1)[-1] for h in d['history'] if h.get('status')=='TASK_REACHED')
    if gap:
        short=gap.task_type.rsplit('.',1)[-1]
        if gap.node['kind'] in ('TaskIR','UnsupportedSemanticIR'):
            counts['tasks_reached']+=1;occurrences[short]+=1
        reached=set(occurrences)|{short}
    else: reached=set(occurrences)
    root=d['roots'][d['current_root']]
    row={'source_identity':g['source_identity'],'root':g['record_identity'],'IR_artifact':g['IR_artifact'],
         'skill_joined':g.get('skill_joined',False),'started':ir.op=='ability','status':result.status.value,
         'primitive':gap.task_type if gap else None,'required_capability':gap.required_capability if gap else None,
         'first_gap_family':('TEMPLATE_PARAMETER_CONTEXT' if gap and gap.node['payload'].get('root_type')=='RPG.GameCore.TaskListTemplate'
                             else family(gap.task_type,gap.required_capability) if gap else None),
         'metrics':dict(counts),'reached_types':sorted(reached),'primitive_occurrences':dict(occurrences),
         'adapter_error':None,'scope':'SYNTHETIC_REFERENCE_ONLY','native_executable':False,
         'logical_time':d['logical_time'],'state_hash':runtime.state.stable_hash(),
         'top_level_tasks_completed':sum(t['status']=='TASK_COMPLETE' and not t.get('container') and
            t['ability_instance_id']==root['root_ability_id'] and len(d['sequences'][t['sequence_frame_id']]['ancestor_nodes'])==1 for t in d['tasks'].values()),
         'nested_abilities':[a['identity'] for a in d['abilities'].values() if a['parent_ability_id']],
         'abilities_completed':sum(a['status']=='ABILITY_COMPLETE' for a in d['abilities'].values()),
         'gap_node':gap.node if gap else None,
         'completed_types':sorted({t['node']['op'].rsplit('.',1)[-1] for t in d['tasks'].values() if t['status']=='TASK_COMPLETE' and not t.get('container')})}
    return row, runtime, result

def main(refresh=False):
    corpus=read(control('real_combat_corpus_v2'))
    compiled=[(g,IRNode.from_dict(read(ROOT/g['IR_artifact']))) for g in corpus['graphs']]
    nodes=[n for _,ir in compiled for n in walk_nodes(ir)]
    state,aliases,policies=fixture({n.payload.get('alias') for n in nodes if n.op=='RPG.GameCore.TargetAlias'},
        {n.payload['key'] for n in nodes if n.op=='lookup'})
    policies[POLICY_ID]=probe_policy()
    write('reference_policy.json',{'state':state.snapshot(),'policies':policies,
         'scope':'EXACT_SAME_R15_SYNTHETIC_FIXTURE','native_fixture':False,
         'additional_lifecycle_or_template_policies':False})
    old=collections.defaultdict(list)
    for g,ir in compiled:
        if g['stratum'] in ('ABILITY_CORPUS','PASSIVE_CORPUS'): old[g['record_identity']].append(ir)
    old={k:v[0] for k,v in old.items() if len(v)==1}
    catalog=load_catalog()
    abilities=catalog.executable_abilities();templates=catalog.compiled_templates()
    new=[]
    for record in catalog.records.values():
        if record.get('newly_decoded'):
            new.append(({'record_identity':record['identity'],'source_identity':list(source_key(record)),
                         'IR_artifact':record['IR_artifact'],'skill_joined':False},IRNode.from_dict(record['ir'])))
    results={};elapsed={}
    historical={tuple(r['source_identity']):r for r in read(R15/'after_probes.json')}
    drift=[];replay=[]
    for phase,rows,abilitycatalog,templatecatalog in [
        ('before',[(g,ir) for g,ir in compiled if g['stratum'] in COMBAT],old,{}),
        ('after',[(g,ir) for g,ir in compiled if g['stratum'] in COMBAT],abilities,templates),
        ('expanded',new,abilities,templates)]:
        if refresh and phase in ('before','after'):
            results[phase]=read(AUDIT/(phase+'_probes.json'))
            elapsed[phase]=read(AUDIT/'probe_summary.json')['timings_seconds'][phase]
            if phase=='after':
                byg={tuple(g['source_identity']):(g,ir) for g,ir in rows}
                for i,oldrow in enumerate(results[phase]):
                    if oldrow['primitive']=='RPG.GameCore.IncludeTaskListTemplate' or \
                        (oldrow.get('gap_node') or {}).get('payload',{}).get('root_type')=='RPG.GameCore.TaskListTemplate':
                        g,ir=byg[tuple(oldrow['source_identity'])]
                        results[phase][i]=run_probe(g,ir,state,aliases,policies,abilitycatalog,templatecatalog)[0]
                write('after_probes.json',results[phase])
            continue
        start=time.perf_counter();output=[]
        for index,(g,ir) in enumerate(rows):
            row,runtime,result=run_probe(g,ir,state,aliases,policies,abilitycatalog,templatecatalog)
            output.append(row)
            if phase=='before':
                original=historical[tuple(g['source_identity'])]
                keys=['status','metrics','first_gap_family','primitive','required_capability']
                changes={k:{'historical':original[k],'rerun':row[k]} for k in keys if original[k]!=row[k]}
                if changes: drift.append({'root':g['record_identity'],'changes':changes})
            if phase=='after' and (index%53==0 or 'Natasha' in g['record_identity'] or
                                    ('_Skill02_Phase01' in g['record_identity'] and row['metrics']['abilities_invoked']>0)):
                # Resume a real root through the same R15 owner graph at a bounded
                # checkpoint; compare full results and states across clone/restore.
                r=BehaviorRuntime(state,actions={'probe':ir},abilities=abilities,templates=templates,aliases=aliases,policies=policies)
                r.state.target_context['current_ability']=g['record_identity']
                r.start_action('probe');r.run_ready(7)
                clone=r.clone();restored=BehaviorRuntime.from_snapshot(r.snapshot())
                outcomes=[engine.run_until_blocked() for engine in (r,clone,restored)]
                hashes=[engine.state.stable_hash() for engine in (r,clone,restored)]
                if outcomes[0]!=outcomes[1] or outcomes[0]!=outcomes[2] or len(set(hashes))!=1:
                    raise ValueError('real root replay mismatch')
                if index%53==0:
                    full=[engine.stable_hash() for engine in (r,clone,restored)]
                    if len(set(full))!=1: raise ValueError('full catalog/runtime snapshot mismatch')
                replay.append({'root':g['record_identity'],'source_identity':g['source_identity'],'checkpoint_budget':7,
                               'result_equal':True,'state_hash':hashes[0],'catalog_snapshot_hash_checked':index%53==0})
            if (index+1)%50==0: print(phase,index+1,flush=True)
        results[phase]=output;elapsed[phase]=time.perf_counter()-start
        write(phase+'_probes.json',output)
    before={tuple(r['source_identity']):r for r in results['before']}
    for phase,rows in results.items():
        for row in rows:
            cap=row.get('required_capability') or ''
            row['first_gap_subtype']=('TEMPLATE_PARAMETER_CONTEXT' if cap.startswith('TEMPLATE_PARAMETER_INHERITANCE') else
                'UNBOUND_RUNTIME_CATALOG_LOOKUP' if cap.startswith('missing decoded child catalog reference:') else
                'ABILITY_OR_MODIFIER_LIFECYCLE_POLICY' if 'entry/lifecycle slot' in cap else
                'EXPLICIT_FIXTURE_OR_CONTEXT_INPUT' if cap.startswith('explicit reference input:') else row['first_gap_family'])
        write(phase+'_probes.json',rows)
    changed=[{'root':r['root'],'source_identity':r['source_identity'],'skill_joined':r['skill_joined'],
              'before':before[tuple(r['source_identity'])]['required_capability'],'after':r['required_capability'],
              'before_family':before[tuple(r['source_identity'])]['first_gap_family'],'after_family':r['first_gap_family']}
             for r in results['after'] if (r['primitive'],r['required_capability']) !=
             (before[tuple(r['source_identity'])]['primitive'],before[tuple(r['source_identity'])]['required_capability'])]
    receipt={'combat':{p:summary(results[p]) for p in ('before','after')},
             'skill_joined':{p:summary([r for r in results[p] if r['skill_joined']]) for p in ('before','after')},
             'expanded':summary(results['expanded']),'historical_baseline_drift':drift,
             'first_blocker_changed_combat':len(changed),'first_blocker_changed_joined':sum(r['skill_joined'] for r in changed),
             'changed_first_blockers':changed,'timings_seconds':elapsed,
             'first_gap_subtype_distributions':{p:dict(collections.Counter(r['first_gap_subtype'] for r in rows if r['first_gap_subtype'])) for p,rows in results.items()},
             'runtime_unbound_catalog_lookups':{p:{'combat_or_expanded':sum(r['first_gap_subtype']=='UNBOUND_RUNTIME_CATALOG_LOOKUP' for r in rows),
                'joined':sum(r['skill_joined'] and r['first_gap_subtype']=='UNBOUND_RUNTIME_CATALOG_LOOKUP' for r in rows)} for p,rows in results.items()},
             'primitive_occurrences':{p:dict(sum((collections.Counter(r['primitive_occurrences']) for r in results[p]),collections.Counter())) for p in results}}
    if refresh:
        receipt['historical_baseline_drift']=read(AUDIT/'probe_summary.json')['historical_baseline_drift']
    write('probe_summary.json',receipt)
    if not refresh: write('replay_receipt.json',{'status':'PASS','roots':replay})
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('changed_first_blockers','primitive_occurrences')},indent=2),flush=True)

if __name__=='__main__': main(refresh='--refresh' in sys.argv)
