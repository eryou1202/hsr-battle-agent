"""Opt-in R21 rational reference turns on the existing BehaviorRuntime.

This module selects actors and owns turn cursors. R15 alone executes IR and
drains work; R17 instances and R19/R20 stores remain authoritative. None of
these policies establishes native AV, action legality, AI, or stage behavior.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from functools import cmp_to_key
from pathlib import Path
from typing import Protocol

from hsr_battle_agent.battle_ir.behavior import Authority, IRNode, TaskIR, stable_hash
from .behavior import GapError, ExecutionStatus
from .behavior_primitives import SCALE, raw_checked

KEY = 'battle_turn_v1'
ADAPTER = 'battle_turn_adapter_v1'
PROVIDERS = 'r22_turn_provider_contracts_v1'
CONTRACT = json.loads(Path(__file__).with_name('battle_turn_contract.json').read_text(encoding='utf-8-sig'))
HOOKS = tuple(CONTRACT['reference_policy']['operation_bindings'])
ORDER = ['DUE_ASC', 'PRIORITY_DESC', 'REGISTRATION_ASC', 'ENQUEUE_ASC', 'ENTRY_ID_UTF8_ASC']
BOUNDARY_ORDER = ['TURN_START', 'BEFORE_ACTION', 'AFTER_ACTION', 'TURN_END', 'DURATION_PROGRESS', 'EXPIRY_CHECK']


class TurnError(ValueError):
    """A rejected atomic reference operation. No native fallback is selected."""
    def __init__(self, code, message):
        self.code, self.message = code, str(message)
        super().__init__(code + ': ' + self.message)


class MonsterDecisionProvider(Protocol):
    """External deterministic provider; the identity is serialized, code is not."""
    identity: dict

    def choose(self, *, snapshot: dict, actor_id: str, permissions: list[dict],
               policy_identity: dict, rng_context: dict) -> dict: ...


@dataclass(frozen=True)
class ActionInsertion:
    """Exact R21 insertion record. Admission validates every field atomically."""
    insertion_id: str
    category: str
    owner_actor_id: str
    action_actor_id: str
    generation: int
    requested_at: dict
    enqueue_ordinal: int
    priority: int
    placement: str
    due_at: dict | None
    parent_turn_id: str | None
    parent_action_root_id: str | None
    action_permission_id: str | None
    policy_id: str
    policy_hash: str
    cancellation: str
    cancellation_reason: str | None
    consumes_normal_av: bool
    counts_normal_turn: bool
    emits_turn_start: bool
    emits_turn_end: bool
    safe_point_token: str | None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        validate_schema(value, {'$ref': '#/$defs/ActionInsertion'}, CONTRACT['state_json_schema'])
        return cls(**copy.deepcopy(value))


def integer(value, minimum=0, bits=256):
    if type(value) is not int or value < minimum or abs(value).bit_length() > bits:
        raise TurnError('SEMANTIC_GAP', 'bounded integer required')
    return value


@dataclass(frozen=True)
class Rational:
    n: int
    d: int = 1
    bits: int = 256

    def __post_init__(self):
        integer(self.bits, 1, 32)
        if type(self.n) is not int or type(self.d) is not int or self.d == 0:
            raise TurnError('SEMANTIC_GAP', 'integer rational with nonzero denominator required')
        self._bound(self.n, self.d)
        sign = -1 if self.d < 0 else 1
        divisor = math.gcd(self.n, self.d)
        object.__setattr__(self, 'n', sign * self.n // divisor)
        object.__setattr__(self, 'd', abs(self.d) // divisor)

    def _bound(self, *values):
        if any(abs(v).bit_length() > self.bits for v in values):
            raise TurnError('SEMANTIC_GAP', 'rational intermediate exceeds max_integer_bits')

    @classmethod
    def read(cls, value, bits=256, *, canonical=True):
        if isinstance(value, Rational):
            return cls(value.n, value.d, bits)
        if type(value) is int:
            return cls(value, 1, bits)
        if not isinstance(value, dict) or set(value) != {'n', 'd'}:
            raise TurnError('SEMANTIC_GAP', 'rational n/d required; floats are forbidden')
        r = cls(value['n'], value['d'], bits)
        if canonical and r.to_dict() != value:
            raise TurnError('SEMANTIC_GAP', 'noncanonical rational')
        return r

    def to_dict(self):
        return {'n': self.n, 'd': self.d}

    def _other(self, value):
        return Rational.read(value, self.bits)

    def add(self, value):
        o = self._other(value)
        a, b, d = self.n * o.d, o.n * self.d, self.d * o.d
        self._bound(a, b, d, a + b)
        return Rational(a + b, d, self.bits)

    def sub(self, value):
        o = self._other(value)
        return self.add(Rational(-o.n, o.d, self.bits))

    def mul(self, value):
        o = self._other(value)
        n, d = self.n * o.n, self.d * o.d
        self._bound(n, d)
        return Rational(n, d, self.bits)

    def div(self, value):
        o = self._other(value)
        if o.n == 0:
            raise TurnError('SEMANTIC_GAP', 'division by zero')
        n, d = self.n * o.d, self.d * o.n
        self._bound(n, d)
        return Rational(n, d, self.bits)

    def compare(self, value):
        o = self._other(value)
        a, b = self.n * o.d, o.n * self.d
        self._bound(a, b)
        return (a > b) - (a < b)

    def maximum(self, value):
        return self if self.compare(value) >= 0 else self._other(value)


def validate_schema(value, schema, root=None, path='$'):
    """Validate the exact bundled R21 schema subset without third-party imports."""
    root = schema if root is None else root
    if '$ref' in schema:
        target = root
        for part in schema['$ref'].removeprefix('#/').split('/'):
            target = target[part]
        validate_schema(value, target, root, path)
    for sub in schema.get('allOf', []):
        validate_schema(value, sub, root, path)
    if 'anyOf' in schema:
        for sub in schema['anyOf']:
            try:
                validate_schema(value, sub, root, path)
                break
            except TurnError:
                pass
        else:
            raise TurnError('SEMANTIC_GAP', path + ' has no matching schema')
    if 'enum' in schema and not any(type(value) is type(v) and value == v for v in schema['enum']):
        raise TurnError('SEMANTIC_GAP', path + ' enum')
    types = {'object': dict, 'array': list, 'integer': int, 'boolean': bool, 'string': str, 'null': type(None)}
    if 'type' in schema and type(value) is not types[schema['type']]:
        raise TurnError('SEMANTIC_GAP', path + ' type')
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        if set(schema.get('required', [])) - set(value):
            raise TurnError('SEMANTIC_GAP', path + ' required fields')
        if schema.get('additionalProperties') is False and set(value) - set(properties):
            raise TurnError('SEMANTIC_GAP', path + ' extra fields')
        for key, child in value.items():
            if key in properties:
                validate_schema(child, properties[key], root, path + '/' + key)
            elif isinstance(schema.get('additionalProperties'), dict):
                validate_schema(child, schema['additionalProperties'], root, path + '/' + key)
    if isinstance(value, list) and 'items' in schema:
        for i, child in enumerate(value):
            validate_schema(child, schema['items'], root, path + '/' + str(i))
    if type(value) is int and value < schema.get('minimum', value):
        raise TurnError('SEMANTIC_GAP', path + ' minimum')
    if isinstance(value, str) and (len(value) < schema.get('minLength', 0) or
            ('pattern' in schema and re.search(schema['pattern'], value) is None)):
        raise TurnError('SEMANTIC_GAP', path + ' string')


def implementation_bindings():
    # Actual file bytes identify the implemented operations, not R21 spec hashes.
    digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {name: {'provider_id': 'r22.reference.' + name, 'version': '1',
                  'implementation_hash': digest, 'semantic_authority': 'REFERENCE_MODEL',
                  'parameters': {}} for name in HOOKS}


def reference_policy(*, distance=None, boundary_listener_policy=None):
    """Explicit R21 reference profile, replacing only declared spec identities."""
    p = copy.deepcopy(CONTRACT['reference_policy'])
    p['identity'] = 'r22_turn_distance_rational_reference_v1'
    p['operation_bindings'] = implementation_bindings()
    if distance is not None:
        p['numeric']['distance'] = Rational.read(distance).to_dict()
    if boundary_listener_policy is not None:
        p['boundary_listener_policy_hash'] = stable_hash(boundary_listener_policy)
    return p


def validate_policy(p, providers):
    validate_schema(p, CONTRACT['policy_json_schema'])
    if p['order'] != ORDER or p['boundary_order'] != BOUNDARY_ORDER:
        raise TurnError('AV_REFERENCE_POLICY_MISSING', 'unsupported reference order')
    if p['category_rules'] != CONTRACT['reference_policy']['category_rules']:
        raise TurnError('AV_REFERENCE_POLICY_MISSING', 'category flags require a new implemented profile')
    if p['operation_bindings'] != implementation_bindings() or providers.get('operations') != implementation_bindings():
        raise TurnError('AV_REFERENCE_POLICY_MISSING', 'unknown operation provider/version/implementation hash')
    bits = p['numeric']['max_integer_bits']
    if not 8 <= bits <= 4096:
        raise TurnError('AV_REFERENCE_POLICY_MISSING', 'numeric bound must be 8..4096')
    if Rational.read(p['numeric']['distance'], bits).n <= 0:
        raise TurnError('AV_REFERENCE_POLICY_MISSING', 'positive caller distance required')
    if (providers.get('authority') != 'REFERENCE_MODEL' or not providers.get('source') or
            providers.get('policy_hash') != stable_hash(p)):
        raise TurnError('AV_REFERENCE_POLICY_MISSING', 'explicit source and matching policy hash required')
    for field, identity in [('availability', p['availability_provider_id']), ('stage', p['terminal_provider_id'])]:
        if providers.get(field, {}).get('provider_id') != identity:
            raise TurnError('INITIATIVE_INPUT_MISSING', 'missing ' + field + ' provider')
    listener = providers.get('boundary_listeners')
    if (not isinstance(listener, dict) or listener.get('mode') != 'EXPLICIT_ACTIVE_R17_REFERENCE' or
            p['boundary_listener_policy_hash'] != stable_hash(listener)):
        raise TurnError('TURN_BOUNDARY_EVENT_UNKNOWN', 'complete explicit reference listener policy required')
    if providers.get('stage', {}).get('status') not in ('RUNNING', 'WAVE_PENDING', 'VICTORY', 'DEFEAT', 'ABORTED'):
        raise TurnError('ENTITY_STATE_UNRESOLVED', 'explicit stage status required')
    if not isinstance(providers.get('availability', {}).get('actors'), dict):
        raise TurnError('INITIATIVE_INPUT_MISSING', 'explicit per-actor availability required')
    for key in ('speeds', 'readiness_sources', 'durations'):
        if not isinstance(providers.get(key), dict):
            raise TurnError('INITIATIVE_INPUT_MISSING', 'explicit ' + key + ' mapping required')
    duration_order = providers.get('duration_order')
    if (not isinstance(duration_order, list) or any(not isinstance(x, str) for x in duration_order) or
            len(duration_order) != len(set(duration_order)) or set(duration_order) != set(providers['durations'])):
        raise TurnError('TURN_BOUNDARY_EVENT_UNKNOWN', 'explicit duration registration order required')


@dataclass(frozen=True)
class TurnBudget:
    normal_turns: int = 1000
    decision_transitions: int = 10000
    queue_pops: int = 10000
    zero_time_insertions: int = 1000
    boundary_callbacks: int = 10000
    scheduler_work: int = 10000

    def __post_init__(self):
        for value in asdict(self).values():
            integer(value)

    @classmethod
    def read(cls, value):
        if isinstance(value, cls):
            return value
        if type(value) is int:
            return cls(**{name: value for name in asdict(cls())})
        if isinstance(value, dict):
            return cls(**value)
        raise TurnError('SEMANTIC_GAP', 'TurnBudget or nonnegative integer required')


@dataclass(frozen=True)
class DecisionReceipt:
    boundary: dict
    state_hash: str
    reason: str
    provider_identity: dict
    available_reference_actions: tuple

    @property
    def kind(self):
        return self.boundary['kind']

    def __getitem__(self, key):
        return self.boundary[key]

    def to_dict(self):
        return asdict(self)


def _s(e):
    return e.state.mechanics[KEY]


def _a(e):
    return e.state.mechanics[ADAPTER]


def _p(e):
    s = _s(e)
    p = e.policies.get(s['policy_id'])
    if p is None or stable_hash(p) != s['policy_hash']:
        raise TurnError('AV_REFERENCE_POLICY_MISSING', 'turn policy changed or missing')
    return p


def _providers(e):
    contracts = e.policies[PROVIDERS]
    if stable_hash(contracts) != _a(e)['provider_contracts_hash']:
        raise TurnError('AV_REFERENCE_POLICY_MISSING', 'provider contract changed')
    return contracts


def _q(e, value):
    return Rational.read(value, _p(e)['numeric']['max_integer_bits'])


def _now(e):
    return _q(e, _s(e)['clock']['now'])


def _id(s, kind):
    name = 'next_' + kind + '_id'
    identity = kind + ':' + str(s[name])
    s[name] += 1
    return identity


def _participant(e, actor):
    for row in _s(e)['participants']:
        if row['actor_id'] == actor:
            return row
    raise TurnError('INITIATIVE_INPUT_MISSING', 'unregistered actor ' + str(actor))


def _top(e):
    return _s(e)['active_stack'][-1] if _s(e)['active_stack'] else None


def _authority(source, version=None):
    return {'kind': 'EXPLICIT_SCENARIO_INPUT', 'source_version': version, 'artifact': source,
            'sha256': stable_hash({'source': source}), 'pointer': ''}


def _node(e, name, op, payload):
    return TaskIR(name, op, Authority('REFERENCE_MODEL', 'r22', 'explicit reference turn envelope',
                  _s(e)['policy_hash'], semantic_status='REFERENCE_MODEL'), payload)


def _sample(e, actor, revision=None):
    from .dynamic_property import read
    spec = _providers(e)['speeds'].get(actor)
    if not isinstance(spec, dict) or spec.get('provider_id') != _participant(e, actor)['speed_ref']['effective_provider_id']:
        raise TurnError('SPEED_PROVIDER_MISSING', 'exact actor speed provider required')
    binding = copy.deepcopy(spec['binding'])
    # The explicit R19 provider continues to enumerate the live R17 set.
    if spec.get('live_modifier_order') == 'SORT_INSTANCE_ID_REFERENCE':
        binding['modifier_order'] = sorted(e.state.modifiers)
    node = _node(e, 'speed/' + actor, 'turn_speed_sample', {})
    try:
        raw = read(e, node, e.state, binding, _participant(e, actor)['speed_ref']['base_property_key'])[0]
        raw_checked(raw)
    except (GapError, ValueError, KeyError) as exc:
        raise TurnError('SPEED_PROVIDER_MISSING', str(exc)) from exc
    speed = _q(e, raw).div(_q(e, SCALE))
    if speed.n <= 0:
        raise TurnError('SPEED_PROVIDER_MISSING', 'positive ordinary mode0 effective speed required')
    if revision is None:
        revision = _a(e)['speed_revisions'][actor]
    integer(revision)
    return {'value': speed.to_dict(), 'provider_revision': revision, 'observed_at': _now(e).to_dict(),
            'input_state_hash': stable_hash({'properties': e.state.properties, 'modifiers':
                {k: asdict(v) for k, v in e.state.modifiers.items()}, 'binding': binding})}


def _op(e, operation, **values):
    """Resolve the caller-bound implemented reference hook, with bounded operands."""
    binding = _p(e)['operation_bindings'][operation]
    if binding != _providers(e)['operations'][operation] or binding != implementation_bindings()[operation]:
        raise TurnError('AV_REFERENCE_POLICY_MISSING', operation)
    q = lambda v: _q(e, v)
    if operation == 'speed_to_action_interval':
        speed = q(values['speed'])
        if speed.n <= 0:
            raise TurnError('SPEED_PROVIDER_MISSING', 'nonpositive speed')
        return q(_p(e)['numeric']['distance']).div(speed)
    if operation == 'initial_initiative_placement':
        return q(values['now']).add(values['interval'])
    if operation == 'elapsed_time_advancement':
        return q(values['now']).maximum(values['due'])
    if operation == 'remaining_time_update':
        return q(values['due']).sub(values['now']).maximum(0)
    if operation == 'speed_change_rebase':
        remaining = _op(e, 'remaining_time_update', due=values['due'], now=values['now'])
        return q(values['now']).add(remaining.mul(values['old_speed']).div(values['new_speed']))
    if operation == 'advance_delay_adjustment':
        fraction = q(values['fraction'])
        if fraction.n < 0 or values['kind'] not in ('ADVANCE', 'DELAY'):
            raise TurnError('SEMANTIC_GAP', 'nonnegative advance/delay fraction required')
        delta = fraction.mul(_op(e, 'speed_to_action_interval', speed=values['speed']))
        due = q(values['due'])
        return (due.sub(delta) if values['kind'] == 'ADVANCE' else due.add(delta)).maximum(values['now'])
    if operation == 'tie_break':
        left, right = values['left'], values['right']
        comparison = q(left['due_at']).compare(right['due_at'])
        if comparison:
            return comparison
        a = (-left['priority'], left['registration_ordinal'], left['enqueue_ordinal'], left['entry_id'].encode('utf-8'))
        b = (-right['priority'], right['registration_ordinal'], right['enqueue_ordinal'], right['entry_id'].encode('utf-8'))
        return (a > b) - (a < b)
    raise TurnError('AV_REFERENCE_POLICY_MISSING', operation)


def _sort(e, entries):
    return sorted(entries, key=cmp_to_key(lambda a, b: _op(e, 'tie_break', left=a, right=b)))


def _eligible(e, entry):
    try:
        row = _participant(e, entry['actor_id'])
    except TurnError:
        return False
    i = _s(e)['initiative'][row['actor_id']]
    return (row['participation'] == 'ENABLED' and row['generation'] == entry['generation'] == i['generation'] and
            i['revision'] == entry['initiative_revision'] and i['normal_entry_id'] == entry['entry_id'] and
            i['due_at'] == entry['due_at'] and not (_top(e) and _top(e)['category'] == 'NORMAL_TURN' and
                                                   _top(e)['action_actor_id'] == row['actor_id']))


def _enqueue(e, actor, due):
    s = _s(e)
    row, i = _participant(e, actor), s['initiative'][actor]
    s['normal_queue'] = [entry for entry in s['normal_queue'] if entry['actor_id'] != actor]
    entry = {'entry_id': _id(s, 'entry'), 'actor_id': actor, 'generation': row['generation'],
             'category': 'NORMAL_TURN', 'due_at': due.to_dict(), 'priority': _p(e)['category_rules']['NORMAL_TURN']['priority'],
             'registration_ordinal': row['registration_ordinal'], 'enqueue_ordinal': s['next_enqueue_ordinal'],
             'initiative_revision': i['revision'], 'insertion_id': None}
    s['next_enqueue_ordinal'] += 1
    i.update(due_at=due.to_dict(), normal_entry_id=entry['entry_id'])
    s['normal_queue'] = _sort(e, s['normal_queue'] + [entry])


def _touch(e):
    s = _s(e)
    s['revision'] += 1
    s['clock']['transition_count'] += 1
    s['decision'] = None
    s['permissions'] = []
    s['failure'] = None


def _context_hash(e):
    document = e.snapshot()
    document['state']['mechanics'].pop(KEY, None)
    document['state']['mechanics'].pop(ADAPTER, None)
    return stable_hash(document)


def _journal(e, kind, arguments, prehash, revision):
    s = _s(e)
    s['command_journal'].append({'command_id': _id(s, 'command'), 'expected_revision': revision,
        'expected_hash': prehash, 'policy_hash': s['policy_hash'], 'kind': kind, 'arguments': copy.deepcopy(arguments)})


def _atomic(e, operation, *args, journal=None, arguments=None):
    before, revision = e.stable_hash(), _s(e)['revision'] if KEY in e.state.mechanics else 0
    candidate = e.clone()
    try:
        result = operation(candidate, *args)
    except TurnError:
        raise
    except (GapError, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise TurnError('SEMANTIC_GAP', 'explicit reference input: ' + str(exc)) from exc
    if journal:
        _journal(candidate, journal, arguments or {}, before, revision)
    validate_runtime(candidate)
    e.state, e.policies, e.trace, e.gaps = candidate.state, candidate.policies, candidate.trace, candidate.gaps
    return result


def initialize_turns(e, participant_bindings, policy, provider_contracts):
    def initialize(c):
        from .action_scheduler import _policy
        if KEY in c.state.mechanics or c.state.scheduler.action_execution or c.state.terminal:
            raise TurnError('INITIATIVE_INPUT_MISSING', 'initialize only idle uninitialized battle')
        _policy(c)
        p, providers = copy.deepcopy(policy), copy.deepcopy(provider_contracts)
        validate_policy(p, providers)
        if not isinstance(participant_bindings, list) or not participant_bindings:
            raise TurnError('INITIATIVE_INPUT_MISSING', 'explicit nonempty participants required')
        from .actor_binding import ActorRuntimeBinding, POLICY_ID as ACTOR
        for binding in participant_bindings:
            actor_input = binding.get('actor_binding')
            if actor_input is not None:
                actor_input = actor_input if isinstance(actor_input, ActorRuntimeBinding) else ActorRuntimeBinding.from_dict(actor_input)
                existing = c.state.mechanics.get(ACTOR, {}).get('actors', {}).get(actor_input.entity_id)
                if existing is None:
                    c.bind_actor(actor_input)
                elif existing['binding'] != actor_input.to_dict():
                    raise TurnError('INITIATIVE_INPUT_MISSING', 'contradictory existing R20 actor binding')
        s = {'schema': 'generic_battle_turn_state/1', 'policy_id': p['identity'], 'policy_hash': stable_hash(p),
             'clock': {'now': {'n': 0, 'd': 1}, 'unit': 'REFERENCE_AV', 'advance_count': 0, 'transition_count': 0},
             'participants': [], 'initiative': {}, 'normal_queue': [], 'active_stack': [], 'pending_insertions': [],
             'pending_interrupts': [], 'permissions': [], 'boundary_work': [], 'decision': None,
             'terminal': {'status': 'RUNNING', 'reason': None, 'stage_policy_hash': stable_hash(providers['stage'])},
             'stage': {'stage_id': providers['stage']['stage_id'], 'wave_index': 0,
                       'provider_id': p['terminal_provider_id'], 'pending_request_id': None, 'generation': 0,
                       'policy_hash': stable_hash(providers['stage'])},
             'revision': 0, 'normal_turn_count': 0, 'action_count': 0, 'command_journal': [], 'failure': None}
        for kind in ['turn', 'entry', 'insertion', 'decision', 'permission', 'event', 'command']:
            s['next_' + kind + '_id'] = 0
        s['next_enqueue_ordinal'] = 0
        s['next_registration_ordinal'] = 0
        c.policies[p['identity']], c.policies[PROVIDERS] = p, providers
        c.state.mechanics[KEY] = s
        c.state.mechanics[ADAPTER] = {'schema': 'r22_turn_adapter/1', 'provider_contracts_hash': stable_hash(providers),
            'speed_revisions': {}, 'permission_seals': {}, 'consumed_permissions': [], 'boundary_plans': {},
            'turn_duration_instances': {}, 'duration_visits': {}, 'insert_actions': {}, 'insertion_depths': {},
            'stage_status': providers['stage']['status'], 'stage_reason': providers['stage'].get('reason'),
            'selected_action': None, 'event_history': [], 'decision_history': [], 'completion_receipts': [],
            'action_history': [],
            'zero_time_chain': 0, 'last_selection_clock': None}
        if not isinstance(participant_bindings, list) or not participant_bindings:
            raise TurnError('INITIATIVE_INPUT_MISSING', 'explicit nonempty participants required')
        # Callers provide immutable ordinals; permutations cannot redefine registration.
        bindings = sorted(participant_bindings, key=lambda b: b['participant']['registration_ordinal'])
        for binding in bindings:
            _register(c, binding, initial=True)
        _touch(c)
        return copy.deepcopy(_s(c))
    return _atomic(e, initialize)


def _register(e, binding, initial=False):
    from .actor_binding import ActorRuntimeBinding, POLICY_ID as ACTOR
    s = _s(e)
    row = copy.deepcopy(binding['participant'])
    validate_schema(row, {'$ref': '#/$defs/Participant'}, CONTRACT['state_json_schema'])
    if row['actor_id'] in s['initiative'] or any(x['registration_ordinal'] == row['registration_ordinal'] for x in s['participants']):
        raise TurnError('INITIATIVE_INPUT_MISSING', 'duplicate actor or registration ordinal')
    if not initial and row['registration_ordinal'] < s['next_registration_ordinal']:
        raise TurnError('INITIATIVE_INPUT_MISSING', 'registration ordinal cannot be reused')
    if row['actor_id'] != row['entity_ref'] or row['availability_provider_id'] != _p(e)['availability_provider_id']:
        raise TurnError('INITIATIVE_INPUT_MISSING', 'explicit matching entity and availability identity required')
    actor_binding = binding.get('actor_binding')
    if actor_binding is not None:
        actor_binding = actor_binding if isinstance(actor_binding, ActorRuntimeBinding) else ActorRuntimeBinding.from_dict(actor_binding)
        if actor_binding.entity_id != row['actor_id']:
            raise TurnError('INITIATIVE_INPUT_MISSING', 'actor binding identity mismatch')
        existing = e.state.mechanics.get(ACTOR, {}).get('actors', {}).get(row['actor_id'])
        if existing is None:
            e.bind_actor(actor_binding)
            s = _s(e)
        elif existing['binding'] != actor_binding.to_dict():
            raise TurnError('INITIATIVE_INPUT_MISSING', 'contradictory existing actor binding')
    record = e.state.mechanics.get(ACTOR, {}).get('actors', {}).get(row['actor_id'])
    if record is None or row['entity_ref'] not in e.state.entities:
        raise TurnError('INITIATIVE_INPUT_MISSING', 'verified existing R20 ActorRuntimeBinding required')
    version = record['binding']['content_version']
    if row['authority']['source_version'] != version or binding.get('content_version') != version:
        raise TurnError('INITIATIVE_INPUT_MISSING', 'actor content version mismatch')
    entity_revision = e.state.entities[row['entity_ref']].get('reference_entity_revision', row['entity_revision'])
    if entity_revision != row['entity_revision'] or row['speed_ref']['authority']['source_version'] != version:
        raise TurnError('INITIATIVE_INPUT_MISSING', 'actor/provider revision or version mismatch')
    if row['speed_ref']['provider_policy_hash'] != stable_hash(_providers(e)['speeds'].get(row['actor_id'])):
        raise TurnError('SPEED_PROVIDER_MISSING', 'speed provider policy hash mismatch')
    _validate_availability(e, row['actor_id'], version)
    _a(e)['speed_revisions'][row['actor_id']] = integer(binding['provider_revision'])
    s['participants'].append(row)
    s['next_registration_ordinal'] = max(s['next_registration_ordinal'], row['registration_ordinal'] + 1)
    sample = _sample(e, row['actor_id'])
    s['initiative'][row['actor_id']] = {'actor_id': row['actor_id'], 'generation': row['generation'], 'due_at': None,
        'effective_speed_sample': sample, 'cycle_index': 0, 'normal_entry_id': None, 'disabled_remaining': None,
        'disabled_since': None, 'revision': 0, 'authority': 'REFERENCE_MODEL'}
    due = _op(e, 'initial_initiative_placement', now=_now(e), interval=_op(e, 'speed_to_action_interval', speed=sample['value']))
    if row['participation'] == 'ENABLED':
        _enqueue(e, row['actor_id'], due)
    elif row['participation'] == 'DISABLED':
        s['initiative'][row['actor_id']].update(disabled_remaining=due.sub(_now(e)).to_dict(), disabled_since=_now(e).to_dict())


def _validate_availability(e, actor, version):
    availability = _providers(e)['availability']['actors'].get(actor)
    if not isinstance(availability, dict) or type(availability.get('enabled')) is not bool:
        raise TurnError('INITIATIVE_INPUT_MISSING', 'explicit actor availability required')
    if availability.get('content_version') != version or not isinstance(availability.get('actions'), list):
        raise TurnError('INITIATIVE_INPUT_MISSING', 'versioned actor actions required')
    action_ids = [x.get('action_id') for x in availability['actions']]
    if len(action_ids) != len(set(action_ids)):
        raise TurnError('INITIATIVE_INPUT_MISSING', 'duplicate actor action mapping')
    for spec in availability['actions']:
        if spec.get('action_id') not in e.actions or spec.get('ir_hash') != e.actions[spec['action_id']].stable_hash():
            raise TurnError('INITIATIVE_INPUT_MISSING', 'exact local action/IR mapping required')
        if not isinstance(spec.get('target_ids'), list) or len(spec['target_ids']) != len(set(spec['target_ids'])):
            raise TurnError('INITIATIVE_INPUT_MISSING', 'explicit distinct candidate targets required')
        if any(t not in e.state.entities for t in spec['target_ids']):
            raise TurnError('INITIATIVE_INPUT_MISSING', 'candidate entity missing')
        if (not isinstance(spec.get('categories'), list) or not spec['categories'] or
                any(k not in _p(e)['category_rules'] for k in spec['categories'])):
            raise TurnError('INITIATIVE_INPUT_MISSING', 'explicit category availability required')
        if spec.get('cost', {}).get('mode') not in ('EXPLICIT_NO_COST_REFERENCE', 'R20_COST_TASKS_REFERENCE'):
            raise TurnError('INITIATIVE_INPUT_MISSING', 'explicit resource cost policy required')
        integer(spec.get('target_min'))
        integer(spec.get('target_max'))
        if not spec['target_min'] <= spec['target_max'] <= len(spec['target_ids']):
            raise TurnError('INITIATIVE_INPUT_MISSING', 'contradictory target cardinality')


def _cost_nodes(e, spec, actor, *, validate_only=True):
    from .resource_engine import binding, resolve, listener_contract
    cost = spec['cost']
    if cost['mode'] == 'EXPLICIT_NO_COST_REFERENCE':
        if set(cost) != {'mode', 'authority'} or cost['authority'] != 'EXPLICIT_SCENARIO_INPUT':
            raise TurnError('SEMANTIC_GAP', 'explicit no-cost authority required')
        return []
    if cost.get('authority') != 'EXPLICIT_SCENARIO_INPUT' or not isinstance(cost.get('tasks'), list) or not cost['tasks']:
        raise TurnError('SEMANTIC_GAP', 'explicit R20 cost source tasks required')
    nodes = [IRNode.from_dict(raw) for raw in cost['tasks']]
    balances = {}
    for node in nodes:
        if node.op != 'resource_cost_reference':
            raise TurnError('SEMANTIC_GAP', 'cost must use R20 source transaction')
        try:
            row = binding(e, node)
            listener_contract(e, node, row)
            values, owner, key = resolve(e, node, row)
            amount = raw_checked(row['amount'])  # Source expressions need a separately implemented admission adapter.
            if (row['operation'] != 'SUBTRACT' or amount < 0 or row.get('cost_authority') != 'EXPLICIT_SCENARIO_INPUT' or
                    not row.get('cost_source')):
                raise TurnError('SEMANTIC_GAP', 'explicit nonnegative R20 source cost required')
            identity = (row['domain'], owner, key)
            before = balances.get(identity, values[owner][key])
            after = raw_checked(before - amount)
            lo, hi = row['bounds']['minimum'], row['bounds']['maximum']
            if after < lo or (not lo <= before <= hi and row['bounds']['initial_overcap'] != 'ALLOW_REFERENCE'):
                raise TurnError('SEMANTIC_GAP', 'RESOURCE_COST_INSUFFICIENT')
            balances[identity] = after
        except (GapError, ValueError, KeyError) as exc:
            if isinstance(exc, TurnError):
                raise
            raise TurnError('SEMANTIC_GAP', 'RESOURCE_COST_VALIDATION: ' + str(exc)) from exc
    return nodes


def _specs(e, top):
    actor = top['action_actor_id']
    available = _providers(e)['availability']['actors'][actor]
    if not available['enabled'] or _participant(e, actor)['participation'] != 'ENABLED':
        return []
    selected = _a(e)['insert_actions'].get(top['insertion_id']) if top['insertion_id'] else None
    result = []
    for spec in available['actions']:
        if top['category'] not in spec['categories'] or (selected and spec['action_id'] != selected):
            continue
        if spec['action_id'] not in e.legal_actions() or spec['ir_hash'] != e.actions[spec['action_id']].stable_hash():
            continue
        try:
            _cost_nodes(e, spec, actor)
        except TurnError as exc:
            if 'RESOURCE_COST_INSUFFICIENT' in str(exc):
                continue
            raise
        result.append(spec)
    return result


def current_turn_owner(e):
    return _top(e)['turn_owner_actor_id'] if _top(e) else None


def next_actor_preview(e, limit=10):
    integer(limit)
    entries = _sort(e, [copy.deepcopy(x) for x in _s(e)['normal_queue'] if _eligible(e, x)])
    insertions = []
    for x in _s(e)['pending_insertions']:
        if (x['cancellation'] == 'PENDING' and _participant(e, x['action_actor_id'])['generation'] == x['generation'] and
                _participant(e, x['action_actor_id'])['participation'] == 'ENABLED'):
            insertions.append({'entry_id': x['insertion_id'], 'actor_id': x['action_actor_id'], 'category': x['category'],
                'due_at': copy.deepcopy(x['due_at'] or x['requested_at']), 'priority': x['priority'],
                'registration_ordinal': _participant(e, x['action_actor_id'])['registration_ordinal'],
                'enqueue_ordinal': x['enqueue_ordinal'], 'precedence': 'AFTER_ACTIVE_SETTLES'})
    return (_sort(e, insertions) + entries)[:limit]


def legal_action_candidates(e, decision_id):
    s, top = _s(e), _top(e)
    if not s['decision'] or s['decision']['decision_id'] != decision_id or not top or top['phase'] != 'DECISION':
        raise TurnError('SEMANTIC_GAP', 'stale or non-action decision')
    result = []
    for permission in s['permissions']:
        if permission['decision_id'] == decision_id:
            _validate_permission(e, permission, permission['target_ids'], s['revision'])
            result.append(copy.deepcopy(permission))
    return result


def _validate_permission(e, permission, targets, revision):
    s, top = _s(e), _top(e)
    p = permission if isinstance(permission, dict) else next((x for x in s['permissions'] if x['permission_id'] == permission), None)
    if p is None or p not in s['permissions']:
        raise TurnError('SEMANTIC_GAP', 'unknown/altered permission')
    seal = _a(e)['permission_seals'].get(p['permission_id'])
    if (not seal or p['permission_id'] in _a(e)['consumed_permissions'] or not top or top['phase'] != 'DECISION' or
            type(revision) is not int or revision != s['revision'] or p['state_revision'] != s['revision'] or
            not s['decision'] or p['decision_id'] != s['decision']['decision_id'] or
            p['turn_id'] != top['turn_id'] or p['actor_id'] != top['action_actor_id'] or
            p['category'] != top['category'] or seal['generation'] != _participant(e, p['actor_id'])['generation'] or
            _participant(e, p['actor_id'])['participation'] != 'ENABLED' or p['policy_hash'] != stable_hash(_p(e)) or
            seal['context_hash'] != _context_hash(e)):
        raise TurnError('SEMANTIC_GAP', 'stale/consumed permission or actor generation')
    spec = next((x for x in _specs(e, top) if x['action_id'] == p['action_id']), None)
    if (spec is None or p['action_ir_hash'] != e.actions[p['action_id']].stable_hash() or
            p['cost_policy_hash'] != stable_hash(spec['cost']) or
            p['availability_provider_id'] != _p(e)['availability_provider_id']):
        raise TurnError('SEMANTIC_GAP', 'action/content/resource/availability changed')
    if (not isinstance(targets, list) or len(targets) != len(set(targets)) or
            any(t not in p['target_ids'] or t not in e.state.entities for t in targets) or
            not spec['target_min'] <= len(targets) <= spec['target_max']):
        raise TurnError('SEMANTIC_GAP', 'invalid candidate targets/cardinality')
    return p, spec


def submit_action(e, permission, targets, expected_revision):
    def submit(c):
        p, spec = _validate_permission(c, permission, targets, expected_revision)
        top = _top(c)
        _a(c)['selected_action'] = {'permission': copy.deepcopy(p), 'spec': copy.deepcopy(spec), 'targets': list(targets)}
        _a(c)['consumed_permissions'].append(p['permission_id'])
        top.update(permission_id=p['permission_id'], phase='BEFORE_ACTION')
        _touch(c)
        return {'status': 'ACTION_ADMITTED_REFERENCE', 'turn_id': top['turn_id'], 'permission_id': p['permission_id']}
    args = {'permission': permission, 'targets': targets, 'expected_revision': expected_revision}
    return _atomic(e, submit, journal='SUBMIT_ACTION', arguments=args)


def _boundary(e, kind, *, failure=None, request=None, reason=None):
    s, top = _s(e), _top(e)
    old = s['decision']
    if old and old['kind'] == kind and old['state_revision'] == s['revision'] and old['failure'] == failure and old['input_request'] == request:
        return _receipt(e)
    s['permissions'] = []
    decision_id = _id(s, 'decision')
    actor = top['action_actor_id'] if top and kind != 'BATTLE_TERMINAL' else None
    b = {'decision_id': decision_id, 'kind': kind, 'actor_id': actor, 'turn_id': top['turn_id'] if actor else None,
         'action_root_id': top['action_root_id'] if actor else None, 'state_revision': s['revision'],
         'policy_hash': s['policy_hash'], 'candidate_permission_ids': [], 'input_request': copy.deepcopy(request),
         'failure': failure, 'terminal_reason': reason if kind == 'BATTLE_TERMINAL' else None}
    if kind in ('PLAYER_NORMAL_TURN', 'ENEMY_AI_DECISION', 'OUT_OF_TURN_WINDOW', 'PENDING_FORCED_ACTION'):
        for spec in _specs(e, top):
            p = {'permission_id': _id(s, 'permission'), 'decision_id': decision_id, 'turn_id': top['turn_id'],
                 'actor_id': actor, 'category': top['category'], 'action_id': spec['action_id'], 'action_ir_hash': spec['ir_hash'],
                 'target_ids': list(spec['target_ids']), 'state_revision': s['revision'], 'policy_hash': s['policy_hash'],
                 'availability_provider_id': _p(e)['availability_provider_id'], 'cost_policy_hash': stable_hash(spec['cost']),
                 'authority': 'REFERENCE_MODEL'}
            s['permissions'].append(p)
            b['candidate_permission_ids'].append(p['permission_id'])
            _a(e)['permission_seals'][p['permission_id']] = {'generation': _participant(e, actor)['generation'],
                'content_version': _providers(e)['availability']['actors'][actor]['content_version'], 'context_hash': _context_hash(e)}
    if kind == 'PENDING_FORCED_ACTION' and len(b['candidate_permission_ids']) != 1:
        raise TurnError('SEMANTIC_GAP', 'forced decision needs exactly one explicit action')
    s['decision'], s['failure'] = b, failure
    _a(e)['decision_context_hash'] = _context_hash(e)
    _a(e)['decision_history'].append({'decision_id': decision_id, 'kind': kind, 'actor_id': actor,
                                     'clock': copy.deepcopy(s['clock']['now']), 'revision': s['revision']})
    return _receipt(e)


def _receipt(e):
    s = _s(e)
    b = copy.deepcopy(s['decision'])
    return DecisionReceipt(b, e.stable_hash(), b['failure']['message'] if b['failure'] else
        (b['terminal_reason'] or b['kind']), {'policy_id': s['policy_id'], 'policy_hash': s['policy_hash'],
            'availability_provider_id': _p(e)['availability_provider_id'], 'contracts_hash': _a(e)['provider_contracts_hash']},
        tuple(copy.deepcopy(p) for p in s['permissions'] if p['permission_id'] in b['candidate_permission_ids']))


def _failure(e, exc, operation):
    s, top = _s(e), _top(e)
    failure = {'code': exc.code, 'message': exc.message or exc.code, 'evidence_ids': [], 'operation': operation,
               'actor_id': top['action_actor_id'] if top else None, 'turn_id': top['turn_id'] if top else None,
               'action_root_id': top['action_root_id'] if top else None,
               'resume_token': top['turn_id'] if top else 'idle', 'input_state_hash': e.stable_hash(),
               'required_policy_or_input': [exc.message or exc.code]}
    # Repeated reads of the same gap must not change hashes or allocate decisions.
    if s['decision'] and s['decision']['kind'] == 'SEMANTIC_GAP':
        old = s['decision']['failure']
        if old['code'] == failure['code'] and old['message'] == failure['message'] and old['operation'] == operation:
            return _receipt(e)
    return _boundary(e, 'SEMANTIC_GAP', failure=failure)


def _yield(e, name):
    return _boundary(e, 'BUDGET_YIELD', request={'budget': name, 'resume_phase': _top(e)['phase'] if _top(e) else 'IDLE'})


def _make_turn(e, entry, insertion=None):
    s = _s(e)
    actor = entry['actor_id']
    sample = _sample(e, actor)
    if sample['value'] != s['initiative'][actor]['effective_speed_sample']['value']:
        raise TurnError('SPEED_PROVIDER_MISSING', 'authoritative waiting speed changed without notify_speed_change')
    if insertion is None:
        now = _op(e, 'elapsed_time_advancement', now=_now(e), due=entry['due_at'])
        if now.compare(_now(e)) > 0:
            s['clock']['advance_count'] += 1
            _a(e)['zero_time_chain'] = 0
        s['clock']['now'] = now.to_dict()
        s['initiative'][actor]['normal_entry_id'] = None
    else:
        insertion['cancellation'] = 'ADMITTED'
    turn = {'turn_id': _id(s, 'turn'), 'queue_entry_id': entry['entry_id'],
            'turn_owner_actor_id': insertion['owner_actor_id'] if insertion else actor,
            'action_actor_id': actor, 'category': entry['category'], 'phase': 'START_BOUNDARY',
            'selected_at': copy.deepcopy(s['clock']['now']), 'normal_turn_index': s['normal_turn_count'],
            'action_index': s['action_count'], 'parent_turn_id': insertion['parent_turn_id'] if insertion else None,
            'parent_action_root_id': insertion['parent_action_root_id'] if insertion else None,
            'action_root_id': None, 'saved_r15_current_root': None, 'saved_target_context': None,
            'permission_id': None, 'insertion_id': insertion['insertion_id'] if insertion else None,
            'completion_consumed': False}
    s['active_stack'].append(turn)
    duration_order = _providers(e)['duration_order']
    # Provider order is explicit and replayable. Unmapped manual instances are
    # retained; unmapped finite lifetimes still fail in the boundary adapter.
    _a(e)['turn_duration_instances'][turn['turn_id']] = [x for x in duration_order if x in e.state.modifiers] + sorted(
        set(e.state.modifiers) - set(duration_order))
    _a(e)['last_selection_clock'] = copy.deepcopy(s['clock']['now'])
    _touch(e)


def _event_plan(e, turn, kind):
    s, a = _s(e), _a(e)
    plan_key = turn['turn_id'] + '/' + kind
    if plan_key in a['boundary_plans']:
        return next(x for x in s['boundary_work'] if x['boundary_id'] == a['boundary_plans'][plan_key])
    event = {'boundary_id': _id(s, 'event'), 'turn_id': turn['turn_id'], 'event_kind': kind,
        'reference_event_key': _p(e)['boundary_event_keys'][kind], 'owner_actor_id': turn['turn_owner_actor_id'],
        'action_actor_id': turn['action_actor_id'], 'normal_turn_index': turn['normal_turn_index'],
        'event_ordinal': len(s['boundary_work']), 'status': 'PENDING', 'r15_root_id': None,
        'listener_policy_hash': _p(e)['boundary_listener_policy_hash'], 'emitted_listener_ids': [],
        'duration_instance_cursor': 0, 'authority': 'REFERENCE_MODEL'}
    s['boundary_work'].append(event)
    a['boundary_plans'][plan_key] = event['boundary_id']
    return event


def _boundary_nodes(e, turn, event):
    p, contracts = _p(e), _providers(e)
    nodes = []
    kind, identity = event['event_kind'], event['boundary_id']
    if kind in ('DURATION_PROGRESS', 'EXPIRY_CHECK'):
        if p['category_rules'][turn['category']]['duration_progress'] == 'OWNER_NORMAL_TURN_END':
            for instance_id in _a(e)['turn_duration_instances'][turn['turn_id']]:
                instance = e.state.modifiers.get(instance_id)
                if instance is None or instance.owner != turn['action_actor_id']:
                    continue
                spec = contracts['durations'].get(instance_id)
                if spec is None:
                    if instance.duration.get('expiry') != 'MANUAL_REFERENCE':
                        raise TurnError('TURN_BOUNDARY_EVENT_UNKNOWN', 'unmapped modifier turn duration ' + instance_id)
                    continue
                if spec.get('units') != 'OWNER_NORMAL_TURN_END_REFERENCE' or spec.get('creation') != 'SKIP_CREATION_TURN_REFERENCE':
                    raise TurnError('TURN_BOUNDARY_EVENT_UNKNOWN', 'explicit reference duration and creation policy required')
                integer(instance.duration.get('remaining'))
                nodes.append(_node(e, identity + '/' + instance_id, 'r22_modifier_duration_reference',
                    {'instance_id': instance_id, 'turn_id': turn['turn_id'], 'boundary_id': identity,
                     'stage': kind, 'spec': copy.deepcopy(spec), 'owner': turn['action_actor_id']}))
    # Caller event keys have no relation to native 0x13; use R17 dispatch.
    if contracts['boundary_listeners']['mode'] == 'EXPLICIT_ACTIVE_R17_REFERENCE':
        from .modifier_lifecycle import POLICY_ID
        if POLICY_ID not in e.policies:
            raise TurnError('TURN_BOUNDARY_EVENT_UNKNOWN', 'R17 listener policy required')
        nodes.append(_node(e, identity + '/dispatch', 'modifier_event_dispatch',
            {'event_id': event['reference_event_key'], 'source': turn['action_actor_id'],
             'target': turn['action_actor_id'], 'payload': {'turn_boundary': copy.deepcopy(event)},
             'drain_before_resume_reference': True}))
    # Explicit EventIR reference bodies also run in the same R15 root.
    nodes.extend(e.events.get(event['reference_event_key'], []))
    return nodes


def _context(e, turn, targets=None):
    targets = targets if targets is not None else [turn['action_actor_id']]
    # Preserve explicit providers/parameters while replacing actor-specific context.
    e.state.target_context.update(owner=turn['action_actor_id'], caster=turn['action_actor_id'],
        turn_action_entity=turn['action_actor_id'], turn_owner_entity=turn['turn_owner_actor_id'],
        ability_target=targets[0] if targets else turn['action_actor_id'], ability_targets=list(targets),
        skill_targets=list(targets), param_entity=targets[0] if targets else turn['action_actor_id'],
        param_entity_stack=list(targets), reference_turn_id=turn['turn_id'])


def _start_boundary(e, turn, kind):
    from .action_scheduler import start_reference_envelope
    event = _event_plan(e, turn, kind)
    if event['status'] == 'PENDING':
        nodes = _boundary_nodes(e, turn, event)
        _context(e, turn)
        event['r15_root_id'] = start_reference_envelope(e, event['boundary_id'], nodes, boundary=event)
        event['status'] = 'DISPATCHED'
    return event


def _settle_turn(e):
    s, a, turn = _s(e), _a(e), _top(e)
    actor = turn['action_actor_id']
    row, i = _participant(e, actor), s['initiative'][actor]
    rules = _p(e)['category_rules'][turn['category']]
    if rules['consumes_normal_av']:
        i['revision'] += 1
        i['cycle_index'] += 1
        if row['participation'] == 'ENABLED':
            sample = _sample(e, actor)
            i['effective_speed_sample'] = sample
            due = _now(e).add(_op(e, 'speed_to_action_interval', speed=sample['value']))
            _enqueue(e, actor, due)
        else:
            i['normal_entry_id'] = None
            i['due_at'] = None
            if row['participation'] == 'DISABLED':
                sample = _sample(e, actor)
                i['effective_speed_sample'] = sample
                i['disabled_remaining'] = _op(e, 'speed_to_action_interval', speed=sample['value']).to_dict()
                i['disabled_since'] = _now(e).to_dict()
    if rules['counts_normal_turn']:
        s['normal_turn_count'] += 1
    s['action_count'] += 1
    if turn['insertion_id']:
        next(x for x in s['pending_insertions'] if x['insertion_id'] == turn['insertion_id'])['cancellation'] = 'COMPLETED'
    a['event_history'].append({'kind': 'TURN_SETTLED', 'turn_id': turn['turn_id'], 'actor_id': actor,
                               'category': turn['category'], 'clock': copy.deepcopy(s['clock']['now'])})
    turn['phase'] = 'SETTLED'
    s['active_stack'].pop()
    a['selected_action'] = None
    _touch(e)


def _drive_r15(e, budget, callback_budget):
    from .action_scheduler import WorkBudget
    return e.run_until_action_complete(WorkBudget(max_total_transitions=budget, max_task_transitions=budget,
        max_callbacks=callback_budget, max_child_invocations=budget, max_time_advances=budget))


def run_until_decision(e, budget=10000):
    limits = asdict(TurnBudget.read(budget))
    used = dict.fromkeys(limits, 0)
    zero_steps = 0
    while True:
        try:
            _p(e)
            _providers(e)
            s, a, turn = _s(e), _a(e), _top(e)
            if turn and turn['phase'] == 'DECISION' and not a.get('external_boundary'):
                if _participant(e, turn['action_actor_id'])['participation'] != 'ENABLED':
                    def cancel(c):
                        cancelled = _s(c)['active_stack'].pop()
                        _a(c)['event_history'].append({'kind': 'UNSUBMITTED_TURN_CANCELLED',
                            'turn_id': cancelled['turn_id'], 'actor_id': cancelled['action_actor_id'],
                            'reason': 'explicit actor lifecycle output'})
                        _a(c)['selected_action'] = None
                        if cancelled['insertion_id']:
                            request = next(x for x in _s(c)['pending_insertions'] if x['insertion_id'] == cancelled['insertion_id'])
                            request.update(cancellation='CANCELLED', cancellation_reason='ACTOR_UNAVAILABLE_BEFORE_ACTION')
                        _touch(c)
                    _atomic(e, cancel)
                    used['decision_transitions'] += 1
                    zero_steps += 1
                    continue
                if a['stage_status'] != 'RUNNING':
                    raise TurnError('ENTITY_STATE_UNRESOLVED', a['stage_status'] +
                        ': stage transition at an unsubmitted decision requires an explicit continuation/cancellation policy')
                if s['decision'] and s['decision']['kind'] in ('PLAYER_NORMAL_TURN', 'ENEMY_AI_DECISION', 'OUT_OF_TURN_WINDOW', 'PENDING_FORCED_ACTION'):
                    # The same valid boundary is a pure read; external mutations require new permissions.
                    if a.get('decision_context_hash') == _context_hash(e):
                        return _receipt(e)
                    _touch(e)
                controller = _participant(e, turn['action_actor_id'])['controller']
                if turn['category'] == 'FORCED_ACTION' or controller == 'FORCED':
                    kind = 'PENDING_FORCED_ACTION'
                elif turn['category'] != 'NORMAL_TURN':
                    kind = 'OUT_OF_TURN_WINDOW'
                elif controller == 'MONSTER_AI':
                    kind = 'ENEMY_AI_DECISION'
                elif controller == 'PLAYER':
                    kind = 'PLAYER_NORMAL_TURN'
                else:
                    raise TurnError('ENTITY_STATE_UNRESOLVED', 'STAGE controller action provider unresolved')
                return _boundary(e, kind, request={'provider_id': _providers(e).get('monster_decision', {}).get('provider_id', 'explicit-enemy-input-required'),
                    'actor_id': turn['action_actor_id'], 'rng_context': asdict(e.state.rng), 'policy_hash': s['policy_hash']}
                    if kind == 'ENEMY_AI_DECISION' else None)
            if used['decision_transitions'] >= limits['decision_transitions']:
                return _yield(e, 'decision_transitions')
            if zero_steps >= _p(e)['max_zero_time_transitions']:
                return _yield(e, 'zero_time_transitions')
            if turn is None:
                execution = e.state.scheduler.action_execution
                if execution and execution['roots'][execution['current_root']]['status'] != 'ACTION_REFERENCE_COMPLETE':
                    raise TurnError('TURN_OWNER_UNKNOWN', 'unowned R15 root prevents normal turn selection')
                status = a['stage_status']
                if status in ('VICTORY', 'DEFEAT', 'ABORTED'):
                    s['terminal'].update(status=status, reason=a['stage_reason'] or status)
                    e.state.terminal = True
                    return _boundary(e, 'BATTLE_TERMINAL', reason=s['terminal']['reason'])
                if status == 'WAVE_PENDING':
                    s['terminal'].update(status='WAVE_PENDING', reason=a['stage_reason'])
                    s['stage']['pending_request_id'] = s['stage']['pending_request_id'] or 'wave:' + str(s['stage']['generation'])
                    raise TurnError('ENTITY_STATE_UNRESOLVED', 'WAVE_PENDING: explicit stage transition required')
                pending = [x for x in s['pending_insertions'] if x['cancellation'] == 'PENDING']
                if pending:
                    if used['zero_time_insertions'] >= min(limits['zero_time_insertions'], _p(e)['max_zero_time_transitions']):
                        return _yield(e, 'zero_time_insertions')
                    entries = [{'entry_id': x['insertion_id'], 'actor_id': x['action_actor_id'], 'category': x['category'],
                                'due_at': x['due_at'] or x['requested_at'], 'priority': x['priority'],
                                'registration_ordinal': _participant(e, x['action_actor_id'])['registration_ordinal'],
                                'enqueue_ordinal': x['enqueue_ordinal']} for x in pending]
                    entry = _sort(e, entries)[0]
                    insertion = next(x for x in pending if x['insertion_id'] == entry['entry_id'])
                    _atomic(e, lambda c: _make_turn(c, entry, next(x for x in _s(c)['pending_insertions'] if x['insertion_id'] == insertion['insertion_id'])))
                    _a(e)['zero_time_chain'] += 1
                    used['zero_time_insertions'] += 1
                else:
                    if used['normal_turns'] >= limits['normal_turns']:
                        return _yield(e, 'normal_turns')
                    if used['queue_pops'] >= limits['queue_pops']:
                        return _yield(e, 'queue_pops')
                    if not s['normal_queue']:
                        raise TurnError('ENTITY_STATE_UNRESOLVED', 'no eligible participant; explicit stage condition required')
                    entry = s['normal_queue'][0]
                    def select(c):
                        _s(c)['normal_queue'].pop(0)
                        if _eligible(c, entry):
                            _make_turn(c, entry)
                        else:
                            _touch(c)
                    _atomic(e, select)
                    used['queue_pops'] += 1
                    if _top(e):
                        used['normal_turns'] += 1
                used['decision_transitions'] += 1
                zero_steps += 1
                continue
            phase = turn['phase']
            if a.get('external_boundary'):
                kind = 'EXTERNAL'
                event = next(x for x in s['boundary_work'] if x['boundary_id'] == a['external_boundary']['boundary_id'])
                root_id = event['r15_root_id']
            elif phase in ('ACTION_RUNNING', 'ACTION_SUSPENDED'):
                kind, event = None, None
                root_id = turn['action_root_id']
            else:
                kind = {'START_BOUNDARY': 'TURN_START', 'BEFORE_ACTION': 'BEFORE_ACTION',
                        'AFTER_ACTION': 'AFTER_ACTION', 'END_BOUNDARY': 'TURN_END',
                        'DURATION_EXPIRY': 'DURATION_PROGRESS'}.get(phase)
                if kind is None:
                    raise TurnError('TURN_OWNER_UNKNOWN', 'unexpected phase ' + phase)
                if phase == 'DURATION_EXPIRY':
                    plan = a['boundary_plans'].get(turn['turn_id'] + '/DURATION_PROGRESS')
                    if plan and next(x for x in s['boundary_work'] if x['boundary_id'] == plan)['status'] == 'COMMITTED':
                        kind = 'EXPIRY_CHECK'
                rules = _p(e)['category_rules'][turn['category']]
                skip = (kind == 'TURN_START' and not rules['emits_turn_start']) or (kind == 'TURN_END' and not rules['emits_turn_end'])
                if skip:
                    _atomic(e, lambda c: (_top(c).update(phase='DECISION' if kind == 'TURN_START' else 'DURATION_EXPIRY'), _touch(c)))
                    used['decision_transitions'] += 1
                    continue
                if used['scheduler_work'] >= limits['scheduler_work']:
                    return _yield(e, 'scheduler_work')
                _atomic(e, lambda c: _start_boundary(c, _top(c), kind))
                s, a, turn = _s(e), _a(e), _top(e)
                event = _event_plan(e, turn, kind)
                root_id = event['r15_root_id']
            execution = e.state.scheduler.action_execution
            if execution['current_root'] != root_id:
                raise TurnError('TURN_OWNER_UNKNOWN', 'R15 current root differs from exact turn/boundary owner')
            if used['scheduler_work'] >= limits['scheduler_work']:
                return _yield(e, 'scheduler_work')
            before_metrics = copy.deepcopy(execution['metrics'])
            if event is not None:
                event['status'] = 'DRAINING'
            before_hash = e.state.stable_hash()
            result = _drive_r15(e, limits['scheduler_work'] - used['scheduler_work'],
                                limits['boundary_callbacks'] - used['boundary_callbacks'])
            execution = e.state.scheduler.action_execution
            # Scheduler work includes container/event/time transitions, not just leaf nodes.
            used['scheduler_work'] += len(execution['history']) - a.get('scheduler_history_cursor', {}).get(root_id, 0)
            a = _a(e)
            a.setdefault('scheduler_history_cursor', {})[root_id] = len(execution['history'])
            used['boundary_callbacks'] += execution['metrics']['callbacks_completed'] - before_metrics['callbacks_completed']
            if before_hash != e.state.stable_hash():
                _touch(e)
            s, a, turn = _s(e), _a(e), _top(e)
            if result.status == ExecutionStatus.SEMANTIC_GAP:
                return _failure(e, TurnError('SEMANTIC_GAP', result.gap.required_capability), 'R15_' + phase)
            if result.status == ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED:
                return _yield(e, 'scheduler_work_or_callbacks')
            if result.status != ExecutionStatus.ACTION_REFERENCE_COMPLETE:
                barriers = [copy.deepcopy(b) for b in execution['barriers'].values()
                    if b['action_root_id'] == root_id and b['status'] != 'RELEASED']
                if barriers:
                    if phase in ('ACTION_RUNNING', 'ACTION_SUSPENDED'):
                        turn['phase'] = 'ACTION_SUSPENDED'
                    return _boundary(e, 'SUSPENDED_ACTION_INPUT', request={'barriers': barriers, 'r15_status': result.status.value})
                return _failure(e, TurnError('ACTION_NOT_COMPLETE', 'R15 root has no drained original completion request'), 'R15_' + phase)
            def complete(c):
                t, sc, ac = _top(c), _s(c), _a(c)
                if kind is None:
                    if t['completion_consumed'] or root_id in ac['completion_receipts']:
                        raise TurnError('ACTION_NOT_COMPLETE', 'completion receipt already consumed')
                    t['completion_consumed'] = True
                    ac['completion_receipts'].append(root_id)
                    ac['action_history'].append({'root_id': root_id, 'turn_id': t['turn_id'],
                        'actor_id': t['action_actor_id'], 'clock': copy.deepcopy(sc['clock']['now']),
                        'r15_history': copy.deepcopy(c.state.scheduler.action_execution['history']),
                        'completion': 'ACTION_REFERENCE_COMPLETE'})
                    t['phase'] = 'AFTER_ACTION'
                else:
                    ev = (next(x for x in sc['boundary_work'] if x['boundary_id'] == ac['external_boundary']['boundary_id'])
                          if kind == 'EXTERNAL' else _event_plan(c, t, kind))
                    ev['status'] = 'COMMITTED'
                    callbacks = sorted(c.state.scheduler.action_execution['callbacks'].values(),
                                       key=lambda cb: (cb['enqueue_order'], cb['frame_id']))
                    ev['emitted_listener_ids'] = [cb['registration_id'] for cb in callbacks
                        if cb['action_root_id'] == root_id and cb.get('registration_id')]
                    ac['event_history'].append({'kind': kind, 'turn_id': t['turn_id'], 'root_id': root_id,
                        'clock': copy.deepcopy(sc['clock']['now']), 'listener_ids': list(ev['emitted_listener_ids']),
                        'r15_history': copy.deepcopy(c.state.scheduler.action_execution['history'])})
                    if kind == 'EXTERNAL':
                        ac.pop('external_boundary')
                    elif kind == 'TURN_START':
                        t['phase'] = 'DECISION'
                    elif kind == 'BEFORE_ACTION':
                        selected = ac['selected_action']
                        actor, spec, targets = t['action_actor_id'], selected['spec'], selected['targets']
                        if _participant(c, actor)['participation'] != 'ENABLED':
                            # The boundary root has drained, but no content action
                            # began. Lifecycle cancellation consumes no AV/count.
                            sc['active_stack'].pop()
                            ac['selected_action'] = None
                            if t['insertion_id']:
                                request = next(x for x in sc['pending_insertions'] if x['insertion_id'] == t['insertion_id'])
                                request.update(cancellation='CANCELLED', cancellation_reason='ACTOR_UNAVAILABLE_BEFORE_ACTION')
                            ac['event_history'].append({'kind': 'UNSUBMITTED_TURN_CANCELLED',
                                'turn_id': t['turn_id'], 'actor_id': actor, 'reason': 'actor unavailable after BEFORE_ACTION'})
                            _touch(c)
                            return
                        _context(c, t, targets)
                        costs = _cost_nodes(c, spec, actor)
                        from .action_scheduler import start_action, prepend_reference_costs
                        action_id = spec['action_id']
                        if c.actions[action_id].stable_hash() != selected['permission']['action_ir_hash']:
                            raise TurnError('SEMANTIC_GAP', 'content changed after BEFORE_ACTION')
                        t['action_root_id'] = start_action(c, action_id)
                        if costs:
                            prepend_reference_costs(c, costs)
                        t['phase'] = 'ACTION_RUNNING'
                    elif kind == 'AFTER_ACTION':
                        t['phase'] = 'END_BOUNDARY'
                    elif kind == 'TURN_END':
                        t['phase'] = 'DURATION_EXPIRY'
                    elif kind == 'EXPIRY_CHECK':
                        _settle_turn(c)
                _touch(c)
            _atomic(e, complete)
            used['decision_transitions'] += 1
            zero_steps += 1
        except TurnError as exc:
            return _failure(e, exc, 'GLOBAL_TURN')


def run_until_next_turn(e, budget=10000):
    # External decisions are never auto-submitted, including inserted/enemy work.
    return run_until_decision(e, budget)


def is_terminal(e):
    return _s(e)['terminal']['status'] in ('VICTORY', 'DEFEAT', 'ABORTED') and e.state.terminal


def notify_speed_change(e, actor, provider_revision):
    def change(c):
        row, i = _participant(c, actor), _s(c)['initiative'][actor]
        if row['participation'] != 'ENABLED':
            raise TurnError('SPEED_PROVIDER_MISSING', 'disabled/removed speed change unsupported; explicit enable adapter required')
        integer(provider_revision)
        if provider_revision <= _a(c)['speed_revisions'][actor]:
            raise TurnError('SPEED_PROVIDER_MISSING', 'stale speed provider revision')
        sample, old = _sample(c, actor, provider_revision), i['effective_speed_sample']
        active = _top(c) and _top(c)['action_actor_id'] == actor and _top(c)['category'] == 'NORMAL_TURN'
        if not active:
            due = _op(c, 'speed_change_rebase', now=_now(c), due=i['due_at'],
                      old_speed=old['value'], new_speed=sample['value'])
            i['revision'] += 1
            _enqueue(c, actor, due)
        # Active sample may update, but cannot introduce a competing normal entry.
        i['effective_speed_sample'] = sample
        _a(c)['speed_revisions'][actor] = provider_revision
        _touch(c)
        return copy.deepcopy(i)
    return _atomic(e, change, journal='SPEED_CHANGED', arguments={'actor_id': actor, 'provider_revision': provider_revision})


def adjust_readiness(e, actor, kind, fraction, source_ref):
    def adjust(c):
        row, i = _participant(c, actor), _s(c)['initiative'][actor]
        if row['participation'] != 'ENABLED' or (_top(c) and _top(c)['action_actor_id'] == actor):
            raise TurnError('SEMANTIC_GAP', 'readiness adjustment requires enabled waiting actor')
        if not isinstance(source_ref, dict) or not source_ref.get('mapping_id'):
            raise TurnError('AV_REFERENCE_POLICY_MISSING', 'explicit source mapping required')
        mapping = _providers(c)['readiness_sources'].get(source_ref['mapping_id'])
        if (mapping is None or source_ref.get('policy_hash') != stable_hash(mapping) or
                mapping.get('authority') != 'REFERENCE_MODEL' or mapping.get('basis') != 'FULL_CURRENT_INTERVAL' or
                kind not in mapping.get('kinds', [])):
            raise TurnError('AV_REFERENCE_POLICY_MISSING', 'source effect to AV mapping missing or mismatched')
        due = _op(c, 'advance_delay_adjustment', now=_now(c), due=i['due_at'], speed=i['effective_speed_sample']['value'],
                  fraction=fraction, kind=kind)
        i['revision'] += 1
        _enqueue(c, actor, due)
        _touch(c)
        return due.to_dict()
    return _atomic(e, adjust, journal='ADJUST_READINESS', arguments={'actor_id': actor, 'kind': kind,
        'fraction': Rational.read(fraction, _p(e)['numeric']['max_integer_bits']).to_dict(), 'source_ref': source_ref})


def request_insertion(e, insertion):
    insertion = insertion.to_dict() if isinstance(insertion, ActionInsertion) else insertion
    def request(c):
        s, p, a, top = _s(c), _p(c), _a(c), _top(c)
        value = copy.deepcopy(insertion)
        validate_schema(value, {'$ref': '#/$defs/ActionInsertion'}, CONTRACT['state_json_schema'])
        category = value['category']
        if category == 'ULTIMATE_INTERRUPT' or value['placement'] == 'NEXT_SAFE_POINT':
            raise TurnError('INTERRUPT_POLICY_MISSING', 'safe-point R15 interrupt adapter is unavailable')
        rules = p['category_rules'][category]
        row = _participant(c, value['action_actor_id'])
        if (value['policy_id'] != p['identity'] or value['policy_hash'] != s['policy_hash'] or
                value['generation'] != row['generation'] or row['participation'] != 'ENABLED' or
                value['requested_at'] != s['clock']['now'] or value['due_at'] is not None or
                value['cancellation'] != 'PENDING' or value['cancellation_reason'] is not None or
                value['safe_point_token'] is not None or value['insertion_id'] != 'insertion:' + str(s['next_insertion_id']) or
                value['enqueue_ordinal'] != s['next_enqueue_ordinal']):
            raise TurnError('SEMANTIC_GAP', 'invalid insertion identity/generation/time/state')
        for key in ('priority', 'placement', 'consumes_normal_av', 'counts_normal_turn', 'emits_turn_start', 'emits_turn_end'):
            if value[key] != rules[key]:
                raise TurnError('AV_REFERENCE_POLICY_MISSING', 'insertion category flag mismatch ' + key)
        if top:
            if (value['parent_turn_id'] != top['turn_id'] or value['parent_action_root_id'] != top['action_root_id'] or
                    value['owner_actor_id'] != top['turn_owner_actor_id']):
                raise TurnError('TURN_OWNER_UNKNOWN', 'insertion parent/owner mismatch')
            parent_depth = a['insertion_depths'].get(top['insertion_id'], 0)
        else:
            if value['parent_turn_id'] is not None or value['parent_action_root_id'] is not None:
                raise TurnError('TURN_OWNER_UNKNOWN', 'idle insertion cannot name a parent')
            _participant(c, value['owner_actor_id'])
            parent_depth = 0
        if parent_depth + 1 > p['max_insert_depth']:
            raise TurnError('SEMANTIC_GAP', 'insertion depth budget exceeded')
        # Request carries an explicit actor action mapping, not a stale reusable permission.
        if value['action_permission_id'] is not None:
            raise TurnError('SEMANTIC_GAP', 'queued insertion receives a fresh permission at its own decision')
        specs = _providers(c)['availability']['actors'][value['action_actor_id']]['actions']
        actions = [x['action_id'] for x in specs if category in x['categories']]
        if len(actions) != 1:
            raise TurnError('SEMANTIC_GAP', 'insertion needs exactly one explicit category action mapping')
        action_id = actions[0]
        a['insert_actions'][value['insertion_id']] = action_id
        a['insertion_depths'][value['insertion_id']] = parent_depth + 1
        s['pending_insertions'].append(value)
        _id(s, 'insertion')
        s['next_enqueue_ordinal'] += 1
        _touch(c)
        return copy.deepcopy(value)
    return _atomic(e, request, journal='INSERT_ACTION', arguments={'insertion': insertion})


def lifecycle(e, actor, operation, *, source_ref, binding=None):
    def apply(c):
        if source_ref.get('authority') != 'EXPLICIT_SCENARIO_INPUT' or not source_ref.get('source'):
            raise TurnError('ENTITY_STATE_UNRESOLVED', 'explicit lifecycle source required')
        if operation == 'REGISTER_ENTITY':
            _register(c, binding)
            _touch(c)
            return
        s, row = _s(c), _participant(c, actor)
        i = s['initiative'][actor]
        active = _top(c) and _top(c)['action_actor_id'] == actor
        if operation in ('DEFEAT', 'REMOVE_ENTITY'):
            row['participation'] = 'REMOVED'
            row['generation'] += 1
            row['entity_revision'] += 1
            i.update(generation=row['generation'], due_at=None, normal_entry_id=None, revision=i['revision'] + 1)
            s['normal_queue'] = [x for x in s['normal_queue'] if x['actor_id'] != actor]
            for x in s['pending_insertions']:
                if (x['action_actor_id'] == actor or x['owner_actor_id'] == actor) and x['cancellation'] == 'PENDING':
                    x.update(cancellation='CANCELLED', cancellation_reason=operation)
            if operation == 'DEFEAT':
                c.state.entities[actor]['alive'] = False
            if active and _top(c)['phase'] in ('START_BOUNDARY', 'DECISION', 'BEFORE_ACTION') and not _top(c)['action_root_id']:
                # No admitted R15 content root to settle. A pending boundary root is retained.
                if not any(x['turn_id'] == _top(c)['turn_id'] and x['status'] in ('DISPATCHED', 'DRAINING') for x in s['boundary_work']):
                    s['active_stack'].pop()
                    _a(c)['selected_action'] = None
        elif operation == 'DISABLE':
            if row['participation'] != 'ENABLED' or active:
                raise TurnError('ENTITY_STATE_UNRESOLVED', 'disable requires waiting enabled actor')
            i.update(disabled_remaining=_op(c, 'remaining_time_update', now=_now(c), due=i['due_at']).to_dict(),
                     disabled_since=_now(c).to_dict(), due_at=None, normal_entry_id=None, revision=i['revision'] + 1)
            row['participation'] = 'DISABLED'
            row['entity_revision'] += 1
            s['normal_queue'] = [x for x in s['normal_queue'] if x['actor_id'] != actor]
            for x in s['pending_insertions']:
                if (x['action_actor_id'] == actor or x['owner_actor_id'] == actor) and x['cancellation'] == 'PENDING':
                    x.update(cancellation='CANCELLED', cancellation_reason='DISABLE')
        elif operation == 'REVIVE':
            if row['participation'] != 'REMOVED' or active or not isinstance(binding, dict):
                raise TurnError('ENTITY_STATE_UNRESOLVED', 'revive needs removed actor and explicit new-generation inputs')
            if binding.get('generation') != row['generation'] + 1 or binding.get('content_version') != row['authority']['source_version']:
                raise TurnError('ENTITY_STATE_UNRESOLVED', 'revive generation/version mismatch')
            # Existing HP/resources are not rolled back; caller supplies explicit revive HP.
            hp = raw_checked(binding['hp_raw'])
            if not 0 < hp <= c.state.properties[actor]['max_hp']:
                raise TurnError('ENTITY_STATE_UNRESOLVED', 'explicit positive revive HP bounds required')
            c.state.properties[actor]['hp'], c.state.entities[actor]['alive'] = hp, True
            row.update(generation=binding['generation'], participation='ENABLED', entity_revision=row['entity_revision'] + 1)
            i.update(generation=row['generation'], revision=i['revision'] + 1, disabled_remaining=None, disabled_since=None)
            sample = _sample(c, actor)
            i['effective_speed_sample'] = sample
            _enqueue(c, actor, _now(c).add(_op(c, 'speed_to_action_interval', speed=sample['value'])))
        elif operation == 'ENABLE':
            if row['participation'] != 'DISABLED' or active:
                raise TurnError('ENTITY_STATE_UNRESOLVED', 'enable requires disabled waiting actor')
            sample = _sample(c, actor)
            remaining = _q(c, i['disabled_remaining']).mul(i['effective_speed_sample']['value']).div(sample['value'])
            i.update(effective_speed_sample=sample, disabled_remaining=None, disabled_since=None, revision=i['revision'] + 1)
            row.update(participation='ENABLED', entity_revision=row['entity_revision'] + 1)
            _enqueue(c, actor, _now(c).add(remaining))
        else:
            raise TurnError('ENTITY_STATE_UNRESOLVED', 'unsupported lifecycle operation')
        c.state.entities[row['entity_ref']]['reference_entity_revision'] = row['entity_revision']
        _touch(c)
        return copy.deepcopy(row)
    return _atomic(e, apply, journal=operation if operation != 'ENABLE' else 'DISABLE',
        arguments={'actor_id': actor, 'operation': operation, 'source_ref': source_ref, 'binding': binding})


def stage_transition(e, status, *, source_ref, reason=None):
    def apply(c):
        if (source_ref.get('provider_id') != _p(c)['terminal_provider_id'] or
                source_ref.get('policy_hash') != stable_hash(_providers(c)['stage']) or
                status not in ('RUNNING', 'WAVE_PENDING', 'VICTORY', 'DEFEAT', 'ABORTED')):
            raise TurnError('ENTITY_STATE_UNRESOLVED', 'explicit matched stage provider output required')
        s, a = _s(c), _a(c)
        a['stage_status'], a['stage_reason'] = status, reason
        s['stage']['generation'] += 1
        s['stage']['pending_request_id'] = 'wave:' + str(s['stage']['generation']) if status == 'WAVE_PENDING' else None
        s['terminal'].update(status='WAVE_PENDING' if status == 'WAVE_PENDING' else 'RUNNING', reason=reason)
        _touch(c)
    return _atomic(e, apply, journal='STAGE_TRANSITION', arguments={'status': status, 'source_ref': source_ref, 'reason': reason})


def enemy_decision(e, provider=None):
    """Deterministic explicit MonsterDecisionProvider. Output uses normal submission."""
    b = _s(e)['decision']
    if not b or b['kind'] != 'ENEMY_AI_DECISION':
        raise TurnError('SEMANTIC_GAP', 'enemy decision boundary required')
    spec = _providers(e).get('monster_decision')
    if spec is None:
        return _receipt(e)
    if not spec.get('provider_id') or not spec.get('version') or spec.get('authority') != 'REFERENCE_MODEL':
        raise TurnError('SEMANTIC_GAP', 'versioned deterministic MonsterDecisionProvider required')
    candidates = legal_action_candidates(e, b['decision_id'])
    snapshot = copy.deepcopy(e.snapshot())
    if provider is None:
        if spec.get('mode') != 'FIRST_PERMISSION_REFERENCE' or not candidates:
            raise TurnError('SEMANTIC_GAP', 'explicit deterministic provider implementation missing')
        output = {'permission': candidates[0], 'targets': candidates[0]['target_ids'][:1]}
    else:
        if getattr(provider, 'identity', None) != spec:
            raise TurnError('SEMANTIC_GAP', 'MonsterDecisionProvider identity mismatch')
        output = provider.choose(snapshot=snapshot, actor_id=b['actor_id'], permissions=copy.deepcopy(candidates),
            policy_identity={'id': _s(e)['policy_id'], 'hash': _s(e)['policy_hash']}, rng_context=asdict(e.state.rng))
    return submit_action(e, output['permission'], output['targets'], b['state_revision'])


def dispatch_turn_event(e, event_key, payload=None):
    """Admit an explicit external modifier event at a drained decision safe point.

    It is an R15 boundary envelope with replayable R17 callbacks. It grants no
    action interruption and provides no implicit mapping for native event IDs.
    """
    def dispatch(c):
        from .action_scheduler import start_reference_envelope
        s, a, top = _s(c), _a(c), _top(c)
        if not top or top['phase'] != 'DECISION' or a.get('external_boundary'):
            raise TurnError('INTERRUPT_POLICY_MISSING', 'external event requires drained decision boundary')
        mapping = _providers(c).get('external_events', {}).get(event_key)
        if not mapping or mapping.get('authority') != 'EXPLICIT_SCENARIO_INPUT':
            raise TurnError('TURN_BOUNDARY_EVENT_UNKNOWN', 'explicit external reference event mapping required')
        event = {'boundary_id': _id(s, 'event'), 'turn_id': top['turn_id'], 'event_kind': 'BEFORE_ACTION',
            'reference_event_key': event_key, 'owner_actor_id': top['turn_owner_actor_id'],
            'action_actor_id': top['action_actor_id'], 'normal_turn_index': top['normal_turn_index'],
            'event_ordinal': len(s['boundary_work']), 'status': 'DISPATCHED', 'r15_root_id': None,
            'listener_policy_hash': _p(c)['boundary_listener_policy_hash'], 'emitted_listener_ids': [],
            'duration_instance_cursor': 0, 'authority': 'REFERENCE_MODEL'}
        _context(c, top)
        nodes = [_node(c, event['boundary_id'] + '/external', 'modifier_event_dispatch',
            {'event_id': event_key, 'source': top['action_actor_id'], 'target': top['action_actor_id'],
             'payload': copy.deepcopy(payload or {}), 'drain_before_resume_reference': True})]
        nodes += c.events.get(event_key, [])
        event['r15_root_id'] = start_reference_envelope(c, event['boundary_id'], nodes, boundary=event)
        s['boundary_work'].append(event)
        a['external_boundary'] = {'boundary_id': event['boundary_id']}
        _touch(c)
        return copy.deepcopy(event)
    return _atomic(e, dispatch, journal='SAFE_POINT', arguments={'event_key': event_key, 'payload': payload})


def validate_runtime(e, *, strict_queue=False):
    if KEY not in e.state.mechanics:
        return
    s, p = _s(e), _p(e)
    # R21 POLICY-ONLY sample snapshots need no R22 provider adapter to remain compatible.
    validate_schema(s, CONTRACT['state_json_schema'])
    bits = p['numeric']['max_integer_bits']
    def visit(value):
        if isinstance(value, dict):
            if set(value) == {'n', 'd'}:
                Rational.read(value, bits)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, float):
            raise TurnError('SEMANTIC_GAP', 'float in turn state')
        elif type(value) is int:
            integer(value, -((1 << bits) - 1), bits)
    visit(s)
    if ADAPTER not in e.state.mechanics:
        return
    validate_policy(p, _providers(e))
    ids = [x['actor_id'] for x in s['participants']]
    ordinals = [x['registration_ordinal'] for x in s['participants']]
    if len(ids) != len(set(ids)) or len(ordinals) != len(set(ordinals)) or set(ids) != set(s['initiative']):
        raise TurnError('INITIATIVE_INPUT_MISSING', 'participant identity/cardinality')
    if len(s['active_stack']) > 1:
        raise TurnError('INTERRUPT_POLICY_MISSING', 'R22 has no parent suspension adapter')
    if s['normal_queue'] != _sort(e, s['normal_queue']):
        raise TurnError('SEMANTIC_GAP', 'noncanonical queue')
    entries = s['normal_queue']
    if len({x['entry_id'] for x in entries}) != len(entries):
        raise TurnError('SEMANTIC_GAP', 'duplicate entry ID')
    for row in s['participants']:
        actor, i = row['actor_id'], s['initiative'][row['actor_id']]
        if row['generation'] != i['generation']:
            raise TurnError('SEMANTIC_GAP', 'initiative generation mismatch')
        active_normal = _top(e) and _top(e)['category'] == 'NORMAL_TURN' and _top(e)['action_actor_id'] == actor
        expected = int(row['participation'] == 'ENABLED' and not active_normal)
        if sum(x['actor_id'] == actor and _eligible(e, x) for x in entries) != expected:
            raise TurnError('SEMANTIC_GAP', 'live normal entry cardinality')
    if strict_queue and any(not _eligible(e, x) for x in entries):
        raise TurnError('SEMANTIC_GAP', 'stale queue entry on restore')
    b = s['decision']
    if b:
        kinds = ('PLAYER_NORMAL_TURN', 'ENEMY_AI_DECISION', 'OUT_OF_TURN_WINDOW', 'PENDING_FORCED_ACTION')
        if b['kind'] == 'SEMANTIC_GAP' and (b['failure'] is None or b['candidate_permission_ids']):
            raise TurnError('SEMANTIC_GAP', 'gap boundary exclusivity')
        if b['kind'] not in kinds and b['candidate_permission_ids']:
            raise TurnError('SEMANTIC_GAP', 'non-action boundary permissions')
        if b['kind'] == 'BATTLE_TERMINAL' and (not is_terminal(e) or _top(e) or b['actor_id'] is not None):
            raise TurnError('SEMANTIC_GAP', 'terminal requires settled explicit stage declaration')


def record_command(e, kind, arguments):
    """External full public command receipt; posthash never enters hashed state."""
    prehash = e.stable_hash()
    args = copy.deepcopy(arguments)
    mapping = {'initialize': e.initialize_turns, 'advance': e.run_until_decision, 'complete': e.run_until_next_turn,
               'submit': e.submit_action, 'speed_change': e.notify_speed_change, 'adjust': e.adjust_readiness,
               'insertion': e.request_insertion, 'lifecycle': e.turn_lifecycle, 'stage': e.turn_stage_transition,
               'enemy': e.request_enemy_decision, 'release_barrier': e.release_action_barrier,
               'modifier_event': e.dispatch_turn_event}
    result = mapping[kind](**args)
    return {'schema': 'r22_public_command_receipt/1', 'kind': kind, 'arguments': args,
            'prehash': prehash, 'posthash': e.stable_hash()}, result


def replay_commands(e, receipts):
    runtime = e.clone()
    outputs = []
    for expected in receipts:
        if runtime.stable_hash() != expected['prehash']:
            raise TurnError('SEMANTIC_GAP', 'replay prehash mismatch')
        observed, output = record_command(runtime, expected['kind'], expected['arguments'])
        if observed != expected:
            raise TurnError('SEMANTIC_GAP', 'replay external receipt mismatch')
        outputs.append(output)
    return runtime, tuple(outputs)
