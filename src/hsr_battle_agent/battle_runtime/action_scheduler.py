"""Reference action scheduling inside BehaviorRuntime; no battle turn/AV binding."""
from __future__ import annotations
import copy
from dataclasses import asdict, dataclass, field
from hsr_battle_agent.battle_ir.behavior import IRNode, TaskSequenceIR, canonical_json, stable_hash
from .behavior import ExecutionResult, ExecutionStatus, GapError
from .behavior_primitives import raw_checked, NumericSemanticGap

POLICY_ID = 'r15_action_scheduler_reference_v1'
ORDER = ['TASK_CONTINUATIONS', 'EVENT_CALLBACKS', 'CHILD_ABILITIES', 'LOGICAL_TIME']

class SerializableFrame:
    def snapshot(self):
        return copy.deepcopy(asdict(self))

    def clone(self):
        return type(self)(**self.snapshot())

    def stable_hash(self):
        return stable_hash(self.snapshot())

    @classmethod
    def from_snapshot(cls, value):
        canonical_json(value)
        return cls(**copy.deepcopy(value))


@dataclass
class OwnedFrame(SerializableFrame):
    frame_id: str
    action_root_id: str
    ability_instance_id: str
    task_frame_id: str | None
    parent_ability_id: str | None
    parent_task_id: str | None
    controller_owner: str
    callback_owner: str | None = None
    status: str = 'READY'

@dataclass
class TaskFrame(OwnedFrame):
    node: dict = field(default_factory=dict)
    sequence_frame_id: str = ''
    wait_kind: str | None = None
    wait_id: str | None = None
    children: list[str] = field(default_factory=list)

@dataclass
class SequenceFrame(OwnedFrame):
    nodes: list[dict] = field(default_factory=list)
    cursor: int = 0
    active_task_id: str | None = None
    ancestor_nodes: list[str] = field(default_factory=list)

@dataclass
class AbilityExecution(OwnedFrame):
    identity: str = ''
    node: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    sequence_frame_id: str | None = None
    children: list[str] = field(default_factory=list)
    invocation_path: list[str] = field(default_factory=list)
    completion_requested: bool = False

@dataclass
class ChildAbilityFrame(OwnedFrame):
    child_ability_id: str = ''
    resume_condition: str = ''

@dataclass
class Barrier(OwnedFrame):
    classification: str = ''
    release_key: str = ''
    due_time: int | None = None

@dataclass
class ScheduledContinuation(OwnedFrame):
    due_time: int = 0
    enqueue_order: int = 0
    barrier_id: str | None = None
    nodes: list[dict] = field(default_factory=list)
    context: dict = field(default_factory=dict)

@dataclass
class CallbackFrame(OwnedFrame):
    enqueue_order: int = 0
    stable_order_key: list = field(default_factory=list)
    source_event: dict = field(default_factory=dict)
    callback_ir: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    sequence_frame_id: str | None = None
    callback_path: list[str] = field(default_factory=list)
    modifier_instance_id: str | None = None
    registration_id: str | None = None

@dataclass
class CompletionRequest(OwnedFrame):
    source_node: dict = field(default_factory=dict)
    signal: str = 'COMPLETION_REQUEST'

@dataclass
class ActionExecutionRoot(SerializableFrame):
    action_root_id: str
    action_id: str
    root_ability_id: str
    policy_identity: str
    status: str = 'RUNNING'
    completion_requested: bool = False
    semantic_authority: str = 'REFERENCE_MODEL'

@dataclass(frozen=True)
class WorkBudget(SerializableFrame):
    max_task_transitions: int = 10000
    max_callbacks: int = 10000
    max_child_invocations: int = 10000
    max_time_advances: int = 10000
    max_total_transitions: int = 10000

    def __post_init__(self):
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in asdict(self).values()):
            raise ValueError('nonnegative integer scheduler budgets required')


def reference_policy():
    """Explicit caller policy. Logical units have no native second/FPS/AV meaning."""
    return {'identity': POLICY_ID, 'semantic_authority': 'REFERENCE_MODEL',
        'battle_turn_scheduler': 'NOT_YET_BOUND_FROM_REAL_CONTENT', 'processing_order': ORDER.copy(),
        'logical_time': 'NONNEGATIVE_INTEGER_RAW_REFERENCE_UNITS',
        'invocation': {'owner': 'INHERIT_EXPLICIT', 'caster': 'INHERIT_EXPLICIT',
            'ability_target': 'RESOLVED_ORDERED_LIST', 'skill_targets': 'INHERIT_EXPLICIT',
            'param_entity_stack': 'INHERIT_EXPLICIT', 'parameters': 'INHERIT_EXPLICIT',
            'dynamic_provider_parent': 'EXPLICIT_SHARED', 'rng': 'SHARED_REFERENCE_STREAM',
            'event_scope': 'ACTION_OWNED', 'scheduler_ownership': 'SAME_ACTION_ROOT',
            'controller': 'REFERENCE_CHILD', 'parent_resume': 'WAIT_CHILD_TREE_REFERENCE'},
        'max_ability_depth': 16, 'max_task_depth': 64, 'max_template_depth': 16,
        'max_callback_depth': 32, 'role_bindings': {}, 'waits': {}, 'presentation': {}}


def _policy(engine):
    p = engine.policies.get(POLICY_ID)
    if not isinstance(p, dict) or p.get('identity') != POLICY_ID or p.get('processing_order') != ORDER:
        raise ValueError('explicit versioned R15 reference policy and ordering required')
    if p.get('semantic_authority') != 'REFERENCE_MODEL' or p.get('logical_time') != 'NONNEGATIVE_INTEGER_RAW_REFERENCE_UNITS':
        raise ValueError('R15 reference authority/logical unit policy required')
    for key in ('max_ability_depth', 'max_task_depth', 'max_template_depth', 'max_callback_depth'):
        if isinstance(p.get(key), bool) or not isinstance(p.get(key), int) or p[key] <= 0:
            raise ValueError('positive scheduler depth bounds required')
    canonical_json(p)
    return p


def _data(engine):
    return engine.state.scheduler.action_execution


def _id(d, prefix):
    d['next_id'] += 1
    return prefix + ':' + str(d['next_id'])


def _ownership(d, aid, tid=None, callback=None):
    a = d['abilities'][aid]
    return dict(action_root_id=a['action_root_id'], ability_instance_id=aid,
        task_frame_id=tid, parent_ability_id=a['parent_ability_id'], parent_task_id=a['parent_task_id'],
        controller_owner=aid, callback_owner=callback)


def _sequence(d, aid, nodes, *, tid=None, callback=None, ancestors=()):
    sid = _id(d, 'sequence')
    d['sequences'][sid] = asdict(SequenceFrame(sid, **_ownership(d, aid, tid, callback),
        nodes=[n.to_dict() for n in nodes], ancestor_nodes=list(ancestors)))
    d['task_queue'].append(sid)
    return sid


def _new_ability(d, root, node, context, identity, parent=None, tid=None, path=()):
    aid = _id(d, 'ability')
    context = copy.deepcopy(context)
    context.update(current_ability=identity, ability_instance_id=aid, action_root_id=root,
                   parent_ability_id=parent, parent_task_id=tid)
    d['abilities'][aid] = asdict(AbilityExecution(aid, root, aid, tid, parent, tid, aid,
        identity=identity, node=node.to_dict(), context=context, invocation_path=list(path) + [identity]))
    d['child_queue'].append(aid)
    if parent:
        d['abilities'][parent]['children'].append(aid)
        d['metrics']['abilities_invoked'] += 1
    return aid


def start_action(engine, action_id):
    _policy(engine)
    if action_id not in engine.legal_actions():
        raise ValueError('action is not available')
    previous = _data(engine)
    if engine.state.scheduler.continuation or engine.state.scheduler.callbacks or engine.state.pending_events:
        raise ValueError('legacy pending work must be drained before R15 action')
    d = {'schema': 'action_execution_scheduler/1', 'policy_identity': POLICY_ID,
        'logical_time': previous.get('logical_time', 0), 'next_id': previous.get('next_id', 0),
        'next_enqueue': 0, 'roots': {}, 'abilities': {}, 'tasks': {}, 'sequences': {},
        'child_frames': {}, 'barriers': {}, 'continuations': {}, 'callbacks': {}, 'events': {},
        'completion_requests': {}, 'task_queue': [], 'child_queue': [], 'event_queue': [],
        'callback_queue': [], 'time_queue': [], 'history': [], 'metrics': {
            'tasks_reached': 0, 'tasks_completed': 0, 'abilities_invoked': 0,
            'child_abilities_completed': 0, 'barriers_encountered': 0, 'callbacks_completed': 0,
            'logical_time_advances': 0}}
    if previous:
        # Preserve other action-owned work and completed frame relationships.
        # The current drive selects only the new root's queues.
        metrics = d['metrics']
        d = copy.deepcopy(previous)
        d['metrics'] = metrics
        d['history'] = []
    rid = _id(d, 'action')
    d['current_root'] = rid
    root_node = engine.actions[action_id]
    root_identity = root_node.payload.get('content_name') or action_id
    aid = _new_ability(d, rid, root_node, engine.state.target_context, 'ability:' + root_identity)
    d['roots'][rid] = asdict(ActionExecutionRoot(rid, action_id, aid, POLICY_ID))
    engine.state.scheduler.action_execution = d
    engine.state.scheduler.completion_requested = False
    engine.trace = []
    return rid


def start_reference_envelope(engine, identity, nodes, *, boundary):
    """R22 explicit boundary root in the existing scheduler, never content repair.

    The envelope owns its completion signal; original Ability IR is unchanged.
    Every callback, child, barrier and transaction still passes R15's drain gate.
    """
    from hsr_battle_agent.battle_ir.behavior import AbilityIR, TaskIR, Authority
    authority = Authority('REFERENCE_MODEL', 'r22', 'reference boundary envelope',
                          boundary['listener_policy_hash'], semantic_status='REFERENCE_MODEL')
    node = AbilityIR(identity, 'ability', authority, {'tasks': TaskSequenceIR(
        identity + '/sequence', 'immediate_sequence', authority, {'tasks': list(nodes) + [
            TaskIR(identity + '/envelope-completion', 'completion', authority,
                   {'authority': 'EXPLICIT_REFERENCE_BOUNDARY_ROOT'})]})})
    if identity in engine.actions:
        raise ValueError('boundary identity collides with caller content')
    engine.actions[identity] = node
    try:
        root_id = start_action(engine, identity)
        _data(engine)['roots'][root_id]['reference_turn_boundary'] = copy.deepcopy(boundary)
        return root_id
    finally:
        del engine.actions[identity]


def prepend_reference_costs(engine, nodes):
    """Execute explicit R20 source costs before the original root Ability entry.

    Costs are owned by that root. They are not inserted into or hashed as source
    content, and do not provide a missing action completion request.
    """
    d = _data(engine)
    root = d['roots'][d['current_root']]
    ability = d['abilities'][root['root_ability_id']]
    if ability['status'] != 'READY' or ability['sequence_frame_id'] is not None:
        raise ValueError('cost admission precedes original ability execution')
    ability['reference_admission_costs'] = [node.to_dict() for node in nodes]


def _roles(node, policy):
    p = node.payload
    values = dict(p.get('fields', {}))
    values.update(p.get('roles', {}))
    values.update(p.get('reference_binding', {}).get('roles', {}))
    binding = policy.get('role_bindings', {}).get(node.op, {})
    for slot in p.get('reference_binding', {}).get('unknown_slots', []):
        mask = str(slot['mask'])
        role = binding.get('slots', {}).get(mask)
        if role is None:
            if mask not in binding.get('structure_only_masks', []):
                raise GapError(node, 'scheduler operand policy for anonymous mask:' + mask)
            continue
        values[role] = values['unbound_bit_' + str(slot['field_index'])]
    return values


def _required(node, values, key):
    if key not in values:
        raise GapError(node, 'explicit scheduler reference input:' + key)
    return values[key]


def _integer(node, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GapError(node, 'nonnegative integer logical duration')
    return value


def _callback(d, aid, tid, node, context, source, path=(), owner=None, modifier=None, registration=None):
    cid = _id(d, 'callback')
    ordinal = d['next_enqueue']
    d['next_enqueue'] += 1
    d['callbacks'][cid] = asdict(CallbackFrame(cid, **_ownership(d, aid, tid, owner or aid),
        enqueue_order=ordinal, stable_order_key=[ordinal, cid], source_event=copy.deepcopy(source),
        callback_ir=node.to_dict(), context=copy.deepcopy(context), callback_path=list(path),
        modifier_instance_id=modifier, registration_id=registration))
    d['callback_queue'].append(cid)
    return cid


def _owned_event(engine, d, t, node, nodes, path, p, source):
    """One R15 event queue for legacy events and modifier lifecycle callbacks."""
    if node.stable_hash() in path or len(path) >= p['max_callback_depth']:
        raise GapError(node, 'SCHEDULER_CALLBACK_CYCLE_OR_DEPTH')
    eid = _id(d, 'event')
    d['events'][eid] = dict(_ownership(d, t['ability_instance_id'], t['frame_id'], t['callback_owner']),
        frame_id=eid, status='READY', source_event=copy.deepcopy(source), nodes=[n.to_dict() for n in nodes], cursor=0,
        context=copy.deepcopy(engine.state.target_context), callback_path=path + [node.stable_hash()])
    d['events'][eid]['source_event']['r15_event_id'] = eid
    d['event_queue'].append(eid)
    return eid


def _time_entry(d, aid, tid, due, barrier=None, nodes=(), context=None, callback=None):
    eid = _id(d, 'continuation')
    ordinal = d['next_enqueue']
    d['next_enqueue'] += 1
    d['continuations'][eid] = asdict(ScheduledContinuation(eid,
        **_ownership(d, aid, tid, callback), due_time=due, enqueue_order=ordinal,
        barrier_id=barrier, nodes=[n.to_dict() for n in nodes], context=copy.deepcopy(context or {})))
    d['time_queue'].append(eid)
    d['time_queue'].sort(key=lambda i: (d['continuations'][i]['due_time'], d['continuations'][i]['enqueue_order']))
    return eid


def _barrier(d, task, classification, key, due=None):
    bid = _id(d, 'barrier')
    d['barriers'][bid] = asdict(Barrier(bid,
        **_ownership(d, task['ability_instance_id'], task['frame_id'], task['callback_owner']),
        status='WAITING', classification=classification, release_key=key, due_time=due))
    task.update(status='WAITING', wait_kind='BARRIER', wait_id=bid)
    d['metrics']['barriers_encountered'] += 1
    if due is not None:
        _time_entry(d, task['ability_instance_id'], task['frame_id'], due, bid, callback=task['callback_owner'])
    return bid


def release_barrier(engine, barrier_id):
    d = _data(engine)
    b = d['barriers'][barrier_id]
    if b['action_root_id'] != d['current_root']:
        raise ValueError('barrier belongs to a different action')
    b['status'] = 'RELEASED'


def _finish_task(d, t):
    t['status'] = 'TASK_COMPLETE'
    s = d['sequences'][t['sequence_frame_id']]
    s['cursor'] += 1
    s['active_task_id'] = None
    if s['frame_id'] not in d['task_queue']:
        d['task_queue'].append(s['frame_id'])
    if not t.get('container'):
        d['metrics']['tasks_completed'] += 1
    d['history'].append({'task': t['frame_id'], 'node': t['node']['node_id'],
                         'op': t['node']['op'], 'time': d['logical_time'], 'status': 'TASK_COMPLETE'})


def _tree_done(d, aid):
    a = d['abilities'][aid]
    return a['status'] == 'ABILITY_COMPLETE' and all(_tree_done(d, c) for c in a['children'])


def _settle(d, state):
    rid = d['current_root']
    changed = True
    while changed:
        changed = False
        for t in d['tasks'].values():
            if t['action_root_id'] != rid or t['status'] != 'WAITING':
                continue
            mode, key = t['wait_kind'], t['wait_id']
            done = mode == 'BARRIER' and d['barriers'][key]['status'] == 'RELEASED'
            if mode == 'SEQUENCES':
                done = all(d['sequences'][s]['status'] == 'SEQUENCE_COMPLETE' for s in t['children'])
            if mode == 'EVENT_DRAIN_REFERENCE':
                done = d['events'][key]['status'] == 'COMPLETE' and all(
                    c['status'] in ('CALLBACK_COMPLETE', 'CALLBACK_CANCELLED_REFERENCE')
                    for c in d['callbacks'].values() if c['source_event'].get('r15_event_id') == key)
            if mode in ('WAIT_CHILD_REFERENCE', 'WAIT_CHILD_TREE_REFERENCE'):
                child = d['child_frames'][key]['child_ability_id']
                done = d['abilities'][child]['status'] == 'ABILITY_COMPLETE' if mode == 'WAIT_CHILD_REFERENCE' else _tree_done(d, child)
                if done:
                    d['child_frames'][key]['status'] = 'RELATIONSHIP_SATISFIED'
            if done:
                _finish_task(d, t)
                changed = True
        for c in d['callbacks'].values():
            if c['action_root_id'] == rid and c['status'] == 'RUNNING' and d['sequences'][c['sequence_frame_id']]['status'] == 'SEQUENCE_COMPLETE':
                owned_pending = any(other['callback_owner'] == c['frame_id'] and other['status'] not in ('CALLBACK_COMPLETE', 'CALLBACK_CANCELLED_REFERENCE') for other in d['callbacks'].values())
                owned_pending |= any(e['callback_owner'] == c['frame_id'] and e['status'] != 'COMPLETE' for e in d['events'].values())
                owned_pending |= any(e['callback_owner'] == c['frame_id'] and e['status'] != 'COMPLETE' for e in d['continuations'].values())
                owned_pending |= any(a['callback_owner'] == c['frame_id'] and not _tree_done(d, a['frame_id']) for a in d['abilities'].values())
                if not owned_pending:
                    c['status'] = 'CALLBACK_COMPLETE'
                    d['metrics']['callbacks_completed'] += 1
                    if c.get('modifier_instance_id'):
                        key = 'modifier_callbacks_completed'
                        d['metrics'][key] = d['metrics'].get(key, 0) + 1
                    changed = True
        for a in d['abilities'].values():
            sid = a['sequence_frame_id']
            if a['action_root_id'] != rid or a['status'] != 'RUNNING' or sid is None or d['sequences'][sid]['status'] != 'SEQUENCE_COMPLETE':
                continue
            aid = a['frame_id']
            own_pending = any(c['ability_instance_id'] == aid and c['status'] not in ('CALLBACK_COMPLETE', 'CALLBACK_CANCELLED_REFERENCE') for c in d['callbacks'].values())
            own_pending |= any(e['ability_instance_id'] == aid and e['status'] != 'COMPLETE' for e in d['events'].values())
            own_pending |= any(e['ability_instance_id'] == aid and e['status'] != 'COMPLETE' for e in d['continuations'].values())
            own_pending |= any(r['status'] != 'COMPLETE' and r['request']['payload']['ownership']['ability_instance_id'] == aid
                               for r in state.damage_requests.values())
            if not own_pending:
                a['status'] = 'ABILITY_COMPLETE'
                if a['parent_ability_id']:
                    d['metrics']['child_abilities_completed'] += 1
                changed = True
    for f in d['child_frames'].values():
        if f['action_root_id'] == rid and f['resume_condition'] == 'FIRE_AND_CONTINUE_REFERENCE' and _tree_done(d, f['child_ability_id']):
            f['status'] = 'RELATIONSHIP_SATISFIED'
    root = d['roots'][d['current_root']]
    rid = root['action_root_id']
    owned_done = all(a['status'] == 'ABILITY_COMPLETE' for a in d['abilities'].values() if a['action_root_id'] == rid)
    owned_done &= all(t['status'] == 'TASK_COMPLETE' for t in d['tasks'].values() if t['action_root_id'] == rid)
    owned_done &= all(b['status'] == 'RELEASED' for b in d['barriers'].values() if b['action_root_id'] == rid)
    owned_done &= all(s['status'] == 'SEQUENCE_COMPLETE' for s in d['sequences'].values() if s['action_root_id'] == rid)
    owned_done &= all(c['status'] in ('CALLBACK_COMPLETE', 'CALLBACK_CANCELLED_REFERENCE') for c in d['callbacks'].values() if c['action_root_id'] == rid)
    owned_done &= all(e['status'] == 'COMPLETE' for e in d['events'].values() if e['action_root_id'] == rid)
    owned_done &= all(e['status'] == 'COMPLETE' for e in d['continuations'].values() if e['action_root_id'] == rid)
    owned_done &= all(f['status'] == 'RELATIONSHIP_SATISFIED' for f in d['child_frames'].values() if f['action_root_id'] == rid)
    owned_done &= not state.damage_transactions and not state.pending_events
    owned_done &= all(r['status'] == 'COMPLETE' for r in state.damage_requests.values()
                      if r['request']['payload']['ownership']['action_root_id'] == rid)
    if root['completion_requested'] and owned_done:
        root['status'] = 'ACTION_REFERENCE_COMPLETE'


def _serialized_template_parameters(engine, node, binding):
    """Evaluate original compiled dictionaries only under a hash-keyed policy."""
    if (binding.get('caller_context') != 'INHERIT_EXPLICIT' or
            binding.get('provider_inheritance') != 'INHERIT_EXPLICIT' or
            binding.get('dictionary_masks') != {'4':'numeric', '8':'string', '32':'sequence'}):
        raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: explicit serialized dictionary roles required')
    fields = node.payload.get('decoded', {}).get('structure', {}).get('fields', [])
    slots = node.payload.get('reference_binding', {}).get('unknown_slots', [])
    result = copy.deepcopy(binding)
    result.update(parameters={}, numeric_parameters={}, string_parameters={}, sequence_parameters={})
    for f in fields:
        mask = str(f['mask'])
        if mask in ('1', '2'): continue
        if mask not in binding['dictionary_masks']:
            raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: unbound serialized context mask:'+mask)
        slot = next((s for s in slots if str(s['mask'])==mask), None)
        # Known parameter roles may omit an unknown-slot row; exact source order
        # still selects the compiled field, never a default or a name heuristic.
        index = slot['field_index'] if slot else fields.index(f)
        value = node.payload.get('fields', {}).get('unbound_bit_'+str(index))
        if value is None and mask=='4':
            value = node.payload.get('reference_binding', {}).get('roles', {}).get('parameters')
        if not isinstance(value, dict) or value.get('kind') != 'dict':
            raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: exact compiled dictionary required:'+mask)
        items = value.get('children', [])
        if len(items)%2 or value.get('count') != len(items)//2:
            raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: dictionary framing')
        kind = binding['dictionary_masks'][mask]
        bucket = result[kind+'_parameters']
        for key, operand in zip(items[::2], items[1::2]):
            if not isinstance(key,str) or key in result['parameters']:
                raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: duplicate/invalid parameter identity')
            while isinstance(operand,dict) and 'child' in operand:
                operand = operand['child']
            if kind in ('numeric', 'string'):
                if not isinstance(operand,IRNode) or operand.kind != 'ExpressionIR':
                    raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: compiled expression required')
                operand = engine.evaluate(operand)
                if (kind=='numeric' and type(operand) is not int) or (kind=='string' and not isinstance(operand,str)):
                    raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: parameter value type')
            else:
                # Sequence bodies remain original IR data; executing a sequence
                # parameter needs its own supported source primitive.
                if not ((isinstance(operand,IRNode) and operand.kind=='TaskSequenceIR') or
                        (isinstance(operand,dict) and operand.get('type')=='RPG.GameCore.SequenceConfig')):
                    raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: compiled sequence body required')
                operand = copy.deepcopy(operand.to_dict() if isinstance(operand,IRNode) else operand)
            bucket[key] = operand
            result['parameters'][key] = copy.deepcopy(operand)
    return result


def _invoke(engine, d, task, node, p, template=False):
    a = d['abilities'][task['ability_instance_id']]
    spec = p['invocation']
    for key, value in {'owner': 'INHERIT_EXPLICIT', 'caster': 'INHERIT_EXPLICIT',
        'ability_target': 'RESOLVED_ORDERED_LIST', 'skill_targets': 'INHERIT_EXPLICIT',
        'param_entity_stack': 'INHERIT_EXPLICIT', 'parameters': 'INHERIT_EXPLICIT',
        'dynamic_provider_parent': 'EXPLICIT_SHARED', 'rng': 'SHARED_REFERENCE_STREAM',
        'event_scope': 'ACTION_OWNED', 'scheduler_ownership': 'SAME_ACTION_ROOT', 'controller': 'REFERENCE_CHILD'}.items():
        if spec.get(key) != value:
            raise GapError(node, 'NATIVE_POLICY_UNKNOWN: invocation relationship:' + key)
    mode = _required(node, spec, 'parent_resume')
    if mode not in ('FIRE_AND_CONTINUE_REFERENCE', 'WAIT_CHILD_REFERENCE', 'WAIT_CHILD_TREE_REFERENCE'):
        raise GapError(node, 'NATIVE_POLICY_UNKNOWN: parent resume condition')
    template_binding = None
    if template:
        structure = node.payload.get('decoded', {}).get('structure', {})
        masks = {str(f.get('mask')) for f in structure.get('fields', []) if f.get('mask') in (4, 8, 16, 32)}
        has_parameters = bool(masks) or node.payload.get('roles', {}).get('parameters') is not None or \
            node.payload.get('reference_binding', {}).get('roles', {}).get('parameters') is not None
        template_binding = p.get('template_call_bindings', {}).get(node.stable_hash())
        if has_parameters or template_binding is not None:
            if not isinstance(template_binding, dict) or template_binding.get('authority') != 'REFERENCE_MODEL':
                raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: explicit template parameter/context mapping required')
            if template_binding.get('mode') == 'SERIALIZED_DICTIONARIES_REFERENCE':
                template_binding = _serialized_template_parameters(engine, node, template_binding)
            if template_binding.get('caller_context') != 'INHERIT_EXPLICIT' or any(
                not isinstance(template_binding.get(key), dict) for key in
                ('parameters', 'numeric_parameters', 'string_parameters', 'sequence_parameters')):
                raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: complete explicit parameter/context mapping required')
            # The hash-keyed caller policy accounts for every serialized dictionary.
            # The raw fields and policy remain in the snapshot; no defaults applied.
            p = copy.deepcopy(p)
            binding = p.setdefault('role_bindings', {}).setdefault(node.op, {})
            binding['structure_only_masks'] = sorted(set(binding.get('structure_only_masks', [])) | masks)
    r = _roles(node, p)
    context = copy.deepcopy(engine.state.target_context)
    if template:
        identity = _required(node, r, 'template')
        if not isinstance(identity, str) or not identity:
            raise GapError(node, 'explicit nonempty template identity')
        if r.get('parameters') is not None and template_binding is None:
            raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: template parameter inheritance/evaluation remains unknown')
        if template_binding is not None:
            context['parameters'] = copy.deepcopy(template_binding['parameters'])
            context['template_call_binding'] = copy.deepcopy(template_binding)
        catalog = engine.templates
        if template_binding and 'template_catalog_key' in template_binding:
            if (template_binding.get('caller_root_IR_hash') != IRNode.from_dict(a['node']).stable_hash() or
                    template_binding.get('source_template_identity') != identity):
                raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: exact caller/template scope mismatch')
            identity = template_binding['template_catalog_key']
        token = 'template:' + identity
    else:
        identity = engine.evaluate(_required(node, r, 'AbilityName'))
        if not isinstance(identity, str) or not identity:
            raise GapError(node, 'explicit nonempty child ability identity')
        targets = engine.select(_required(node, r, 'TargetType'))
        context['ability_targets'] = targets
        context.pop('ability_target', None)
        if len(targets) == 1:
            context['ability_target'] = targets[0]
        catalog = engine.abilities
        token = 'ability:' + identity
    if identity not in catalog:
        raise GapError(node, 'missing decoded child catalog reference:' + str(identity))
    path = a['invocation_path']
    limit = p['max_template_depth'] if template else p['max_ability_depth']
    if token in path or len(path) >= limit:
        raise GapError(node, 'SCHEDULER_CYCLE_OR_DEPTH: ability/template invocation')
    for key in ('owner', 'caster', 'skill_targets', 'parameters', 'dynamic_provider_parent'):
        _required(node, context, key)
    for key in ('owner', 'caster'):
        if context[key] not in engine.state.entities:
            raise GapError(node, 'resolved invocation owner/caster')
    if context['dynamic_provider_parent'] not in engine.state.dynamic_values:
        raise GapError(node, 'resolved invocation dynamic provider parent')
    context['reference_parameters'] = copy.deepcopy(context.get('reference_parameters', [])) + [context['parameters']]
    context['param_entity_stack'] = copy.deepcopy(context.get('param_entity_stack', [context.get('param_entity')]))
    child = _new_ability(d, a['action_root_id'], catalog[identity], context, token, a['frame_id'], task['frame_id'], path)
    d['abilities'][child]['callback_owner'] = task['callback_owner']
    fid = _id(d, 'child')
    d['child_frames'][fid] = asdict(ChildAbilityFrame(fid, **_ownership(d, a['frame_id'], task['frame_id'], task['callback_owner']),
        child_ability_id=child, resume_condition=mode))
    if mode == 'FIRE_AND_CONTINUE_REFERENCE':
        _finish_task(d, task)
    else:
        task.update(status='WAITING', wait_kind=mode, wait_id=fid)


def _primitive(engine, d, t, node, p):
    op, payload = node.op.rsplit('.', 1)[-1], node.payload
    aid = t['ability_instance_id']
    callback = d['callbacks'].get(t['callback_owner'])
    path = callback['callback_path'] if callback else []
    from .defense_break import POLICY_ID as DEFENSE_POLICY, OPS as DEFENSE_OPS, execute as defense_execute
    if DEFENSE_POLICY in engine.policies and node.op in DEFENSE_OPS:
        children = defense_execute(engine, node, t)
        if children:
            s = d['sequences'][t['sequence_frame_id']]
            ancestors = s['ancestor_nodes'] + [node.stable_hash()]
            if node.stable_hash() in s['ancestor_nodes'] or len(ancestors) > p['max_task_depth']:
                raise GapError(node, 'SCHEDULER_TASK_CYCLE_OR_DEPTH')
            sid = _sequence(d, aid, children, tid=t['frame_id'], callback=t['callback_owner'], ancestors=ancestors)
            t.update(status='WAITING', wait_kind='SEQUENCES', children=[sid])
        else:
            _finish_task(d, t)
        return
    from .resource_engine import POLICY_ID as RESOURCE_POLICY, SOURCE_OPS as RESOURCE_OPS, execute as resource_execute
    if RESOURCE_POLICY in engine.policies and node.op in RESOURCE_OPS:
        children = resource_execute(engine, node, t)
        s = d['sequences'][t['sequence_frame_id']]
        ancestors = s['ancestor_nodes'] + [node.stable_hash()]
        if node.stable_hash() in s['ancestor_nodes'] or len(ancestors) > p['max_task_depth']:
            raise GapError(node, 'SCHEDULER_TASK_CYCLE_OR_DEPTH')
        sid = _sequence(d, aid, children, tid=t['frame_id'], callback=t['callback_owner'], ancestors=ancestors)
        t.update(status='WAITING', wait_kind='SEQUENCES', children=[sid])
        return
    from .damage_pipeline import POLICY_ID as DAMAGE_POLICY, SOURCE_OPS, execute as damage_execute
    if DAMAGE_POLICY in engine.policies and node.op in (*SOURCE_OPS, 'RPG.GameCore.DamagePerformFinish'):
        children = damage_execute(engine, node, t)
        if children:
            s = d['sequences'][t['sequence_frame_id']]
            ancestors = s['ancestor_nodes'] + [node.stable_hash()]
            if node.stable_hash() in s['ancestor_nodes'] or len(ancestors) > p['max_task_depth']:
                raise GapError(node, 'SCHEDULER_TASK_CYCLE_OR_DEPTH')
            sid = _sequence(d, aid, children, tid=t['frame_id'], callback=t['callback_owner'], ancestors=ancestors)
            t.update(status='WAITING', wait_kind='SEQUENCES', children=[sid])
        else:
            _finish_task(d, t)
        return
    from .modifier_lifecycle import POLICY_ID as MODIFIER_POLICY, execute as modifier_execute
    if MODIFIER_POLICY in engine.policies:
        children = modifier_execute(engine, node)
        if children is not None:
            if children:
                if all(child.op == 'reference_context_callback' for child in children):
                    _owned_event(engine, d, t, node, children, path, p, {'lifecycle_node': node.to_dict()})
                else:
                    sequence = d['sequences'][t['sequence_frame_id']]
                    ancestors = sequence['ancestor_nodes'] + [node.stable_hash()]
                    if node.stable_hash() in sequence['ancestor_nodes'] or len(ancestors) > p['max_task_depth']:
                        raise GapError(node, 'SCHEDULER_TASK_CYCLE_OR_DEPTH')
                    sid = _sequence(d, aid, children, tid=t['frame_id'], callback=t['callback_owner'], ancestors=ancestors)
                    t.update(status='WAITING', wait_kind='SEQUENCES', children=[sid])
                    return
            _finish_task(d, t)
            return
    if op in ('TriggerAbility', 'IncludeTaskListTemplate'):
        _invoke(engine, d, t, node, p, op == 'IncludeTaskListTemplate')
        return
    if op in ('SkillPerformFinish', 'completion'):
        a = d['abilities'][aid]
        a['completion_requested'] = True
        root = d['roots'][a['action_root_id']]
        if root['root_ability_id'] == aid:
            root['completion_requested'] = True
            engine.state.scheduler.completion_requested = True
        cid = _id(d, 'completion')
        d['completion_requests'][cid] = asdict(CompletionRequest(cid,
            **_ownership(d, aid, t['frame_id'], t['callback_owner']), status='REQUESTED', source_node=node.to_dict()))
        _finish_task(d, t)
        return
    if op == 'DamagePerformFinish':
        raise GapError(node, 'DAMAGE_LIFECYCLE: native damage settlement signal unknown')
    if op.startswith('DamageByAttackProperty'):
        raise GapError(node, 'DAMAGE_REFERENCE_INPUT_MISSING: explicit damage policy and source task operands')
    spec = p.get('waits', {}).get(node.node_id, p.get('waits', {}).get(op))
    if op in ('WaitSecond', 'WaitAnimState', 'WaitTimelineFinish', 'barrier'):
        if op == 'barrier':
            spec = {'classification': 'EXTERNAL_PRESENTATION_BARRIER', 'release_key': payload['key']}
        if spec is None:
            raise GapError(node, 'NATIVE_BEHAVIOR_UNKNOWN: explicit wait policy:' + op)
        mode = spec.get('classification')
        if op == 'WaitSecond':
            if mode != 'LOGICAL_DELAY_REFERENCE' or spec.get('duration_units') != 'SERIALIZED_RAW_REFERENCE_UNITS':
                raise GapError(node, 'explicit reference timing/unit policy')
            r = _roles(node, p)
            expression = _required(node, r, 'duration')
            try:
                delay = _integer(node, raw_checked(engine.evaluate(expression)))
            except NumericSemanticGap as exc:
                raise GapError(node, str(exc)) from exc
        elif mode == 'LOGICAL_DELAY_REFERENCE':
            delay = _integer(node, _required(node, spec, 'duration_raw'))
        elif mode in ('BARRIER_ONLY_REFERENCE', 'EXTERNAL_PRESENTATION_BARRIER'):
            delay = None
        else:
            raise GapError(node, 'NATIVE_BEHAVIOR_UNKNOWN: wait classification')
        due = d['logical_time'] + delay if delay is not None else None
        bid = _barrier(d, t, mode, spec.get('release_key', node.node_id), due)
        if mode == 'BARRIER_ONLY_REFERENCE':
            # Actual suspension, released only at the logical queue phase.
            _time_entry(d, aid, t['frame_id'], d['logical_time'], bid, callback=t['callback_owner'])
        return
    presentation = p.get('presentation', {}).get(node.node_id, p.get('presentation', {}).get(op))
    if presentation is not None:
        mode = presentation.get('classification')
        if op in ('MoveToTargetList', 'MoveToTargetPosition', 'TriggerAnimStateWithMove') and mode != 'POSITION_RELEVANT_REFERENCE':
            raise GapError(node, 'POSITION: explicit modeled movement required')
        if mode == 'PRESENTATION_INSTANT_REFERENCE':
            engine.state.presentation.setdefault('r15_reference_nodes', []).append(node.node_id)
            _finish_task(d, t)
            return
        if mode == 'PRESENTATION_BARRIER_REFERENCE':
            _barrier(d, t, mode, presentation.get('release_key', node.node_id))
            return
        if mode == 'POSITION_RELEVANT_REFERENCE':
            positions = _required(node, presentation, 'positions')
            for eid, position in positions.items():
                if eid not in engine.state.entities or 'position' not in engine.state.entities[eid]:
                    raise GapError(node, 'explicit modeled position required')
                if not isinstance(position, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in position):
                    raise GapError(node, 'integer reference position coordinates required')
                engine.state.entities[eid]['position'] = copy.deepcopy(position)
            delay = _integer(node, presentation.get('duration_raw', 0))
            _barrier(d, t, mode, node.node_id, d['logical_time'] + delay)
            return
        if mode != 'STATE_RELEVANT':
            raise GapError(node, 'UNKNOWN: presentation/state classification')
    if op in ('MoveToTargetList', 'MoveToTargetPosition', 'TriggerAnimStateWithMove'):
        raise GapError(node, 'POSITION: explicit movement position/relevance policy required')
    if op == 'schedule':
        if node.stable_hash() in path or len(path) >= p['max_callback_depth']:
            raise GapError(node, 'SCHEDULER_ZERO_DELAY_OR_CALLBACK_CYCLE')
        due = _integer(node, payload['tick'])
        if due < d['logical_time']:
            raise GapError(node, 'logical continuation cannot precede current time')
        eid = _time_entry(d, aid, t['frame_id'], due, nodes=payload['tasks'], context=engine.state.target_context, callback=t['callback_owner'])
        d['continuations'][eid]['callback_path'] = path + [node.stable_hash()]
        d['continuations'][eid]['release_key'] = payload.get('release')
        _finish_task(d, t)
        return
    if op in ('event_dispatch', 'modifier_event_dispatch'):
        source = {'node': node.to_dict(), 'payload': payload.get('payload', {})}
        if op == 'event_dispatch':
            name = payload['event_type']
            if name not in engine.events:
                raise GapError(node, 'explicit event callback catalog:' + name)
            nodes = engine.events[name]
        else:
            if MODIFIER_POLICY in engine.policies:
                from .modifier_lifecycle import dispatch
                nodes = dispatch(engine, node, only=payload.get('only_instance'))
            else:
                from .behavior_expansion import modifier_event
                nodes = modifier_event(engine, node, engine.state)
        eid = _owned_event(engine, d, t, node, nodes, path, p, source)
        if payload.get('drain_before_resume_reference'):
            if MODIFIER_POLICY not in engine.policies or payload['drain_before_resume_reference'] is not True:
                raise GapError(node, 'MODIFIER_LIFECYCLE_POLICY_MISSING: explicit R17 event drain')
            t.update(status='WAITING', wait_kind='EVENT_DRAIN_REFERENCE', wait_id=eid)
            return
        _finish_task(d, t)
        return
    if node.kind == 'UnsupportedSemanticIR':
        raise GapError(node, payload['required_capability'])
    children = engine.registry.invoke('task', engine, node, engine.state)
    if children == ExecutionStatus.WAITING_SCHEDULER:
        raise GapError(node, 'legacy waiting task requires owned R15 barrier policy')
    if not children:
        _finish_task(d, t)
        return
    s = d['sequences'][t['sequence_frame_id']]
    ancestors = s['ancestor_nodes'] + [node.stable_hash()]
    if node.stable_hash() in s['ancestor_nodes'] or len(ancestors) > p['max_task_depth']:
        raise GapError(node, 'SCHEDULER_TASK_CYCLE_OR_DEPTH')
    sid = _sequence(d, aid, children, tid=t['frame_id'], callback=t['callback_owner'], ancestors=ancestors)
    t.update(status='WAITING', wait_kind='SEQUENCES', children=[sid])


def _transition(engine, kind, identity, p):
    d = _data(engine)
    if kind == 'CHILD_ABILITIES':
        a = d['abilities'][identity]
        node = IRNode.from_dict(a['node'])
        template_entry = node.op == 'structure_record' and node.payload.get('root_type') == 'RPG.GameCore.TaskListTemplate'
        if template_entry:
            binding = p.get('template_entry_bindings', {}).get(node.stable_hash())
            if (not isinstance(binding, dict) or binding.get('authority') != 'REFERENCE_MODEL' or
                binding.get('task_list_mask') != 2 or binding.get('parameter_context') != 'EXPLICIT_CALLER_MAPPING_ONLY'):
                raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: exact template entry/context policy required')
            fields = node.payload.get('decoded', {}).get('fields', [])
            if any(f.get('mask') not in (1, 2, 4, 8) for f in fields):
                raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: unknown template definition field')
            if any(f.get('mask') in (4, 8) for f in fields) and 'template_call_binding' not in a['context']:
                raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: definition dictionaries require explicit caller mapping')
            lists = [v for f in fields if f.get('mask') == 2 for v in f.get('values', []) if v.get('kind') == 'list']
            if len(lists) != 1 or not all(isinstance(child, IRNode) for child in lists[0].get('children', [])):
                raise GapError(node, 'TEMPLATE_PARAMETER_INHERITANCE: exact compiled template task-list required')
            nodes = [TaskSequenceIR(node.node_id+'/template_entry', 'immediate_sequence', node.authority,
                     {'tasks':lists[0]['children'], 'ordering_authority':'EXPLICIT_REFERENCE_TEMPLATE_ENTRY'})]
        elif node.op in ('structure_record', 'decoded_graph'):
            raise GapError(node, 'ability entry/lifecycle slot policy remains unbound')
        elif node.kind == 'AbilityIR':
            nodes = [node.payload['tasks']]
            slots = node.payload.get('reference_unbound_sequences', [])
            if slots:
                binding = p.get('lifecycle_slot_bindings', {}).get(node.stable_hash())
                if not isinstance(binding, dict) or binding.get('authority') != 'REFERENCE_MODEL':
                    raise GapError(node, 'ability entry/lifecycle slot policy remains unbound')
                ordered = binding.get('ordered_masks', [])
                if (not isinstance(ordered, list) or not all(type(mask) is int for mask in ordered) or
                    len(ordered) != len(slots)+1 or len(set(ordered)) != len(ordered) or
                    set(ordered) != {16, *slots}):
                    raise GapError(node, 'LIFECYCLE_SLOT_POLICY: all nonempty slots and entry required exactly once')
                nodes = []
                for mask in ordered:
                    if mask == 16:
                        nodes.append(node.payload['tasks']); continue
                    fields = [f for f in node.payload.get('decoded', {}).get('fields', []) if f.get('mask') == mask]
                    if len(fields) != 1:
                        raise GapError(node, 'LIFECYCLE_SLOT_POLICY: exact serialized slot required')
                    tasks = [child for value in fields[0].get('values', []) for child in value.get('children', [])]
                    if not tasks or not all(isinstance(child, IRNode) for child in tasks):
                        raise GapError(node, 'LIFECYCLE_SLOT_POLICY: compiled slot tasks required')
                    nodes.append(TaskSequenceIR(node.node_id+'/lifecycle/'+str(mask), 'immediate_sequence',
                        node.authority, {'tasks':tasks, 'ordering_authority':'EXPLICIT_REFERENCE_SLOT_POLICY'}))
        elif node.kind == 'TaskSequenceIR':
            nodes = [node]
        else:
            raise GapError(node, 'executable child ability or template sequence required')
        if a.get('reference_admission_costs'):
            nodes = [IRNode.from_dict(raw) for raw in a['reference_admission_costs']] + nodes
        a['sequence_frame_id'] = _sequence(d, identity, nodes)
        a['status'] = 'RUNNING'
        d['child_queue'].remove(identity)
    elif kind == 'TASK_CONTINUATIONS':
        s = d['sequences'][identity]
        d['task_queue'].remove(identity)
        if s['cursor'] == len(s['nodes']):
            s['status'] = 'SEQUENCE_COMPLETE'
        else:
            node = IRNode.from_dict(s['nodes'][s['cursor']])
            if node.kind == 'AbilityIR':
                raise GapError(node, 'ability nodes require explicit child invocation ownership')
            tid = s['active_task_id']
            if tid is None:
                tid = _id(d, 'task')
                s['active_task_id'] = tid
                d['tasks'][tid] = asdict(TaskFrame(tid,
                    **_ownership(d, s['ability_instance_id'], tid, s['callback_owner']), node=node.to_dict(), sequence_frame_id=identity))
            t = d['tasks'][tid]
            if node.kind == 'TaskSequenceIR':
                ancestors = s['ancestor_nodes'] + [node.stable_hash()]
                if node.stable_hash() in s['ancestor_nodes'] or len(ancestors) > p['max_task_depth']:
                    raise GapError(node, 'SCHEDULER_TASK_CYCLE_OR_DEPTH')
                child = _sequence(d, s['ability_instance_id'], node.payload['tasks'], tid=tid, callback=s['callback_owner'], ancestors=ancestors)
                t.update(status='WAITING', wait_kind='SEQUENCES', children=[child], container=True)
            else:
                callback = d['callbacks'].get(s['callback_owner'])
                saved = engine.state.target_context
                engine.state.target_context = copy.deepcopy(callback['context'] if callback else d['abilities'][s['ability_instance_id']]['context'])
                _primitive(engine, d, t, node, p)
                if callback:
                    callback['context'] = copy.deepcopy(engine.state.target_context)
                else:
                    d['abilities'][s['ability_instance_id']]['context'] = copy.deepcopy(engine.state.target_context)
                engine.state.target_context = saved
                d['metrics']['tasks_reached'] += 1
                d['history'].append({'node': node.to_dict(), 'task': tid, 'status': 'TASK_REACHED'})
    elif kind == 'EVENT_CALLBACKS':
        if identity in d['events']:
            e = d['events'][identity]
            if e['cursor'] < len(e['nodes']):
                raw = e['nodes'][e['cursor']]
                node = IRNode.from_dict(raw)
                context = e['context']
                callback_source = copy.deepcopy(e['source_event'])
                modifier = registration = None
                if node.op == 'reference_context_callback':
                    if node.payload['mutation_result'] != 'NORMAL_GENERIC_TASK_EXECUTION':
                        raise GapError(node, 'explicit callback mutation result policy')
                    context = node.payload['context']
                    modifier = node.payload.get('modifier_instance_id')
                    registration = node.payload.get('registration_id')
                    if 'source_event' in node.payload:
                        callback_source['modifier_event'] = copy.deepcopy(node.payload['source_event'])
                    node = node.payload['callback']
                cid = _callback(d, e['ability_instance_id'], e['task_frame_id'], node, context,
                          callback_source, e['callback_path'], owner=e['callback_owner'],
                          modifier=modifier, registration=registration)
                if modifier:
                    d['metrics']['modifier_callbacks_invoked'] = d['metrics'].get('modifier_callbacks_invoked', 0) + 1
                    instance = engine.state.modifiers.get(modifier)
                    if instance:
                        instance.pending_lifecycle_callbacks.append(cid)
                e['cursor'] += 1
            if e['cursor'] == len(e['nodes']):
                e['status'] = 'COMPLETE'
                d['event_queue'].remove(identity)
        else:
            c = d['callbacks'][identity]
            node = IRNode.from_dict(c['callback_ir'])
            c['sequence_frame_id'] = _sequence(d, c['ability_instance_id'], [node], tid=c['task_frame_id'], callback=identity)
            c['status'] = 'RUNNING'
            d['callback_queue'].remove(identity)
    elif kind == 'LOGICAL_TIME':
        e = d['continuations'][identity]
        d['logical_time'] = e['due_time']
        engine.state.scheduler.tick = e['due_time']
        if e['barrier_id']:
            d['barriers'][e['barrier_id']]['status'] = 'RELEASED'
        if e.get('release_key'):
            for b in d['barriers'].values():
                if b['release_key'] == e['release_key'] and b['action_root_id'] == e['action_root_id']:
                    b['status'] = 'RELEASED'
        if e['nodes']:
            eid = _id(d, 'event')
            d['events'][eid] = dict(_ownership(d, e['ability_instance_id'], e['task_frame_id'], e['callback_owner']),
                frame_id=eid, status='READY', source_event={'scheduled_continuation': identity},
                nodes=copy.deepcopy(e['nodes']), cursor=0, context=copy.deepcopy(e['context']),
                callback_path=e.get('callback_path', []))
            d['event_queue'].append(eid)
        e['status'] = 'COMPLETE'
        d['time_queue'].remove(identity)
        d['metrics']['logical_time_advances'] += 1
    _settle(d, engine.state)
    for callback in d['callbacks'].values():
        if (callback.get('modifier_instance_id') and callback['status'] == 'CALLBACK_COMPLETE' and
            not callback.get('modifier_evidence_recorded')):
            engine.state.modifier_history.append({'boundary': 'REFERENCE_CALLBACK_EXECUTED',
                'instance_id': callback['modifier_instance_id'], 'registration_id': callback['registration_id'],
                'callback_frame_id': callback['frame_id'], 'action_root_id': callback['action_root_id'],
                'semantic_authority': 'REFERENCE_MODEL', 'callback_authority': 'REFERENCE_CALLBACK_EXECUTABLE',
                'native_event_meaning': 'NATIVE_EVENT_MEANING_UNKNOWN',
                'native_effective_listener': 'NATIVE_EFFECTIVE_LISTENER_UNKNOWN'})
            callback['modifier_evidence_recorded'] = True
    for instance in engine.state.modifiers.values():
        instance.pending_lifecycle_callbacks = [cid for cid in instance.pending_lifecycle_callbacks
            if cid in d['callbacks'] and d['callbacks'][cid]['status'] not in ('CALLBACK_COMPLETE', 'CALLBACK_CANCELLED_REFERENCE')]
    for request_id, request in engine.state.damage_requests.items():
        if request['status'] != 'COMPLETE':
            request['pending_callbacks'] = [c['frame_id'] for c in d['callbacks'].values()
                if c['source_event'].get('payload', {}).get('damage_request_id') == request_id and
                c['status'] not in ('CALLBACK_COMPLETE', 'CALLBACK_CANCELLED_REFERENCE')]
    d['history'].append({'scheduler_phase': kind, 'frame': identity,
                         'time': d['logical_time'], 'semantic_authority': 'REFERENCE_MODEL'})


def drive(engine, budget=10000, *, advance=True, one_time=False):
    p = _policy(engine)
    if isinstance(budget, int) and not isinstance(budget, bool):
        budget = WorkBudget(max_total_transitions=budget, max_task_transitions=budget,
            max_callbacks=budget, max_child_invocations=budget, max_time_advances=budget)
    if not isinstance(budget, WorkBudget):
        raise TypeError('WorkBudget or nonnegative integer required')
    if not _data(engine):
        raise ValueError('start an R15 action before driving')
    used = {k: 0 for k in ('total', 'tasks', 'callbacks', 'children', 'time')}
    started = _data(engine)['metrics']['tasks_completed']
    limits = {'total': budget.max_total_transitions, 'tasks': budget.max_task_transitions,
        'callbacks': budget.max_callbacks, 'children': budget.max_child_invocations, 'time': budget.max_time_advances}

    def result(status, gap=None):
        return ExecutionResult(status, completed_nodes=max(0, _data(engine)['metrics']['tasks_completed'] - started),
                               gap=gap, trace=tuple(copy.deepcopy(_data(engine)['history'])))

    while True:
        d = _data(engine)
        _settle(d, engine.state)
        if d['roots'][d['current_root']]['status'] == 'ACTION_REFERENCE_COMPLETE':
            return result(ExecutionStatus.ACTION_REFERENCE_COMPLETE)
        choice = None
        rid = d['current_root']
        def owned_queue(queue, table):
            from .damage_pipeline import within_transaction
            transactions = engine.state.damage_transactions
            return [identity for identity in d[queue] if d[table][identity]['action_root_id'] == rid and
                    (not transactions or within_transaction(d, d[table][identity], transactions[-1]))]
        for kind in p['processing_order']:
            queue = {'TASK_CONTINUATIONS': owned_queue('task_queue', 'sequences'),
                'EVENT_CALLBACKS': owned_queue('event_queue', 'events') or owned_queue('callback_queue', 'callbacks'),
                'CHILD_ABILITIES': owned_queue('child_queue', 'abilities'),
                'LOGICAL_TIME': owned_queue('time_queue', 'continuations')}[kind]
            if queue and (kind != 'LOGICAL_TIME' or advance):
                choice = kind, queue[0]
                break
        if choice is None:
            return result(ExecutionStatus.WAITING_SCHEDULER)
        kind, identity = choice
        cost = {'TASK_CONTINUATIONS': 'tasks', 'EVENT_CALLBACKS': 'callbacks', 'CHILD_ABILITIES': 'tasks', 'LOGICAL_TIME': 'time'}[kind]
        if used['total'] >= limits['total'] or used[cost] >= limits[cost]:
            return result(ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED)
        invocation = False
        if kind == 'TASK_CONTINUATIONS':
            seq = d['sequences'][identity]
            if seq['cursor'] < len(seq['nodes']):
                raw = seq['nodes'][seq['cursor']]
                invocation = raw['op'].rsplit('.', 1)[-1] in ('TriggerAbility', 'IncludeTaskListTemplate')
                if invocation and used['children'] >= limits['children']:
                    return result(ExecutionStatus.EXECUTION_BUDGET_EXHAUSTED)
        candidate = engine.state.clone()
        saved = engine.state
        trace_length = len(engine.trace)
        engine.state = candidate
        # A source damage primitive owns an atomic transaction spanning all of
        # its generated stages and callbacks. The checkpoint precedes TaskFrame
        # creation, so retry/restore re-enters exactly the original source node.
        from .damage_pipeline import POLICY_ID as DAMAGE_POLICY, SOURCE_OPS
        from .resource_engine import POLICY_ID as RESOURCE_POLICY, SOURCE_OPS as RESOURCE_OPS
        from .defense_break import POLICY_ID as DEFENSE_POLICY, ENTRY_OPS as DEFENSE_OPS
        if kind == 'TASK_CONTINUATIONS':
            seq = d['sequences'][identity]
            if seq['cursor'] < len(seq['nodes']):
                source = seq['nodes'][seq['cursor']]
                if source['op'] in SOURCE_OPS and DAMAGE_POLICY in engine.policies:
                    candidate.damage_transactions.append({'checkpoint':saved.snapshot(),
                        'trace_length':trace_length,'source_task_id':None,
                        'source_task':copy.deepcopy(source),'request_ids':[]})
                elif source['op'] in RESOURCE_OPS and RESOURCE_POLICY in engine.policies:
                    candidate.damage_transactions.append({'checkpoint':saved.snapshot(),
                        'trace_length':trace_length,'source_task_id':None,'kind':'RESOURCE',
                        'source_task':copy.deepcopy(source)})
                elif source['op'] in DEFENSE_OPS and DEFENSE_POLICY in engine.policies:
                    candidate.damage_transactions.append({'checkpoint':saved.snapshot(),
                        'trace_length':trace_length,'source_task_id':None,'kind':'DEFENSE_REFERENCE',
                        'source_task':copy.deepcopy(source)})
        try:
            _transition(engine, kind, identity, p)
        except GapError as exc:
            engine.state = saved
            del engine.trace[trace_length:]
            if saved.damage_transactions:
                from .behavior_state import BehaviorBattleState
                transaction = saved.damage_transactions[0]
                engine.state = BehaviorBattleState.from_snapshot(transaction['checkpoint'])
                del engine.trace[transaction['trace_length']:]
            engine.gaps.record(exc.gap)
            return result(ExecutionStatus.SEMANTIC_GAP, exc.gap)
        used['total'] += 1
        used[cost] += 1
        if invocation:
            used['children'] += 1
        if one_time and kind == 'LOGICAL_TIME':
            return result(ExecutionStatus.WAITING_SCHEDULER)
