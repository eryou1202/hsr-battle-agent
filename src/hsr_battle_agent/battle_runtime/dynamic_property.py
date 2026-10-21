"""R19 explicit provider contracts and bounded 4.6.51 expression expansion.

Policies are reference abstractions, never inferred effective native precedence.
All stores are existing serialized battle/modifier/context state; no property cache.
"""
from __future__ import annotations

from hsr_battle_agent.battle_ir.behavior import ExpressionIR, stable_hash, walk_nodes
from .behavior import GapError
from .behavior_primitives import fixed_binary, raw_checked

POLICY_ID = 'r19_dynamic_property_reference_v1'
PROGRAM = '4651_STACK_0_1_2_4_17_MODE0_REFERENCE'
AGGREGATION = 'R17_STORAGE_INCLUDES_ADDITIVE_REVERSIBLE_REFERENCE'
SOURCES = ('BASE_PROPERTY', 'EFFECTIVE_PROPERTY', 'MODIFIER_CONTRIBUTION',
           'ABILITY_DYNAMIC_VALUE', 'MODIFIER_LOCAL_DYNAMIC_VALUE', 'SNAPSHOT_VALUE',
           'CONTEXT_OVERRIDE', 'UNKNOWN_PROVIDER')


def fail(node, kind, detail):
    raise GapError(node, kind + ': ' + str(detail))


def policy(engine, node):
    p = engine.policies.get(POLICY_ID)
    if not isinstance(p, dict) or p.get('identity') != POLICY_ID or p.get('authority') != 'REFERENCE_MODEL':
        fail(node, 'PROPERTY_PROVIDER_POLICY_MISSING', POLICY_ID)
    if not p.get('evidence'):
        fail(node, 'PROPERTY_PROVIDER_POLICY_MISSING', 'evidence label')
    return p


def reference_policy():
    return {'identity': POLICY_ID, 'authority': 'REFERENCE_MODEL',
            'evidence': 'R19 caller policy; native evaluator jump-table evidence; effective IFix/provider order UNKNOWN',
            'program_family': PROGRAM, 'lookup_bindings': {}, 'property_bindings': {}, 'rank_bindings': {}}


def compile_program(node):
    """Retain the source envelope; expand only the proven bounded stack family.

    Opcode 4 -> table 0x1E197730 -> 0x1E196678 -> op_Multiply
    at 0x1E1966B3. Right is popped first; AST operands stay left/right.
    Numeric behavior continues to use the existing R12 reference contract.
    """
    raw = node.payload.get('decoded', {})
    if raw.get('type') != 'RPG.GameCore.DynamicFloat' or raw.get('tag') != 1:
        fail(node, 'DYNAMIC_PROGRAM_UNKNOWN', 'tag/type')
    tokens = raw.get('token_ids')
    if not isinstance(tokens, list) or not tokens or len(tokens) > 128 or any(type(t) is not int for t in tokens):
        fail(node, 'DYNAMIC_PROGRAM_UNKNOWN', 'bounded integer token stream')
    stack = []
    i = 0
    try:
        while i < len(tokens):
            position = i
            op = tokens[i]
            i += 1
            identity = node.node_id + '/r19/token/' + str(position)
            if op in (0, 1):
                index = tokens[i]
                i += 1
                values = raw['int64_operands' if op == 0 else 'int32_operands']
                if index < 0 or type(values[index]) is not int:
                    raise ValueError('operand index/type')
                operand = values[index]
                if op == 1 and not -(1 << 31) <= operand < (1 << 31):
                    raise ValueError('int32 operand')
                stack.append(ExpressionIR(identity, 'literal' if op == 0 else 'lookup', node.authority,
                    {'raw': raw_checked(operand)} if op == 0 else {'key': str(operand), 'scope': 'supplied'}))
            elif op in (2, 4):
                right, left = stack.pop(), stack.pop()
                stack.append(ExpressionIR(identity, 'add' if op == 2 else 'mul', node.authority,
                                          {'args': [left, right]}))
            elif op == 17 and i == len(tokens) and len(stack) == 1:
                return ExpressionIR(node.node_id + '/r19', 'identity', node.authority,
                                    {'arg': stack[0], 'serialized_program': raw, 'reference_family': PROGRAM})
            else:
                fail(node, 'DYNAMIC_PROGRAM_UNKNOWN', 'opcode/termination ' + str(op))
    except (IndexError, KeyError, ValueError, TypeError) as exc:
        fail(node, 'DYNAMIC_PROGRAM_UNKNOWN', 'operand/stack ' + str(exc))
    fail(node, 'DYNAMIC_PROGRAM_UNKNOWN', 'missing terminal opcode 17')


def contributions(engine, node, state, eid, key, binding):
    if binding.get('aggregation') != AGGREGATION or binding.get('listener_scope') != 'EXPLICIT_ACTIVE_REFERENCE_INSTANCES_ONLY':
        fail(node, 'PROPERTY_AGGREGATION_UNKNOWN', 'explicit R17 storage/contribution contract')
    total = 0
    rows = []
    # R17 insertion order is serialized in instances' IDs; use explicit ordering.
    order = binding.get('modifier_order')
    if not isinstance(order, list) or len(order) != len(set(order)) or set(order) != set(state.modifiers):
        fail(node, 'PROPERTY_AGGREGATION_UNKNOWN', 'complete ordered active reference modifier IDs')
    for identity in order:
        instance = state.modifiers[identity]
        for c in instance.property_contributions:
            if c.get('entity') == eid and c.get('property') == key:
                if c.get('aggregation_policy', {}).get('aggregation') != 'ADDITIVE_REVERSIBLE_REFERENCE':
                    fail(node, 'PROPERTY_AGGREGATION_UNKNOWN', identity)
                value = raw_checked(c['value'])
                total = fixed_binary('add', total, value)
                rows.append({'modifier': identity, 'raw': value, 'source_node_hash': c['source_node_hash']})
    return total, rows


def read(engine, node, state, binding, key):
    """Return value and selected source; missing providers never fall back silently."""
    if not isinstance(binding, dict) or binding.get('authority') != 'REFERENCE_MODEL' or not binding.get('evidence'):
        fail(node, 'PROPERTY_PROVIDER_POLICY_MISSING', 'binding authority/evidence')
    chain = binding.get('providers')
    if not isinstance(chain, list) or not chain or len(chain) > len(SOURCES):
        fail(node, 'PROPERTY_PROVIDER_POLICY_MISSING', 'ordered providers')
    if any(not isinstance(v, dict) for v in chain) or len({stable_hash(v) for v in chain}) != len(chain):
        fail(node, 'PROPERTY_PROVIDER_POLICY_MISSING', 'distinct explicit providers')
    for provider in chain:
        source = provider.get('source')
        if source not in SOURCES or source == 'UNKNOWN_PROVIDER':
            fail(node, 'PROPERTY_PROVIDER_UNKNOWN', source)
        rows = []
        if source in ('BASE_PROPERTY', 'EFFECTIVE_PROPERTY', 'MODIFIER_CONTRIBUTION'):
            eid = provider.get('entity')
            if eid not in state.entities:
                fail(node, 'PROPERTY_PROVIDER_INPUT_MISSING', 'entity')
            store = state.properties.get(eid, {})
            if key not in store:
                value = None
            else:
                value = raw_checked(store[key])
                total, rows = contributions(engine, node, state, eid, key, binding)
                if source == 'BASE_PROPERTY':
                    value = fixed_binary('sub', value, total)
                elif source == 'MODIFIER_CONTRIBUTION':
                    value = total
                # R17 already mutates storage. EFFECTIVE_PROPERTY never adds twice.
        elif source == 'ABILITY_DYNAMIC_VALUE':
            value = state.dynamic_values.get(provider.get('scope'), {}).get(key)
        elif source in ('MODIFIER_LOCAL_DYNAMIC_VALUE', 'SNAPSHOT_VALUE'):
            identity = provider.get('instance')
            if identity == 'CURRENT_MODIFIER_REFERENCE':
                identity = state.target_context.get('modifier_instance_id')
            instance = state.modifiers.get(identity)
            store = (instance.dynamic_values if source == 'MODIFIER_LOCAL_DYNAMIC_VALUE' else instance.snapshot_data) if instance else {}
            value = store.get(key)
        else:
            value = state.target_context.get(provider.get('store'), {}).get(key)
        missing = provider.get('on_missing')
        if missing not in ('GAP_REFERENCE', 'CONTINUE_EXPLICIT_REFERENCE'):
            fail(node, 'PROPERTY_PROVIDER_POLICY_MISSING', 'provider missing behavior')
        if value is not None:
            return raw_checked(value), {'source': source, 'key': key, 'provider': provider,
                                        'contributions': rows, 'policy_hash': stable_hash(binding)}
        if missing != 'CONTINUE_EXPLICIT_REFERENCE':
            fail(node, 'PROPERTY_PROVIDER_INPUT_MISSING', source + '/' + key)
    fail(node, 'PROPERTY_PROVIDER_INPUT_MISSING', 'explicit chain exhausted/' + key)


def property_read(engine, node, state):
    p = policy(engine, node)
    binding = p['property_bindings'].get(node.payload.get('binding'))
    return read(engine, node, state, binding, str(node.payload['key']))[0]


def rank(engine, node, state):
    if POLICY_ID not in engine.policies:
        raise GapError(node, 'predicate:RPG.GameCore.ByRankActivated')
    p = policy(engine, node)
    binding = p['rank_bindings'].get(node.stable_hash())
    if not isinstance(binding, dict) or binding.get('authority') != 'REFERENCE_MODEL' or not binding.get('evidence'):
        fail(node, 'RANK_POLICY_MISSING', 'exact predicate binding')
    if binding.get('mode') != 'KEYED_THRESHOLD_GE_REFERENCE':
        fail(node, 'RANK_POLICY_UNKNOWN', 'comparison')
    key = node.payload.get('fields', {}).get(binding.get('key_field'))
    actor = state.target_context.get(binding.get('actor_context'))
    progression = state.progression.get(actor, {})
    threshold = progression.get('rank_requirements', {}).get(str(key))
    value = progression.get('rank')
    if type(key) is not int or type(value) is not int or type(threshold) is not int or value < 0 or threshold < 0:
        fail(node, 'RANK_INPUT_MISSING', 'actor rank and keyed explicit threshold')
    return value >= threshold


def install(registry):
    previous = registry.handlers['expression']['lookup'][1]

    def lookup(engine, node, state):
        if POLICY_ID in engine.policies:
            p = policy(engine, node)
            binding = p['lookup_bindings'].get(node.payload['scope'] + '/' + str(node.payload['key']))
            if binding is not None:
                return read(engine, node, state, binding, str(node.payload['key']))[0]
        return previous(engine, node, state)

    def program(engine, node, state):
        if POLICY_ID not in engine.policies:
            raise GapError(node, 'expression:unknown_opcode')  # Frozen diagnostic preserved.
        p = policy(engine, node)
        if p.get('program_family') != PROGRAM:
            fail(node, 'DYNAMIC_PROGRAM_UNKNOWN', 'explicit program/numeric reference policy')
        ast = compile_program(node)
        for operand in walk_nodes(ast):
            if operand.op == 'lookup' and operand.payload['scope'] + '/' + str(operand.payload['key']) not in p['lookup_bindings']:
                fail(node, 'PROPERTY_PROVIDER_POLICY_MISSING', 'program lookup binding')
        return engine.evaluate(ast, state)

    registry.handlers['expression']['lookup'] = (POLICY_ID, lookup)
    registry.register('expression', 'unknown_opcode', program, version=POLICY_ID)
    registry.register('expression', 'property_read_reference', property_read, version=POLICY_ID)
    registry.register('predicate', 'RPG.GameCore.ByRankActivated', rank, version=POLICY_ID)
