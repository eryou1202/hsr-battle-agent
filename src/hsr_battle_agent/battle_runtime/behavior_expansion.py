"""Compositional R13 primitives governed by serialized reference policies.

No numeric enum is interpreted without a caller-supplied mapping. Ordered entity
lists preserve duplicates unless an explicit operation requests stable uniqueness.
"""
from __future__ import annotations

import copy
from hsr_battle_agent.battle_ir.behavior import IRNode, TaskIR, TaskSequenceIR, walk_nodes
from .behavior_primitives import SCALE, fixed_binary, heal_formula2_core, raw_checked
from .behavior_state import ModifierInstance


TARGET_OPERATIONS = {
    "TargetSequence": "sequence", "TargetConcat": "concat", "TargetFilter": "filter",
    "TargetSortByFormation": "sort", "TargetSortByActionOrder": "sort",
    "TargetIndex": "index", "TargetTake": "take", "TargetQuery": "query",
    "TargetFetchNone": "empty", "TargetFetchActualOwner": "fetch",
    "TargetFetchModifierOwner": "fetch", "TargetFetchAimAtTargetList": "fetch",
    "TargetFetchUniqueNameEntity": "unique_name", "TargetFetchByTauntAndAggro": "fetch",
    "TargetFetchParamEntityByIndex": "param_index", "TargetFetchParamEntityList": "fetch",
    **{name: "map" for name in ("TargetMapAdjoinEntity", "TargetMapAllTeamMember",
        "TargetMapSkillTarget", "TargetMapSummoner", "TargetMapAttackTargetList",
        "TargetMapPartEntity", "TargetMapEnemyTeamEntity", "TargetMapSkillSubTarget",
        "TargetMapSummonedMinions", "TargetMapTeamEntity", "TargetMapSkillPointEntity")},
}
PREDICATE_OPERATIONS = {
    "ByAnd": "all", "ByNot": "not", "ByCharacterDamageType": "property_equal",
    "ByCompareHP": "property_compare", "ByCompareHPRatio": "ratio_compare",
    "ByIsContainModifier": "modifier_presence", "ByCompareTarget": "entity_compare",
    "ByTargetTeam": "property_equal", "ByTargetListIntersects": "intersects",
    "ByCompareGridFightProperty": "property_compare", "ByCompareStanceCount": "property_compare",
    "ByCompareCharacterID": "property_compare", "ByIsTeammate": "teammate",
    "ByIsBattleEventEntity": "property_equal",
    "ByTargetAliveState": "property_membership", "ByContainBehaviorFlag": "flag_membership",
}
TASK_OPERATIONS = ("IncludeTaskListTemplate", "PredicateTaskList", "TriggerAbility",
    "AddModifier", "RemoveModifier", "StackProperty", "SetDynamicValue", "HealHP",
    "WaitAnimState", "TriggerAnimState", "TriggerEffect", "CharacterPlayVO", "MoveToTargetPosition")


def gap(node, text):
    from .behavior import GapError
    raise GapError(node, text)


def policy(engine, node, section):
    root = engine.policies.get("r13_reference_v1", {})
    if section not in root:
        gap(node, f"explicit R13 reference policy:{section}")
    return root[section]


def roles(node):
    binding = node.payload.get("reference_binding", {})
    if binding.get("unknown_slots"):
        masks = [slot["mask"] for slot in binding["unknown_slots"]]
        gap(node, f"anonymous bitmap fields require explicit semantic evidence:{node.op}:masks={masks}")
    return binding.get("roles", node.payload.get("roles", {}))


def items(value):
    if isinstance(value, IRNode) and value.kind == "TaskSequenceIR":
        return value.payload["tasks"]
    if isinstance(value, dict) and value.get("kind") == "list":
        return value["children"]
    if isinstance(value, list):
        return value
    raise TypeError("decoded ordered list required")


def required(node, mapping, key):
    if key not in mapping:
        gap(node, f"explicit reference input:{key}")
    return mapping[key]


def enum_policy(engine, node, group, value):
    mapping = policy(engine, node, group)
    return required(node, mapping, str(value))


def validate_ids(node, state, values):
    if not isinstance(values, list) or any(not isinstance(e, str) or e not in state.entities for e in values):
        gap(node, "ordered resolved entity list; null and unknown entities are gaps")
    return list(values)


def input_targets(node, state):
    return validate_ids(node, state, required(node, state.target_context, "selector_input"))


def target(engine, node, state):
    config = policy(engine, node, "target_algebra")
    if config != "ORDERED_LIST_REFERENCE_V1":
        gap(node, "ordered target algebra reference contract")
    short = node.op.rsplit(".", 1)[-1]
    operation = TARGET_OPERATIONS[short]
    r = roles(node)
    if operation == "empty":
        result = []
    elif operation == "sequence":
        result = None
        for child in items(required(node, r, "steps")):
            local = state.clone()
            if result is not None:
                local.target_context["selector_input"] = result
            result = engine.select(child, local)
            state.rng = copy.deepcopy(local.rng)
        result = [] if result is None else result
    elif operation == "concat":
        result = [e for child in items(required(node, r, "selectors")) for e in engine.select(child, state)]
    elif operation == "filter":
        result = []
        for entity in input_targets(node, state):
            local = state.clone()
            local.target_context["param_entity"] = entity
            if engine.predicate(required(node, r, "predicate"), local):
                result.append(entity)
            state.rng = copy.deepcopy(local.rng)
    elif operation == "sort":
        source = input_targets(node, state)
        direction = (enum_policy(engine, node, "sort_directions", r["serialized_direction"])
                     if "serialized_direction" in r else required(node, policy(engine, node, "sort_defaults"), short))
        if direction not in ("ASCENDING", "DESCENDING"):
            gap(node, "reference sort direction")
        key = "formation" if short == "TargetSortByFormation" else "action_order"
        for entity in source:
            value = required(node, state.entities[entity], key)
            if isinstance(value, bool) or not isinstance(value, int):
                gap(node, "integer reference ordering key")
        result = sorted(source, key=lambda e: state.entities[e][key], reverse=direction == "DESCENDING")
    elif operation in ("index", "take"):
        source = input_targets(node, state)
        if operation == "index":
            index = enum_policy(engine, node, "target_indices", required(node, r, "serialized_index"))
            if index == "FIRST":
                index = 0
            elif index == "LAST":
                index = len(source) - 1
            if isinstance(index, bool) or not isinstance(index, int):
                gap(node, "explicit reference index mapping")
            result = [source[index]] if 0 <= index < len(source) else []
        else:
            count = engine.evaluate(required(node, r, "count"), state)
            if count < 0 or count % SCALE:
                gap(node, "nonnegative integral reference target count")
            result = source[:count // SCALE]
    elif operation == "query":
        # Candidate ordering/category values are caller data, never dict/set order.
        source = validate_ids(node, state, required(node, state.target_context, "query_candidates"))
        r = roles(node)
        if not r:
            gap(node, "explicit query masks")
        categories = policy(engine, node, "query_masks")
        result = []
        for entity in source:
            matches = []
            for field, value in r.items():
                accepted = required(node, required(node, categories, field), str(value))
                key = {"team_mask": "team", "entity_mask": "category", "alive_mask": "alive"}[field]
                matches.append(required(node, state.entities[entity], key) in accepted)
            if all(matches):
                result.append(entity)
    elif operation == "map":
        source = input_targets(node, state)
        relation = required(node, policy(engine, node, "target_relations"), short)
        table = required(node, state.mechanics.get("relations", {}), relation)
        result = []
        for entity in source:
            result.extend(validate_ids(node, state, required(node, table, entity)))
    elif operation == "unique_name":
        name = required(node, r, "name")
        table = required(node, state.target_context, "unique_names")
        result = validate_ids(node, state, required(node, table, name))
    elif operation == "param_index":
        if policy(engine, node, "param_indices") != "ZERO_BASED_REFERENCE":
            gap(node, "explicit param entity index origin")
        source = validate_ids(node, state, required(node, state.target_context, "param_entities"))
        index = required(node, r, "index")
        if isinstance(index, bool) or not isinstance(index, int):
            gap(node, "integer parameter index")
        result = [source[index]] if 0 <= index < len(source) else []
    else:
        context_key = required(node, policy(engine, node, "target_fetches"), short)
        value = required(node, state.target_context, context_key)
        result = value if isinstance(value, list) else [value]
    return validate_ids(node, state, result)


def compare(node, operator, left, right):
    operations = {"eq": lambda: left == right, "ne": lambda: left != right,
                  "lt": lambda: left < right, "le": lambda: left <= right,
                  "gt": lambda: left > right, "ge": lambda: left >= right}
    if operator not in operations:
        gap(node, "explicit comparison operator")
    return operations[operator]()


def predicate(engine, node, state):
    contract = policy(engine, node, "predicates")
    if contract != "ALL_TARGETS_REFERENCE_V1":
        gap(node, "predicate quantification reference contract")
    r = roles(node)
    operation = PREDICATE_OPERATIONS[node.op.rsplit(".", 1)[-1]]
    if operation == "all":
        return all(engine.predicate(child, state) for child in items(required(node, r, "args")))
    if operation == "not":
        return not engine.predicate(required(node, r, "arg"), state)
    if operation == "intersects":
        options = [required(node, r, key) for key in ("left_option", "right_option")]
        accepted = policy(engine, node, "intersection_options")
        if options != accepted:
            gap(node, "serialized target intersection flags")
        return any(e in engine.select(r["right"], state) for e in engine.select(r["left"], state))
    if operation == "entity_compare":
        f = node.payload["fields"]
        # Unknown base bool flags must remain explicit; named targets alone do not bind them.
        options = policy(engine, node, "entity_comparison")
        mode = required(node, options, "mode")
        left, right = engine.select(f["TargetType"], state), engine.select(f["CompareType"], state)
        if mode == "ORDERED_EQUAL":
            return left == right
        if mode == "INTERSECTS":
            return any(e in right for e in left)
        gap(node, "entity comparison reference mode")
    selected = engine.select(required(node, r, "target"), state)
    if operation == "teammate":
        caster = required(node, state.target_context, "caster")
        team = required(node, state.entities[caster], "team")
        return all(required(node, state.entities[e], "team") == team for e in selected)
    if operation == "property_membership":
        accepted = enum_policy(engine, node, "alive_masks", required(node, r, "value"))
        return all(required(node, state.entities[e], "alive") in accepted for e in selected)
    if operation == "flag_membership":
        if policy(engine, node, "behavior_flags") != "EXPLICIT_MEMBERSHIP_REFERENCE":
            gap(node, "explicit behavior-flag membership representation")
        return all(required(node, r, "value") in required(node, state.entities[e], "behavior_flags") for e in selected)
    if operation == "modifier_presence":
        name = engine.evaluate(required(node, r, "modifier"), state)
        return all(any(m.owner == e and m.config_identity == name for m in state.modifiers.values()) for e in selected)
    short = node.op.rsplit(".", 1)[-1]
    if operation == "property_equal":
        key = {"ByCharacterDamageType": "damage_type", "ByTargetTeam": "team", "ByIsBattleEventEntity": "event_subtype"}[short]
        expected = required(node, r, "value")
        return all(required(node, state.entities[e], key) == expected for e in selected)
    operator = "eq" if short == "ByCompareCharacterID" else enum_policy(engine, node, "comparison_enums", required(node, r, "serialized_comparison"))
    expected = engine.evaluate(required(node, r, "value"), state)
    values = []
    for entity in selected:
        props = required(node, state.properties, entity)
        key = "hp"
        if short == "ByCompareStanceCount":
            key = "stance_count"
        elif short == "ByCompareCharacterID":
            key = "character_id"
        elif short == "ByCompareGridFightProperty":
            key = required(node, policy(engine, node, "grid_properties"), str(required(node, r, "property")))
        hp = raw_checked(required(node, props, key))
        if operation == "ratio_compare":
            maximum = raw_checked(required(node, props, "max_hp"))
            if maximum <= 0:
                gap(node, "positive max_hp for ratio comparison")
            hp = fixed_binary("div", hp, maximum)
        values.append(compare(node, operator, hp, expected))
    return all(values)


def invoke(engine, node, state, *, template=False):
    configuration = policy(engine, node, "template_invocation" if template else "invocation")
    mode = required(node, configuration, "mode")
    if mode not in ("REFERENCE_CHILD_CONTEXT", "EXPLICIT_CALLER_SUPPLIED"):
        gap(node, "NATIVE_POLICY_UNKNOWN: explicit reference child invocation required")
    for key, expected in {"controller": "REFERENCE_CHILD", "completion": "PARENT_OWNS_COMPLETION",
        "parameters": "EXPLICIT_STACK", "dynamic_provider_parent": "EXPLICIT_SHARED"}.items():
        if required(node, configuration, key) != expected:
            gap(node, f"unsupported reference invocation relationship:{key}")
    if template:
        r = roles(node)
        identity = required(node, r, "template")
        catalog = engine.templates
        parameters = r.get("parameters")
        if parameters is not None and required(node, configuration, "parameter_binding") not in ("STRUCTURE_ONLY", "CALLER_SUPPLIED_REPLACEMENT_REFERENCE"):
            gap(node, "template parameter inheritance/evaluation remains unknown")
        if parameters is not None:
            if mode != "EXPLICIT_CALLER_SUPPLIED" or configuration.get("parameter_binding") != "CALLER_SUPPLIED_REPLACEMENT_REFERENCE":
                gap(node, "template parameter inheritance/evaluation remains unknown")
        targets = None
    else:
        f = node.payload["fields"]
        identity = engine.evaluate(f["AbilityName"], state)
        targets = engine.select(f["TargetType"], state)
        catalog = engine.abilities
    if identity not in catalog:
        gap(node, f"missing {'template' if template else 'ability'} catalog reference:{identity}")
    child = catalog[identity]
    if child.kind not in ("AbilityIR", "TaskSequenceIR") or child.op in ("decoded_graph", "structure_record"):
        gap(node, "catalog entry requires executable task-list IR")
    if required(node, configuration, "scheduler") != "IMMEDIATE_CONTINUATION_ONLY":
        gap(node, "explicit child scheduler ownership policy")
    if any(n.op in ("schedule", "event_dispatch") for n in walk_nodes(child)):
        gap(node, "child deferred callback/event ownership requires scheduler subsystem")
    frames = state.mechanics.setdefault("reference_invocations", [])
    token = ("template:" if template else "ability:") + identity
    limit = required(node, configuration, "max_depth")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        gap(node, "positive invocation depth bound")
    if any(f["identity"] == token for f in frames):
        gap(node, f"recursive invocation cycle:{token}")
    if len(frames) >= limit:
        gap(node, "maximum reference invocation depth")
    saved = copy.deepcopy(state.target_context)
    if mode == "REFERENCE_CHILD_CONTEXT":
        for key in ("owner", "caster"):
            if required(node, configuration, key) != "INHERIT_EXPLICIT" or key not in saved:
                gap(node, f"explicit invocation {key} context")
            if saved[key] not in state.entities:
                gap(node, "resolved invocation owner/caster identities")
        required(node, saved, "parameters")
        provider = required(node, saved, "dynamic_provider_parent")
        if provider not in state.dynamic_values:
            gap(node, "explicit invocation dynamic provider parent binding")
        context = copy.deepcopy(saved)
        if targets is not None:
            context["ability_targets"] = targets
            target_mode = required(node, configuration, "target_context")
            if target_mode == "SINGLE_TARGET" and len(targets) == 1:
                context["ability_target"] = targets[0]
            elif target_mode == "ORDERED_LIST":
                context.pop("ability_target", None)
            else:
                gap(node, "explicit single/list invocation target context")
    else:
        context = copy.deepcopy(required(node, required(node, configuration, "contexts"), identity))
        for key in ("owner", "caster", "parameters", "dynamic_provider_parent"):
            required(node, context, key)
    context["parent_ability"] = saved.get("current_ability")
    for key in ("owner", "caster"):
        if context[key] not in state.entities:
            gap(node, "resolved child invocation owner/caster identities")
    if context["dynamic_provider_parent"] not in state.dynamic_values:
        gap(node, "resolved child invocation dynamic provider parent")
    context["current_ability"] = identity
    context["reference_parameters"] = copy.deepcopy(saved.get("reference_parameters", [])) + [context["parameters"]]
    frames.append({"identity": token, "context": saved,
                   "completion_requested": state.scheduler.completion_requested,
                   "child_hash": child.stable_hash(), "parent_node": node.node_id})
    state.target_context = context
    return [child, TaskIR(node.node_id + "/return", "reference_return", node.authority, {"identity": token})]


def modifier(engine, node, state):
    spec = policy(engine, node, "modifiers")
    if required(node, spec, "lifecycle") != "EXPLICIT_STORAGE_ONLY":
        gap(node, "modifier activation/event/refresh lifecycle policy")
    binding = required(node, required(node, spec, "applications"), node.node_id)
    operation = required(node, binding, "operation")
    instance = ModifierInstance(**required(node, binding, "instance"))
    fields = node.payload.get("fields", {})
    r = roles(node)
    selector = fields.get("TargetType", r.get("target"))
    name = fields.get("ModifierName", r.get("modifier"))
    if selector is None or name is None:
        gap(node, "decoded modifier target/name reference slots")
    targets = engine.select(selector, state)
    identity = engine.evaluate(name, state)
    if targets != [instance.owner] or identity != instance.config_identity:
        gap(node, "modifier application binding must match decoded owner/config operands")
    if "LifeTime" in fields:
        lifetime = engine.evaluate(fields["LifeTime"], state)
        if instance.duration.get("serialized_lifetime_raw") != lifetime:
            gap(node, "explicit modifier duration unit/lifetime binding")
    if "DynamicValues" in fields:
        if instance.dynamic_values != dynamic_dictionary(engine, node, state, fields["DynamicValues"]):
            gap(node, "modifier dynamic values must match explicit serialized operands")
    for value in (instance.stack, instance.count):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            gap(node, "nonnegative reference modifier stack/count")
    if any(e not in state.entities for e in (instance.owner, instance.caster, instance.original_caster)):
        gap(node, "modifier owner/caster identities")
    if instance.event_registrations and required(node, spec, "events") != "REFERENCE_ORDERED_LISTENERS":
        gap(node, "explicit modifier event registration policy")
    existing = state.modifiers.get(instance.instance_id)
    if operation == "INSERT_NEW_REFERENCE":
        if existing is not None:
            gap(node, "modifier insert collision; no numeric stacking interpretation")
    elif operation == "REFRESH_REFERENCE":
        if existing is None or (existing.config_identity, existing.owner) != (instance.config_identity, instance.owner):
            gap(node, "refresh requires same bound modifier identity/owner")
        instance = copy.deepcopy(existing)
        instance.duration = copy.deepcopy(binding["instance"]["duration"])
    elif operation == "REPLACE_REFERENCE":
        if existing is None:
            gap(node, "replace requires bound existing instance")
    else:
        gap(node, "NATIVE_STACK_POLICY_UNKNOWN")
    state.modifiers[instance.instance_id] = instance
    return []


def dynamic_dictionary(engine, node, state, value):
    if not isinstance(value, dict) or value.get("kind") != "dict":
        gap(node, "decoded dynamic-value dictionary")
    children = value["children"]
    if len(children) % 2:
        gap(node, "paired dynamic-value dictionary entries")
    result = {}
    for index in range(0, len(children), 2):
        key = children[index]
        key = engine.evaluate(key, state) if isinstance(key, IRNode) else key
        if isinstance(key, bool) or not isinstance(key, (int, str)):
            gap(node, "explicit dynamic-value key")
        if str(key) in result:
            gap(node, "duplicate dynamic-value key policy")
        result[str(key)] = raw_checked(engine.evaluate(children[index + 1], state))
    return result


def task(engine, node, state):
    short = node.op.rsplit(".", 1)[-1]
    if short == "TriggerAbility":
        return invoke(engine, node, state)
    if short == "IncludeTaskListTemplate":
        return invoke(engine, node, state, template=True)
    if short == "PredicateTaskList":
        if policy(engine, node, "branches") != "SERIALIZED_BRANCH_REFERENCE":
            gap(node, "explicit serialized branch continuation policy")
        r = roles(node)
        chosen = "then" if engine.predicate(required(node, r, "predicate"), state) else "else"
        children = [] if chosen not in r else items(r[chosen])
        return [TaskSequenceIR(node.node_id + "/branch", "immediate_sequence", node.authority, {"tasks": children})]
    if short == "SetDynamicValue":
        provider = required(node, policy(engine, node, "dynamic_providers"), node.node_id)
        f = node.payload["fields"]
        key = engine.evaluate(f["DynamicKey"], state)
        value = raw_checked(engine.evaluate(f["Value"], state))
        if provider not in state.dynamic_values:
            gap(node, "explicit existing dynamic write provider")
        state.dynamic_values[provider][str(key)] = value
        return []
    if short == "AddModifier":
        return modifier(engine, node, state)
    if short == "RemoveModifier":
        r = roles(node)
        if policy(engine, node, "modifier_removal") != "ALL_MATCHING_STORAGE_ONLY":
            gap(node, "explicit modifier removal lifecycle policy")
        targets = engine.select(required(node, r, "target"), state)
        identity = engine.evaluate(required(node, r, "modifier"), state)
        for key, instance in list(state.modifiers.items()):
            if instance.owner in targets and instance.config_identity == identity:
                del state.modifiers[key]
        return []
    if short == "StackProperty":
        r = roles(node)
        spec = policy(engine, node, "property_stack")
        if required(node, spec, "hooks") != "EXPLICIT_STORAGE_ONLY":
            gap(node, "property stack hooks policy")
        key = required(node, required(node, spec, "properties"), str(required(node, r, "property")))
        value = engine.evaluate(required(node, r, "value"), state)
        for entity in engine.select(required(node, r, "target"), state):
            props = required(node, state.properties, entity)
            props[key] = fixed_binary("add", required(node, props, key), value)
        return []
    if short == "HealHP":
        if node.payload["fields"].get("FormulaType") != 2:
            gap(node, "explicit decoded FormulaType2 binding")
        spec = required(node, policy(engine, node, "heal_inputs"), node.node_id)
        for hook in ("pre_heal_hooks", "effective_amount_modifiers", "settlement",
                     "property_mutation_hooks", "post_heal_hooks", "resource_listeners"):
            if required(node, required(node, spec, "hooks"), hook) != "EXPLICIT_EMPTY_REFERENCE":
                gap(node, f"unsupported reference heal hook:{hook}")
        if required(node, spec, "formula") != "FORMULA_TYPE2_REFERENCE" or required(node, spec, "settlement") != "CLAMP_HP_REFERENCE":
            gap(node, "explicit FormulaType2 HP settlement policy")
        amount = heal_formula2_core(required(node, spec, "operands"), required(node, spec, "cap_enabled")).amount_raw
        targets = engine.select(node.payload["fields"]["TargetType"], state)
        for entity in targets:
            props = required(node, state.properties, entity)
            hp, maximum = raw_checked(required(node, props, "hp")), raw_checked(required(node, props, "max_hp"))
            if not 0 <= hp <= maximum:
                gap(node, "bounded reference HP storage")
            props["hp"] = min(maximum, fixed_binary("add", hp, amount))
        return []
    spec = required(node, policy(engine, node, "presentation"), short)
    classification = required(node, spec, "classification")
    if classification == "PRESENTATION_ONLY_REFERENCE" and short in ("TriggerAnimState", "TriggerEffect", "CharacterPlayVO"):
        state.presentation.setdefault("reference_nodes", []).append(node.node_id)
        return []
    if classification == "SCHEDULER_BARRIER_REFERENCE" and short == "WaitAnimState":
        from .behavior import ExecutionStatus
        key = required(node, spec, "barrier")
        return [] if state.scheduler.barriers.get(key, False) else ExecutionStatus.WAITING_SCHEDULER
    if classification == "POSITION_MUTATION_REFERENCE" and short == "MoveToTargetPosition":
        for entity, position in required(node, spec, "positions").items():
            if entity not in state.entities:
                gap(node, "resolved position mutation entity")
            state.entities[entity]["position"] = copy.deepcopy(position)
        return []
    gap(node, "UNKNOWN_REQUIRES_ORACLE: presentation/scheduler classification")


def reference_return(engine, node, state):
    frames = state.mechanics.get("reference_invocations", [])
    if not frames or frames[-1]["identity"] != node.payload["identity"]:
        gap(node, "matched invocation continuation frame")
    frame = frames.pop()
    state.target_context = frame["context"]
    state.scheduler.completion_requested = frame["completion_requested"]
    return []


def modifier_event(engine, node, state):
    spec = policy(engine, node, "event_callbacks")
    if spec != "ORDERED_OWNER_CONTEXT_REFERENCE_V1":
        gap(node, "event ID/listener ordering reference policy")
    event_id = node.payload["event_id"]
    listeners = []
    for instance in state.modifiers.values():
        for ordinal, registration in enumerate(instance.event_registrations):
            if registration.get("event_id") == event_id:
                order = required(node, registration, "order")
                if isinstance(order, bool) or not isinstance(order, int):
                    gap(node, "integer event listener order")
                listeners.append((order, instance.instance_id, ordinal, instance, registration))
    result = []
    for _, _, ordinal, instance, registration in sorted(listeners, key=lambda x: x[:3]):
        callback = IRNode.from_dict(required(node, registration, "callback"))
        condition = registration.get("condition")
        local = state.clone()
        local.target_context.update(owner=instance.owner, caster=instance.caster,
                                    modifier_owner=instance.owner, original_caster=instance.original_caster)
        if condition is not None and not engine.predicate(IRNode.from_dict(condition), local):
            state.rng = copy.deepcopy(local.rng)
            continue
        state.rng = copy.deepcopy(local.rng)
        # A scheduled context wrapper preserves owner/caster across snapshot/resume.
        result.append(TaskIR(node.node_id + "/listener/" + instance.instance_id + "/" + str(ordinal),
            "reference_context_callback", node.authority,
            {"context": local.target_context, "callback": callback,
             "mutation_result": required(node, registration, "mutation_result")}))
    return result


def context_callback(engine, node, state):
    if node.payload["mutation_result"] != "NORMAL_GENERIC_TASK_EXECUTION":
        gap(node, "explicit event callback mutation result policy")
    frames = state.mechanics.setdefault("reference_invocations", [])
    identity = "callback:" + node.node_id
    frames.append({"identity": identity, "context": copy.deepcopy(state.target_context),
                   "completion_requested": state.scheduler.completion_requested})
    state.target_context = node.payload["context"]
    return [node.payload["callback"], TaskIR(node.node_id + "/return", "reference_return", node.authority, {"identity": identity})]


def install(registry):
    for short in TARGET_OPERATIONS:
        registry.register("target", "RPG.GameCore." + short, target, "conditional_reference_r13_v1")
    for short in PREDICATE_OPERATIONS:
        registry.register("predicate", "RPG.GameCore." + short, predicate, "conditional_reference_r13_v1")
    for short in TASK_OPERATIONS:
        identity = "RPG.GameCore." + short
        previous = registry.handlers["task"].get(identity)
        def handler(engine, node, state, previous=previous):
            if "r13_reference_v1" not in engine.policies and previous:
                return previous[1](engine, node, state)
            return task(engine, node, state)
        registry.handlers["task"][identity] = ("conditional_reference_r13_v1", handler)
    registry.register("task", "reference_return", reference_return, "reference_r13_v1")
    registry.register("task", "modifier_event_dispatch", modifier_event, "reference_r13_v1")
    registry.register("task", "reference_context_callback", context_callback, "reference_r13_v1")
