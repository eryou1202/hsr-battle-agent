"""Explicit source-backed R18 sandbox bindings; no native actor/default formula."""
from __future__ import annotations
import copy
from hsr_battle_agent.battle_ir.behavior import IRNode, AbilityIR, TaskSequenceIR, TaskIR, TargetSelectorIR, walk_nodes
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState, ModifierInstance
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID, STAGES, reference_policy, attack_fields
from hsr_battle_agent.battle_runtime.action_scheduler import POLICY_ID as SCHEDULER
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID as MODIFIER, reference_policy as modifier_policy
from r15_scheduler_probes import probe_policy

def task_binding(node,*,coefficient_mask=4):
    fields=attack_fields(node,node.payload['fields']['unbound_bit_1'])
    return {'authority':'REFERENCE_MODEL','source_task_hash':node.stable_hash(),
        'origin':'Caller-authored R18 sandbox formula; anonymous mask role NOT native evidenced',
        'source_version':'4.6.51','target_mask':2,'attack_mask':4,
        'task_fields':{str(f['mask']):('TARGET_REFERENCE' if f['mask']==2 else 'ATTACK_DATA_REFERENCE' if f['mask']==4 else 'OPAQUE_REFERENCE_UNUSED')
                       for f in node.payload['decoded']['structure']['fields']},
        'attack_fields':{str(f['mask']):('FORMULA_OPERAND_REFERENCE' if f['mask']==coefficient_mask else 'OPAQUE_REFERENCE_UNUSED') for f in fields},
        'attacker':'a','original_caster':'a','damage_kind':None,'per_hit':None,
        'formula':{'op':'mul','args':[{'op':'property','entity':'ATTACKER_REFERENCE','key':'reference_atk'},
                                    {'op':'source_expression','mask':coefficient_mask}]},
        'critical':'NO_CRIT_EXPLICIT_REFERENCE','negative':'REJECT_REFERENCE','rounding':'RAW_STEP2_REFERENCE',
        'duplicates':'PRESERVE_SERIALIZED_REFERENCE','ordered_stages':list(STAGES),
        'listener_scope':'EXPLICIT_ACTIVE_REFERENCE_INSTANCES_ONLY','events':{s:[] for s in STAGES},
        'boundaries':{'shield':'BYPASS_EXPLICIT_SANDBOX','toughness':'NO_MUTATION_EXPLICIT_SANDBOX',
                      'break':'NO_PROCESSING_EXPLICIT_SANDBOX','resources':'NO_PROCESSING_EXPLICIT_SANDBOX'},
        'settlement':{'storage':'MODE0_RAW_REFERENCE','clamp':'ZERO_MAX_HP_REFERENCE',
            'hp_property':'hp','max_hp_property':'max_hp','life_state':'PRESERVE_EXPLICIT_REFERENCE',
            'death_callbacks':'NO_PROCESSING_EXPLICIT_SANDBOX','battle_end':'NO_PROCESSING_EXPLICIT_SANDBOX'}}
def wrapper(nodes,name='isolated_real_damage'):
    nodes=list(nodes);a=nodes[0].authority
    return AbilityIR(name,'ability',a,{'content_name':name,'tasks':TaskSequenceIR(name+'/seq','immediate_sequence',a,
        {'tasks':nodes+[TaskIR(name+'/finish','RPG.GameCore.SkillPerformFinish',a)]})})
def make_runtime(nodes,*,root=None,coefficient=2*SCALE,targets=('b',),coefficient_mask=4):
    nodes=list(nodes);authority=nodes[0].authority
    ids=['a',*dict.fromkeys(targets)]
    state=BehaviorBattleState(entities={e:{'alive':True} for e in ids},
        properties={e:{'hp':100*SCALE,'max_hp':100*SCALE,'reference_atk':10*SCALE} for e in ids},
        target_context={'owner':'a','caster':'a','original_caster':'a','ability_target':list(targets),
            'ability_targets':list(targets),'skill_targets':list(targets),'param_entity':'b',
            'parameters':{},'param_entity_stack':['b'],'dynamic_provider_parent':'supplied'},
        dynamic_values={'supplied':{str(n.payload['key']):coefficient for node in nodes for n in walk_nodes(node) if n.op=='lookup'}})
    aliases={n.payload['alias']:TargetSelectorIR('alias/'+n.payload['alias'],'explicit',authority,{'entities':list(targets)})
             for node in nodes for n in walk_nodes(node) if n.op=='RPG.GameCore.TargetAlias'}
    policies={SCHEDULER:probe_policy(),MODIFIER:modifier_policy(),POLICY_ID:reference_policy()}
    policies[POLICY_ID]['tasks']={n.stable_hash():task_binding(n,coefficient_mask=coefficient_mask) for n in nodes}
    return BehaviorRuntime(state,actions={'probe':root or wrapper(nodes)},aliases=aliases,policies=policies)

def reference_listener(runtime,callback,*,event_id='r18_sandbox_amount',stage='DAMAGE_AMOUNT_MODIFICATION',priority=0,identity='sandbox_listener',operation=None):
    """Caller-supplied active R17 instance/listener, explicitly synthetic authority.

    The damage task remains real decoded content. This is a sandbox listener
    fixture, not a recovered native listener or default empty effective set.
    """
    from hsr_battle_agent.battle_ir.behavior import Authority
    authority=Authority('SANDBOX_EXTENSION','r18-reference','EXPLICIT_R18_SANDBOX_LISTENER','',semantic_status='REFERENCE_MODEL')
    spec={'pending_callbacks':'RETAIN_ENQUEUED_REFERENCE','retained_read_policy':'LIVE_THEN_DISPATCH_SNAPSHOT_REFERENCE'}
    registration={'event_id':event_id,'registration_id':identity+'/registration','order':priority,
        'context_policy':'OWNER_CASTER_TARGET_EVENT_EXPLICIT_REFERENCE','condition':None,
        'callback':callback.to_dict(),'authority':['LISTENER_REFERENCE_CONFIGURED','NATIVE_EFFECTIVE_LISTENER_UNKNOWN']}
    runtime.state.modifiers[identity]=ModifierInstance(identity,'EXPLICIT_SANDBOX_CALLBACK','b','a','a',1,1,
        {'units':'EXPLICIT_REFERENCE_UNITS','remaining':100,'expiry':'MANUAL_REFERENCE'},
        event_registrations=[registration],authority=authority.to_dict(),target='b',
        activation_state='REFERENCE_INSTANCE_ACTIVE',provider_binding={
            'application_context':copy.deepcopy(runtime.state.target_context),'source_provider':'supplied',
            'precedence':['SOURCE_PROVIDER'],'definition_policy':spec})
    for binding in runtime.policies[POLICY_ID]['tasks'].values():
        if event_id not in binding['events'][stage]:binding['events'][stage].append(event_id)
    if operation is not None:
        runtime.policies[POLICY_ID]['amount_callbacks'][callback.stable_hash()]={
            'authority':'REFERENCE_MODEL','operation':operation,'aggregation':'SERIALIZED_R17_LISTENER_ORDER_REFERENCE'}
