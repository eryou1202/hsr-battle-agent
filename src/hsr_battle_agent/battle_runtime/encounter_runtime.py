"""R25 authored reference encounters on R15/R17/R20/R22/R24 authority.

The coordinator records cursors and receipts, never a second entity/life/HP store
or writable stage result. Native stage content, event IDs and rules are unknown.
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path

from hsr_battle_agent.battle_ir.behavior import stable_hash
from . import battle_turn as turn
from .behavior import ExecutionStatus
from .behavior_primitives import raw_checked

KEY = 'reference_encounter_v1'
POLICY = 'r25_encounter_reference_v1'
EVENTS = ('ENCOUNTER_START', 'WAVE_START', 'ENTITY_DEFEATED', 'WAVE_CLEAR',
          'BEFORE_WAVE_TRANSITION', 'AFTER_WAVE_TRANSITION', 'ENCOUNTER_VICTORY',
          'ENCOUNTER_DEFEAT', 'ENCOUNTER_ABORTED')
CARRY = ('hp', 'actor_resources', 'team_sp', 'energy', 'modifiers', 'shield',
         'toughness_break', 'speed_av', 'progression', 'rng')
PREDICATES = ('ALL_TARGET_SIDE_DEFEATED_REFERENCE', 'ALL_PLAYER_SIDE_DEFEATED_REFERENCE',
              'SPECIFIC_ACTOR_DEFEATED_REFERENCE', 'SURVIVE_N_NORMAL_TURNS_REFERENCE',
              'EXPLICIT_OBJECTIVE_FLAG_REFERENCE', 'COMPOSITE_AND_REFERENCE', 'COMPOSITE_OR_REFERENCE')
TRANSITIONS = {
    'NOT_INITIALIZED': ('INITIALIZING',), 'INITIALIZING': ('WAVE_ACTIVE',),
    'WAVE_ACTIVE': ('OBJECTIVE_PENDING',),
    'OBJECTIVE_PENDING': ('WAVE_ACTIVE', 'WAVE_CLEAR_PENDING', 'TRANSITION_DRAINING'),
    'WAVE_CLEAR_PENDING': ('TRANSITION_DRAINING',),
    'TRANSITION_DRAINING': ('WAVE_READY', 'ENCOUNTER_VICTORY', 'ENCOUNTER_DEFEAT', 'ENCOUNTER_ABORTED'),
    'WAVE_READY': ('WAVE_INITIALIZING',), 'WAVE_INITIALIZING': ('WAVE_ACTIVE',),
    'ENCOUNTER_VICTORY': (), 'ENCOUNTER_DEFEAT': (), 'ENCOUNTER_ABORTED': ()}


def gap(code, detail):
    raise turn.TurnError('SEMANTIC_GAP', code + ': ' + str(detail))


def reference_policy():
    return {'identity': POLICY, 'version': '1', 'authority': 'REFERENCE_MODEL',
        'implementation_hash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'life_state': 'ZERO_HP_DEFEAT_AFTER_OWNED_DRAIN_REFERENCE',
        'safe_point': 'ALL_OWNED_ROOTS_AND_TRANSACTIONS_DRAINED_REFERENCE',
        'initiative': {'clock': 'PRESERVE_REFERENCE', 'player_due_at': 'PRESERVE_REFERENCE',
            'new_actor_due_at': 'R22_FULL_INTERVAL_AT_NOW_REFERENCE',
            'pending_insertions': 'DRAIN_BEFORE_TRANSITION_REFERENCE',
            'queued_actions': 'NO_ADMITTED_ACTION_AT_COMMIT_REFERENCE'},
        'retirement': 'REMOVE_PREVIOUS_WAVE_REFERENCE',
        'callbacks': {kind: 'reference.encounter.'+kind.lower() for kind in EVENTS},
        'carryover': {kind: {'mode': 'PRESERVE_REFERENCE'} for kind in CARRY}}


def _c(e):
    return e.state.mechanics[KEY]


def _policy(e):
    p = e.policies[POLICY]
    if p != reference_policy() or stable_hash(p) != _c(e)['policy_hash']:
        gap('ENCOUNTER_POLICY_MISMATCH', 'exact versioned implemented reference policy required')
    return p


def _definition(e):
    return _c(e)['definition']


def _wave(e):
    return _definition(e)['waves'][turn._s(e)['stage']['wave_index']]


def _pointer_leaves(value, path=''):
    if isinstance(value, dict) and value:
        for k, v in value.items():
            yield from _pointer_leaves(v, path+'/'+k.replace('~', '~0').replace('/', '~1'))
    elif isinstance(value, list) and value:
        for i, v in enumerate(value): yield from _pointer_leaves(v, path+'/'+str(i))
    else: yield path


@dataclass(frozen=True)
class EncounterDefinition:
    """Versioned JSON value; copies keep admitted contracts immutable to callers."""
    document: dict

    def to_dict(self): return copy.deepcopy(self.document)

    @classmethod
    def from_dict(cls, document):
        try:
            return cls._validated(document)
        except turn.TurnError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
            gap('ENCOUNTER_DEFINITION_INCOMPLETE', str(exc))

    @classmethod
    def _validated(cls, document):
        value = copy.deepcopy(document)
        required = {'schema', 'encounter_id', 'content_version', 'source_version', 'policy_hash',
            'sides', 'player_side', 'target_side', 'actors', 'initial_actor_refs', 'waves',
            'terminal_rules', 'limits', 'provenance'}
        if set(value) != required or value['schema'] != 'reference_encounter_definition/1':
            gap('ENCOUNTER_DEFINITION_INCOMPLETE', 'exact required fields')
        if any(value[k] in (None, '', 'UNKNOWN') for k in ('encounter_id', 'content_version', 'source_version')):
            gap('ENCOUNTER_DEFINITION_INCOMPLETE', 'identity/version unknown')
        if value['content_version'] != value['source_version']:
            gap('ENCOUNTER_VERSION_MISMATCH', 'cross-version encounter binding')
        if (not isinstance(value['sides'], list) or len(value['sides']) != len(set(value['sides'])) or
            value['player_side'] == value['target_side'] or
            not {value['player_side'], value['target_side']} <= set(value['sides'])):
            gap('ENCOUNTER_SIDE_MISSING', 'explicit distinct sides')
        if not isinstance(value['waves'], list) or not value['waves'] or not value['initial_actor_refs']:
            gap('ENCOUNTER_DEFINITION_INCOMPLETE', 'nonempty initial actors and ordered waves')
        actors = value['actors']
        if not isinstance(actors, dict) or not actors: gap('ENCOUNTER_ACTOR_MISSING', 'actor references')
        used = list(value['initial_actor_refs'])
        wave_ids = []
        for w in value['waves']:
            if set(w) != {'wave_id', 'actor_refs', 'objective', 'availability'} or not w['actor_refs'] or not w['wave_id']:
                gap('WAVE_DEFINITION_INCOMPLETE', 'identity/spawns/objective')
            if set(w['availability']) != set(value['initial_actor_refs'] + w['actor_refs']):
                gap('WAVE_AVAILABILITY_UNKNOWN', 'explicit active actor availability per wave')
            wave_ids.append(w['wave_id'])
            used.extend(w['actor_refs'])
            _validate_objective(w['objective'])
        if len(wave_ids) != len(set(wave_ids)) or len(used) != len(set(used)) or set(used) != set(actors):
            gap('ENCOUNTER_IDENTITY_COLLISION', 'actors and waves must be unique; reuse needs another policy')
        for actor, spec in actors.items():
            if (not actor or set(spec) != {'side', 'binding_hash'} or spec['side'] not in value['sides'] or
                    not isinstance(spec['binding_hash'], str) or len(spec['binding_hash']) != 64):
                gap('ENCOUNTER_ACTOR_MISSING', actor)
        if any(actors[a]['side'] != value['player_side'] for a in value['initial_actor_refs']):
            gap('ENCOUNTER_SIDE_MISMATCH', 'persistent actors must be player side in this profile')
        if any(actors[a]['side'] != value['target_side'] for w in value['waves'] for a in w['actor_refs']):
            gap('ENCOUNTER_SIDE_MISMATCH', 'wave actors must be target side in this profile')
        rules = value['terminal_rules']
        if (set(rules) != {'victory', 'defeat', 'abort', 'conflict'} or
            rules['victory'] != 'LAST_WAVE_OBJECTIVE_REFERENCE' or rules['conflict'] != 'SEMANTIC_GAP_REFERENCE'):
            gap('TERMINAL_RULE_UNKNOWN', 'explicit victory/defeat/abort/conflict rules')
        _validate_objective(rules['defeat']); _validate_objective(rules['abort'])
        limits = value['limits']
        if set(limits) != {'actor_registrations', 'wave_transitions', 'objective_evaluations',
                           'stage_callbacks', 'normal_turns', 'scheduler_steps', 'zero_time_transitions'}:
            gap('ENCOUNTER_LIMIT_UNKNOWN', 'all limit categories must be declared')
        for v in limits.values():
            if v is not None: turn.integer(v, 1)
        provenance = value['provenance']
        for path in _pointer_leaves({k: v for k, v in value.items() if k != 'provenance'}):
            entry = provenance.get(path)
            if (not isinstance(entry, dict) or entry.get('authority') != 'EXPLICIT_SCENARIO_INPUT' or
                    not entry.get('evidence') or entry.get('source_version') != value['source_version']):
                gap('ENCOUNTER_PROVENANCE_MISSING', path)
        return cls(value)


def _validate_objective(obj, depth=0):
    if depth > 32 or not isinstance(obj, dict) or obj.get('kind') not in PREDICATES:
        gap('OBJECTIVE_INPUT_UNSUPPORTED', 'bounded explicit objective required')
    kind = obj['kind']
    keys = {'ALL_TARGET_SIDE_DEFEATED_REFERENCE': {'kind'}, 'ALL_PLAYER_SIDE_DEFEATED_REFERENCE': {'kind'},
        'SPECIFIC_ACTOR_DEFEATED_REFERENCE': {'kind', 'actor_id'},
        'SURVIVE_N_NORMAL_TURNS_REFERENCE': {'kind', 'count', 'side'},
        'EXPLICIT_OBJECTIVE_FLAG_REFERENCE': {'kind', 'scope', 'key', 'expected'},
        'COMPOSITE_AND_REFERENCE': {'kind', 'children'}, 'COMPOSITE_OR_REFERENCE': {'kind', 'children'}}
    if set(obj) != keys[kind]: gap('OBJECTIVE_INPUT_UNSUPPORTED', kind)
    if kind.startswith('COMPOSITE_'):
        if not isinstance(obj['children'], list) or not obj['children']: gap('OBJECTIVE_INPUT_UNSUPPORTED', 'empty composite')
        for child in obj['children']: _validate_objective(child, depth+1)
    if kind == 'SURVIVE_N_NORMAL_TURNS_REFERENCE': turn.integer(obj['count'], 1)
    if kind == 'EXPLICIT_OBJECTIVE_FLAG_REFERENCE' and type(obj['expected']) is not bool:
        gap('OBJECTIVE_INPUT_UNSUPPORTED', 'boolean flag expected')
    for key in ('side', 'actor_id', 'scope', 'key'):
        if key in obj and (not isinstance(obj[key], str) or not obj[key]):
            gap('OBJECTIVE_INPUT_UNSUPPORTED', key)


def _alive(e, actor):
    from .actor_binding import POLICY_ID as ACTOR
    record = e.state.mechanics.get(ACTOR, {}).get('actors', {}).get(actor)
    if record is None: gap('LIFE_STATE_AUTHORITY_UNKNOWN', actor)
    b = record['binding']
    spec = b['overrides'].get('entity_state', b['fields'].get('entity_state', {}))
    if spec.get('status') != 'KNOWN' or type(spec.get('value', {}).get('alive')) is not bool:
        gap('LIFE_STATE_AUTHORITY_UNKNOWN', actor)
    alive = e.state.entities[actor].get('alive')
    if type(alive) is not bool: gap('LIFE_STATE_AUTHORITY_UNKNOWN', actor)
    return alive


def _side_actors(e, side):
    d = _definition(e)
    if side not in d['sides']: gap('OBJECTIVE_INPUT_UNSUPPORTED', 'unknown side')
    scope = d['initial_actor_refs'] + _wave(e)['actor_refs']
    return [a for a in scope if d['actors'][a]['side'] == side]


def _evaluate(e, obj):
    _validate_objective(obj)
    kind = obj['kind']
    if kind.startswith('COMPOSITE_'):
        children = [_evaluate(e, x) for x in obj['children']]  # UNKNOWN never short-circuits.
        result = (all if kind == 'COMPOSITE_AND_REFERENCE' else any)(x['satisfied'] for x in children)
        return {'kind': kind, 'satisfied': result, 'children': children}
    if kind == 'EXPLICIT_OBJECTIVE_FLAG_REFERENCE':
        store = e.state.dynamic_values.get(obj['scope'], {})
        if obj['key'] not in store or type(store[obj['key']]) is not bool:
            gap('OBJECTIVE_FLAG_UNKNOWN', obj['scope']+'/'+obj['key'])
        return {'kind': kind, 'satisfied': store[obj['key']] == obj['expected'], 'observed': store[obj['key']]}
    if kind == 'SPECIFIC_ACTOR_DEFEATED_REFERENCE':
        actors = [obj['actor_id']]
        if actors[0] not in _definition(e)['actors'] or actors[0] not in e.state.entities:
            gap('OBJECTIVE_ACTOR_UNKNOWN', actors[0])
    else:
        side = obj.get('side', _definition(e)['target_side'] if kind == 'ALL_TARGET_SIDE_DEFEATED_REFERENCE'
                       else _definition(e)['player_side'])
        actors = _side_actors(e, side)
    if not actors: gap('OBJECTIVE_SIDE_EMPTY', kind)
    evidence = [{'actor_id': a, 'alive': _alive(e, a), 'generation': turn._participant(e, a)['generation']}
                for a in actors]
    result = all(not x['alive'] for x in evidence)
    if kind == 'SURVIVE_N_NORMAL_TURNS_REFERENCE':
        result = (any(x['alive'] for x in evidence) and
                  turn._s(e)['normal_turn_count'] - _c(e)['wave_start_turn'] >= obj['count'])
    return {'kind': kind, 'satisfied': result, 'actors': evidence}


def evaluate_encounter_objectives(e):
    _policy(e)
    rules = _definition(e)['terminal_rules']
    return {'wave_index': turn._s(e)['stage']['wave_index'], 'wave': _evaluate(e, _wave(e)['objective']),
            'defeat': _evaluate(e, rules['defeat']), 'abort': _evaluate(e, rules['abort']),
            'authority': 'REFERENCE_MODEL'}


def _safe(e, *, allow_event=False, allow_insertions=False):
    s = turn._s(e)
    if s['active_stack'] or e.state.damage_transactions or e.state.pending_events:
        gap('ENCOUNTER_SAFE_POINT_BLOCKED', 'active turn/transaction/event')
    legacy = e.state.scheduler
    if legacy.continuation or legacy.callbacks: gap('ENCOUNTER_SAFE_POINT_BLOCKED', 'legacy work')
    execution = legacy.action_execution
    if execution and not allow_event:
        if any(r['status'] != 'ACTION_REFERENCE_COMPLETE' for r in execution['roots'].values()):
            gap('ENCOUNTER_SAFE_POINT_BLOCKED', 'R15 roots/children/callbacks not drained')
    if not allow_insertions and any(x['cancellation'] == 'PENDING' for x in s['pending_insertions']):
        gap('ENCOUNTER_SAFE_POINT_BLOCKED', 'mandatory insertions must drain')


def _move(e, prior, following, request):
    c = _c(e)
    if c['phase'] != prior or following not in TRANSITIONS.get(prior, ()):
        gap('ENCOUNTER_ILLEGAL_TRANSITION', prior+' -> '+following)
    receipt = {'sequence': len(c['transitions']), 'prior': prior, 'next': following,
        'request_id': request, 'policy_id': POLICY, 'policy_hash': c['policy_hash'],
        'provider_id': turn._p(e)['terminal_provider_id'], 'wave_index': turn._s(e)['stage']['wave_index'],
        'stage_generation': turn._s(e)['stage']['generation'],
        'actor_generations': {a['actor_id']: a['generation'] for a in turn._s(e)['participants']}}
    receipt['receipt_hash'] = stable_hash(receipt)
    c['transitions'].append(receipt)
    c['phase'] = following
    turn._touch(e)


def _stage_source(e):
    return {'provider_id': turn._p(e)['terminal_provider_id'], 'policy_hash': stable_hash(turn._providers(e)['stage']),
            'encounter_policy_hash': _c(e)['policy_hash'], 'encounter_sequence': len(_c(e)['transitions'])}


def authorize_stage(e, status, source):
    if source != _stage_source(e): gap('ENCOUNTER_STAGE_AUTHORITY_REQUIRED', status)
    _safe(e)
    c = _c(e)
    outcome = (c['pending_transition'] or {}).get('outcome')
    valid = ((status == 'WAVE_PENDING' and c['phase'] == 'WAVE_CLEAR_PENDING') or
        (status == 'RUNNING' and c['phase'] == 'WAVE_INITIALIZING' and outcome == 'NEXT_WAVE') or
        (status in ('VICTORY', 'DEFEAT', 'ABORTED') and c['phase'] == 'TRANSITION_DRAINING' and outcome == status))
    if not valid: gap('ENCOUNTER_STAGE_AUTHORITY_REQUIRED', 'objective/cursor does not authorize '+status)


def authorize_lifecycle(e):
    if _c(e)['phase'].startswith('ENCOUNTER_'):
        gap('ENCOUNTER_ALREADY_TERMINAL', 'actor lifecycle is sealed')


def _stage(e, status, reason):
    e.turn_stage_transition(status, source_ref=_stage_source(e), reason=reason)


def _event(e, kind, *, actor=None, generation=None):
    c = _c(e)
    identity = '/'.join((KEY, _definition(e)['encounter_id'], str(turn._s(e)['stage']['wave_index']),
                         kind, actor or '', str(generation) if generation is not None else ''))
    if any(x['event_id'] == identity for x in c['events']): return
    c['events'].append({'event_id': identity, 'kind': kind, 'wave_index': turn._s(e)['stage']['wave_index'],
        'stage_generation': turn._s(e)['stage']['generation'], 'actor_id': actor, 'actor_generation': generation,
        'event_key': _policy(e)['callbacks'][kind], 'status': 'QUEUED', 'root_id': None,
        'listener_ids': [], 'scheduler_summary': None, 'listener_policy_hash': _c(e)['policy_hash']})


def _binding(e, actor, inputs):
    b = copy.deepcopy(inputs[actor])
    if stable_hash(b) != _definition(e)['actors'][actor]['binding_hash']:
        gap('ENCOUNTER_BINDING_HASH_MISMATCH', actor)
    if (b['participant']['actor_id'] != actor or b['content_version'] != _definition(e)['content_version'] or
            b['participant']['participation'] != 'ENABLED' or b['participant']['generation'] != 0):
        gap('ENCOUNTER_SPAWN_CONTRACT_INVALID', actor)
    return b


def _validate_actor(e, actor):
    if not _alive(e, actor): gap('ENCOUNTER_INITIAL_LIFE_STATE_INVALID', actor)
    p = e.state.properties[actor]
    if not 0 < raw_checked(p['hp']) <= raw_checked(p['max_hp']): gap('ENCOUNTER_INITIAL_HP_INVALID', actor)
    if e.state.entities[actor].get('team') != _definition(e)['actors'][actor]['side']:
        gap('ENCOUNTER_SIDE_MISMATCH', actor)


def initialize_encounter(e, definition, actor_inputs, turn_policy, provider_contracts, policy):
    d = (definition if isinstance(definition, EncounterDefinition) else EncounterDefinition.from_dict(definition)).to_dict()
    EncounterDefinition.from_dict(d)
    def initialize(c):
        if KEY in c.state.mechanics or turn.KEY in c.state.mechanics:
            if KEY in c.state.mechanics and _c(c)['initialization_hash'] == stable_hash(args):
                return current_encounter(c)
            gap('ENCOUNTER_ALREADY_INITIALIZED', d['encounter_id'])
        if policy != reference_policy() or d['policy_hash'] != stable_hash(policy):
            gap('ENCOUNTER_POLICY_MISMATCH', 'explicit implemented policy required')
        if set(actor_inputs) != set(d['actors']): gap('ENCOUNTER_ACTOR_MISSING', 'exact actor input set')
        if provider_contracts['stage']['status'] != 'RUNNING' or provider_contracts['stage']['stage_id'] != d['encounter_id']:
            gap('ENCOUNTER_STAGE_MISMATCH', 'initial running encounter identity')
        c.policies[POLICY] = copy.deepcopy(policy)
        c.state.mechanics[KEY] = {'schema': 'reference_encounter_state/1', 'definition': d,
            'policy_hash': stable_hash(policy), 'initialization_hash': stable_hash(args),
            'actor_inputs': copy.deepcopy(actor_inputs), 'phase': 'NOT_INITIALIZED', 'transitions': [],
            'events': [], 'life_candidates': {}, 'life_receipts': [], 'evaluations': [],
            'evaluation_fingerprint': None, 'pending_transition': None, 'prepared': None,
            'terminal_receipt': None, 'wave_start_turn': 0,
            'counters': dict.fromkeys(d['limits'], 0)}
        refs = d['initial_actor_refs'] + d['waves'][0]['actor_refs']
        bindings = [_binding(c, a, actor_inputs) for a in refs]
        c.initialize_turns(bindings, turn_policy, provider_contracts)
        for a in refs: _validate_actor(c, a)
        if any(turn._providers(c)['availability']['actors'][a] != d['waves'][0]['availability'][a] for a in refs):
            gap('WAVE_AVAILABILITY_UNKNOWN', 'initial provider/definition disagreement')
        _c(c)['counters']['actor_registrations'] = len(refs)
        _move(c, 'NOT_INITIALIZED', 'INITIALIZING', 'initialize/'+d['encounter_id'])
        _event(c, 'ENCOUNTER_START'); _event(c, 'WAVE_START')
        return current_encounter(c)
    args = {'definition': d, 'actor_inputs': actor_inputs, 'turn_policy': turn_policy,
            'provider_contracts': provider_contracts, 'policy': policy}
    return turn._atomic(e, initialize)


def observe_hp(e, actor, before, after, node):
    """Called inside the existing R18/R24 transaction; rollback includes this cursor."""
    if KEY not in e.state.mechanics or actor not in _definition(e)['actors']: return
    _policy(e)
    try: participant = turn._participant(e, actor)
    except turn.TurnError: gap('ENCOUNTER_HP_ACTOR_UNREGISTERED', actor)
    key = actor+':'+str(participant['generation'])
    if after == 0 and key not in _c(e)['life_candidates']:
        _c(e)['life_candidates'][key] = {'candidate_id': key, 'actor_id': actor,
            'generation': participant['generation'], 'hp_before_raw': before, 'hp_after_raw': after,
            'source_task_id': node.node_id, 'source_task_hash': node.stable_hash(),
            'observation': 'HP_REACHED_ZERO', 'status': 'PENDING_OWNED_DRAIN'}


def _confirm_life(e):
    _safe(e, allow_insertions=True)
    c = _c(e)
    # Explicit zero-HP reference policy also covers initial/external committed observations.
    for row in turn._s(e)['participants']:
        actor = row['actor_id']
        key = actor+':'+str(row['generation'])
        if row['participation'] != 'REMOVED' and e.state.properties[actor]['hp'] == 0 and key not in c['life_candidates']:
            c['life_candidates'][key] = {'candidate_id': key, 'actor_id': actor, 'generation': row['generation'],
                'observation': 'HP_REACHED_ZERO', 'status': 'PENDING_OWNED_DRAIN',
                'hp_after_raw': 0, 'source': 'committed safe point observation'}
    pending = [x for x in c['life_candidates'].values() if x['status'] == 'PENDING_OWNED_DRAIN']
    for observed in pending:
        actor = observed['actor_id']
        row = turn._participant(e, actor)
        if row['generation'] != observed['generation'] or e.state.properties[actor]['hp'] != 0:
            observed['status'] = 'SUPERSEDED_REFERENCE'
            continue
        before = e.state.entities[actor].get('alive')
        e.turn_lifecycle(actor, 'DEFEAT', source_ref={'authority': 'EXPLICIT_SCENARIO_INPUT',
            'source': POLICY+'/zero_hp_after_owned_drain'})
        c = _c(e)
        c['life_candidates'][observed['candidate_id']]['status'] = 'DEFEAT_CONFIRMED_REFERENCE'
        receipt = {'candidate_id': observed['candidate_id'], 'actor_id': actor,
            'prior_alive': before, 'alive': False, 'generation': turn._participant(e, actor)['generation'],
            'events': ['ENTITY_LIFE_STATE_CHANGED', 'DEFEAT_CONFIRMED_REFERENCE', 'ACTOR_PARTICIPATION_REMOVED']}
        receipt['receipt_hash'] = stable_hash(receipt)
        c['life_receipts'].append(receipt)
        _event(e, 'ENTITY_DEFEATED', actor=actor, generation=observed['generation'])
    return bool(pending)


def _fingerprint(e):
    return stable_hash({'entities': e.state.entities, 'properties': e.state.properties,
        'flags': e.state.dynamic_values, 'turns': turn._s(e)['normal_turn_count'],
        'wave': turn._s(e)['stage']['wave_index']})


def _evaluate_and_plan(e):
    _safe(e)
    result = evaluate_encounter_objectives(e)
    hits = [k for k in ('wave', 'defeat', 'abort') if result[k]['satisfied']]
    if len(hits) > 1: gap('OBJECTIVE_RESULTS_CONFLICT', hits)
    prior = _c(e)['phase']
    _move(e, prior, 'OBJECTIVE_PENDING', 'evaluate/'+str(len(_c(e)['evaluations'])))
    _c(e)['evaluations'].append(copy.deepcopy(result))
    _c(e)['evaluation_fingerprint'] = _fingerprint(e)
    _c(e)['counters']['objective_evaluations'] += 1
    if not hits:
        _move(e, 'OBJECTIVE_PENDING', 'WAVE_ACTIVE', 'continue')
        return
    kind = hits[0]
    wave = turn._s(e)['stage']['wave_index']
    outcome = ('NEXT_WAVE' if wave+1 < len(_definition(e)['waves']) else 'VICTORY') if kind == 'wave' else kind.upper()
    if outcome == 'ABORT': outcome = 'ABORTED'
    _c(e)['pending_transition'] = {'outcome': outcome, 'objective_evidence': result,
        'request_id': 'settlement/'+str(wave)+'/'+str(len(_c(e)['evaluations']))}
    if kind == 'wave':
        _move(e, 'OBJECTIVE_PENDING', 'WAVE_CLEAR_PENDING', 'wave_objective_satisfied')
        _event(e, 'WAVE_CLEAR')
    else:
        _move(e, 'OBJECTIVE_PENDING', 'TRANSITION_DRAINING', 'terminal_objective_satisfied')
        _event(e, 'ENCOUNTER_'+outcome)


def _verify_pending(e):
    """Callbacks may change objective inputs; stale success cannot authorize commit."""
    evidence = evaluate_encounter_objectives(e)
    hits = [k for k in ('wave', 'defeat', 'abort') if evidence[k]['satisfied']]
    if len(hits) > 1: gap('OBJECTIVE_RESULTS_CONFLICT', hits)
    outcome = _c(e)['pending_transition']['outcome']
    expected = 'wave' if outcome in ('NEXT_WAVE', 'VICTORY') else ('abort' if outcome == 'ABORTED' else 'defeat')
    if hits != [expected]: gap('OBJECTIVE_EVIDENCE_STALE', 'owned callbacks changed the pending objective')
    return evidence


def next_wave_preview(e):
    _policy(e)
    index = turn._s(e)['stage']['wave_index'] + 1
    if index >= len(_definition(e)['waves']): return None
    return copy.deepcopy(_definition(e)['waves'][index])


def _prepare(e, actor_inputs=None):
    _safe(e)
    if _c(e)['phase'] != 'WAVE_READY': gap('ENCOUNTER_ILLEGAL_TRANSITION', 'prepare requires WAVE_READY')
    _verify_pending(e)
    index = turn._s(e)['stage']['wave_index'] + 1
    if index >= len(_definition(e)['waves']): gap('WAVE_IDENTITY_UNKNOWN', index)
    inputs = _c(e)['actor_inputs'] if actor_inputs is None else actor_inputs
    refs = _definition(e)['waves'][index]['actor_refs']
    bindings = [_binding(e, a, inputs) for a in refs]
    # Real R20 construction and R22 participant validation run on a throwaway clone.
    probe = e.clone()
    _register_wave(probe, bindings, index)
    receipt = {'request_id': _c(e)['pending_transition']['request_id'], 'wave_index': index,
        'stage_generation': turn._s(e)['stage']['generation'], 'bindings': bindings,
        'policy_hash': _c(e)['policy_hash'], 'prepare_context_hash': _prepare_context(e)}
    receipt['receipt_hash'] = stable_hash(receipt)
    return receipt


def prepare_next_wave(e, actor_inputs=None):
    return _prepare(e, actor_inputs)  # Read-only prepare; caller may review/retry corrected explicit inputs.


def _prepare_context(e):
    state = e.state.snapshot()
    state['mechanics'].pop(KEY)
    s = state['mechanics'].pop(turn.KEY)
    state['mechanics'].pop(turn.ADAPTER)
    return stable_hash({'state': state, 'policies': e.policies, 'actions': {k: v.stable_hash() for k, v in e.actions.items()},
        'initiative': s['initiative'], 'queue': s['normal_queue'], 'participants': s['participants'],
        'clock': s['clock']['now'], 'stage': s['stage']})


def _register_wave(e, bindings, index):
    from .actor_binding import ActorRuntimeBinding
    # Bind all entities before R22 validates cross-target availability.
    for b in bindings:
        if b['actor_binding'] is None: gap('WAVE_ACTOR_BINDING_MISSING', b['participant']['actor_id'])
        e.bind_actor(ActorRuntimeBinding.from_dict(b['actor_binding']))
    providers = copy.deepcopy(turn._providers(e))
    providers['availability']['actors'].update(copy.deepcopy(_definition(e)['waves'][index]['availability']))
    e.policies[turn.PROVIDERS] = providers
    turn._a(e)['provider_contracts_hash'] = stable_hash(providers)
    for b in bindings:
        actor = b['participant']['actor_id']
        e.turn_lifecycle(actor, 'REGISTER_ENTITY', source_ref={'authority': 'EXPLICIT_SCENARIO_INPUT',
            'source': POLICY+'/explicit_wave_spawn'}, binding=b)
        _validate_actor(e, actor)
    for actor in _definition(e)['initial_actor_refs']:
        turn._validate_availability(e, actor, _definition(e)['content_version'])


def _commit_wave(e):
    _safe(e)
    _verify_pending(e)
    prepared = _c(e)['prepared']
    index = turn._s(e)['stage']['wave_index']+1
    if (prepared is None or prepared['wave_index'] != index or
        prepared['stage_generation'] != turn._s(e)['stage']['generation']):
        gap('WAVE_PREPARE_STALE', index)
    unsigned = copy.deepcopy(prepared); seal = unsigned.pop('receipt_hash')
    if stable_hash(unsigned) != seal: gap('WAVE_PREPARE_STALE', 'receipt hash')
    if prepared['prepare_context_hash'] != _prepare_context(e): gap('WAVE_PREPARE_STALE', 'battle inputs changed after prepare')
    _move(e, 'WAVE_READY', 'WAVE_INITIALIZING', prepared['request_id'])
    for actor in _wave(e)['actor_refs']:
        if turn._participant(e, actor)['participation'] != 'REMOVED':
            e.turn_lifecycle(actor, 'REMOVE_ENTITY', source_ref={'authority': 'EXPLICIT_SCENARIO_INPUT',
                'source': POLICY+'/retire_previous_wave'})
    _register_wave(e, prepared['bindings'], index)
    turn._s(e)['stage']['wave_index'] = index
    _stage(e, 'RUNNING', 'reference next wave registered')
    c = _c(e)
    c['counters']['actor_registrations'] += len(prepared['bindings'])
    c['counters']['wave_transitions'] += 1
    c['wave_start_turn'] = turn._s(e)['normal_turn_count']
    c['prepared'] = c['pending_transition'] = None
    c['evaluation_fingerprint'] = None
    _event(e, 'AFTER_WAVE_TRANSITION'); _event(e, 'WAVE_START')


def _dispatch(e, event):
    from .action_scheduler import start_reference_envelope
    from .modifier_lifecycle import POLICY_ID as MODIFIER
    _safe(e, allow_insertions=True)
    if MODIFIER not in e.policies: gap('ENCOUNTER_CALLBACK_POLICY_MISSING', 'R17')
    owner = event['actor_id'] or _definition(e)['initial_actor_refs'][0]
    e.state.target_context.update(owner=owner, caster=owner, ability_target=owner,
        ability_targets=[owner], skill_targets=[owner], turn_action_entity=owner,
        turn_owner_entity=owner, param_entity=owner, param_entity_stack=[owner])
    nodes = [turn._node(e, event['event_id']+'/dispatch', 'modifier_event_dispatch',
        {'event_id': event['event_key'], 'source': owner, 'target': owner,
         'payload': {'encounter_event': copy.deepcopy(event)}, 'drain_before_resume_reference': True})]
    nodes += e.events.get(event['event_key'], [])
    event['root_id'] = start_reference_envelope(e, event['event_id'], nodes, boundary=event)
    event['status'] = 'DISPATCHED'
    turn._touch(e)


def _limit(e, name, amount=1):
    limit = _definition(e)['limits'][name]
    return limit is not None and _c(e)['counters'][name]+amount > limit


def idle_step(e, scheduler_budget, callback_budget):
    """One bounded idle operation. R22 calls this before any actor selection.

    Return (progressed, R15 work, callbacks, boundary). A pending insertion drains
    through R22 before an objective can change participants/wave/terminal status.
    """
    _policy(e)
    c = _c(e)
    if c['phase'].startswith('ENCOUNTER_'): return False, 0, 0, None
    if _limit(e, 'zero_time_transitions'):
        return False, 0, 0, turn._yield(e, 'encounter.zero_time_transitions')
    event = next((x for x in c['events'] if x['status'] != 'COMMITTED'), None)
    if event:
        if event['status'] == 'QUEUED':
            if _limit(e, 'stage_callbacks'):
                return False, 0, 0, turn._yield(e, 'encounter.stage_callbacks')
            turn._atomic(e, lambda r: _dispatch(r, next(x for x in _c(r)['events'] if x['event_id'] == event['event_id'])))
            return True, 0, 0, None
        if scheduler_budget <= 0 or callback_budget <= 0 or _limit(e, 'scheduler_steps'):
            return False, 0, 0, turn._yield(e, 'encounter.scheduler_steps_or_callbacks')
        d = e.state.scheduler.action_execution
        before = len(d['history']); callbacks = d['metrics']['callbacks_completed']
        remaining = _definition(e)['limits']['scheduler_steps']
        work_budget = scheduler_budget if remaining is None else min(scheduler_budget, remaining-c['counters']['scheduler_steps'])
        result = turn._drive_r15(e, work_budget, callback_budget)
        d = e.state.scheduler.action_execution
        work, callbacks = len(d['history'])-before, d['metrics']['callbacks_completed']-callbacks
        _c(e)['counters']['scheduler_steps'] += work
        turn._touch(e)
        if result.status == ExecutionStatus.SEMANTIC_GAP:
            return False, work, callbacks, turn._failure(e, turn.TurnError('SEMANTIC_GAP', result.gap.required_capability), 'ENCOUNTER_CALLBACK')
        if result.status == ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED:
            return False, work, callbacks, turn._yield(e, 'encounter.scheduler_work')
        if result.status != ExecutionStatus.ACTION_REFERENCE_COMPLETE:
            return False, work, callbacks, turn._boundary(e, 'SUSPENDED_ACTION_INPUT', request={
                'encounter_event_id': event['event_id'], 'r15_status': result.status.value})
        def complete(r):
            _safe(r, allow_insertions=True)
            ev = next(x for x in _c(r)['events'] if x['event_id'] == event['event_id'])
            owned = r.state.scheduler.action_execution
            ev['status'] = 'COMMITTED'
            ev['listener_ids'] = [x['registration_id'] for x in sorted(owned['callbacks'].values(),
                key=lambda x: (x['enqueue_order'], x['frame_id']))
                if x['action_root_id'] == ev['root_id'] and x.get('registration_id')]
            ev['scheduler_summary'] = copy.deepcopy(owned['history'])
            _c(r)['counters']['stage_callbacks'] += 1
            turn._touch(r)
        turn._atomic(e, complete)
        return True, work, callbacks, None
    _safe(e, allow_insertions=True)
    if any(x['cancellation'] == 'PENDING' for x in turn._s(e)['pending_insertions']):
        if (any(x['status'] == 'PENDING_OWNED_DRAIN' for x in c['life_candidates'].values()) or
            any(row['participation'] != 'REMOVED' and e.state.properties[row['actor_id']]['hp'] == 0
                for row in turn._s(e)['participants'])):
            turn._atomic(e, _confirm_life)
            return True, 0, 0, None
        return False, 0, 0, None
    phase = c['phase']
    if phase == 'WAVE_ACTIVE' and _fingerprint(e) == c['evaluation_fingerprint']:
        if _limit(e, 'normal_turns'):
            return False, 0, 0, turn._yield(e, 'encounter.normal_turns')
        return False, 0, 0, None
    if phase == 'WAVE_ACTIVE' and _limit(e, 'objective_evaluations'):
        return False, 0, 0, turn._yield(e, 'encounter.objective_evaluations')
    if phase == 'WAVE_READY':
        refs = next_wave_preview(e)['actor_refs']
        if _limit(e, 'actor_registrations', len(refs)) or _limit(e, 'wave_transitions'):
            return False, 0, 0, turn._yield(e, 'encounter.registrations_or_waves')
    def advance(r):
        rc = _c(r)
        rc['counters']['zero_time_transitions'] += 1
        rc['counters']['normal_turns'] = turn._s(r)['normal_turn_count']
        if _confirm_life(r):
            turn._touch(r)
            return
        rc = _c(r)
        if phase in ('INITIALIZING', 'WAVE_INITIALIZING'):
            _move(r, phase, 'WAVE_ACTIVE', 'wave_start_callbacks_drained')
        elif phase == 'WAVE_ACTIVE': _evaluate_and_plan(r)
        elif phase == 'WAVE_CLEAR_PENDING':
            _stage(r, 'WAVE_PENDING', 'reference wave clear; callbacks draining')
            _move(r, phase, 'TRANSITION_DRAINING', rc['pending_transition']['request_id'])
            outcome = _c(r)['pending_transition']['outcome']
            _event(r, 'BEFORE_WAVE_TRANSITION' if outcome == 'NEXT_WAVE' else 'ENCOUNTER_'+outcome)
        elif phase == 'TRANSITION_DRAINING':
            _verify_pending(r)
            outcome = rc['pending_transition']['outcome']
            if outcome == 'NEXT_WAVE': _move(r, phase, 'WAVE_READY', 'transition_callbacks_drained')
            else:
                _stage(r, outcome, 'explicit reference objective '+outcome)
                _move(r, phase, 'ENCOUNTER_'+outcome, 'terminal_callbacks_drained')
        elif phase == 'WAVE_READY':
            if rc['prepared'] is None:
                rc['prepared'] = _prepare(r)
                turn._touch(r)
            else: _commit_wave(r)
        else: gap('ENCOUNTER_ILLEGAL_TRANSITION', phase)
    turn._atomic(e, advance)
    return True, 0, 0, None


def finalize_terminal(e):
    c = _c(e)
    if c['terminal_receipt'] is not None: return
    _safe(e)
    status = turn._s(e)['terminal']['status']
    if c['phase'] != 'ENCOUNTER_'+status or any(x['status'] != 'COMMITTED' for x in c['events']):
        gap('ENCOUNTER_TERMINAL_NOT_SETTLED', status)
    receipt = {'schema': 'reference_encounter_terminal_receipt/1', 'result': status,
        'encounter_id': _definition(e)['encounter_id'], 'wave_index': turn._s(e)['stage']['wave_index'],
        'objective_evidence': copy.deepcopy(c['pending_transition']['objective_evidence']),
        'participating_actors': copy.deepcopy(turn._s(e)['participants']),
        'policy_id': POLICY, 'policy_version': '1', 'policy_hash': c['policy_hash'],
        'terminal_reason': turn._s(e)['terminal']['reason'],
        'settled_events': [{'event_id': x['event_id'], 'root_id': x['root_id'], 'listener_ids': x['listener_ids']}
                           for x in c['events']],
        'final_state_hash': e.state.stable_hash(),
        'hash_scope': 'BehaviorBattleState before attaching this immutable receipt (terminal boundary already stored)'}
    receipt['receipt_hash'] = stable_hash(receipt)
    c['terminal_receipt'] = receipt


def current_encounter(e):
    return copy.deepcopy(e.state.mechanics.get(KEY))


def current_wave(e):
    return copy.deepcopy(_wave(e))


def encounter_result(e):
    return copy.deepcopy(_c(e)['terminal_receipt'])


def run_until_encounter_boundary(e, budget=10000):
    _policy(e)
    return e.run_until_decision(budget=budget)


def validate_runtime(e):
    if KEY not in e.state.mechanics: return
    _policy(e)
    c = _c(e)
    EncounterDefinition.from_dict(c['definition'])
    if c['phase'] not in TRANSITIONS: gap('ENCOUNTER_SNAPSHOT_INVALID', 'phase')
    if len({x['event_id'] for x in c['events']}) != len(c['events']): gap('ENCOUNTER_SNAPSHOT_INVALID', 'duplicate event')
    for i, receipt in enumerate(c['transitions']):
        unsigned = copy.deepcopy(receipt); seal = unsigned.pop('receipt_hash')
        if (receipt['sequence'] != i or stable_hash(unsigned) != seal or
                (i and receipt['prior'] != c['transitions'][i-1]['next']) or
                receipt['next'] not in TRANSITIONS.get(receipt['prior'], ())):
            gap('ENCOUNTER_SNAPSHOT_INVALID', 'transition receipt')
    if c['transitions'][-1]['next'] != c['phase']: gap('ENCOUNTER_SNAPSHOT_INVALID', 'cursor')
    if c['terminal_receipt']:
        receipt = copy.deepcopy(c['terminal_receipt']); seal = receipt.pop('receipt_hash')
        if stable_hash(receipt) != seal or receipt['result'] != turn._s(e)['terminal']['status']:
            gap('ENCOUNTER_SNAPSHOT_INVALID', 'terminal receipt')


def record_command(e, kind, arguments):
    mapping = {'initialize': e.initialize_encounter, 'advance': e.run_until_encounter_boundary,
        'submit': e.submit_action, 'enemy': e.request_enemy_decision, 'lifecycle': e.turn_lifecycle,
        'prepare': e.prepare_next_wave, 'release_barrier': e.release_action_barrier,
        'evaluate': e.evaluate_encounter_objectives, 'preview': e.next_wave_preview,
        'result': e.encounter_result}
    before = e.stable_hash()
    args = copy.deepcopy(arguments)
    result = mapping[kind](**args)
    return {'schema': 'r25_public_command_receipt/1', 'kind': kind, 'arguments': args,
            'prehash': before, 'posthash': e.stable_hash()}, result


def replay_commands(e, receipts):
    r = e.clone(); outputs = []
    for expected in receipts:
        if r.stable_hash() != expected['prehash']: gap('ENCOUNTER_REPLAY_MISMATCH', 'prehash')
        receipt, output = record_command(r, expected['kind'], expected['arguments'])
        if receipt != expected: gap('ENCOUNTER_REPLAY_MISMATCH', expected['kind'])
        outputs.append(output)
    return r, tuple(outputs)
