"""Additive, recorded R19 policies on the unchanged R18 joined fixture."""
from __future__ import annotations
import copy
from hsr_battle_agent.battle_ir.behavior import walk_nodes
from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE
from hsr_battle_agent.battle_runtime.dynamic_property import POLICY_ID, reference_policy, AGGREGATION

def provider_binding(source, **kwargs):
    return {'authority':'REFERENCE_MODEL','evidence':'R19 explicit caller input; native provider precedence UNKNOWN',
            'providers':[{'source':source,'on_missing':'GAP_REFERENCE',**kwargs}]}

def finish_binding():
    return {'mode':'ASSERT_OWNED_DAMAGE_DRAINED_REFERENCE','authority':'REFERENCE_MODEL',
            'evidence':'R18 bounded local assertion retained; native finish event/controller/death effects UNKNOWN',
            'scope':'CURRENT_ABILITY_AND_DESCENDANTS_REFERENCE','completion':'NO_ABILITY_OR_ACTION_REQUEST'}

def extend(state, policies, nodes, *, expressions=True, ranks=False):
    state=state.clone();policies=copy.deepcopy(policies)
    for n in nodes:
        if n.op=='RPG.GameCore.DamagePerformFinish':policies[DAMAGE]['finish_tasks'][n.stable_hash()]=finish_binding()
    if expressions or ranks:
        p=reference_policy();policies[POLICY_ID]=p
        # The operand already exists in R18. Bind it explicitly; do not replace programs or inject values.
        for n in nodes:
            if n.op=='unknown_opcode':
                for key in n.payload.get('decoded',{}).get('int32_operands',[]):
                    p['lookup_bindings']['supplied/'+str(key)]=provider_binding('ABILITY_DYNAMIC_VALUE',scope='supplied')
        if ranks:
            for n in nodes:
                if n.op=='RPG.GameCore.ByRankActivated':
                    p['rank_bindings'][n.stable_hash()]={'authority':'REFERENCE_MODEL',
                        'evidence':'4.6.51 metadata TriggerKey; threshold comparison is caller reference ONLY',
                        'mode':'KEYED_THRESHOLD_GE_REFERENCE','key_field':'unbound_bit_0','actor_context':'caster'}
            # Separate cohort: progression values are explicitly added and serialized here.
            actor=state.target_context['caster'];row=state.progression.setdefault(actor,{})
            row['rank']=0
            row['rank_requirements']={str(n.payload['fields']['unbound_bit_0']):1 for n in nodes
                                      if n.op=='RPG.GameCore.ByRankActivated' and 'unbound_bit_0' in n.payload['fields']}
    return state,policies

def effective_binding(state, entity):
    return provider_binding('EFFECTIVE_PROPERTY',entity=entity)|{'aggregation':AGGREGATION,
        'listener_scope':'EXPLICIT_ACTIVE_REFERENCE_INSTANCES_ONLY','modifier_order':sorted(state.modifiers)}
