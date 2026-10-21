"""R20 actor input contract on the existing BehaviorBattleState.

Construction is deterministic reference initialization, not native admission.
Static records prove only their serialized fields; scenario values stay labelled.
"""
from __future__ import annotations
import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from hsr_battle_agent.battle_ir.behavior import Authority, TaskIR, canonical_json, stable_hash
from .behavior import GapError
from .behavior_primitives import raw_checked
from .behavior_state import ModifierInstance, validate_json

POLICY_ID = 'r20_actor_binding_reference_v1'
AUTHORITIES = ('REAL_CONTENT_STATIC', 'REAL_CONTENT_RECONSTRUCTED', 'REFERENCE_MODEL',
               'EXPLICIT_SCENARIO_INPUT', 'EFFECTIVE_RUNTIME_UNKNOWN')
FIELDS = {'level','promotion','rank','skill_levels','activated_skill_tree_rows',
          'rank_requirements','progression_thresholds','available_skills','base_properties',
          'effective_properties','hp','max_hp','actor_resources','team','entity_state',
          'dynamic_providers','ability_references','active_modifiers','presentation'}

def pointer(document, path):
    if path == '': return document
    if not isinstance(path,str) or not path.startswith('/'): raise ValueError('JSON pointer required')
    for key in path[1:].split('/'):
        key=key.replace('~1','/').replace('~0','~')
        document=document[int(key)] if isinstance(document,list) else document[key]
    return document

def source_reference(path, *, version, pointer_path, identity, kind, expected_sha256):
    """Verify an explicitly pinned caller artifact; never discover content implicitly."""
    data=Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest()!=expected_sha256: raise ValueError('actor source pin mismatch')
    record=pointer(json.loads(data.decode('utf-8-sig')),pointer_path)
    return {'version':version,'artifact':str(path),'artifact_sha256':expected_sha256,
            'pointer':pointer_path,'record':record,'record_hash':stable_hash(record),
            'identity':identity,'kind':kind,'verification':'PINNED_ARTIFACT_JSON_POINTER'}

def supplied(value, evidence='caller scenario input'):
    return {'status':'KNOWN','value':value,'authority':'EXPLICIT_SCENARIO_INPUT','evidence':evidence}

def unknown(evidence='effective initialization unavailable'):
    return {'status':'UNKNOWN','authority':'EFFECTIVE_RUNTIME_UNKNOWN','evidence':evidence}

def reference_policy():
    return {'identity':POLICY_ID,'authority':'REFERENCE_MODEL','evidence':'caller reference actor initialization',
            'construction':'EXPLICIT_FIELDS_ONLY_REFERENCE','properties':'EXPLICIT_EFFECTIVE_OR_BASE_REFERENCE',
            'skill_tree_bindings':{},'initial_modifiers':'EXPLICIT_ACTIVE_INSTANCES_REFERENCE'}

@dataclass(frozen=True)
class ActorRuntimeBinding:
    entity_id: str
    content_version: str
    content: dict
    fields: dict
    overrides: dict
    policy: dict

    def to_dict(self):
        return json.loads(canonical_json({'entity_id':self.entity_id,'content_version':self.content_version,
            'content':self.content,'fields':self.fields,'overrides':self.overrides,'policy':self.policy}))

    @classmethod
    def from_dict(cls, value): return cls(**copy.deepcopy(value))

    def bind(self, engine):
        """Atomic initialization; a failed binding leaves runtime and trace unchanged."""
        document=self.to_dict(); validate_json(document)
        authority=Authority('REFERENCE_MODEL',self.content_version,self.content.get('artifact',''),
                            self.content.get('artifact_sha256',''),semantic_status='REFERENCE_MODEL')
        node=TaskIR('actor_binding/'+str(self.entity_id),'actor_binding_reference',authority,document)
        candidate=engine.state.clone()
        try:
            _bind(engine,node,candidate,document)
        except (KeyError,TypeError,ValueError,AttributeError,OSError) as exc:
            raise GapError(node,'ACTOR_BINDING_INPUT_GAP: '+str(exc)) from exc
        engine.state=candidate
        return copy.deepcopy(candidate.mechanics[POLICY_ID]['actors'][self.entity_id])

def fail(node, kind, detail): raise GapError(node,kind+': '+str(detail))

def _bind(engine,node,state,b):
    eid=b['entity_id'];p=b['policy'];c=b['content']
    if not isinstance(eid,str) or not eid: fail(node,'ACTOR_IDENTITY_MISSING','entity ID')
    if state.scheduler.action_execution:
        execution = state.scheduler.action_execution
        turn_adapter = state.mechanics.get('battle_turn_adapter_v1')
        drained_reference_boundary = (turn_adapter is not None and
            execution['roots'][execution['current_root']]['status'] == 'ACTION_REFERENCE_COMPLETE' and
            not state.damage_transactions and not state.pending_events)
        if not drained_reference_boundary:
            fail(node,'ACTOR_INITIALIZATION_PHASE_GAP','bind before action execution or at a drained explicit R22 boundary')
    if (p.get('identity')!=POLICY_ID or p.get('authority')!='REFERENCE_MODEL' or not p.get('evidence') or
        p.get('construction')!='EXPLICIT_FIELDS_ONLY_REFERENCE' or
        p.get('properties')!='EXPLICIT_EFFECTIVE_OR_BASE_REFERENCE'):
        fail(node,'ACTOR_INITIALIZATION_POLICY_MISSING','explicit policy')
    if c.get('version')!=b['content_version']: fail(node,'VERSIONED_CONTENT_GAP','actor source/runtime version mismatch')
    version_evidence=c.get('version_evidence')
    if not isinstance(version_evidence,dict): fail(node,'VERSIONED_CONTENT_GAP','pinned source version manifest required')
    manifest_bytes=Path(version_evidence['artifact']).read_bytes()
    manifest=json.loads(manifest_bytes.decode('utf-8-sig'))
    if (hashlib.sha256(manifest_bytes).hexdigest()!=version_evidence['sha256'] or
        pointer(manifest,version_evidence['version_pointer'])!=b['content_version']):
        fail(node,'VERSIONED_CONTENT_GAP','manifest version/pin disagreement')
    shard=pointer(c['record'],version_evidence['record_shard_pointer'])
    shard_hash=pointer(c['record'],version_evidence['record_shard_hash_pointer'])
    if not any(row.get('relative_path')==shard and row.get('sha256')==shard_hash
               for row in pointer(manifest,version_evidence['files_pointer'])):
        fail(node,'VERSIONED_CONTENT_GAP','decoded record source shard not in version manifest')
    if (c.get('kind') not in ('Avatar','Monster') or type(c.get('identity')) not in (str,int) or
        not c.get('artifact') or len(c.get('artifact_sha256',''))!=64 or
        c.get('verification')!='PINNED_ARTIFACT_JSON_POINTER' or stable_hash(c.get('record'))!=c.get('record_hash')):
        fail(node,'ACTOR_CONTENT_PROVENANCE_GAP','pinned record identity')
    artifact=Path(c['artifact']).read_bytes()
    if (hashlib.sha256(artifact).hexdigest()!=c['artifact_sha256'] or
        pointer(json.loads(artifact.decode('utf-8-sig')),c['pointer'])!=c['record']):
        fail(node,'ACTOR_CONTENT_PROVENANCE_GAP','artifact/record pin mismatch')
    # Identity needs an exact record field, not a name heuristic or row ordinal.
    identity_path=c.get('identity_pointer')
    if identity_path is None or pointer(c['record'],identity_path)!=c['identity']:
        fail(node,'ACTOR_CONTENT_PROVENANCE_GAP','exact identity pointer')
    old=state.mechanics.get(POLICY_ID,{}).get('actors',{})
    if eid in old: fail(node,'ACTOR_ALREADY_BOUND','explicit replacement contract required')
    if set(b['fields'])-FIELDS or set(b['overrides'])-FIELDS: fail(node,'ACTOR_FIELD_UNKNOWN','field contract')
    values={};provenance={}
    for name,entry in b['fields'].items():
        _field(node,c,name,entry)
        provenance[name]=copy.deepcopy(entry)
        if entry['status']=='KNOWN': values[name]=copy.deepcopy(entry['value'])
    for name,entry in b['overrides'].items():
        _field(node,c,name,entry)
        if entry['authority']!='EXPLICIT_SCENARIO_INPUT': fail(node,'ACTOR_OVERRIDE_AUTHORITY_GAP',name)
        provenance[name]={'input':provenance.get(name),'override':copy.deepcopy(entry)}
        if entry['status']=='KNOWN': values[name]=copy.deepcopy(entry['value'])
        else: values.pop(name,None)
    entity=copy.deepcopy(state.entities.get(eid,{}))
    # Existing fixture storage is retained and explicitly identified as inherited,
    # never upgraded into known actor field provenance.
    inherited={'entity':copy.deepcopy(entity),'properties':copy.deepcopy(state.properties.get(eid,{})),
               'progression':copy.deepcopy(state.progression.get(eid,{})),
               'resources':copy.deepcopy(state.actor_resources.get(eid,{}))}
    for name in ('level','promotion','rank'):
        if name in values and (type(values[name]) is not int or values[name]<0): fail(node,'ACTOR_FIELD_INVALID',name)
    if 'level' in values and values['level']==0: fail(node,'ACTOR_FIELD_INVALID','level requires positive reference integer')
    if 'entity_state' in values:
        if not isinstance(values['entity_state'],dict): fail(node,'ACTOR_FIELD_INVALID','entity_state')
        if {'content_identity','content_version','content_kind','team'} & set(values['entity_state']):
            fail(node,'ACTOR_FIELD_INVALID','reserved entity identity field')
        entity.update(values['entity_state'])
    entity.update(content_identity=c['identity'],content_version=b['content_version'],content_kind=c['kind'])
    for name in ('level','promotion','team'):
        if name in values: entity[name]=values[name]
    if 'team' in values and (not isinstance(values['team'],str) or not values['team']): fail(node,'ACTOR_FIELD_INVALID','team identity')
    state.entities[eid]=entity
    prog=copy.deepcopy(state.progression.get(eid,{}))
    for name in ('rank','promotion','skill_levels','rank_requirements','progression_thresholds','available_skills'):
        if name in values: prog[name]=values[name]
    for name in ('skill_levels','rank_requirements','progression_thresholds'):
        if name in values and (not isinstance(values[name],dict) or any(type(v) is not int or v<0 for v in values[name].values())):
            fail(node,'ACTOR_FIELD_INVALID',name)
    if 'available_skills' in values and (not isinstance(values['available_skills'],list) or any(type(v) not in (str,int) for v in values['available_skills'])):
        fail(node,'ACTOR_FIELD_INVALID','available skill identities')
    if 'activated_skill_tree_rows' in values:
        rows=values['activated_skill_tree_rows']
        if not isinstance(rows,dict) or any(type(v) is not bool for v in rows.values()): fail(node,'PROGRESSION_INPUT_GAP','explicit boolean activated rows')
        prog['activated_skill_tree_rows']=copy.deepcopy(rows)
        prog['skill_tree_rows']={k:{'activated':True,'authority':'EXPLICIT_SCENARIO_INPUT'} for k,v in rows.items() if v}
    if prog: state.progression[eid]=prog
    props=copy.deepcopy(state.properties.get(eid,{}))
    base=values.get('base_properties');effective=values.get('effective_properties')
    if base is not None and effective is not None and base!=effective:
        from .dynamic_property import AGGREGATION
        if p.get('effective_property_relation')!=AGGREGATION: fail(node,'PROPERTY_INITIALIZATION_GAP','R19 base/effective contribution relation')
    for mapping in (base,effective,values.get('actor_resources')):
        if mapping is not None:
            if not isinstance(mapping,dict): fail(node,'ACTOR_FIELD_INVALID','raw property/resource map')
            for v in mapping.values(): raw_checked(v)
    if base is not None: props.update(base)
    if effective is not None: props.update(effective)
    for name in ('hp','max_hp'):
        if name in values: props[name]=raw_checked(values[name])
    if 'hp' in props and 'max_hp' in props and not 0<=props['hp']<=props['max_hp']: fail(node,'HP_INITIALIZATION_GAP','reference HP bounds')
    if props: state.properties[eid]=props
    if 'actor_resources' in values: state.actor_resources[eid]=values['actor_resources']
    if 'dynamic_providers' in values:
        if not isinstance(values['dynamic_providers'],dict): fail(node,'ACTOR_FIELD_INVALID','dynamic provider scopes')
        for scope,store in values['dynamic_providers'].items():
            if scope in state.dynamic_values and state.dynamic_values[scope]!=store: fail(node,'DYNAMIC_PROVIDER_COLLISION',scope)
            if not isinstance(store,dict): fail(node,'ACTOR_FIELD_INVALID','dynamic provider store')
            for v in store.values(): raw_checked(v)
            state.dynamic_values[scope]=copy.deepcopy(store)
    for ref in values.get('ability_references',[]):
        if ref not in engine.abilities: fail(node,'ACTOR_ABILITY_CATALOG_GAP',ref)
    if 'presentation' in values: state.presentation.setdefault('actors',{})[eid]=values['presentation']
    for row in values.get('active_modifiers',[]):
        if p.get('initial_modifiers')!='EXPLICIT_ACTIVE_INSTANCES_REFERENCE': fail(node,'INITIAL_MODIFIER_POLICY_MISSING','explicit active instances')
        m=ModifierInstance(**row)
        if m.owner!=eid or any(x not in state.entities for x in (m.owner,m.caster,m.original_caster,m.target)):
            fail(node,'INITIAL_MODIFIER_OWNERSHIP_GAP',m.instance_id)
        if m.instance_id in state.modifiers or m.definition_id not in state.modifier_definitions:
            fail(node,'INITIAL_MODIFIER_DEFINITION_GAP',m.definition_id)
        definition=state.modifier_definitions[m.definition_id]
        if (stable_hash(definition['decoded_graph'])!=definition['graph_hash'] or
            m.authority.get('definition_graph_hash')!=definition['graph_hash'] or
            m.config_identity!=definition['config_identity'] or m.activation_state!='REFERENCE_INSTANCE_ACTIVE'):
            fail(node,'INITIAL_MODIFIER_DEFINITION_GAP','exact definition/active authority')
        if m.authority.get('semantic_authority')!='REFERENCE_MODEL' or not m.reference_policy.get('initialization_evidence'):
            fail(node,'INITIAL_MODIFIER_POLICY_MISSING','explicit activation evidence')
        if (type(m.stack) is not int or m.stack<0 or type(m.count) is not int or m.count<0 or
            m.duration.get('units')!='EXPLICIT_REFERENCE_UNITS' or
            m.provider_binding.get('source_provider') not in state.dynamic_values or
            not isinstance(m.provider_binding.get('definition_policy'),dict)):
            fail(node,'INITIAL_MODIFIER_POLICY_MISSING','stack/duration and explicit provider policy')
        for store in (m.dynamic_values,m.snapshot_data):
            for v in store.values(): raw_checked(v)
        # Contributions must already be reflected in caller effective properties.
        if m.property_contributions and p.get('initial_contributions')!='R17_STORAGE_ALREADY_INCLUDES_REFERENCE':
            fail(node,'PROPERTY_INITIALIZATION_GAP','initial contribution storage policy')
        existing={r['registration_id'] for inst in state.modifiers.values() for r in inst.event_registrations}
        for r in m.event_registrations:
            if r['registration_id'] in existing or r['modifier_instance_id']!=m.instance_id or r['owner']!=eid:
                fail(node,'INITIAL_LISTENER_OWNERSHIP_GAP',m.instance_id)
            if (type(r.get('event_id')) not in (str,int) or type(r.get('order')) is not int or
                r.get('context_policy')!='OWNER_CASTER_TARGET_EVENT_EXPLICIT_REFERENCE'):
                fail(node,'INITIAL_LISTENER_POLICY_GAP','event/order/context')
            existing.add(r['registration_id'])
            if r['registration_id'].startswith('listener:'):
                state.next_listener_id=max(state.next_listener_id,int(r['registration_id'].split(':')[1]))
        state.modifiers[m.instance_id]=m
        if m.instance_id.startswith('modifier:'):
            state.next_modifier_id=max(state.next_modifier_id,int(m.instance_id.split(':')[1]))
    if base is not None and effective is not None:
        from .dynamic_property import read, AGGREGATION
        source={'authority':'REFERENCE_MODEL','evidence':'R20 verifies explicit base/effective initialization using R19',
            'aggregation':AGGREGATION,'listener_scope':'EXPLICIT_ACTIVE_REFERENCE_INSTANCES_ONLY',
            'modifier_order':sorted(state.modifiers),
            'providers':[{'source':'BASE_PROPERTY','entity':eid,'on_missing':'GAP_REFERENCE'}]}
        for key,value in base.items():
            if read(engine,node,state,source,key)[0]!=value:
                fail(node,'PROPERTY_INITIALIZATION_GAP','base/effective contribution mismatch '+key)
    state.mechanics.setdefault(POLICY_ID,{'actors':{}})['actors'][eid]={
        'binding':b,'field_provenance':provenance,'inherited_reference_state':inherited,
        'constructor_status':'ACTOR_STATE_CONSTRUCTED','native_legality':'EFFECTIVE_RUNTIME_UNKNOWN'}

def _field(node,c,name,entry):
    if not isinstance(entry,dict) or entry.get('authority') not in AUTHORITIES or not entry.get('evidence'):
        fail(node,'ACTOR_FIELD_PROVENANCE_GAP',name)
    if entry.get('status')=='UNKNOWN':
        if 'value' in entry: fail(node,'ACTOR_FIELD_PROVENANCE_GAP','unknown carries value')
        return
    if entry.get('status')!='KNOWN' or 'value' not in entry or entry['value'] is None: fail(node,'ACTOR_FIELD_PROVENANCE_GAP',name)
    if entry['authority'] in ('REAL_CONTENT_STATIC','REAL_CONTENT_RECONSTRUCTED'):
        if entry.get('version')!=c['version']: fail(node,'VERSIONED_CONTENT_GAP',name)
        if pointer(c['record'],entry['pointer'])!=entry['value']: fail(node,'ACTOR_FIELD_PROVENANCE_GAP','exact source field '+name)
    elif entry['authority']=='EFFECTIVE_RUNTIME_UNKNOWN': fail(node,'ACTOR_FIELD_PROVENANCE_GAP','unknown authority with known value')

def install(registry):
    previous=registry.handlers['predicate']['RPG.GameCore.BySkillPointActivated'][1]
    def skill_tree(engine,node,state):
        if POLICY_ID not in engine.policies: return previous(engine,node,state)
        p=engine.policies[POLICY_ID];binding=p.get('skill_tree_bindings',{}).get(node.stable_hash())
        if (not isinstance(binding,dict) or binding.get('authority')!='REFERENCE_MODEL' or not binding.get('evidence') or
            binding.get('comparison')!='EXPLICIT_ACTIVATED_BOOLEAN_REFERENCE'):
            fail(node,'PROGRESSION_POLICY_MISSING','exact skill-tree predicate binding')
        actor=state.target_context.get(binding.get('actor_context'))
        target_field=binding.get('source_target_field')
        if target_field is not None:
            if binding.get('target_policy')!='EXACT_CONTEXT_ACTOR_REFERENCE' or engine.select(node.payload['fields'][target_field],state)!=[actor]:
                fail(node,'PROGRESSION_ACTOR_OWNERSHIP_GAP','source target and explicit actor context agreement')
        key=node.payload.get('fields',{}).get(binding.get('key_field'))
        rows=state.progression.get(actor,{}).get('activated_skill_tree_rows')
        if type(key) is not int or actor not in state.entities or not isinstance(rows,dict) or str(key) not in rows or type(rows[str(key)]) is not bool:
            fail(node,'PROGRESSION_INPUT_MISSING','actor and explicit activation for serialized TriggerKey')
        return rows[str(key)]
    registry.handlers['predicate']['RPG.GameCore.BySkillPointActivated']=(POLICY_ID,skill_tree)
