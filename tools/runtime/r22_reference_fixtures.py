"""Explicit R22 synthetic actor/action inputs. Not native initialization."""
from __future__ import annotations
import copy
from functools import lru_cache
from hsr_battle_agent.battle_ir.behavior import stable_hash
from hsr_battle_agent.battle_runtime.battle_turn import (reference_policy, implementation_bindings, KEY, _authority)
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.dynamic_property import AGGREGATION
from hsr_battle_agent.battle_runtime.modifier_lifecycle import POLICY_ID as MODIFIER, reference_policy as modifier_policy
from r20_reference_fixtures import actor_binding
from tests.battle_runtime.test_behavior_r15 import R15Tests, ability, finish, task, expr


@lru_cache(maxsize=20)
def _actor(actor, speed):
    return actor_binding(actor, 1001, base_properties={'speed': speed * SCALE, 'hp': 100 * SCALE,
        'max_hp': 100 * SCALE, 'x': 0}, actor_resources={'reference_actor_counter': 4 * SCALE}).to_dict()


def inputs(runtime, speeds=(('a', 100), ('b', 200)), *, controllers=None, durations=None, stage='RUNNING'):
    controllers = controllers or {}
    listener = {'mode': 'EXPLICIT_ACTIVE_R17_REFERENCE', 'source': 'R22 explicitly supplied listener state and reference keys',
                'registration_order': 'R17_PRIORITY_INSTANCE_REGISTRATION_REFERENCE'}
    p = reference_policy(boundary_listener_policy=listener)
    providers = {'authority': 'REFERENCE_MODEL', 'source': 'R22 explicit reference battle fixture',
        'policy_hash': stable_hash(p), 'operations': implementation_bindings(), 'speeds': {},
        'availability': {'provider_id': p['availability_provider_id'], 'version': '1', 'actors': {}},
        'stage': {'provider_id': p['terminal_provider_id'], 'stage_id': 'reference-stage', 'version': '1',
                  'status': stage, 'authority': 'EXPLICIT_SCENARIO_INPUT', 'reason': None},
        'boundary_listeners': listener, 'durations': durations or {},
        'duration_order': list(durations or {}),
        'readiness_sources': {'explicit': {'authority': 'REFERENCE_MODEL', 'basis': 'FULL_CURRENT_INTERVAL',
                                         'kinds': ['ADVANCE', 'DELAY'], 'source': 'caller reference adjustment'}},
        'external_events': {}}
    participants = []
    for ordinal, (actor, speed) in enumerate(speeds):
        speed_spec = {'provider_id': 'r22.explicit.speed.' + actor, 'version': '1', 'live_modifier_order': 'SORT_INSTANCE_ID_REFERENCE',
            'binding': {'authority': 'REFERENCE_MODEL', 'evidence': 'explicit effective R20 speed through R19',
                'providers': [{'source': 'EFFECTIVE_PROPERTY', 'entity': actor, 'on_missing': 'GAP_REFERENCE'}],
                'aggregation': AGGREGATION, 'listener_scope': 'EXPLICIT_ACTIVE_REFERENCE_INSTANCES_ONLY', 'modifier_order': []}}
        providers['speeds'][actor] = speed_spec
        categories = ['NORMAL_TURN', 'EXTRA_TURN', 'INSERTED_ACTION', 'FOLLOW_UP_ACTION', 'FORCED_ACTION']
        providers['availability']['actors'][actor] = {'enabled': True, 'content_version': '4.6.51',
            'actions': [{'action_id': name, 'ir_hash': ir.stable_hash(), 'target_ids': [actor], 'target_min': 1, 'target_max': 1,
                'categories': categories, 'cost': {'mode': 'EXPLICIT_NO_COST_REFERENCE', 'authority': 'EXPLICIT_SCENARIO_INPUT'}}
                for name, ir in sorted(runtime.actions.items())]}
        participants.append({'content_version': '4.6.51', 'actor_binding': copy.deepcopy(_actor(actor, speed)), 'provider_revision': 0,
            'participant': {'actor_id': actor, 'entity_ref': actor, 'generation': 0, 'registration_ordinal': ordinal,
                'controller': controllers.get(actor, 'PLAYER'), 'participation': 'ENABLED', 'entity_revision': 0,
                'summon_parent_actor': None, 'availability_provider_id': p['availability_provider_id'],
                'authority': _authority('explicit R22 actor binding', '4.6.51'),
                'speed_ref': {'base_property_key': 'speed', 'effective_provider_id': speed_spec['provider_id'],
                    'provider_policy_hash': stable_hash(speed_spec), 'authority': _authority('R19 effective speed binding', '4.6.51')}}})
    return participants, p, providers


def runtime(*, speeds=(('a', 100), ('b', 200)), root=None, initialize=True, **kwargs):
    r = R15Tests().runtime(root or ability('synthetic-explicitly-finished',
        task('resource-effect', 'resource_write', scope='actor', owner='a', key='reference_actor_counter',
             operation='add', value=expr(SCALE, True)), finish()))
    r.policies[MODIFIER] = modifier_policy()
    bindings, p, providers = inputs(r, speeds, **kwargs)
    if initialize:
        r.initialize_turns(bindings, p, providers)
    return r, bindings, p, providers


def source_ref(providers):
    return {'mapping_id': 'explicit', 'policy_hash': stable_hash(providers['readiness_sources']['explicit'])}


def insertion(r, actor='b', category='FOLLOW_UP_ACTION'):
    s = r.state.mechanics[KEY]
    top = s['active_stack'][-1] if s['active_stack'] else None
    rules = r.policies[s['policy_id']]['category_rules'][category]
    return {'insertion_id': 'insertion:' + str(s['next_insertion_id']), 'category': category,
        'owner_actor_id': top['turn_owner_actor_id'] if top else actor, 'action_actor_id': actor,
        'generation': next(x['generation'] for x in s['participants'] if x['actor_id'] == actor),
        'requested_at': copy.deepcopy(s['clock']['now']), 'enqueue_ordinal': s['next_enqueue_ordinal'],
        'priority': rules['priority'], 'placement': rules['placement'], 'due_at': None,
        'parent_turn_id': top['turn_id'] if top else None, 'parent_action_root_id': top['action_root_id'] if top else None,
        'action_permission_id': None, 'policy_id': s['policy_id'], 'policy_hash': s['policy_hash'],
        'cancellation': 'PENDING', 'cancellation_reason': None, 'safe_point_token': None,
        **{k: rules[k] for k in ['consumes_normal_av', 'counts_normal_turn', 'emits_turn_start', 'emits_turn_end']}}


def submit(r, boundary=None):
    b = boundary or r.run_until_decision()
    candidates = r.legal_action_candidates(b['decision_id'])
    return r.submit_action(candidates[0], candidates[0]['target_ids'], b['state_revision'])
