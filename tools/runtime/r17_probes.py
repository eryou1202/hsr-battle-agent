"""R17 measurements: frozen fixtures, explicit instances, expanded roots separate."""
from __future__ import annotations
import collections
import copy
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r17_checks import AUDIT, read, write, sha
from r16_dependency_closure import load_catalog, control, COMBAT, AUDIT as R16
from r16_probes import run_probe
from r15_scheduler_probes import summary, probe_policy, POLICY_ID as SCHEDULER_POLICY
from r13_reference_fixtures import fixture
from r17_reference_fixtures import definition_binding, application_binding, configure, declared_keys, callback_nodes
from hsr_battle_agent.battle_ir.behavior import IRNode, TaskIR, TaskSequenceIR, AbilityIR, walk_nodes, stable_hash
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE

def wrapper(node,name,authority):
    finish=TaskIR(name+'/finish','RPG.GameCore.SkillPerformFinish',authority)
    return AbilityIR(name,'ability',authority,{'content_name':name,
        'tasks':TaskSequenceIR(name+'/seq','immediate_sequence',authority,{'tasks':[node,finish]})})

def name_of(node):
    roles=node.payload.get('reference_binding',{}).get('roles',node.payload.get('roles',{}))
    value=roles.get('modifier',node.payload.get('fields',{}).get('ModifierName'))
    return value.payload.get('value') if isinstance(value,IRNode) and value.op=='literal' else None

def make_explicit(node,definition,base_state,base_policies,aliases,abilities,templates,*,activation_ids):
    state=base_state.clone();policies=copy.deepcopy(base_policies)
    cb=list(callback_nodes(definition))
    keys=declared_keys(definition)|{str(n.payload['key']) for task in cb for n in walk_nodes(task) if n.op=='lookup'}
    # Every constant is recorded in this separate sandbox fixture; no native inputs.
    initial={k:2*SCALE for k in sorted(keys)}
    spec=definition_binding(definition,
        data_only_masks=[f['mask'] for f in definition['decoded_fields'] if f['mask'] not in (8,33554432)],
        activation_event_ids=activation_ids,source_precedence=['MODIFIER_LOCAL','SNAPSHOT','SOURCE_PROVIDER'],
        activation='ACTIVATE_REFERENCE',pending_callbacks='RETAIN_ENQUEUED_REFERENCE')
    # Explicitly classify non-DynamicValueLookup mask 8 as data for this sandbox.
    for f in definition['decoded_fields']:
        if f['mask']==8 and '8' not in spec['field_bindings']:spec['field_bindings']['8']='DATA_ONLY_EXPLICIT_REFERENCE'
    binding=application_binding(node,definition,owner='RESOLVED_TARGET_REFERENCE',caster='a',original_caster='a',
        source_provider='supplied',duration={'units':'EXPLICIT_REFERENCE_UNITS','remaining':5,'expiry':'EXPLICIT_ADVANCE_REFERENCE'},
        initial_dynamic_values=initial,snapshot_properties={'caster_hp':{'entity':'CASTER_REFERENCE','property':'hp'}},
        operand_roles={str(s['mask']):'OPAQUE_DATA_REFERENCE' for s in node.payload.get('reference_binding',{}).get('unknown_slots',[])})
    p=configure(state,policies,node,definition,definition_policy=spec,application_policy=binding)
    # Concrete callback contributions require serialized reference property mappings.
    for task in cb:
        if task.op=='RPG.GameCore.StackProperty':
            r=task.payload.get('reference_binding',{}).get('roles',task.payload.get('roles',{}))
            prop=r.get('property')
            if type(prop) is int:
                key='reference_property_'+str(prop)
                for entity in state.entities:state.properties[entity][key]=0
                p['property_tasks'][task.stable_hash()]={'aggregation':'ADDITIVE_REVERSIBLE_REFERENCE','properties':{str(prop):key}}
        if task.op=='RPG.GameCore.SetDynamicValue':
            binding={'provider':'MODIFIER_LOCAL_REFERENCE'}
            f=task.payload.get('fields',{})
            if set(f)=={'unbound_bit_0','unbound_bit_1'}:
                # Caller-authored sandbox roles for this exact task hash; no native field naming.
                binding['operand_fields']={'value':'unbound_bit_0','key':'unbound_bit_1'}
            p.setdefault('dynamic_writes',{})[task.stable_hash()]=binding
        if task.op=='RPG.GameCore.RemoveModifier':
            p['removals'][task.stable_hash()]={'selection':'CONFIG_TARGET_REFERENCE','identity_filter':{},
                'reason':'DECODED_CALLBACK_EXPLICIT_REMOVAL_REFERENCE','pending_callbacks':'RETAIN_ENQUEUED_REFERENCE'}
    return state,policies

def main(reuse_frozen=False):
    corpus=read(control('real_combat_corpus_v2'))
    compiled=[(g,IRNode.from_dict(read(ROOT/g['IR_artifact']))) for g in corpus['graphs']]
    for g,node in compiled:
        if node.stable_hash()!=g['canonical_IR_hash']:raise ValueError('frozen IR changed')
    nodes=[n for _,root in compiled for n in walk_nodes(root)]
    state,aliases,policies=fixture({n.payload.get('alias') for n in nodes if n.op=='RPG.GameCore.TargetAlias'},
                                 {n.payload['key'] for n in nodes if n.op=='lookup'})
    policies[SCHEDULER_POLICY]=probe_policy()
    write('frozen_reference_policy.json',{'state':state.snapshot(),'policies':policies,
        'category':'UNCHANGED_FROZEN_FIXTURE','additional_modifier_inputs':False,'native_actor':False})
    catalog=load_catalog();abilities=catalog.executable_abilities();templates=catalog.compiled_templates()
    definitions=catalog.modifier_definitions()
    index=[]
    for d in definitions.values():
        index.append({k:v for k,v in d.items() if k not in ('compiled_decoded','decoded_graph','decoded_fields','unknown_fields')}|
            {'field_masks':[f['mask'] for f in d['decoded_fields']],
             'unknown_fields_retained':len(d['unknown_fields']),
             'definition_hash':stable_hash(d),'compiled_body_hash':stable_hash(d['compiled_decoded'])})
    write('modifier_definition_index.json',index)
    pins={d['source_artifact']:sha(ROOT/d['source_artifact']) for d in definitions.values()}
    for d in definitions.values():
        if pins[d['source_artifact']]!=d['source_artifact_sha256']:raise ValueError('definition artifact pin mismatch')
    controls=[control(n) for n in ['dependency_closure_v1','support_census_v6','semantic_gap_ledger_v4','ability_dependency_graph_v1',
                'action_scheduler_v1','real_combat_corpus_v2']]
    controls.append(ROOT/'data/control/real_runtime_generic_primitive_ledger_20261007_001.json')
    write('source_pins.json',{'controls':{p.relative_to(ROOT).as_posix():sha(p) for p in controls},'modifier_source_artifacts':pins})
    before=read(R16/'after_probes.json')
    write('before_probes.json',before)
    frozen=read(AUDIT/'after_probes.json') if reuse_frozen else []
    replays=read(AUDIT/'frozen_replay.json') if reuse_frozen else []
    elapsed=read(AUDIT/'probe_summary.json')['frozen_seconds'] if reuse_frozen else None
    start=time.perf_counter()
    for i,(g,node) in enumerate([] if reuse_frozen else [(g,n) for g,n in compiled if g['stratum'] in COMBAT]):
        row,r,result=run_probe(g,node,state,aliases,policies,abilities,templates);row['category']='UNCHANGED_FROZEN_FIXTURE';frozen.append(row)
        if i%61==0:
            checkpoint=BehaviorRuntime(state,actions={'probe':node},abilities=abilities,templates=templates,aliases=aliases,policies=policies)
            checkpoint.start_action('probe');checkpoint.run_ready(7)
            engines=[checkpoint,checkpoint.clone(),BehaviorRuntime.from_snapshot(checkpoint.snapshot())]
            results=[e.run_until_blocked() for e in engines]
            hashes=[e.state.stable_hash() for e in engines]
            if results[0]!=results[1] or results[0]!=results[2] or len(set(hashes))!=1:raise ValueError('frozen replay failure')
            replays.append({'root':g['record_identity'],'hash':hashes[0],'PASS':True})
        if (i+1)%50==0:print('frozen',i+1,flush=True)
    write('after_probes.json',frozen);write('frozen_replay.json',replays)
    bysource={tuple(r['source_identity']):r for r in before}
    drift=[{'root':r['root'],'differences':{k:[bysource[tuple(r['source_identity'])].get(k),r.get(k)] for k in
                ['status','metrics','first_gap_family','primitive','required_capability']
                if bysource[tuple(r['source_identity'])].get(k)!=r.get(k)}} for r in frozen]
    drift=[r for r in drift if r['differences']];write('frozen_drift.json',drift)
    if drift:raise ValueError('unchanged frozen fixtures drifted')
    receipt={'category':'UNCHANGED_FROZEN_FIXTURE','combat':{'before':summary(before),'after':summary(frozen)},
        'joined':{'before':summary([r for r in before if r['skill_joined']]),'after':summary([r for r in frozen if r['skill_joined']])},
        'frozen_seconds':elapsed if reuse_frozen else time.perf_counter()-start,'definitions':len(definitions),
        'directory_definitions':sum(not d['source_pointer'] for d in definitions.values()),
        'inline_definitions':sum(bool(d['source_pointer']) for d in definitions.values()),'R17_new_decoded_graphs':0}
    write('probe_summary.json',receipt)
    expanded=[]
    for record in catalog.records.values():
        if record.get('newly_decoded'):
            g={'record_identity':record['identity'],'source_identity':list((record['source_shard_sha256'],record['record_start'],record['record_end'])),
               'IR_artifact':record['IR_artifact'],'skill_joined':False}
            row,_,_=run_probe(g,IRNode.from_dict(record['ir']),state,aliases,policies,abilities,templates)
            row['category']='NEW_EXPANDED_CORPUS';row['origin']='R16_EXPANDED_ONLY_NO_R17_NEW_READER';expanded.append(row)
    write('expanded_probes.json',expanded);receipt['expanded']=summary(expanded)
    byname=collections.defaultdict(list)
    for definition in definitions.values():byname[definition['config_identity']].append(definition)
    first_inputs=[];explicit=[];policydocs=[]
    blockers=[r for r in before if r['skill_joined'] and r['primitive']=='RPG.GameCore.AddModifier' and r['gap_node']['node_id']=='/record/task_list/0']
    compiled_by_source={tuple(g['source_identity']):(g,n) for g,n in compiled}
    for row in blockers:
        node=IRNode.from_dict(row['gap_node']);name=name_of(node);choices=byname[name]
        parent=tuple(row['source_identity']);scoped=[d for d in choices if tuple(d['parent_source_identity'])==parent]
        choices=scoped or [d for d in choices if not d['source_pointer']]
        classification={'root':row['root'],'source_identity':row['source_identity'],'node_id':node.node_id,'config_reference':name,
            'decoded_config_present':bool(choices),'exact_source_candidates':[d['source_identity'] for d in choices],
            'exact_reference_available':len(choices)==1,'owner_caster_context_available':'FROZEN_SYNTHETIC_CONTEXT_ONLY',
            'provider_available':'FROZEN_SYNTHETIC_PROVIDER_ONLY','native_effective_state':'NATIVE_EFFECTIVE_STATE_UNKNOWN',
            'unchanged_frozen_fixture_unblocked':False,'required_explicit_policy':True,
            'unknown_operand_masks':[s['mask'] for s in node.payload.get('reference_binding',{}).get('unknown_slots',[])]}
        if len(choices)!=1:
            classification.update(classification='CONTENT_GRAPH_MISSING' if not choices else 'REFERENCE_INSTANCE_INPUT_MISSING',explicit_reference_application_completed=False)
        else:
            definition=choices[0]
            explicit_state,explicit_policies=make_explicit(node,definition,state,policies,aliases,abilities,templates,activation_ids=[])
            probe=BehaviorRuntime(explicit_state,actions={'probe':wrapper(node,row['root']+'/isolated',node.authority)},
                aliases=aliases,abilities=abilities,templates=templates,policies=explicit_policies)
            try:targets=probe.select(node.payload['reference_binding']['roles']['target']);classification['reference_target_binding']=targets
            except Exception as exc:classification['reference_target_binding_error']=str(exc)
            result=probe.step('probe');metrics=probe.state.scheduler.action_execution['metrics']
            classification.update(classification='REFERENCE_INSTANCE_INPUT_MISSING',
                explicit_reference_application_completed=metrics.get('modifier_applications_completed',0)>0,
                isolated_reference_status=result.status.value,isolated_gap=result.gap.required_capability if result.gap else None,
                lifecycle_callback_evidence='DECODED_CALLBACK_IR_REQUIRES_EXPLICIT_EVENT_CONTEXT_POLICY',
                listener_registrations=metrics.get('listeners_registered',0),native_unblocked=False)
            classification['explicit_reference_policy_sufficient_for_application']=metrics.get('modifier_applications_completed',0)>0
            classification['native_target_owner_caster_provider_available']=False
            classification['listener_event_probes']=[]
            if result.status.value=='ACTION_REFERENCE_COMPLETE':
                event_ids=sorted({registration['event_id'] for m in probe.state.modifiers.values()
                                  for registration in m.event_registrations},key=lambda v:(type(v).__name__,str(v)))
                for event_id in event_ids:
                    callback_probe=probe.clone()
                    event=TaskIR(node.node_id+'/event_probe/'+str(event_id),'modifier_event_dispatch',node.authority,
                                 {'event_id':event_id,'source':'a','payload':{'explicit_reference_event_probe':True}})
                    callback_probe.actions['callback_probe']=wrapper(event,row['root']+'/callback_probe',node.authority)
                    callback_result=callback_probe.step('callback_probe')
                    classification['listener_event_probes'].append({'category':'EXPLICIT_MODIFIER_REFERENCE_FIXTURE',
                        'scope':'JOINED_LISTENER_EVENT_PROBE','event_id':event_id,'status':callback_result.status.value,
                        'gap':callback_result.gap.required_capability if callback_result.gap else None,
                        'metrics':callback_probe.state.scheduler.action_execution['metrics'],
                        'native_event_meaning':'NATIVE_EVENT_MEANING_UNKNOWN'})
            classification['lifecycle_callback_evidence_sufficient_for_reference_registration']=result.status.value=='ACTION_REFERENCE_COMPLETE'
            classification['all_registered_event_probes_reference_complete']=bool(classification['listener_event_probes']) and all(
                e['status']=='ACTION_REFERENCE_COMPLETE' for e in classification['listener_event_probes'])
            # Same full root, with ONLY its first AddModifier explicitly configured.
            g,root=compiled_by_source[parent]
            full=BehaviorRuntime(explicit_state,actions={'probe':root},aliases=aliases,abilities=abilities,templates=templates,policies=explicit_policies)
            full_result=full.step('probe')
            classification['explicit_full_root_status']=full_result.status.value
            classification['explicit_full_root_next_gap']=full_result.gap.required_capability if full_result.gap else None
            classification['full_root_metrics']=full.state.scheduler.action_execution['metrics']
            explicit.append({'root':row['root'],'category':'EXPLICIT_MODIFIER_REFERENCE_FIXTURE','scope':'ISOLATED_REAL_ADDMODIFIER_NODE',
                'status':result.status.value,'gap':result.gap.required_capability if result.gap else None,'metrics':metrics,
                'definition_id':definition['definition_id'],'instances':len(probe.state.modifiers),'native_actor':False})
            policydocs.append({'root':row['root'],'definition_id':definition['definition_id'],'policies':explicit_policies[POLICY_ID],
                              'initial_properties':explicit_state.properties,'initial_dynamic_values':explicit_state.dynamic_values,
                              'context':explicit_state.target_context})
        first_inputs.append(classification)
    write('joined_addmodifier_first_gap_analysis.json',first_inputs)
    write('explicit_joined_application_probes.json',explicit);write('explicit_joined_fixture_policies.json',policydocs)
    receipt['joined_first_input']={'before':len(blockers),'after_unchanged':len(blockers),
        'genuinely_unblocked_frozen':0,'explicit_application_completed':sum(r.get('explicit_reference_application_completed',False) for r in first_inputs),
        'still_native_effective_unknown':len(blockers),'classifications':dict(collections.Counter(r['classification'] for r in first_inputs))}
    write('probe_summary.json',receipt)
    print('DONE',receipt['joined_first_input'],flush=True)

if __name__=='__main__':main('--reuse-frozen' in sys.argv)
