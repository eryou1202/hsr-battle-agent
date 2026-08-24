"""Strongest honest Turn -> real content -> formula -> event-boundary E2E."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.healing import (  # noqa: E402
    RealSkillExternalBindings,
    ResolvedDynamicFloat,
)
from hsr_battle_agent.battle_ir.property import MaterializationKind, PropertyEntry  # noqa: E402
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet  # noqa: E402
from hsr_battle_agent.battle_ir.turns import ActionCompletionBoundary  # noqa: E402
from hsr_battle_agent.battle_runtime import healing as heal_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime import property as property_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime import turns as turn_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime.predicates import (  # noqa: E402
    fixpoint_equal,
    fixpoint_from_int32,
)
from hsr_battle_agent.battle_sandbox.sandbox import Sandbox  # noqa: E402
from hsr_battle_agent.game_data.real_skill import (  # noqa: E402
    load_natasha_skill02_heal_config,
)


def fp(value: int) -> int:
    return fixpoint_from_int32(value)


def seed(sandbox: Sandbox, entity: EntityRef, property_id: int, value: int) -> None:
    property_runtime.set_property_entry(
        sandbox.context.state,
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


class TestRealSkillTurnE2E30(unittest.TestCase):
    def test_turn_selects_natasha_and_real_skill_reaches_ordered_boundaries(self) -> None:
        sandbox = Sandbox(seed=30)
        natasha = EntityRef(100)
        ally = EntityRef(200)
        seed(sandbox, natasha, turn_runtime.REMAINING_ACTION_DELAY_PROPERTY_ID, 10)
        seed(sandbox, ally, turn_runtime.REMAINING_ACTION_DELAY_PROPERTY_ID, 20)
        seed(sandbox, natasha, heal_runtime.HEAL_RATIO_PROPERTY_ID, 0)
        seed(sandbox, ally, heal_runtime.MAX_HP_PROPERTY_ID, 1000)
        seed(sandbox, ally, heal_runtime.CURRENT_HP_PROPERTY_ID, 400)
        seed(sandbox, ally, heal_runtime.HEAL_TAKEN_RATIO_PROPERTY_ID, 0)
        turn_runtime.initialize_turn_timeline(
            sandbox.context.state, TargetSet.of(natasha, ally)
        )

        turn = turn_runtime.advance_to_next_actor(sandbox.context.state)
        self.assertEqual(turn.actor, natasha)
        config = load_natasha_skill02_heal_config()
        bindings = RealSkillExternalBindings(
            predicate_satisfied=True,
            predicate_provenance="e2e:explicit-BySkillPointActivated-resolution",
            ability_target=ally,
            target_provenance="e2e:explicit-AbilityTargetEntity-resolution",
            dynamic_values=(
                ResolvedDynamicFloat(
                    formula_operand=config.dispel_numbers.sole_int32_operand,
                    value_raw=fp(1),
                    provenance="e2e:external-DispelStatus.Numbers",
                ),
                ResolvedDynamicFloat(
                    formula_operand=config.heal_percentage.sole_int32_operand,
                    value_raw=fp(1),
                    provenance="e2e:external-HealPercentage",
                ),
                ResolvedDynamicFloat(
                    formula_operand=config.modify_value.sole_int32_operand,
                    value_raw=fp(50),
                    provenance="e2e:external-ModifyValue",
                ),
            ),
            ordinary_healer_branch=True,
            healer_branch_provenance="e2e:explicit-non-225-component-branch",
        )
        hp_before = property_runtime.get_property_entry(
            sandbox.context.state, ally, heal_runtime.CURRENT_HP_PROPERTY_ID
        ).materialized
        state_hash_before = sandbox.state_hash()
        result = heal_runtime.execute_natasha_skill02_boundary(
            sandbox.context.state, natasha, config, bindings
        )

        self.assertEqual(result.status, "ORDERED_EFFECT_BOUNDARIES_EMITTED")
        self.assertEqual(result.dispel_request.order, 2)
        self.assertTrue(fixpoint_equal(result.heal_request.amount_raw, fp(650)))
        self.assertEqual(
            result.heal_request.consumer_status,
            "POSITIVE_HEAL_EVENT_CONSUMER_NOT_RECOVERED",
        )
        hp_after = property_runtime.get_property_entry(
            sandbox.context.state, ally, heal_runtime.CURRENT_HP_PROPERTY_ID
        ).materialized
        self.assertTrue(fixpoint_equal(hp_after, hp_before))
        self.assertEqual(sandbox.state_hash(), state_hash_before)

        # The real-content boundary does not guess post-action recharge.
        turn_runtime.acknowledge_action_completion(
            sandbox.context.state,
            ActionCompletionBoundary(
                actor=natasha,
                next_action_delay_raw=fp(30),
                provenance="e2e:explicit-next-delay-after-boundary",
            ),
        )
        next_turn = turn_runtime.advance_to_next_actor(sandbox.context.state)
        self.assertEqual(next_turn.actor, ally)


if __name__ == "__main__":
    unittest.main()
