"""Unit coverage for the scoped real Natasha heal boundary runtime."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.healing import (  # noqa: E402
    RealSkillExternalBindings,
)
from hsr_battle_agent.battle_ir.property import MaterializationKind, PropertyEntry  # noqa: E402
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet  # noqa: E402
from hsr_battle_agent.battle_runtime import healing as heal_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime import property as property_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime import turns as turn_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime.predicates import (  # noqa: E402
    fixpoint_equal,
    fixpoint_from_int32,
)
from hsr_battle_agent.battle_sandbox.state import BattleState  # noqa: E402
from hsr_battle_agent.game_data.real_skill import (  # noqa: E402
    load_natasha_skill02_heal_config,
)


def fp(value: int) -> int:
    return fixpoint_from_int32(value)


def seed(state: BattleState, entity: EntityRef, property_id: int, value: int) -> None:
    property_runtime.set_property_entry(
        state,
        entity,
        property_id,
        PropertyEntry(
            source_generation=[1],
            source_active=[True],
            source_value=[fp(value)],
            materialization_kind=int(MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION),
            generation_counter=1,
            active_source_extent=1,
            last_changed_source=0,
            base_or_fallback=0,
            materialized=fp(value),
        ),
    )


class TestHealFormulaType4Ordinary30(unittest.TestCase):
    def test_missing_hp_plus_modify_and_ordinary_ratios(self) -> None:
        amount = heal_runtime.heal_formula_type4_ordinary(
            target_max_hp_raw=fp(1000),
            target_current_hp_raw=fp(400),
            heal_percentage_raw=fp(1),
            modify_value_raw=fp(50),
            healer_heal_ratio_raw=fp(1),
            target_heal_taken_ratio_raw=fp(0),
        )
        self.assertTrue(fixpoint_equal(amount, fp(1300)))

    def test_non_positive_result_clamps_to_zero(self) -> None:
        amount = heal_runtime.heal_formula_type4_ordinary(
            target_max_hp_raw=fp(100),
            target_current_hp_raw=fp(200),
            heal_percentage_raw=fp(1),
            modify_value_raw=fp(0),
            healer_heal_ratio_raw=fp(0),
            target_heal_taken_ratio_raw=fp(0),
        )
        self.assertEqual(amount, 0)


class TestHealBoundaryGuards30(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_natasha_skill02_heal_config()
        self.caster = EntityRef(1)
        self.target = EntityRef(2)
        self.state = BattleState()
        seed(self.state, self.caster, turn_runtime.REMAINING_ACTION_DELAY_PROPERTY_ID, 1)
        turn_runtime.initialize_turn_timeline(self.state, TargetSet.of(self.caster))
        turn_runtime.advance_to_next_actor(self.state)

    def bindings(self, *, predicate: bool, ordinary: bool = True) -> RealSkillExternalBindings:
        return RealSkillExternalBindings(
            predicate_satisfied=predicate,
            predicate_provenance="test:external-predicate",
            ability_target=self.target,
            target_provenance="test:AbilityTargetEntity",
            dynamic_values=(),
            ordinary_healer_branch=ordinary,
            healer_branch_provenance="test:ordinary-component",
        )

    def test_false_predicate_emits_no_success_tasks(self) -> None:
        result = heal_runtime.execute_natasha_skill02_boundary(
            self.state, self.caster, self.config, self.bindings(predicate=False)
        )
        self.assertEqual(result.status, "PREDICATE_FALSE_NO_SUCCESS_TASKS")
        self.assertIsNone(result.dispel_request)
        self.assertIsNone(result.heal_request)

    def test_special_component_branch_is_explicitly_rejected(self) -> None:
        with self.assertRaises(heal_runtime.UnsupportedSpecialHealComponentError):
            heal_runtime.execute_natasha_skill02_boundary(
                self.state,
                self.caster,
                self.config,
                self.bindings(predicate=True, ordinary=False),
            )

    def test_non_active_caster_is_rejected(self) -> None:
        with self.assertRaises(heal_runtime.RealSkillTurnMismatchError):
            heal_runtime.execute_natasha_skill02_boundary(
                self.state, EntityRef(99), self.config, self.bindings(predicate=False)
            )


if __name__ == "__main__":
    unittest.main()
