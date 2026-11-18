"""Explicit original-task bindings into existing R17 reference lifecycle.

This bridge supplies policy, never instances or native lifecycle claims.
"""
from .modifier_lifecycle import POLICY_ID, reference_policy


def bind_compare_target_reference(runtime, node, *, selector_policy, result_policy):
    """Opt in unchanged serialized operands; selection/status remain reference inputs.

    4.6.51 reader 0x1E4113D0 binds masks 4/8 to +20/+28. Evaluate
    0xE808840 compares the first selected entities, refusing a null left.
    This does not implement patched/native selector masks or task statuses.
    """
    from .behavior import GapError
    if node.op != 'RPG.GameCore.ByCompareTarget' or node.kind != 'PredicateIR':
        raise ValueError('exact ByCompareTarget predicate required')
    if selector_policy != 'MASK15_CALLER_RESOLVED_REFERENCE':
        raise ValueError('explicit mask-15 reference selection required')
    if result_policy != 'BOOLEAN_TO_R15_BRANCH_REFERENCE':
        raise ValueError('explicit predicate result ownership required')
    slots = node.payload.get('reference_binding', {}).get('unknown_slots', [])
    if slots != [{'field_index': 0, 'mask': 4}, {'field_index': 1, 'mask': 8}]:
        raise GapError(node, 'COMPARE_TARGET_SERIALIZED_LAYOUT_UNSUPPORTED')
    fields = node.payload.get('fields', {})
    if set(fields) != {'unbound_bit_0', 'unbound_bit_1'}:
        raise GapError(node, 'COMPARE_TARGET_SERIALIZED_LAYOUT_UNSUPPORTED')
    for operand in fields.values():
        if getattr(operand, 'kind', None) != 'TargetSelectorIR':
            raise GapError(node, 'COMPARE_TARGET_SELECTOR_OPERAND_MISSING')
    receipt = dict(selector_policy=selector_policy, result_policy=result_policy,
        field_map={'TargetType': 'unbound_bit_0', 'CompareType': 'unbound_bit_1'},
        mode='FIRST_NON_NULL_EQUAL', native_mask=15,
        authority='SOURCE_OPERATION_WITH_REFERENCE_CONTEXT_AND_STATUS',
        native_effective_validated=False)
    runtime.policies.setdefault('r13_reference_v1', {}).setdefault(
        'original_entity_comparisons', {})[node.stable_hash()] = receipt
    return dict(task_hash=node.stable_hash(), **receipt)


def original_compare_fields(engine, node):
    """Resolve an opt-in view without mutating the original IR or its hash."""
    from .behavior import GapError
    config = engine.policies.get('r13_reference_v1', {}).get(
        'original_entity_comparisons', {}).get(node.stable_hash())
    if config is None:
        return None
    expected = {'TargetType': 'unbound_bit_0', 'CompareType': 'unbound_bit_1'}
    if (config.get('field_map') != expected or config.get('mode') != 'FIRST_NON_NULL_EQUAL'
            or config.get('selector_policy') != 'MASK15_CALLER_RESOLVED_REFERENCE'
            or config.get('result_policy') != 'BOOLEAN_TO_R15_BRANCH_REFERENCE'
            or config.get('native_mask') != 15):
        raise GapError(node, 'COMPARE_TARGET_REFERENCE_CONTRACT_UNSUPPORTED')
    # Revalidate snapshot-supplied policy and operands as well as API-bound inputs.
    slots = node.payload.get('reference_binding', {}).get('unknown_slots', [])
    if slots != [{'field_index': 0, 'mask': 4}, {'field_index': 1, 'mask': 8}]:
        raise GapError(node, 'COMPARE_TARGET_SERIALIZED_LAYOUT_UNSUPPORTED')
    fields = node.payload.get('fields', {})
    if set(fields) != set(expected.values()) or any(
            getattr(v, 'kind', None) != 'TargetSelectorIR' for v in fields.values()):
        raise GapError(node, 'COMPARE_TARGET_SELECTOR_OPERAND_MISSING')
    return {name: fields[key] for name, key in expected.items()}


def bind_remove_reference(runtime, node, *, pending_callbacks, identity_filter):
    if node.op != 'RPG.GameCore.RemoveModifier':
        raise ValueError('exact RemoveModifier task required')
    roles = node.payload.get('reference_binding', {}).get('roles', {})
    if set(roles) != {'target', 'modifier'}:
        raise ValueError('decoded target and modifier operands required')
    if pending_callbacks not in ('RETAIN_ENQUEUED_REFERENCE', 'CANCEL_NOT_STARTED_REFERENCE'):
        raise ValueError('explicit callback policy required')
    if not isinstance(identity_filter, dict):
        raise ValueError('explicit instance identity filter required')
    policy = runtime.policies.setdefault(POLICY_ID, reference_policy())
    policy['removals'][node.stable_hash()] = {
        'selection': 'CONFIG_TARGET_REFERENCE', 'identity_filter': dict(identity_filter),
        'reason': 'EXPLICIT_ORIGINAL_REMOVE_REFERENCE', 'pending_callbacks': pending_callbacks}
    return {'task_hash': node.stable_hash(), 'source_span': node.payload['span'],
            'authority': 'REFERENCE_MODEL', 'status': 'POLICY_INPUT_BOUND_ONLY',
            'native_effective_validated': False}
