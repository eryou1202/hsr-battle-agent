"""Opt-in R24 reference defense transactions on R15/R17 and BehaviorBattleState.

All amounts are R12 raw integers. No native elemental IDs, defense task aliases,
break formula, timing or shield precedence are inferred from decoded damage IR.
The mechanics entry is part of the existing snapshot, not an external registry.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, asdict
from hsr_battle_agent.battle_ir.behavior import Authority, IRNode, TaskIR, stable_hash, encode
from .behavior import GapError
from .behavior_primitives import raw_checked, fixed_binary, NumericSemanticGap

POLICY_ID = 'r24_defense_break_reference_v1'
EVENTS = ('BEFORE_SHIELD_ABSORPTION', 'AFTER_SHIELD_ABSORPTION', 'SHIELD_DEPLETED',
          'SHIELD_REMOVED', 'BEFORE_TOUGHNESS_CHANGE', 'AFTER_TOUGHNESS_CHANGE',
          'BREAK_TRIGGERED', 'BREAK_EFFECT_EXECUTION', 'BREAK_RECOVERY')
ENTRY_OPS = ('reference_defense_request', 'reference_defense_boundary',
             'reference_shield_lifecycle', 'reference_break_recovery')
OPS = ENTRY_OPS + ('reference_defense_stage', 'reference_defense_commit')
KNOWN = ('KNOWN_ZERO', 'KNOWN_NONZERO', 'EXPLICIT_REFERENCE_VALUE')


@dataclass(frozen=True)
class ToughnessRequest:
    source: object
    source_ability: object
    source_task: str
    actor: str
    target: str
    attack_element: str | None
    base_reduction: dict
    reduction_modifiers: list
    authority: str


@dataclass(frozen=True)
class ToughnessEvaluation:
    reduction_raw: int
    weakness_match: bool
    weakness_authority: str
    break_eligible: bool


@dataclass(frozen=True)
class ToughnessSettlement:
    before_raw: int
    after_raw: int
    applied_delta_raw: int
    reached_zero: bool
    break_triggered_reference: bool
    break_generation: int
    authority: str = 'REFERENCE_MODEL'


def reference_authority(node):
    return Authority('SANDBOX_EXTENSION', node.authority.source_version,
        'EXPLICIT_R24_REFERENCE_DEFENSE', '', semantic_status='REFERENCE_MODEL', ledger_refs=(POLICY_ID,))


def fail(node, kind, detail):
    raise GapError(node, kind + ': ' + str(detail))


def supplied(value, evidence='explicit R24 scenario input'):
    return {'status': 'EXPLICIT_REFERENCE_VALUE', 'value': copy.deepcopy(value),
            'authority': 'EXPLICIT_SCENARIO_INPUT', 'evidence': evidence}


def reference_value(value, evidence):
    return {'status': 'EXPLICIT_REFERENCE_VALUE', 'value': copy.deepcopy(value),
            'authority': 'REFERENCE_MODEL', 'evidence': evidence, 'policy_id': POLICY_ID}


def unknown(status='UNKNOWN_NATIVE_VALUE'):
    if status not in ('MISSING', 'UNKNOWN_NATIVE_VALUE'):
        raise ValueError('unknown state tag')
    return {'status': status, 'authority': 'EFFECTIVE_RUNTIME_UNKNOWN'}


def value(node, entry, kind):
    if not isinstance(entry, dict) or entry.get('status') not in KNOWN or 'value' not in entry:
        fail(node, kind, 'known value required; unknown is not zero/absence')
    if entry.get('authority') not in ('EXPLICIT_SCENARIO_INPUT', 'REFERENCE_MODEL', 'SOURCE_BACKED'):
        fail(node, kind, 'value provenance required')
    if entry['status'] == 'KNOWN_ZERO' and entry['value'] != 0:
        fail(node, kind, 'KNOWN_ZERO mismatch')
    if entry['status'] == 'KNOWN_NONZERO' and entry['value'] == 0:
        fail(node, kind, 'KNOWN_NONZERO mismatch')
    if entry['authority'] == 'SOURCE_BACKED':
        evidence = entry.get('evidence')
        if not isinstance(evidence, dict) or not all(k in evidence for k in
                ('source_version', 'body_sha256', 'source_span', 'operand_role', 'uncertainty')):
            fail(node, kind, 'source-backed observation requires exact evidence')
        # R24 has no proven source defense operand binder. Evidence presence alone
        # cannot promote an observation to executable native semantics.
        fail(node, 'DEFENSE_SOURCE_OPERAND_NOT_BOUND', 'use a separate explicit reference value')
    return entry['value']


def number(node, raw, kind='DEFENSE_NUMERIC_GAP'):
    n = raw_checked(raw)
    if n < 0:
        fail(node, kind, 'nonnegative raw reference integer')
    return n


def reference_policy():
    """Caller-selected reference rules; nothing in this policy is native authority."""
    return {'identity': POLICY_ID, 'authority': 'REFERENCE_MODEL', 'native_semantics': 'UNKNOWN',
            'shield_order': 'PRIORITY_THEN_INPUT_ORDER_REFERENCE',
            'precedence': 'CONSUME_ALL_REFERENCE', 'overflow': 'HP_REMAINDER_REFERENCE',
            'zero_capacity': 'REMOVE_REFERENCE', 'negative': 'REJECT_REFERENCE',
            'overcap': 'REJECT_REFERENCE', 'weakness': 'EXACT_STRING_SET_REFERENCE',
            'mismatch': 'NO_REDUCTION_REFERENCE', 'trigger': 'POSITIVE_TO_ZERO_ONCE_REFERENCE',
            'shield_selection': 'SNAPSHOT_IDS_BEFORE_CALLBACKS_LIVE_CAPACITY_REFERENCE',
            'recovery_repeat': 'RESET_EXPLICIT_INITIAL_COUNT_REFERENCE',
            'events': {key: [] for key in EVENTS}, 'damage_hooks': {}}


def policy(engine, node):
    p = engine.policies.get(POLICY_ID)
    expected = reference_policy()
    if not isinstance(p, dict) or any(p.get(k) != expected[k] for k in
            ('identity', 'authority', 'shield_order', 'negative', 'overcap', 'weakness', 'mismatch', 'trigger',
             'shield_selection', 'recovery_repeat')):
        fail(node, 'DEFENSE_POLICY_MISSING', 'explicit versioned reference rules')
    if p.get('precedence') not in ('CONSUME_ALL_REFERENCE', 'FIRST_APPLICABLE_REFERENCE') or \
            p.get('overflow') not in ('HP_REMAINDER_REFERENCE', 'DISCARD_REFERENCE') or \
            p.get('zero_capacity') not in ('REMOVE_REFERENCE', 'RETAIN_INACTIVE_REFERENCE'):
        fail(node, 'DEFENSE_POLICY_MISSING', 'shield precedence/overflow/removal')
    events = p.get('events')
    if not isinstance(events, dict) or set(events) != set(EVENTS) or any(
            not isinstance(ids, list) or any(type(i) is not str for i in ids) for ids in events.values()):
        fail(node, 'DEFENSE_EVENT_POLICY_MISSING', 'explicit reference event keys for each stage')
    store = engine.state.mechanics.get(POLICY_ID)
    if store is None or store['policy'] != p:
        fail(node, 'DEFENSE_POLICY_MISSING', 'state-bound policy snapshot mismatch')
    if not engine.state.scheduler.action_execution:
        fail(node, 'DEFENSE_OWNERSHIP_MISSING', 'R15 ActionExecutionRoot')
    return p, store


def _shield(node, state, target, instance):
    item = copy.deepcopy(instance)
    for key in ('instance_id', 'owner', 'caster', 'source', 'priority', 'capacity', 'elements', 'expiry'):
        if key not in item:
            fail(node, 'SHIELD_INSTANCE_INPUT_MISSING', key)
    if not isinstance(item['instance_id'], str) or not item['instance_id'] or item['owner'] != target or \
            item['caster'] not in state.entities or type(item['priority']) is not int or not item['source']:
        fail(node, 'SHIELD_INSTANCE_INPUT_MISSING', 'identity/owner/caster/source/priority')
    capacity = item['capacity']
    if capacity.get('status') in KNOWN:
        amount = number(node, value(node, capacity, 'SHIELD_CAPACITY_UNKNOWN'))
        item['status'] = 'SHIELD_INSTANCE_ACTIVE' if amount else 'SHIELD_INSTANCE_CONSTRUCTED'
    elif capacity.get('status') in ('MISSING', 'UNKNOWN_NATIVE_VALUE') and 'value' not in capacity:
        item['status'] = 'SHIELD_INSTANCE_CONSTRUCTED'
    else:
        fail(node, 'SHIELD_CAPACITY_UNKNOWN', 'typed capacity')
    if item['elements'] is not None and (not isinstance(item['elements'], list) or
            any(type(e) is not str for e in item['elements'])):
        fail(node, 'WEAKNESS_MAPPING_UNKNOWN', 'explicit shield element strings or all-elements null')
    expiry = item['expiry']
    if expiry != 'MANUAL_REFERENCE':
        _timing(node, expiry)
    mid = item.get('modifier_instance_id')
    if mid is not None:
        m = state.modifiers.get(mid)
        if m is None or m.owner != target or m.caster != item['caster'] or m.activation_state != 'REFERENCE_INSTANCE_ACTIVE':
            fail(node, 'SHIELD_MODIFIER_BINDING_MISSING', 'existing active R17 instance only')
    return item


def _timing(node, spec):
    if not isinstance(spec, dict) or spec.get('boundary') not in ('TURN_START', 'TURN_END', 'EXPLICIT_CALLBACK') or \
            type(spec.get('remaining')) is not int or spec['remaining'] < 1 or \
            spec.get('authority') != 'EXPLICIT_SCENARIO_INPUT':
        fail(node, 'DEFENSE_BOUNDARY_POLICY_MISSING', 'explicit boundary and positive count')


def initialize(state, node, entity, inputs, p):
    """Mutates a caller-owned candidate state; public binding below is atomic."""
    if entity not in state.entities or not isinstance(inputs, dict):
        fail(node, 'DEFENSE_INITIALIZATION_GAP', 'exact existing entity')
    if set(inputs) - {'current','maximum','weaknesses','eligible','break_state','shields','recovery','temporary_weaknesses'}:
        fail(node, 'DEFENSE_INITIALIZATION_GAP', 'unknown defensive field')
    if p.get('identity') != POLICY_ID or p.get('authority') != 'REFERENCE_MODEL':
        fail(node, 'DEFENSE_POLICY_MISSING', 'reference initialization policy')
    store = state.mechanics.setdefault(POLICY_ID, {'policy': copy.deepcopy(p), 'actors': {},
        'requests': {}, 'history': [], 'next_id': 0})
    if store['policy'] != p or entity in store['actors']:
        fail(node, 'DEFENSE_INITIALIZATION_GAP', 'policy mismatch or actor already initialized')
    actor = {k: copy.deepcopy(inputs.get(k, unknown('MISSING'))) for k in
             ('current', 'maximum', 'weaknesses', 'eligible', 'break_state', 'shields')}
    actor['identity'] = {'entity_id': entity, 'content_version': state.entities[entity].get('content_version'),
                         'content_identity': state.entities[entity].get('content_identity')}
    actor['recovery'] = copy.deepcopy(inputs.get('recovery'))
    actor['temporary_weaknesses'] = copy.deepcopy(inputs.get('temporary_weaknesses', []))
    for key, entry in actor.items():
        if key not in ('current', 'maximum', 'weaknesses', 'eligible', 'break_state', 'shields'):
            continue
        if not isinstance(entry, dict) or entry.get('status') not in (*KNOWN, 'MISSING', 'UNKNOWN_NATIVE_VALUE'):
            fail(node, 'DEFENSE_INITIALIZATION_GAP', key)
        if entry['status'] not in KNOWN:
            if 'value' in entry:
                fail(node, 'DEFENSE_INITIALIZATION_GAP', 'unknown carries value')
            continue
        v = value(node, entry, 'DEFENSE_INITIALIZATION_GAP')
        if key in ('current', 'maximum'):
            number(node, v)
        if key == 'weaknesses' and (not isinstance(v, list) or any(type(e) is not str for e in v)):
            fail(node, 'WEAKNESS_MAPPING_UNKNOWN', 'explicit string set')
        if key == 'eligible' and type(v) is not bool:
            fail(node, 'BREAK_ELIGIBILITY_UNKNOWN', 'explicit boolean')
        if key == 'break_state' and (not isinstance(v, dict) or type(v.get('active')) is not bool or
                type(v.get('generation')) is not int or v['generation'] < 0):
            fail(node, 'BREAK_STATE_UNKNOWN', 'explicit active state and generation')
        if key == 'shields':
            if not isinstance(v, list):
                fail(node, 'SHIELD_STATE_UNKNOWN', 'explicit instance list')
            entry['value'] = [_shield(node, state, entity, s) for s in v]
            ids = [s['instance_id'] for s in entry['value']]
            if len(ids) != len(set(ids)):
                fail(node, 'SHIELD_INSTANCE_INPUT_MISSING', 'duplicate shield identity')
    if actor['current']['status'] in KNOWN and actor['maximum']['status'] in KNOWN and \
            actor['current']['value'] > actor['maximum']['value']:
        fail(node, 'TOUGHNESS_STATE_INVALID', 'current exceeds maximum')
    for change in actor['temporary_weaknesses']:
        if change.get('operation') not in ('ADD_REFERENCE', 'REMOVE_REFERENCE') or \
                type(change.get('element')) is not str or not change.get('evidence'):
            fail(node, 'WEAKNESS_MAPPING_UNKNOWN', 'explicit temporary weakness authority')
    if actor['recovery'] is not None:
        _timing(node, actor['recovery'])
        number(node, actor['recovery']['restore_raw'])
        actor['recovery']['repeat_count'] = actor['recovery']['remaining']
    if actor['break_state']['status'] in KNOWN and actor['current']['status'] in KNOWN and \
            actor['break_state']['value']['active'] and actor['current']['value'] != 0:
        fail(node, 'TOUGHNESS_STATE_INVALID', 'active break requires zero current toughness under this policy')
    store['actors'][entity] = actor


def bind(engine, entity, inputs, node):
    candidate = engine.state.clone()
    try:
        initialize(candidate, node, entity, inputs, engine.policies[POLICY_ID])
    except (KeyError, TypeError, ValueError, NumericSemanticGap) as exc:
        fail(node, 'DEFENSE_INITIALIZATION_GAP', str(exc))
    engine.state = candidate


def _event(node, p, record, stage, **extra):
    record['stages'].append(stage)
    return [TaskIR(node.node_id + '/event/' + str(len(record['stages'])) + '/' + str(i),
        'modifier_event_dispatch', reference_authority(node),
        {'event_id': key, 'source': record['actor'], 'target': record['target'],
         'payload': {'defense_request_id': record['id'], 'defense_stage': stage,
                     'authority': 'REFERENCE_MODEL', **extra}, 'drain_before_resume_reference': True})
        for i, key in enumerate(p['events'][stage])]


def _step(node, rid, stage, **extra):
    return TaskIR(node.node_id + '/' + stage, 'reference_defense_stage', reference_authority(node),
                  {'request_id': rid, 'stage': stage, **extra})


def _remove(engine, node, store, actor, shield, reason):
    mid = shield.get('modifier_instance_id')
    if mid is not None:
        from .modifier_lifecycle import remove_instance
        m = engine.state.modifiers.get(mid)
        if m is not None:
            remove_instance(engine, node, m, reason, 'RETAIN_ENQUEUED_REFERENCE')
    shield['status'] = 'SHIELD_INSTANCE_REMOVED'
    store['history'].append({'domain': 'SHIELD_REMOVAL', 'instance': copy.deepcopy(shield),
                              'reason': reason, 'authority': 'REFERENCE_MODEL'})
    actor['shields']['value'].remove(shield)


def _begin(engine, node, frame):
    p, store = policy(engine, node)
    spec = encode(node.payload)
    if 'damage_request_id' in spec:
        from .damage_pipeline import normalize_amount
        original = engine.state.damage_requests[spec['damage_request_id']]
        spec['amount_raw'] = normalize_amount(node, original['amount_raw'], original['request']['payload']['spec'])
        if spec.get('hp_settlement') is not None:
            fail(node, 'DEFENSE_DOUBLE_HP_MUTATION', 'R18 owns HP settlement')
    if spec.get('authority') not in ('EXPLICIT_SCENARIO_INPUT', 'REFERENCE_MODEL'):
        fail(node, 'DEFENSE_REQUEST_AUTHORITY_MISSING', 'scenario/reference request, never decoded defense')
    if spec['actor'] not in engine.state.entities or spec['target'] not in store['actors'] or not spec.get('source'):
        fail(node, 'DEFENSE_REQUEST_INPUT_MISSING', 'actor/target/source')
    store['next_id'] += 1
    rid = 'defense:' + str(store['next_id'])
    record = {'id': rid, 'actor': spec['actor'], 'target': spec['target'], 'spec': spec,
        'source_ability': engine.state.target_context.get('current_ability'),
        'ownership': {'action_root_id': engine.state.scheduler.action_execution['current_root'],
                      'ability_instance_id': frame['ability_instance_id'], 'task_frame_id': frame['frame_id']},
        'status': 'PENDING', 'stages': [], 'authority': 'REFERENCE_MODEL', 'policy_hash': stable_hash(p)}
    store['requests'][rid] = record
    engine.state.damage_transactions[-1]['source_task_id'] = frame['frame_id']
    nodes = [_step(node, rid, stage) for stage in ('SHIELD', 'TOUGHNESS', 'COMPLETE')]
    nodes.append(TaskIR(node.node_id + '/commit', 'reference_defense_commit', node.authority, {'request_id': rid}))
    return nodes


def _shield_stage(engine, node, p, store, r, actor):
    spec = r['spec']
    amount = number(node, spec['amount_raw'])
    r.update(incoming_raw=amount, hp_remainder_raw=amount, absorbed_raw=0, shield_changes=[])
    if spec.get('shield') == 'SKIP_EXPLICIT_REFERENCE':
        return []
    if spec.get('shield') != 'APPLY_REFERENCE':
        fail(node, 'SHIELD_POLICY_MISSING', 'explicit apply/skip choice')
    shields = value(node, actor['shields'], 'SHIELD_STATE_UNKNOWN')
    applicable = []
    for ordinal, s in enumerate(shields):
        if s['elements'] is not None and type(spec.get('element')) is not str:
            fail(node, 'WEAKNESS_MAPPING_UNKNOWN', 'element needed for shield applicability')
        if s['elements'] is None or spec['element'] in s['elements']:
            capacity = number(node, value(node, s['capacity'], 'SHIELD_CAPACITY_UNKNOWN'))
            if capacity > 0:
                applicable.append((s['priority'], ordinal, s))
    # BEFORE callbacks drain before mutation; the next phase re-reads live state.
    r['shield_order'] = [s['instance_id'] for _, _, s in sorted(applicable)]
    return _event(node, p, r, 'BEFORE_SHIELD_ABSORPTION') + [_step(node, r['id'], 'ABSORB')]


def _absorb(engine, node, p, store, r, actor):
    shields = value(node, actor['shields'], 'SHIELD_STATE_UNKNOWN')
    depleted = []
    for identity in r['shield_order']:
        s = next((s for s in shields if s['instance_id'] == identity), None)
        if s is None:
            continue  # a completed same-action BEFORE callback explicitly removed it
        before = number(node, value(node, s['capacity'], 'SHIELD_CAPACITY_UNKNOWN'))
        take = min(before, r['hp_remainder_raw'])
        s['capacity'] = reference_value(before - take, 'reference shield consumption')
        r['absorbed_raw'] = fixed_binary('add', r['absorbed_raw'], take)
        r['hp_remainder_raw'] -= take
        r['shield_changes'].append({'instance_id': identity, 'before_raw': before,
                                    'absorbed_raw': take, 'after_raw': before - take})
        if before - take == 0:
            depleted.append(identity)
            if p['zero_capacity'] == 'RETAIN_INACTIVE_REFERENCE':
                s['status'] = 'SHIELD_INSTANCE_CONSTRUCTED'
        if p['precedence'] == 'FIRST_APPLICABLE_REFERENCE' or r['hp_remainder_raw'] == 0:
            break
    if p['overflow'] == 'DISCARD_REFERENCE' and r['shield_order']:
        r['discarded_raw'] = r['hp_remainder_raw']
        r['hp_remainder_raw'] = 0
    nodes = _event(node, p, r, 'AFTER_SHIELD_ABSORPTION')
    for identity in depleted:
        nodes += _event(node, p, r, 'SHIELD_DEPLETED', shield_instance_id=identity)
        if p['zero_capacity'] == 'REMOVE_REFERENCE':
            nodes.append(_step(node, r['id'], 'REMOVE_DEPLETED', shield_instance_id=identity))
    return nodes


def _toughness(node, p, r, actor):
    req = r['spec'].get('toughness')
    if req is None:
        return []
    if req.get('authority') not in ('EXPLICIT_SCENARIO_INPUT', 'REFERENCE_MODEL') or not req.get('source'):
        fail(node, 'TOUGHNESS_OPERAND_UNKNOWN', 'separately authored reduction provenance')
    current = number(node, value(node, actor['current'], 'TOUGHNESS_CURRENT_UNKNOWN'))
    maximum = number(node, value(node, actor['maximum'], 'TOUGHNESS_MAXIMUM_UNKNOWN'))
    if current > maximum:
        fail(node, 'TOUGHNESS_STATE_INVALID', 'current exceeds maximum')
    reduction = number(node, value(node, req['base_reduction'], 'TOUGHNESS_OPERAND_UNKNOWN'))
    for modifier in req['modifiers']:
        reduction = fixed_binary('mul', reduction, number(node, value(node, modifier, 'TOUGHNESS_MODIFIER_UNKNOWN')))
    if req.get('ignore_weakness') is True:
        match, authority = True, 'EXPLICIT_SCENARIO_INPUT_IGNORE_WEAKNESS'
    elif 'match_override' in req:
        match = value(node, req['match_override'], 'WEAKNESS_MATCH_UNKNOWN')
        authority = 'EXPLICIT_SCENARIO_INPUT_MATCH_OVERRIDE'
        if req['match_override'].get('authority') != 'EXPLICIT_SCENARIO_INPUT':
            fail(node, 'WEAKNESS_MATCH_UNKNOWN', 'override is scenario authority')
    else:
        if req.get('ignore_weakness') is not False or type(req.get('element')) is not str:
            fail(node, 'WEAKNESS_MAPPING_UNKNOWN', 'explicit string element and override choice')
        weaknesses = set(value(node, actor['weaknesses'], 'WEAKNESS_SET_UNKNOWN'))
        for change in actor['temporary_weaknesses']:
            if change['operation'] == 'ADD_REFERENCE': weaknesses.add(change['element'])
            else: weaknesses.discard(change['element'])
        match, authority = req['element'] in weaknesses, 'EXACT_STRING_SET_REFERENCE'
    if type(match) is not bool:
        fail(node, 'WEAKNESS_MATCH_UNKNOWN', 'explicit boolean result')
    eligible = value(node, actor['eligible'], 'BREAK_ELIGIBILITY_UNKNOWN')
    breaking = value(node, actor['break_state'], 'BREAK_STATE_UNKNOWN')
    r['toughness_request'] = asdict(ToughnessRequest(req['source'], r['source_ability'],
        r['ownership']['task_frame_id'], r['actor'], r['target'], req.get('element'),
        req['base_reduction'], req['modifiers'], req['authority']))
    delta = min(current, reduction) if match else 0
    after = current - delta
    actor['current'] = reference_value(after, 'reference toughness settlement')
    r['toughness_evaluation'] = {'request': copy.deepcopy(req), 'before_raw': current,
        'maximum_raw': maximum, 'reduction_raw': reduction, 'weakness_match': match,
        'weakness_authority': authority, 'applied_delta_raw': -delta, 'after_raw': after,
        'TOUGHNESS_REACHED_ZERO': current > 0 and after == 0, 'BREAK_ELIGIBLE': eligible,
        'BREAK_TRIGGERED_REFERENCE': False}
    triggered = current > 0 and after == 0 and eligible and not breaking['active']
    if triggered:
        breaking.update(active=True, generation=breaking['generation'] + 1,
                        instance_id=r['id'] + '/break', breaker=r['actor'], element=req.get('element'),
                        effect_status='BREAK_EFFECT_PENDING', recovery_status=(
                            'RECOVERY_PENDING_REFERENCE' if actor['recovery'] else 'BREAK_RECOVERY_POLICY_MISSING'))
        r['toughness_evaluation']['BREAK_TRIGGERED_REFERENCE'] = True
        actor['break_state'] = reference_value(breaking, 'reference zero-crossing break activation')
    r['toughness_evaluation']['typed_evaluation'] = asdict(ToughnessEvaluation(reduction, match, authority, eligible))
    r['toughness_settlement'] = asdict(ToughnessSettlement(current, after, -delta, current > 0 and after == 0,
                                                          triggered, breaking['generation']))
    return triggered


def _recover(engine, node, p, store, r, actor):
    recovery = actor.get('recovery')
    if recovery is None:
        fail(node, 'BREAK_RECOVERY_POLICY_MISSING', r['target'])
    breaking = value(node, actor['break_state'], 'BREAK_STATE_UNKNOWN')
    if not breaking['active']:
        return []
    maximum = number(node, value(node, actor['maximum'], 'TOUGHNESS_MAXIMUM_UNKNOWN'))
    restore = number(node, recovery['restore_raw'])
    if restore > maximum:
        fail(node, 'TOUGHNESS_STATE_INVALID', 'recovery overcap rejected')
    actor['current'] = reference_value(restore, 'explicit reference recovery')
    breaking.update(active=False, recovery_status='RECOVERED_REFERENCE')
    actor['break_state'] = reference_value(breaking, 'explicit reference break recovery')
    return _event(node, p, r, 'BREAK_RECOVERY', generation=breaking['generation'], restore_raw=restore)


def _boundary(engine, node, frame):
    p, store = policy(engine, node)
    # Reuse the same atomic request continuation for expiry/recovery callbacks.
    spec = encode(node.payload)
    spec.update(authority='REFERENCE_MODEL', amount_raw=0, shield='SKIP_EXPLICIT_REFERENCE', toughness=None)
    entry = TaskIR(node.node_id + '/request', 'reference_defense_request', node.authority, spec)
    nodes = _begin(engine, entry, frame)
    rid = nodes[0].payload['request_id']
    return [_step(node, rid, 'BOUNDARY')] + nodes[2:]


def _execute(engine, node, frame):
    p, store = policy(engine, node)
    if node.op == 'reference_defense_request':
        return _begin(engine, node, frame)
    if node.op in ('reference_defense_boundary', 'reference_shield_lifecycle', 'reference_break_recovery'):
        nodes = _boundary(engine, node, frame)
        store['requests'][nodes[0].payload['request_id']]['operation'] = node.op
        return nodes
    r = store['requests'][node.payload['request_id']]
    actor = store['actors'][r['target']]
    if node.op == 'reference_defense_commit':
        txn = engine.state.damage_transactions[-1]
        if r['status'] != 'COMPLETE' or txn['source_task_id'] != r['ownership']['task_frame_id']:
            fail(node, 'DEFENSE_TRANSACTION_UNKNOWN', 'owned request completion')
        engine.state.damage_transactions.pop()
        return []
    stage = node.payload['stage']
    if stage == 'SHIELD':
        return _shield_stage(engine, node, p, store, r, actor)
    if stage == 'ABSORB':
        return _absorb(engine, node, p, store, r, actor)
    if stage == 'REMOVE_DEPLETED':
        identity = node.payload['shield_instance_id']
        s = next((s for s in actor['shields']['value'] if s['instance_id'] == identity), None)
        if s is not None and value(node, s['capacity'], 'SHIELD_CAPACITY_UNKNOWN') == 0:
            _remove(engine, node, store, actor, s, 'SHIELD_DEPLETED_REFERENCE')
            return _event(node, p, r, 'SHIELD_REMOVED', shield_instance_id=identity)
        return []
    if stage == 'TOUGHNESS':
        if r['spec'].get('toughness') is None: return []
        return _event(node, p, r, 'BEFORE_TOUGHNESS_CHANGE') + [_step(node, r['id'], 'REDUCE')]
    if stage == 'REDUCE':
        triggered = _toughness(node, p, r, actor)
        nodes = _event(node, p, r, 'AFTER_TOUGHNESS_CHANGE')
        if triggered:
            nodes += _event(node, p, r, 'BREAK_TRIGGERED')
            nodes += [_step(node, r['id'], 'EFFECT')]
        return nodes
    if stage == 'EFFECT':
        breaking = value(node, actor['break_state'], 'BREAK_STATE_UNKNOWN')
        effect = r['spec'].get('effect')
        if effect is None:
            breaking['effect_status'] = 'BREAK_EFFECT_NOT_BOUND'
            return []
        if effect.get('authority') != 'EXPLICIT_SCENARIO_INPUT' or not effect.get('identity'):
            fail(node, 'BREAK_EFFECT_NOT_BOUND', 'fully specified caller-authored envelope')
        r['effect_envelope'] = copy.deepcopy(effect) | {'breaker': r['actor'], 'target': r['target'],
            'ownership': copy.deepcopy(r['ownership']), 'generation': breaking['generation']}
        breaking['effect_status'] = 'BREAK_EFFECT_EXECUTING_REFERENCE'
        return _event(node, p, r, 'BREAK_EFFECT_EXECUTION') + [
            n if isinstance(n, IRNode) else IRNode.from_dict(n) for n in effect['tasks']] + [
            _step(node, r['id'], 'EFFECT_COMPLETE')]
    if stage == 'EFFECT_COMPLETE':
        value(node, actor['break_state'], 'BREAK_STATE_UNKNOWN')['effect_status'] = 'BREAK_EFFECT_COMPLETE_REFERENCE'
        return []
    if stage == 'BOUNDARY':
        spec = r['spec']; op = r['operation']; nodes = []
        if op == 'reference_break_recovery':
            return _recover(engine, node, p, store, r, actor)
        shields = value(node, actor['shields'], 'SHIELD_STATE_UNKNOWN')
        if op == 'reference_shield_lifecycle':
            mode = spec['mode']; identity = spec['instance_id']
            old = next((s for s in shields if s['instance_id'] == identity), None)
            if mode in ('REMOVE_REFERENCE', 'REPLACE_REFERENCE'):
                if old is None: fail(node, 'SHIELD_INSTANCE_INPUT_MISSING', identity)
                _remove(engine, node, store, actor, old, mode)
                nodes += _event(node, p, r, 'SHIELD_REMOVED', shield_instance_id=identity)
            if mode == 'REFRESH_REFERENCE':
                if old is None: fail(node, 'SHIELD_INSTANCE_INPUT_MISSING', identity)
                new = _shield(node, engine.state, r['target'], spec['instance'])
                if any(new.get(k) != old.get(k) for k in ('instance_id', 'owner', 'caster', 'source', 'modifier_instance_id')):
                    fail(node, 'SHIELD_INSTANCE_INPUT_MISSING', 'refresh identity change')
                shields[shields.index(old)] = new
            elif mode in ('INSERT_REFERENCE', 'REPLACE_REFERENCE'):
                new = _shield(node, engine.state, r['target'], spec['instance'])
                if new['instance_id'] != identity or any(s['instance_id'] == identity for s in shields):
                    fail(node, 'SHIELD_INSTANCE_INPUT_MISSING', 'insert identity or duplicate')
                shields.append(new)
            elif mode != 'REMOVE_REFERENCE':
                fail(node, 'SHIELD_LIFECYCLE_POLICY_MISSING', mode)
            return nodes
        boundary = spec['boundary']
        for s in list(shields):
            expiry = s['expiry']
            if isinstance(expiry, dict) and expiry['boundary'] == boundary:
                expiry['remaining'] -= 1
                if expiry['remaining'] == 0:
                    _remove(engine, node, store, actor, s, 'SHIELD_EXPIRED_REFERENCE')
                    nodes += _event(node, p, r, 'SHIELD_REMOVED', shield_instance_id=s['instance_id'])
        breaking = value(node, actor['break_state'], 'BREAK_STATE_UNKNOWN')
        recovery = actor['recovery']
        if breaking['active'] and recovery and recovery['boundary'] == boundary:
            recovery['remaining'] -= 1
            if recovery['remaining'] == 0:
                nodes += _recover(engine, node, p, store, r, actor)
                recovery['remaining'] = recovery.get('repeat_count', 1)
        return nodes
    if stage == 'COMPLETE':
        if 'damage_request_id' in r['spec']:
            original = engine.state.damage_requests[r['spec']['damage_request_id']]
            original.update(hp_directed_amount_raw=r['hp_remainder_raw'], defense_request_id=r['id'],
                            defense_authority='SEPARATE_EXPLICIT_REFERENCE_INPUT_NOT_DECODED')
        if r['spec'].get('hp_settlement') is not None:
            from .damage_pipeline import settle_hp
            settle_hp(engine, node, r['target'], r['spec']['hp_settlement'], r['hp_remainder_raw'], r)
        r['status'] = 'COMPLETE'
        store['history'].append(copy.deepcopy(r))
        return []
    fail(node, 'DEFENSE_STAGE_UNKNOWN', stage)


def execute(engine, node, frame):
    try:
        return _execute(engine, node, frame)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, NumericSemanticGap) as exc:
        fail(node, 'DEFENSE_REFERENCE_INPUT_MISSING', str(exc))


def damage_hook_nodes(engine, node, request_id, spec):
    """Independent scenario authority, keyed by exact original damage task hash."""
    p, _ = policy(engine, node)
    hook = copy.deepcopy(p['damage_hooks'].get(spec['source_task_hash']))
    if hook is None or hook.get('authority') != 'EXPLICIT_SCENARIO_INPUT':
        fail(node, 'DEFENSE_DAMAGE_HOOK_MISSING', 'exact original task and separate scenario authority')
    request = engine.state.damage_requests[request_id]['request']['payload']
    hook.update(actor=request['attacker'], target=request['target'], damage_request_id=request_id,
                source={'original_damage_task_hash': spec['source_task_hash'],
                        'defense_operands': 'SEPARATE_EXPLICIT_REFERENCE_INPUT_NOT_DECODED'})
    # Amount is filled after R18 amount callbacks, without evaluating the formula again.
    hook['amount_raw'] = 0
    return TaskIR(node.node_id + '/defense', 'reference_defense_request', reference_authority(node), hook)


def turn_boundary_nodes(engine, node, actor, boundary):
    if POLICY_ID not in engine.policies or actor not in engine.state.mechanics.get(POLICY_ID, {}).get('actors', {}):
        return []
    return [TaskIR(node.node_id + '/defense', 'reference_defense_boundary', node.authority,
        {'actor': actor, 'target': actor, 'boundary': boundary,
         'source': {'reference_turn_boundary': node.payload}, 'authority': 'REFERENCE_MODEL'})]
