"""Explicit R20 fixtures; identities/source keys live only in fixture inputs."""
from __future__ import annotations
import copy
from pathlib import Path
from r20_checks import ROOT,read,sha
from hsr_battle_agent.battle_runtime.actor_binding import (ActorRuntimeBinding, source_reference, supplied,
    reference_policy as actor_policy, POLICY_ID as ACTOR)
from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE, STAGES, reference_policy as resource_policy
from hsr_battle_agent.battle_runtime.dynamic_property import POLICY_ID as PROPERTY
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE

OWNER=ROOT/'tmp/audit/r14_real_combat_corpus_20261008_001/owner_tables.json'
JOINS=ROOT/'data/control/generic_runtime_skill_root_join_census_v1_20261008_001.json'

def actor_content(avatar_id):
    rows=read(OWNER)['avatars']
    index=next(i for i,r in enumerate(rows) if r['graph']['fields'][0]['values'][0]['value']==avatar_id)
    c=source_reference(OWNER,version='4.6.51',pointer_path='/avatars/'+str(index),
        identity=avatar_id,kind='Avatar',expected_sha256=sha(OWNER))
    c['identity_pointer']='/graph/fields/0/values/0/value'
    from r13_frozen_reader import SNAPSHOT,MANIFEST_SHA
    c['version_evidence']={'artifact':str(SNAPSHOT/'SNAPSHOT_MANIFEST.json'),'sha256':MANIFEST_SHA,
        'version_pointer':'/content_version','files_pointer':'/files',
        'record_shard_pointer':'/source_shard','record_shard_hash_pointer':'/source_shard_sha256'}
    return c

def actor_binding(eid,avatar_id,fields=None,**changes):
    values={'level':1,'promotion':0,'rank':0,'team':'reference-team',
        'base_properties':{'hp':100*SCALE,'max_hp':100*SCALE,'reference_atk':10*SCALE},
        'actor_resources':{'reference_actor_counter':0}}
    values.update(changes)
    return ActorRuntimeBinding(eid,'4.6.51',actor_content(avatar_id),
        fields if fields is not None else {k:supplied(v,'R20 explicit fixture; native initialized state unknown') for k,v in values.items()},
        {},actor_policy())

def resource_spec(*,domain='ACTOR_RESOURCE',owner='a',key='reference_actor_counter',amount=2*SCALE,operation='ADD',listeners=()):
    return {'authority':'REFERENCE_MODEL','evidence':'R20 explicitly authored resource policy; no native cost/gain/cap equivalence',
        'domain':domain,'owner':owner,'owner_resolution':'EXACT_OWNER_REFERENCE','resource_key':key,
        'operation':operation,'amount':amount,'numeric':'R12_FIXED_RAW_STEP2_REFERENCE','overflow':'GAP_REFERENCE',
        'bounds':{'minimum':0,'maximum':10*SCALE,'handling':'CLAMP_REFERENCE','initial_overcap':'REJECT_REFERENCE'},
        'event_order':list(STAGES),'events':{s:[] for s in STAGES},'listeners':'EXPLICIT_ACTIVE_R17_REFERENCE',
        'listener_registrations':list(listeners),'event_source':'a','target_entity':'a'}

def progression_policy(nodes):
    p=actor_policy()
    for n in nodes:
        if n.op=='RPG.GameCore.BySkillPointActivated':
            fields=n.payload['fields'];key=trigger_field(n)
            target=next((k for k,v in fields.items() if getattr(v,'kind',None)=='TargetSelectorIR'),None)
            p['skill_tree_bindings'][n.stable_hash()]={'authority':'REFERENCE_MODEL','evidence':'exact source TriggerKey with caller activation booleans',
                'comparison':'EXPLICIT_ACTIVATED_BOOLEAN_REFERENCE','key_field':key,'actor_context':'caster',
                'source_target_field':target,'target_policy':'EXACT_CONTEXT_ACTOR_REFERENCE'}
    return p

def trigger_field(node):
    fields=node.payload['fields']
    for key in ('PointTriggerKey','TriggerKey'):
        if key in fields:return key
    # Both encountered readers serialize TriggerKey in mask 8. Slot indices
    # vary when an explicit target mask precedes it; never assume field zero.
    slot=next((s for s in node.payload.get('reference_binding',{}).get('unknown_slots',[]) if s['mask']==8),None)
    return 'unbound_bit_'+str(slot['field_index']) if slot else 'unbound_bit_0'

def extend(engine,nodes,*,avatar_id,level=1,promotion=0,activation=True,rank=0):
    nodes=list(nodes);p=progression_policy(nodes);engine.policies[ACTOR]=p
    rows={str(n.payload['fields'][trigger_field(n)]):activation
          for n in nodes if n.op=='RPG.GameCore.BySkillPointActivated'}
    thresholds={str(n.payload['fields'][trigger_field(n)]):1 for n in nodes if n.op=='RPG.GameCore.ByRankActivated'}
    # R19 owns the keyed rank comparison. R20 initializes its actual inputs.
    if PROPERTY in engine.policies:
        for n in nodes:
            if n.op=='RPG.GameCore.ByRankActivated':
                engine.policies[PROPERTY]['rank_bindings'][n.stable_hash()]={'authority':'REFERENCE_MODEL',
                    'evidence':'R20 explicit actor rank and threshold fixture','mode':'KEYED_THRESHOLD_GE_REFERENCE',
                    'key_field':trigger_field(n),'actor_context':'caster'}
    actor=engine.state.target_context['caster']
    binding=actor_binding(actor,avatar_id,level=level,promotion=promotion,rank=rank,
        activated_skill_tree_rows=rows,rank_requirements=thresholds)
    engine.bind_actor(binding)
    rp=resource_policy();engine.policies[RESOURCE]=rp
    listeners=sorted(r['registration_id'] for m in engine.state.modifiers.values() if m.activation_state=='REFERENCE_INSTANCE_ACTIVE' for r in m.event_registrations)
    for n in nodes:
        if n.op!='RPG.GameCore.ModifySPNew':continue
        f=n.payload['fields'];target=next((k for k,v in f.items() if getattr(v,'kind',None)=='TargetSelectorIR'),None)
        amount=next((k for k,v in f.items() if getattr(v,'kind',None)=='ExpressionIR'),None)
        if target is None or amount is None:continue
        # This is a recorded reference interpretation, not native AddRatio maths.
        spec=resource_spec(owner=actor,listeners=listeners)
        spec['source_fields']={k:'TARGET_REFERENCE' if k==target else 'AMOUNT_REFERENCE' if k==amount else 'OPAQUE_RETAINED_REFERENCE' for k in f}
        spec['amount_interpretation']='SERIALIZED_OPERAND_AS_DELTA_REFERENCE'
        rp['bindings'][n.stable_hash()]=spec
    return binding
