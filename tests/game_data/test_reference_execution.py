"""Executable-reference bridge tests using real canonical behavior records."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
import unittest

from hsr_battle_agent.game_data.behavior_compiler import BehaviorCompiler
from hsr_battle_agent.game_data.damage_survival_reference import SurvivalState
from hsr_battle_agent.game_data.reference_execution import (
    ExecutionContext,
    ReferenceBattleState,
    RuntimeEntity,
    SemanticExecutor,
)


CORPUS_PATH = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")
HOT_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_Natasha_00_Ability.json:GlobalModifiers:MAvatar_Natasha_00_HOT_HPByMaxHP"
PROPERTY_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Property.json:MCommon_AttackRatioUp"


def _record(behavior_id: str) -> dict:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return next(record for record in corpus["records"] if record["behavior_id"] == behavior_id)


class ReferenceExecutionTest(unittest.TestCase):
    def test_natasha_hot_compiles_and_executes_through_generic_bridge(self) -> None:
        compiled = BehaviorCompiler().compile_record(_record(HOT_ID))
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("900"), Decimal("900"))),
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("800"), Decimal("1000"))),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled,
            "MODIFIER_CALLBACK:MAvatar_Natasha_00_HOT_HPByMaxHP._CallbackList[0]:OnPhase1",
            state,
            ExecutionContext(
                caster_id="p1",
                modifier_owner_id="p1",
                modifier_id="MAvatar_Natasha_00_HOT_HPByMaxHP",
                dynamic_hash_values={"1733325153": "0.05", "2136609680": "0"},
            ),
        )
        self.assertEqual(result.state.entity("p1").survival.hp, Decimal("850.00"))
        self.assertEqual([item["disposition"] for item in result.trace], ["BRANCH_SUCCESS", "HEADLESS_PRESENTATION_OMITTED", "HEAL_COMMITTED"])

    def test_real_stack_property_compiles_and_executes_through_generic_bridge(self) -> None:
        compiled = BehaviorCompiler().compile_record(_record(PROPERTY_ID))
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1000"), Decimal("1000")))})
        result = SemanticExecutor().execute_entrypoint(
            compiled,
            "MODIFIER_CALLBACK:MCommon_AttackRatioUp._CallbackList[0]:OnStack",
            state,
            ExecutionContext(
                caster_id="p1",
                modifier_owner_id="p1",
                modifier_id="MCommon_AttackRatioUp",
                dynamic_hash_values={"2128130574": "0.12"},
            ),
        )
        self.assertEqual(result.state.property_state("p1").read("AttackAddedRatio"), Decimal("0.12"))
        self.assertEqual(result.trace[0]["disposition"], "PROPERTY_CONTRIBUTION_SET")

    def test_dynamic_value_write_uses_shared_store_and_scope_resolution(self) -> None:
        record = {
            "behavior_id": "dynamic-fixture", "owner_kind": "Modifier", "owner_ref": "dynamic-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTACK", "operations": [{
                "operation_id": "set", "source_type": "RPG.GameCore.SetDynamicValue", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"ContextScope": "ContextCaster", "DynamicKey": {"Value": "stacks"},
                              "Value": {"IsDynamic": False, "FixedValue": {"Value": 3}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONSTACK", state, ExecutionContext(caster_id="p1"))
        self.assertEqual(result.state.dynamic_store.read("p1", "stacks"), Decimal("3"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET")

    def test_unbound_operation_remains_a_hard_execution_error(self) -> None:
        compiled = BehaviorCompiler().compile_record({
            "behavior_id": "fixture", "owner_kind": "Modifier", "owner_ref": "fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "bad", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "children": [],
            }]}],
        })
        self.assertEqual(compiled["compile_status"], "COMPILED_STRUCTURE_ONLY")
        with self.assertRaisesRegex(Exception, "not compiled"):
            SemanticExecutor().execute_entrypoint(
                compiled, "ONSTART",
                ReferenceBattleState(entities={"p": RuntimeEntity("p", "light", SurvivalState(Decimal("1"), Decimal("1")))}),
                ExecutionContext(caster_id="p"),
            )

    def test_closed_entrypoint_executes_even_when_another_entrypoint_is_structural_only(self) -> None:
        record = {
            "behavior_id": "mixed", "owner_kind": "Modifier", "owner_ref": "mixed", "source_refs": [],
            "entrypoints": [
                {"event": "HEAL", "operations": [{
                    "operation_id": "heal", "source_type": "RPG.GameCore.HealHP", "kind": "HEAL_REQUEST",
                    "semantic_status": "MODELLED", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "Caster"},
                    "arguments": {"FormulaType": "HealByHealerMaxHP", "HealPercentage": {"IsDynamic": False, "FixedValue": {"Value": 1}}, "ModifyValue": {"IsDynamic": False, "FixedValue": {"Value": 0}}}, "children": [],
                }]},
                {"event": "UNBOUND", "operations": [{
                    "operation_id": "add", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER",
                    "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "arguments": {}, "children": [],
                }]},
            ],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "COMPILED_STRUCTURE_ONLY")
        self.assertTrue(compiled["entrypoints"][0]["executable_reference"])
        self.assertFalse(compiled["entrypoints"][1]["executable_reference"])
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("10")))})
        result = SemanticExecutor().execute_entrypoint(compiled, "HEAL", state, ExecutionContext(caster_id="p1"))
        self.assertEqual(result.state.entity("p1").survival.hp, Decimal("10"))


if __name__ == "__main__":
    unittest.main()
