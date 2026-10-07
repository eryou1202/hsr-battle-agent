"""R13 generic reference regressions, including real non-character corpus records."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools/runtime"))
from hsr_battle_agent.battle_ir.behavior import (AbilityIR, Authority, CompletionIR,
    ExpressionIR, IRNode, PredicateIR, TaskIR, TaskSequenceIR, TargetSelectorIR)
from hsr_battle_agent.battle_ir.behavior_expansion_binding import ExpansionCompiler
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, ExecutionStatus, GapError
from hsr_battle_agent.battle_runtime.behavior_expansion import TARGET_OPERATIONS
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState, ModifierInstance
from r12_runtime_reentry import ARCHIVED_DECODER_ROLES

A = Authority("REFERENCE_MODEL", "r13-test", "synthetic-explicit-fixture", "", semantic_status="REFERENCE_MODEL")


def node(cls, op, payload=None, identity=None):
    return cls(identity or op, op, A, payload)


def literal(value, raw=False):
    return node(ExpressionIR, "literal", {"raw" if raw else "value": value})


def target(op="explicit", **roles):
    if op == "explicit":
        return node(TargetSelectorIR, op, roles)
    return node(TargetSelectorIR, "RPG.GameCore." + op, {"roles": roles})


def pred(op, **roles):
    return node(PredicateIR, "RPG.GameCore." + op, {"roles": roles})


def action(tasks):
    return node(AbilityIR, "ability", {"tasks": node(TaskSequenceIR, "immediate_sequence", {"tasks": tasks})})


def invocation_policy():
    return {"mode": "REFERENCE_CHILD_CONTEXT", "owner": "INHERIT_EXPLICIT", "caster": "INHERIT_EXPLICIT",
        "controller": "REFERENCE_CHILD", "completion": "PARENT_OWNS_COMPLETION",
        "parameters": "EXPLICIT_STACK", "dynamic_provider_parent": "EXPLICIT_SHARED",
        "target_context": "SINGLE_TARGET", "max_depth": 4, "scheduler": "IMMEDIATE_CONTINUATION_ONLY"}


def policies():
    return {"r13_reference_v1": {"target_algebra": "ORDERED_LIST_REFERENCE_V1",
        "predicates": "ALL_TARGETS_REFERENCE_V1", "branches": "SERIALIZED_BRANCH_REFERENCE",
        "sort_directions": {"1": "ASCENDING", "0": "DESCENDING"},
        "target_indices": {"0": "FIRST", "1": "LAST", "2": 8},
        "comparison_enums": {"1": "lt", "5": "ge"},
        "query_masks": {"team_mask": {"2": ["allies"]}, "entity_mask": {"2": ["actor"]}, "alive_mask": {"1": [True]}},
        "target_relations": {name: name for name, op in TARGET_OPERATIONS.items() if op == "map"},
        "target_fetches": {"TargetFetchActualOwner": "owner", "TargetFetchModifierOwner": "modifier_owner",
            "TargetFetchAimAtTargetList": "aim_targets", "TargetFetchByTauntAndAggro": "taunt_targets"},
        "intersection_options": [0, 0], "invocation": invocation_policy(),
        "template_invocation": {**invocation_policy(), "parameter_binding": "STRUCTURE_ONLY"}}}


def state():
    entities = {"a": {"formation": 2, "action_order": 1, "team": "allies", "damage_type": 1, "category": "actor", "alive": True},
                "b": {"formation": 1, "action_order": 2, "team": "allies", "damage_type": 2, "category": "actor", "alive": True},
                "c": {"formation": 1, "action_order": 0, "team": "enemies", "damage_type": 2, "category": "actor", "alive": False}}
    return BehaviorBattleState(entities=entities, properties={"a": {"hp": 2*SCALE, "max_hp": 10*SCALE},
        "b": {"hp": 8*SCALE, "max_hp": 10*SCALE}, "c": {"hp": 0, "max_hp": 10*SCALE}},
        dynamic_values={"parent": {}}, target_context={"selector_input": ["a", "c", "b", "a"],
            "query_candidates": ["c", "b", "a", "a"], "caster": "a", "owner": "a", "param_entity": "a",
            "modifier_owner": "b", "aim_targets": ["b", "a"], "taunt_targets": ["b"], "unique_names": {"unit": ["b"]},
            "parameters": {}, "dynamic_provider_parent": "parent", "current_ability": "root"},
        mechanics={"relations": {name: {"a": ["b", "a"], "b": [], "c": ["a"]}
            for name, op in TARGET_OPERATIONS.items() if op == "map"}})


class BehaviorR13Tests(unittest.TestCase):
    def runtime(self, **kwargs):
        return BehaviorRuntime(state(), policies=policies(), **kwargs)

    def test_sequence_is_pipeline_and_concat_preserves_duplicates(self):
        runtime = self.runtime()
        sequence = target("TargetSequence", steps=[target(entities=["a", "b", "a"]),
            target("TargetSortByFormation", serialized_direction=1), target("TargetIndex", serialized_index=0)])
        self.assertEqual(runtime.select(sequence), ["b"])
        concat = target("TargetConcat", selectors=[target(entities=["a", "b"]), target(entities=["a"])])
        self.assertEqual(runtime.select(concat), ["a", "b", "a"])
        self.assertEqual(runtime.select(target("TargetSequence", steps=[])), [])
        self.assertEqual(runtime.select(target("TargetConcat", selectors=[])), [])

    def test_all_map_operators_use_ordered_explicit_relations(self):
        runtime = self.runtime()
        for name, operation in TARGET_OPERATIONS.items():
            if operation == "map":
                with self.subTest(name=name):
                    self.assertEqual(runtime.select(target(name)), ["b", "a", "a", "b", "a"])
        runtime.state.mechanics["relations"]["TargetMapSummoner"].pop("c")
        with self.assertRaises(GapError):
            runtime.select(target("TargetMapSummoner"))

    def test_sort_stability_direction_and_action_order(self):
        runtime = self.runtime()
        self.assertEqual(runtime.select(target("TargetSortByFormation", serialized_direction=1)), ["c", "b", "a", "a"])
        self.assertEqual(runtime.select(target("TargetSortByFormation", serialized_direction=0)), ["a", "a", "c", "b"])
        self.assertEqual(runtime.select(target("TargetSortByActionOrder", serialized_direction=1)), ["c", "a", "a", "b"])
        runtime.state.entities["b"].pop("formation")
        with self.assertRaises(GapError):
            runtime.select(target("TargetSortByFormation", serialized_direction=1))

    def test_index_out_of_range_and_empty_reference(self):
        runtime = self.runtime()
        self.assertEqual(runtime.select(target("TargetIndex", serialized_index=0)), ["a"])
        self.assertEqual(runtime.select(target("TargetIndex", serialized_index=1)), ["a"])
        self.assertEqual(runtime.select(target("TargetIndex", serialized_index=2)), [])
        runtime.state.target_context["selector_input"] = []
        self.assertEqual(runtime.select(target("TargetIndex", serialized_index=1)), [])
        with self.assertRaises(GapError):
            runtime.select(target("TargetIndex", serialized_index=99))

    def test_take_requires_integer_nonnegative_fixed_amount(self):
        runtime = self.runtime()
        self.assertEqual(runtime.select(target("TargetTake", count=literal(2*SCALE, True))), ["a", "c"])
        for value in (-SCALE, SCALE//2):
            with self.assertRaises(GapError):
                runtime.select(target("TargetTake", count=literal(value, True)))

    def test_query_masks_candidate_order_and_missing_state(self):
        runtime = self.runtime()
        selector = target("TargetQuery", team_mask=2, entity_mask=2, alive_mask=1)
        self.assertEqual(runtime.select(selector), ["b", "a", "a"])
        runtime.state.entities["a"].pop("alive")
        with self.assertRaises(GapError):
            runtime.select(selector)

    def test_fetch_context_null_empty_and_unique_name(self):
        runtime = self.runtime()
        for op, expected in (("TargetFetchActualOwner", ["a"]), ("TargetFetchModifierOwner", ["b"]),
            ("TargetFetchAimAtTargetList", ["b", "a"]), ("TargetFetchByTauntAndAggro", ["b"]), ("TargetFetchNone", [])):
            self.assertEqual(runtime.select(target(op)), expected)
        self.assertEqual(runtime.select(target("TargetFetchUniqueNameEntity", name="unit")), ["b"])
        runtime.state.target_context["aim_targets"] = []
        self.assertEqual(runtime.select(target("TargetFetchAimAtTargetList")), [])
        runtime.state.target_context["owner"] = None
        with self.assertRaises(GapError):
            runtime.select(target("TargetFetchActualOwner"))

    def test_target_filter_param_context_and_rng_rollback(self):
        runtime = self.runtime()
        filt = target("TargetFilter", predicate=pred("ByCharacterDamageType", target=node(TargetSelectorIR, "ParamEntity"), value=1))
        self.assertEqual(runtime.select(filt), ["a", "a"])
        original = runtime.state.stable_hash()
        sequence = target("TargetConcat", selectors=[node(TargetSelectorIR, "random", {"source": target(entities=["a", "b"])}), target("TargetQuery", team_mask=99)])
        with self.assertRaises(GapError):
            runtime.select(sequence)
        self.assertEqual(runtime.state.stable_hash(), original)

    def test_logical_predicates_short_circuit(self):
        runtime = self.runtime()
        false = pred("ByCharacterDamageType", target=target(entities=["a"]), value=2)
        unknown = pred("Unsupported")
        self.assertFalse(runtime.predicate(pred("ByAnd", args=[false, unknown])))
        self.assertTrue(runtime.predicate(pred("ByNot", arg=false)))
        self.assertTrue(runtime.predicate(pred("ByAnd", args=[])))

    def test_property_team_and_hp_ratio_predicates(self):
        runtime = self.runtime()
        self.assertTrue(runtime.predicate(pred("ByTargetTeam", target=target(entities=["a", "b"]), value="allies")))
        self.assertTrue(runtime.predicate(pred("ByCompareHP", target=target(entities=["a"]), serialized_comparison=1, value=literal(3*SCALE, True))))
        ratio = pred("ByCompareHPRatio", target=target(entities=["b"]), serialized_comparison=5, value=literal(SCALE//2, True))
        self.assertTrue(runtime.predicate(ratio))
        runtime.state.properties["b"]["max_hp"] = 0
        with self.assertRaises(GapError):
            runtime.predicate(ratio)

    def test_membership_modifier_presence_and_entity_compare(self):
        runtime = self.runtime()
        instance = ModifierInstance("id", "buff", "a", "b", "b", 1, 1, {})
        runtime.state.modifiers["id"] = instance
        self.assertTrue(runtime.predicate(pred("ByIsContainModifier", target=target(entities=["a"]), modifier=literal("buff"))))
        self.assertFalse(runtime.predicate(pred("ByIsContainModifier", target=target(entities=["b"]), modifier=literal("buff"))))
        self.assertTrue(runtime.predicate(pred("ByTargetListIntersects", left=target(entities=["a", "a"]), right=target(entities=["a"]), left_option=0, right_option=0)))
        with self.assertRaises(GapError):
            runtime.predicate(pred("ByTargetListIntersects", left=target(entities=[]), right=target(entities=[]), left_option=1, right_option=0))
        runtime.policies["r13_reference_v1"]["entity_comparison"] = {"mode": "ORDERED_EQUAL"}
        comparison = node(PredicateIR, "RPG.GameCore.ByCompareTarget", {"fields": {"TargetType": target(entities=["a"]), "CompareType": target(entities=["a"])}})
        self.assertTrue(runtime.predicate(comparison))

    def test_predicate_task_list_branch_and_continuation(self):
        branch = node(TaskIR, "RPG.GameCore.PredicateTaskList", {"roles": {
            "predicate": pred("ByAnd", args=[]), "then": [node(TaskIR, "dynamic_write", {"scope": "parent", "key": "x", "value": literal(SCALE, True)})]}})
        runtime = self.runtime(actions={"run": action([branch, node(CompletionIR, "completion")])})
        self.assertEqual(runtime.step("run").status, ExecutionStatus.COMPLETED)
        self.assertEqual(runtime.state.dynamic_values["parent"]["x"], SCALE)

    def invoke(self, name="child", target_ids=None):
        return node(TaskIR, "RPG.GameCore.TriggerAbility", {"fields": {
            "TargetType": target(entities=target_ids or ["b"]), "AbilityName": literal(name)}})

    def test_invocation_context_parent_completion_and_restore(self):
        child = action([node(TaskIR, "barrier", {"key": "ready"}), node(CompletionIR, "completion")])
        runtime = self.runtime(actions={"run": action([self.invoke()])}, abilities={"child": child})
        before_context = copy.deepcopy(runtime.state.target_context)
        self.assertEqual(runtime.step("run").status, ExecutionStatus.WAITING_SCHEDULER)
        self.assertEqual(runtime.state.target_context["ability_target"], "b")
        self.assertEqual(runtime.state.target_context["parent_ability"], "root")
        restored = BehaviorRuntime.from_snapshot(runtime.snapshot())
        self.assertEqual(restored.stable_hash(), runtime.stable_hash())
        for current in (runtime, restored):
            current.state.scheduler.barriers["ready"] = True
            self.assertEqual(current.run_until_decision().status, ExecutionStatus.DECISION_POINT)
            self.assertEqual(current.state.target_context, before_context)
        self.assertEqual(runtime.stable_hash(), restored.stable_hash())

    def test_invocation_cycle_missing_depth_and_provider_are_gaps(self):
        runtime = self.runtime(actions={"run": action([self.invoke()])}, abilities={"child": action([self.invoke()])})
        self.assertIn("cycle", runtime.step("run").gap.required_capability)
        runtime = self.runtime(actions={"run": action([self.invoke("missing")])})
        self.assertIn("catalog", runtime.step("run").gap.required_capability)
        runtime = self.runtime(actions={"run": action([self.invoke()])}, abilities={"child": action([self.invoke("next")]), "next": action([])})
        runtime.policies["r13_reference_v1"]["invocation"]["max_depth"] = 1
        self.assertIn("depth", runtime.step("run").gap.required_capability)
        runtime = self.runtime(actions={"run": action([self.invoke()])}, abilities={"child": action([])})
        runtime.state.dynamic_values.clear()
        self.assertEqual(runtime.step("run").status, ExecutionStatus.SEMANTIC_GAP)
        self.assertNotIn("reference_invocations", state().mechanics)

    def test_explicit_caller_invocation_and_list_targets(self):
        runtime = self.runtime(actions={"run": action([self.invoke(target_ids=["a", "b"])])}, abilities={"child": action([])})
        runtime.policies["r13_reference_v1"]["invocation"]["target_context"] = "ORDERED_LIST"
        self.assertEqual(runtime.step("run").status, ExecutionStatus.DECISION_POINT)
        runtime = self.runtime(actions={"run": action([self.invoke()])}, abilities={"child": action([])})
        configuration = runtime.policies["r13_reference_v1"]["invocation"]
        configuration.update(mode="EXPLICIT_CALLER_SUPPLIED", contexts={"child": {"owner": "b", "caster": "a", "parameters": {}, "dynamic_provider_parent": "parent"}})
        self.assertEqual(runtime.step("run").status, ExecutionStatus.DECISION_POINT)

    def test_template_catalog_parameters_cycle_and_snapshot(self):
        include = node(TaskIR, "RPG.GameCore.IncludeTaskListTemplate", {"roles": {"template": "generic-template"}})
        runtime = self.runtime(actions={"run": action([include])}, templates={"generic-template": action([])})
        self.assertEqual(BehaviorRuntime.from_snapshot(runtime.snapshot()).stable_hash(), runtime.stable_hash())
        self.assertEqual(runtime.step("run").status, ExecutionStatus.DECISION_POINT)
        runtime = self.runtime(actions={"run": action([include])}, templates={"generic-template": action([include])})
        self.assertIn("cycle", runtime.step("run").gap.required_capability)
        include = node(TaskIR, "RPG.GameCore.IncludeTaskListTemplate", {"roles": {"template": "generic-template", "parameters": {"unknown": 1}}})
        runtime = self.runtime(actions={"run": action([include])}, templates={"generic-template": action([])})
        self.assertIn("parameter inheritance", runtime.step("run").gap.required_capability)

    def test_serialized_dynamic_write_explicit_provider(self):
        write = node(TaskIR, "RPG.GameCore.SetDynamicValue", {"fields": {"DynamicKey": literal("arbitrary"), "Value": literal(2*SCALE, True)}}, "write")
        runtime = self.runtime(actions={"run": action([write])})
        runtime.policies["r13_reference_v1"]["dynamic_providers"] = {"write": "parent"}
        self.assertEqual(runtime.step("run").status, ExecutionStatus.DECISION_POINT)
        self.assertEqual(runtime.state.dynamic_values["parent"]["arbitrary"], 2*SCALE)
        runtime = self.runtime(actions={"run": action([write])})
        self.assertEqual(runtime.step("run").status, ExecutionStatus.SEMANTIC_GAP)

    def test_modifier_insert_refresh_replace_and_numeric_unknown(self):
        instance = ModifierInstance("id", "buff", "b", "a", "a", 1, 1, {"ticks": 3})
        apply = node(TaskIR, "RPG.GameCore.AddModifier", {"fields": {"TargetType": target(entities=["b"]), "ModifierName": literal("buff")}}, "apply")
        runtime = self.runtime(actions={"run": action([apply])})
        binding = {"operation": "INSERT_NEW_REFERENCE", "instance": instance.__dict__}
        runtime.policies["r13_reference_v1"]["modifiers"] = {"lifecycle": "EXPLICIT_STORAGE_ONLY", "applications": {"apply": binding}}
        self.assertEqual(runtime.step("run").status, ExecutionStatus.DECISION_POINT)
        self.assertEqual(runtime.step("run").status, ExecutionStatus.SEMANTIC_GAP)
        runtime.state.scheduler.continuation.clear()
        binding = runtime.policies["r13_reference_v1"]["modifiers"]["applications"]["apply"]
        binding["operation"] = "REFRESH_REFERENCE"
        binding["instance"]["duration"] = {"ticks": 5}
        self.assertEqual(runtime.step("run").status, ExecutionStatus.DECISION_POINT)
        self.assertEqual(runtime.state.modifiers["id"].duration, {"ticks": 5})
        binding["operation"] = "REPLACE_REFERENCE"
        binding["instance"]["stack"] = 7
        self.assertEqual(runtime.step("run").status, ExecutionStatus.DECISION_POINT)
        self.assertEqual(runtime.state.modifiers["id"].stack, 7)
        binding["operation"] = 7
        self.assertEqual(runtime.step("run").status, ExecutionStatus.SEMANTIC_GAP)

    def test_modifier_removal_and_property_stack_atomicity(self):
        remove = node(TaskIR, "RPG.GameCore.RemoveModifier", {"roles": {"target": target(entities=["a"]), "modifier": literal("buff")}})
        stack = node(TaskIR, "RPG.GameCore.StackProperty", {"roles": {"target": target(entities=["a", "b"]), "property": 48, "value": literal(SCALE, True)}})
        runtime = self.runtime(actions={"remove": action([remove]), "stack": action([stack])})
        runtime.state.modifiers["id"] = ModifierInstance("id", "buff", "a", "a", "a", 1, 1, {})
        runtime.policies["r13_reference_v1"].update(modifier_removal="ALL_MATCHING_STORAGE_ONLY", property_stack={"hooks": "EXPLICIT_STORAGE_ONLY", "properties": {"48": "hp"}})
        self.assertEqual(runtime.step("remove").status, ExecutionStatus.DECISION_POINT)
        self.assertEqual(runtime.state.modifiers, {})
        runtime.state.properties["b"].pop("hp")
        before = copy.deepcopy(runtime.state.properties)
        self.assertEqual(runtime.step("stack").status, ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(runtime.state.properties, before)

    def test_event_listener_order_owner_context_condition_and_resume(self):
        dispatch = node(TaskIR, "modifier_event_dispatch", {"event_id": "explicit-event"})
        runtime = self.runtime(actions={"run": action([dispatch])})
        runtime.policies["r13_reference_v1"]["event_callbacks"] = "ORDERED_OWNER_CONTEXT_REFERENCE_V1"
        for identity, owner, order in (("first", "b", 1), ("second", "a", 2)):
            callback = action([node(TaskIR, "barrier", {"key": identity}), self.invoke("sink")])
            registration = {"event_id": "explicit-event", "order": order, "callback": callback.to_dict(), "mutation_result": "NORMAL_GENERIC_TASK_EXECUTION"}
            runtime.state.modifiers[identity] = ModifierInstance(identity, "buff", owner, "a", "a", 1, 1, {}, event_registrations=[registration])
        runtime.abilities["sink"] = action([])
        saved = copy.deepcopy(runtime.state.target_context)
        self.assertEqual(runtime.step("run").status, ExecutionStatus.WAITING_SCHEDULER)
        self.assertEqual(runtime.state.target_context["owner"], "b")
        restored = BehaviorRuntime.from_snapshot(runtime.snapshot())
        for current in (runtime, restored):
            current.state.scheduler.barriers.update(first=True, second=True)
            self.assertEqual(current.run_until_decision().status, ExecutionStatus.DECISION_POINT)
            self.assertEqual(current.state.target_context, saved)
        self.assertEqual(runtime.stable_hash(), restored.stable_hash())

    def test_heal_requires_all_hooks_and_rolls_back_multi_target(self):
        heal = node(TaskIR, "RPG.GameCore.HealHP", {"fields": {"TargetType": target(entities=["a", "b"]), "FormulaType": 2}}, "heal")
        runtime = self.runtime(actions={"run": action([heal])})
        hooks = {key: "EXPLICIT_EMPTY_REFERENCE" for key in ("pre_heal_hooks", "effective_amount_modifiers", "settlement", "property_mutation_hooks", "post_heal_hooks", "resource_listeners")}
        spec = {"hooks": hooks, "formula": "FORMULA_TYPE2_REFERENCE", "settlement": "CLAMP_HP_REFERENCE", "cap_enabled": False,
            "operands": {"d50": 2*SCALE, "d28": SCALE, "d60": 0, "dD0": 0, "d38": 0, "d128": 0, "d48": 100*SCALE, "dD8": 0}}
        runtime.policies["r13_reference_v1"]["heal_inputs"] = {"heal": spec}
        self.assertEqual(runtime.step("run").status, ExecutionStatus.DECISION_POINT)
        self.assertEqual(runtime.state.properties["a"]["hp"], 4*SCALE)
        self.assertEqual(runtime.state.properties["b"]["hp"], 10*SCALE)
        runtime.state.properties["b"].pop("max_hp")
        before = copy.deepcopy(runtime.state.properties)
        self.assertEqual(runtime.step("run").status, ExecutionStatus.SEMANTIC_GAP)
        self.assertEqual(runtime.state.properties, before)
        runtime.state.scheduler.continuation.clear()
        runtime.policies["r13_reference_v1"]["heal_inputs"]["heal"]["hooks"].pop("resource_listeners")
        self.assertEqual(runtime.step("run").status, ExecutionStatus.SEMANTIC_GAP)

    def test_presentation_barrier_position_and_policy_hash(self):
        tasks = [node(TaskIR, "RPG.GameCore." + name) for name in ("TriggerAnimState", "TriggerEffect", "CharacterPlayVO", "WaitAnimState", "MoveToTargetPosition")]
        runtime = self.runtime(actions={"run": action(tasks)})
        baseline_hash = runtime.stable_hash()
        runtime.policies["r13_reference_v1"]["presentation"] = {name: {"classification": "PRESENTATION_ONLY_REFERENCE"} for name in ("TriggerAnimState", "TriggerEffect", "CharacterPlayVO")}
        runtime.policies["r13_reference_v1"]["presentation"].update(WaitAnimState={"classification": "SCHEDULER_BARRIER_REFERENCE", "barrier": "anim"}, MoveToTargetPosition={"classification": "POSITION_MUTATION_REFERENCE", "positions": {"a": [1, 2]}})
        self.assertNotEqual(runtime.stable_hash(), baseline_hash)
        self.assertEqual(runtime.step("run").status, ExecutionStatus.WAITING_SCHEDULER)
        runtime.state.scheduler.barriers["anim"] = True
        self.assertEqual(runtime.run_until_decision().status, ExecutionStatus.DECISION_POINT)
        self.assertEqual(runtime.state.entities["a"]["position"], [1, 2])

    def test_alias_cycle_and_reference_authority(self):
        alias = node(TargetSelectorIR, "RPG.GameCore.TargetAlias", {"alias": "generic"})
        runtime = self.runtime(aliases={"generic": alias})
        with self.assertRaises(GapError):
            runtime.select(alias)
        runtime.aliases["generic"] = target(entities=["a"])
        self.assertEqual(runtime.select(alias), ["a"])
        self.assertTrue(all(row["semantic_authority"] == "REFERENCE_MODEL" for row in runtime.trace))

    def test_compiler_anonymous_masks_are_retained_not_guessed(self):
        compiler = ExpansionCompiler(A, {"primitives": []}, ARCHIVED_DECODER_ROLES)
        record = {"kind": "TargetSelector", "concrete_type": "RPG.GameCore.TargetSequence", "structure": {"fields": [{"mask": 1, "values": [{"kind": "list", "children": []}]}]}}
        ir = compiler.convert(record, "/selector")
        self.assertEqual(ir.payload["field_bindings_status"], "UNRESOLVED")
        self.assertIn("unbound_bit_0", ir.payload["fields"])
        self.assertFalse(ir.payload["reference_binding"]["native_field_names_recovered"])
        self.assertEqual(self.runtime().select(ir), [])
        record["structure"]["fields"][0]["mask"] = 16
        ir = compiler.convert(record, "/unknown")
        with self.assertRaises(GapError):
            self.runtime().select(ir)

    def test_compiler_named_empty_branches_and_dynamic_literal(self):
        compiler = ExpansionCompiler(A, {"primitives": []}, ARCHIVED_DECODER_ROLES)
        record = {"kind": "TaskConfig", "concrete_type": "RPG.GameCore.PredicateTaskList", "structure": {"fields": [{"field": "SuccessTaskList", "values": [{"kind": "list", "children": []}]}]}}
        ir = compiler.convert(record, "/branch")
        self.assertIn("then", ir.payload["reference_binding"]["roles"])
        value = {"type": "RPG.GameCore.DynamicString", "fields": [{"mask": 4, "values": [{"kind": "string", "value": "any"}]}]}
        self.assertEqual(self.runtime().evaluate(compiler.convert(value, "/value")), "any")

    def test_real_non_character_modifier_and_alias_regression(self):
        from r13_coverage import read, sha
        ledger = read("data/control/real_runtime_generic_primitive_ledger_20261007_001.json")
        source = "tmp/audit/r11c_4651_effective_runtime_semantic_closure_20261006_001/mandatory_common_modifier_decode.json"
        compiler = ExpansionCompiler(Authority("REAL_CONTENT_RECONSTRUCTED", "4.6.51", source, sha(REPO/source)), ledger, ARCHIVED_DECODER_ROLES)
        archive = read(source)
        for record in archive["entries"]:
            with self.subTest(name=record["name"]):
                ir = compiler.compile_record(record["graph"], "/" + record["name"], record["name"])
                self.assertEqual(IRNode.from_dict(ir.to_dict()), ir)
                runtime = self.runtime(actions={"root": ir})
                self.assertEqual(runtime.step("root").status, ExecutionStatus.SEMANTIC_GAP)
        source = "tmp/audit/r11_4651_natasha_semantic_closure_20261005_001/global_alias_decode.json"
        alias_archive = read(source)
        compiled = [compiler.convert(entry["value"], f"/entries/{i}") for i, entry in enumerate(alias_archive["entries"])]
        self.assertGreater(len(compiled), 100)
        self.assertTrue(any(ir.op.endswith("TargetSequence") for ir in compiled))

    def test_clone_replay_policy_serialization_and_catalog_hashes(self):
        runtime = self.runtime(actions={"run": action([self.invoke(), node(CompletionIR, "completion")])}, abilities={"child": action([])})
        child_hash = runtime.abilities["child"].stable_hash()
        replayed, results = runtime.replay(["run"])
        clone = runtime.clone()
        self.assertEqual(runtime.step("run").status, ExecutionStatus.COMPLETED)
        clone.step("run")
        self.assertEqual(runtime.stable_hash(), clone.stable_hash())
        self.assertEqual(runtime.stable_hash(), replayed.stable_hash())
        self.assertEqual(runtime.abilities["child"].stable_hash(), child_hash)
        self.assertEqual(results[0].status, ExecutionStatus.COMPLETED)

    def test_additional_property_predicates_and_parameter_indices(self):
        runtime = self.runtime()
        runtime.policies["r13_reference_v1"].update(grid_properties={"4": "hp"}, param_indices="ZERO_BASED_REFERENCE")
        runtime.state.target_context["param_entities"] = ["b", "a"]
        self.assertEqual(runtime.select(target("TargetFetchParamEntityByIndex", index=1)), ["a"])
        self.assertEqual(runtime.select(target("TargetFetchParamEntityByIndex", index=-1)), [])
        runtime.policies["r13_reference_v1"]["target_fetches"]["TargetFetchParamEntityList"] = "param_entities"
        self.assertEqual(runtime.select(target("TargetFetchParamEntityList")), ["b", "a"])
        runtime.state.properties["a"].update(stance_count=SCALE, character_id=7*SCALE)
        self.assertTrue(runtime.predicate(pred("ByCompareGridFightProperty", target=target(entities=["a"]), property=4, serialized_comparison=1, value=literal(3*SCALE, True))))
        self.assertTrue(runtime.predicate(pred("ByCompareStanceCount", target=target(entities=["a"]), serialized_comparison=1, value=literal(2*SCALE, True))))
        self.assertTrue(runtime.predicate(pred("ByCompareCharacterID", target=target(entities=["a"]), value=literal(7*SCALE, True))))
        self.assertTrue(runtime.predicate(pred("ByIsTeammate", target=target(entities=["a", "b"]))))
        runtime.state.entities["b"]["event_subtype"] = 21
        self.assertTrue(runtime.predicate(pred("ByIsBattleEventEntity", target=target(entities=["b"]), value=21)))

    def test_invocation_deferred_ownership_unknown_and_context_rollback(self):
        runtime = self.runtime(actions={"run": action([self.invoke()])}, abilities={"child": action([node(TaskIR, "schedule", {"tick": 1, "tasks": []})])})
        before = copy.deepcopy(runtime.state.target_context)
        self.assertIn("ownership", runtime.step("run").gap.required_capability)
        self.assertEqual(runtime.state.target_context, before)

    def test_frozen_reader_bounds_unknown_readers_and_literals(self):
        from r13_frozen_reader import FrozenReader, StructuralGap
        parser = FrozenReader(bytes([0, 4]), 0, 2, {}, {})
        value = parser.read(0x1E58A230)
        self.assertEqual(value["signed_payload"]["decoded_signed"], "2")
        with self.assertRaises(StructuralGap):
            parser.read(1)
        with self.assertRaises(StructuralGap):
            parser.take(1)

    def test_alive_mask_flag_membership_and_missing_entity_inputs(self):
        runtime = self.runtime()
        runtime.policies["r13_reference_v1"].update(alive_masks={"1": [True]}, behavior_flags="EXPLICIT_MEMBERSHIP_REFERENCE")
        runtime.state.entities["a"]["behavior_flags"] = [76]
        self.assertTrue(runtime.predicate(pred("ByTargetAliveState", target=target(entities=["a", "b"]), value=1)))
        self.assertTrue(runtime.predicate(pred("ByContainBehaviorFlag", target=target(entities=["a"]), value=76)))
        with self.assertRaises(GapError):
            runtime.predicate(pred("ByContainBehaviorFlag", target=target(entities=["b"]), value=76))

    def test_template_explicit_replacement_parameters_and_serialized_policy(self):
        include = node(TaskIR, "RPG.GameCore.IncludeTaskListTemplate", {"roles": {"template": "bound", "parameters": {"serialized": "retained"}}})
        runtime = self.runtime(actions={"run": action([include])}, templates={"bound": action([])})
        runtime.policies["r13_reference_v1"]["template_invocation"].update(mode="EXPLICIT_CALLER_SUPPLIED", parameter_binding="CALLER_SUPPLIED_REPLACEMENT_REFERENCE",
            contexts={"bound": {"owner": "a", "caster": "a", "parameters": {"explicit": 2}, "dynamic_provider_parent": "parent"}})
        self.assertEqual(runtime.step("run").status, ExecutionStatus.DECISION_POINT)
        self.assertEqual(include.payload["roles"]["parameters"], {"serialized": "retained"})

    def test_modifier_dynamic_operands_and_lifecycle_lists_are_not_ignored(self):
        instance = ModifierInstance("id", "buff", "b", "a", "a", 1, 1, {}, dynamic_values={"x": SCALE})
        apply = node(TaskIR, "RPG.GameCore.AddModifier", {"fields": {"TargetType": target(entities=["b"]), "ModifierName": literal("buff"),
            "DynamicValues": {"kind": "dict", "children": ["x", literal(SCALE, True)]}}}, "apply")
        runtime = self.runtime(actions={"run": action([apply])})
        runtime.policies["r13_reference_v1"]["modifiers"] = {"lifecycle": "EXPLICIT_STORAGE_ONLY", "applications": {"apply": {"operation": "INSERT_NEW_REFERENCE", "instance": instance.__dict__}}}
        self.assertEqual(runtime.step("run").status, ExecutionStatus.DECISION_POINT)
        unknown = node(AbilityIR, "ability", {"tasks": node(TaskSequenceIR, "immediate_sequence", {"tasks": []}), "reference_unbound_sequences": [4]})
        runtime = self.runtime(actions={"run": unknown})
        self.assertIn("lifecycle", runtime.step("run").gap.required_capability)

    def test_real_named_algebra_graphs_clone_and_snapshot_regression(self):
        from r13_coverage import read, sha
        from r13_reference_fixtures import fixture
        from hsr_battle_agent.battle_ir.behavior import walk_nodes
        source = "tmp/audit/r11_4651_natasha_semantic_closure_20261005_001/global_alias_decode.json"
        compiler = ExpansionCompiler(Authority("REAL_CONTENT_RECONSTRUCTED", "4.6.51", source, sha(REPO/source)),
            read("data/control/real_runtime_generic_primitive_ledger_20261007_001.json"), ARCHIVED_DECODER_ROLES)
        archive = read(source)
        for identity in ("AllTeammate", "AvatarNextTurnOwnerEntity", "AllEnemy"):
            i, entry = next((i, entry) for i, entry in enumerate(archive["entries"]) if entry["key"]["value"] == identity)
            ir = compiler.convert(entry["value"], f"/entries/{i}/value")
            nodes = list(walk_nodes(ir))
            state_value, aliases, policy = fixture({n.payload["alias"] for n in nodes if n.op == "RPG.GameCore.TargetAlias"},
                {n.payload["key"] for n in nodes if n.op == "lookup"})
            runtime = BehaviorRuntime(state_value, aliases=aliases, policies=policy)
            clone = runtime.clone()
            restored = BehaviorRuntime.from_snapshot(runtime.snapshot())
            with self.subTest(identity=identity):
                expected = runtime.select(ir)
                self.assertEqual(clone.select(ir), expected)
                self.assertEqual(restored.select(ir), expected)
                self.assertEqual(runtime.stable_hash(), restored.stable_hash())


if __name__ == "__main__":
    unittest.main()
