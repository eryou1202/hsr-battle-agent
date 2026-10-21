"""Reusable caller-authored sandbox bindings; never native actor/default hooks."""
from __future__ import annotations
import copy
from hsr_battle_agent.battle_ir.behavior import IRNode, stable_hash, walk_nodes
from hsr_battle_agent.battle_ir.content_catalog import walk
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID, reference_policy

def definition_binding(definition, *, data_only_masks, activation_event_ids, source_precedence,
                       activation, pending_callbacks, listener_priority=0):
    """Caller explicitly classifies every field of this exact decoded definition.

    Callback mask roles are reference bindings to archived reader shapes. Numeric
    event values and stacking policies retain their native-unknown authority.
    """
    classification={str(m):'DATA_ONLY_EXPLICIT_REFERENCE' for m in data_only_masks}
    callbacks={}
    for f in definition['compiled_decoded'].get('fields',[]):
        mask=f['mask']
        if mask==33554432:
            classification[str(mask)]='LISTENERS_REFERENCE'
            for value in f['values']:
                for callback in value['children']:
                    mapping={}
                    for x in callback['fields']:
                        role={1:'event_id',4:'tasks'}.get(x['mask'],'UNKNOWN')
                        if x['mask']==2:
                            role=('predicate' if len(x['values'])==1 and isinstance(x['values'][0],dict) and
                                  x['values'][0].get('kind')=='PredicateIR' else 'OPAQUE_DATA_EXPLICIT_REFERENCE')
                        mapping[str(x['mask'])]=role
                    callbacks[stable_hash(callback)]={'fields':mapping,'priority':listener_priority,
                        'context_policy':'OWNER_CASTER_TARGET_EVENT_EXPLICIT_REFERENCE'}
        if mask==8 and any(isinstance(v,dict) and v.get('type')=='DynamicValueLookup' for v in f['values']):
            classification[str(mask)]='DYNAMIC_DECLARATIONS_REFERENCE'
    return {'graph_hash':definition['graph_hash'],'field_bindings':classification,'callbacks':callbacks,
        'activation':activation,'activation_event_ids':list(activation_event_ids),
        'pending_callbacks':pending_callbacks,'retained_read_policy':'LIVE_THEN_DISPATCH_SNAPSHOT_REFERENCE',
        'provider_precedence':list(source_precedence),'lookup_scopes':['supplied']}

def application_binding(node, definition, *, owner, caster, original_caster, source_provider,
                        duration, initial_dynamic_values, snapshot_properties, operand_roles,
                        application_policy='INSERT_NEW_REFERENCE'):
    return {'definition_id':definition['definition_id'],'application_policy':application_policy,
        'match_identity':['definition_id','owner','caster','original_caster','source_ability','target'],
        'owner':owner,'caster':caster,'original_caster':original_caster,'source_ability':'CURRENT_ABILITY_REFERENCE',
        'source_provider':source_provider,'duration':copy.deepcopy(duration),
        'initial_dynamic_values':copy.deepcopy(initial_dynamic_values),'snapshot_properties':copy.deepcopy(snapshot_properties),
        'operand_roles':dict(operand_roles),'stack':1,'count':1,'dynamic_initialization_policy':'SERIALIZED_OVERRIDES_REFERENCE',
        'update_values':'PRESERVE_REFERENCE','update_activation_callbacks':'NO_REACTIVATION_REFERENCE',
        'update_provider':'PRESERVE_PROVIDER_REFERENCE',
        'update_contributions':'PRESERVE_EXPLICIT_CONTRIBUTIONS_REFERENCE'}

def configure(state, policies, node, definition, *, definition_policy, application_policy):
    """Bind one exact source definition + explicit caller inputs to existing state."""
    if definition['graph_hash']!=stable_hash(definition['decoded_graph']): raise ValueError('source graph drift')
    state.modifier_definitions[definition['definition_id']]=copy.deepcopy(definition)
    p=policies.setdefault(POLICY_ID,reference_policy())
    p['definitions'][definition['definition_id']]=copy.deepcopy(definition_policy)
    p['applications'][node.stable_hash()]=copy.deepcopy(application_policy)
    return p

def callback_nodes(definition):
    for _,value in walk(definition['compiled_decoded']):
        if value.get('kind') in ('TaskIR','UnsupportedSemanticIR'):
            yield IRNode.from_dict(value)

def declared_keys(definition):
    return {str(e['id']) for f in definition['compiled_decoded'].get('fields',[])
            for value in f['values'] if isinstance(value,dict) and value.get('type')=='DynamicValueLookup' for e in value.get('entries',[])}

def explicit_operands(node):
    """Anonymous slots stay unresolved unless an author supplies their roles."""
    return {str(slot['mask']):'UNRESOLVED' for slot in node.payload.get('reference_binding',{}).get('unknown_slots',[])}
