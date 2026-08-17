# -*- coding: utf-8 -*-
"""Sandbox executor tests for Handoff 12 HP Transition Runtime.

All core transitions go through the formal PrimitiveRegistry / Executor path.
The cross-layer test builds the SetHP composition with registered fixed-point
primitives and then executes DirectDamageHP mode 0 through the executor.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.hp import LockHPRecord  # noqa: E402
from hsr_battle_agent.battle_ir.property import (  # noqa: E402
    CURRENT_HP_PROPERTY_ID,
    MaterializationKind,
    PropertyEntry,
)
from hsr_battle_agent.battle_ir.targets import EntityRef  # noqa: E402
from hsr_battle_agent.battle_runtime import hp as hp_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime import property as property_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime.predicates import (  # noqa: E402
    fixpoint_equal,
    fixpoint_from_int32,
    fixpoint_less,
)
from hsr_battle_agent.battle_sandbox.sandbox import Sandbox  # noqa: E402
from hsr_battle_agent.battle_sandbox.state import BattleState  # noqa: E402

MAX_HP_PROPERTY_ID = 1
DIRTY_HP_RATIO_PROPERTY_ID = 7
NEGATIVE_HP_PROPERTY_ID = 9


def fp(value: int) -> int:
    return fixpoint_from_int32(value)


def fp_frac(value: float) -> int:
    """Deterministic fractional FixPoint raw for simple test values."""
    common = int(round(value * (1 << 26)))
    return property_runtime._encode_fixpoint_common(common)


def rec(action: str, kind: int, value: int) -> LockHPRecord:
    return LockHPRecord(action_ref=action, kind=kind, value=fp(value))


def set_entry(
    state: BattleState,
    entity: EntityRef,
    property_id: int,
    value: int,
    *,
    extra_sources: list[tuple[int, int]] | None = None,
) -> None:
    """Create a kind-1 source-zero entry, optionally with extra active slots."""
    source_generation = [1]
    source_active = [True]
    source_value = [value]
    if extra_sources:
        for index, (gen, src_value) in enumerate(extra_sources, start=1):
            source_generation.append(gen)
            source_active.append(True)
            source_value.append(src_value)
    property_runtime.set_property_entry(
        state,
        entity,
        property_id,
        PropertyEntry(
            source_generation=source_generation,
            source_active=source_active,
            source_value=source_value,
            materialization_kind=int(
                MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
            ),
            generation_counter=len(source_generation),
            active_source_extent=len(source_active),
            last_changed_source=0,
            base_or_fallback=0,
            materialized=value,
        ),
    )


def seed_hp_state(
    sandbox: Sandbox,
    entity: EntityRef,
    *,
    current: int = 100,
    max_hp: int = 200,
    ratio: int = 0,
    negative: int = 0,
    current_extra: list[tuple[int, int]] | None = None,
    negative_extra: list[tuple[int, int]] | None = None,
) -> None:
    state = sandbox.context.state
    set_entry(state, entity, CURRENT_HP_PROPERTY_ID, fp(current), extra_sources=current_extra)
    set_entry(state, entity, MAX_HP_PROPERTY_ID, fp(max_hp))
    set_entry(state, entity, DIRTY_HP_RATIO_PROPERTY_ID, fp(ratio))
    if negative is not None:
        set_entry(
            state,
            entity,
            NEGATIVE_HP_PROPERTY_ID,
            fp(negative),
            extra_sources=negative_extra,
        )


def execute_direct_damage(
    sandbox: Sandbox,
    entity: EntityRef,
    delta: int,
    *,
    damage_kind: int = 100,
    mode: int = 0,
    negative_hp_gate: bool = False,
):
    return sandbox.execute(
        "battle.ir.hp.direct_damage.transition",
        component=entity,
        delta=fp(delta),
        damage_kind=damage_kind,
        context_token=None,
        input_record=None,
        mode=mode,
        negative_hp_gate=negative_hp_gate,
    ).value


class TestHPTransitionNoLock(unittest.TestCase):
    def test_no_lock_negative_delta_updates_current_hp_source_0(self):
        sandbox = Sandbox(seed=1201)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        result = execute_direct_damage(sandbox, entity, -30)
        self.assertTrue(fixpoint_equal(result.new_current, fp(70)))
        self.assertTrue(fixpoint_equal(result.applied_delta, fp(-30)))
        entry = property_runtime.get_property_entry(
            sandbox.context.state, entity, CURRENT_HP_PROPERTY_ID
        )
        self.assertTrue(fixpoint_equal(entry.source_value[0], fp(70)))
        self.assertTrue(entry.source_active[0])
        self.assertTrue(fixpoint_equal(entry.materialized, fp(70)))

    def test_no_matching_damage_kind_behaves_as_no_lock(self):
        sandbox = Sandbox(seed=1202)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        hp_runtime.set_lock_hp_records(
            sandbox.context.state, entity, [rec("a", 50, 80)]
        )
        result = execute_direct_damage(sandbox, entity, -30, damage_kind=100)
        self.assertFalse(result.lock_hit)
        self.assertTrue(fixpoint_equal(result.new_current, fp(70)))
        self.assertTrue(fixpoint_equal(result.applied_delta, fp(-30)))

    def test_ordinary_no_lock_does_not_read_negative_hp(self):
        sandbox = Sandbox(seed=1203)
        entity = EntityRef(1)
        set_entry(sandbox.context.state, entity, CURRENT_HP_PROPERTY_ID, fp(100))
        set_entry(sandbox.context.state, entity, MAX_HP_PROPERTY_ID, fp(200))
        set_entry(sandbox.context.state, entity, DIRTY_HP_RATIO_PROPERTY_ID, fp(0))
        # No NegativeHP entry at all: if the no-lock path tried to read it,
        # this would raise PropertyEntryNotFoundError.
        result = execute_direct_damage(sandbox, entity, -30)
        self.assertTrue(fixpoint_equal(result.new_current, fp(70)))

    def test_y_le_zero_records_negative_boundary_and_still_writes(self):
        sandbox = Sandbox(seed=1204)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=50, max_hp=100, ratio=0)
        result = execute_direct_damage(sandbox, entity, -100)
        self.assertTrue(result.negative_record_boundary)
        self.assertTrue(fixpoint_equal(result.new_current, fp(-50)))
        entry = property_runtime.get_property_entry(
            sandbox.context.state, entity, CURRENT_HP_PROPERTY_ID
        )
        self.assertTrue(fixpoint_equal(entry.materialized, fp(-50)))
        boundary_ids = [
            event.primitive_id
            for event in sandbox.context.trace.events
            if getattr(event, "event", None) == "PrimitiveStarted"
            and getattr(event, "primitive_id", None)
            == "battle.ir.hp.boundary.NegativeHPRecordBoundary"
        ]
        self.assertEqual(len(boundary_ids), 1)


class TestLockHP(unittest.TestCase):
    def test_one_matching_lock_clamps_to_t(self):
        sandbox = Sandbox(seed=1205)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        hp_runtime.set_lock_hp_records(
            sandbox.context.state, entity, [rec("a", 100, 80)]
        )
        result = execute_direct_damage(sandbox, entity, -50, negative_hp_gate=True)
        self.assertTrue(result.lock_hit)
        self.assertTrue(fixpoint_equal(result.y, fp(100)))
        self.assertTrue(fixpoint_equal(result.new_current, fp(100)))
        self.assertTrue(fixpoint_equal(result.p, fp(50)))
        self.assertEqual(result.flag, 1)
        self.assertEqual(result.lock_actions, ("a",))
        self.assertTrue(result.negative_hp_written)

    def test_equal_lock_values_preserve_descending_selection_and_forward_actions(self):
        sandbox = Sandbox(seed=1206)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        hp_runtime.set_lock_hp_records(
            sandbox.context.state,
            entity,
            [rec("a", 100, 80), rec("b", 100, 80), rec("c", 100, 80)],
        )
        lock = sandbox.execute(
            "battle.ir.hp.try_get_lock_hp",
            component=entity,
            damage_kind=100,
        ).value
        self.assertTrue(lock.success)
        self.assertTrue(fixpoint_equal(lock.lock_value, fp(80)))
        self.assertEqual(lock.actions, ("a", "b", "c"))

        result = execute_direct_damage(sandbox, entity, -50, negative_hp_gate=True)
        self.assertEqual(result.lock_actions, ("a", "b", "c"))

    def test_non_equal_next_accepted_value_stops_scan_at_exact_point(self):
        sandbox = Sandbox(seed=1207)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        hp_runtime.set_lock_hp_records(
            sandbox.context.state,
            entity,
            [rec("a", 100, 90), rec("b", 100, 80), rec("c", 100, 80)],
        )
        lock = sandbox.execute(
            "battle.ir.hp.try_get_lock_hp",
            component=entity,
            damage_kind=100,
        ).value
        self.assertTrue(lock.success)
        self.assertTrue(fixpoint_equal(lock.lock_value, fp(80)))
        self.assertEqual(lock.actions, ("b", "c"))

    def test_lock_hit_but_c_ge_t_falls_back_to_dirty_ratio_bound(self):
        sandbox = Sandbox(seed=1208)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        # Overwrite DirtyHPRatio with 0.5 and lock value with 0.25 using
        # fractional FixPoint raws (the simple integer helper cannot encode 0.5).
        property_runtime.set_property_entry(
            sandbox.context.state,
            entity,
            DIRTY_HP_RATIO_PROPERTY_ID,
            PropertyEntry(
                source_generation=[1],
                source_active=[True],
                source_value=[fp_frac(0.5)],
                materialization_kind=int(
                    MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
                ),
                generation_counter=1,
                active_source_extent=1,
                last_changed_source=0,
                base_or_fallback=0,
                materialized=fp_frac(0.5),
            ),
        )
        hp_runtime.set_lock_hp_records(
            sandbox.context.state,
            entity,
            [LockHPRecord(action_ref="a", kind=100, value=fp_frac(0.25))],
        )
        result = execute_direct_damage(sandbox, entity, -30)
        self.assertTrue(result.lock_hit)
        self.assertEqual(result.flag, 0)
        self.assertTrue(fixpoint_equal(result.p, fp(0)))
        self.assertTrue(fixpoint_equal(result.new_current, fp(70)))


class TestNegativeHP(unittest.TestCase):
    def test_lock_overflow_p_gt_zero(self):
        sandbox = Sandbox(seed=1209)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        hp_runtime.set_lock_hp_records(
            sandbox.context.state, entity, [rec("a", 100, 80)]
        )
        result = execute_direct_damage(sandbox, entity, -50)
        self.assertEqual(result.flag, 1)
        self.assertTrue(fixpoint_is_positive(result.p))

    def test_negative_hp_gate_false_leaves_negative_hp_untouched(self):
        sandbox = Sandbox(seed=1210)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0, negative=10)
        hp_runtime.set_lock_hp_records(
            sandbox.context.state, entity, [rec("a", 100, 80)]
        )
        before = property_runtime.get_property_entry(
            sandbox.context.state, entity, NEGATIVE_HP_PROPERTY_ID
        ).to_dict()
        result = execute_direct_damage(sandbox, entity, -50, negative_hp_gate=False)
        self.assertFalse(result.negative_hp_written)
        after = property_runtime.get_property_entry(
            sandbox.context.state, entity, NEGATIVE_HP_PROPERTY_ID
        ).to_dict()
        self.assertEqual(after, before)

    def test_negative_hp_gate_true_writes_source_0_fp_add(self):
        sandbox = Sandbox(seed=1211)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0, negative=10)
        hp_runtime.set_lock_hp_records(
            sandbox.context.state, entity, [rec("a", 100, 80)]
        )
        result = execute_direct_damage(sandbox, entity, -50, negative_hp_gate=True)
        self.assertTrue(result.negative_hp_written)
        self.assertTrue(fixpoint_equal(result.old_negative, fp(10)))
        self.assertTrue(fixpoint_equal(result.new_negative, fp(60)))
        entry = property_runtime.get_property_entry(
            sandbox.context.state, entity, NEGATIVE_HP_PROPERTY_ID
        )
        self.assertTrue(fixpoint_equal(entry.source_value[0], fp(60)))
        self.assertTrue(fixpoint_equal(entry.materialized, fp(60)))

    def test_negative_hp_property_path_out_applied_is_neg_d(self):
        sandbox = Sandbox(seed=1212)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0, negative=10)
        hp_runtime.set_lock_hp_records(
            sandbox.context.state, entity, [rec("a", 100, 80)]
        )
        result = execute_direct_damage(sandbox, entity, -50, negative_hp_gate=True)
        self.assertTrue(fixpoint_equal(result.applied_delta, fp(50)))


class TestOutputAndPersistence(unittest.TestCase):
    def test_ordinary_out_applied_is_new_minus_old(self):
        sandbox = Sandbox(seed=1213)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        result = execute_direct_damage(sandbox, entity, -30)
        self.assertTrue(fixpoint_equal(result.applied_delta, fp(-30)))

    def test_writes_preserve_modifier_contribution_source_indices(self):
        sandbox = Sandbox(seed=1214)
        entity = EntityRef(1)
        seed_hp_state(
            sandbox,
            entity,
            current=100,
            max_hp=200,
            ratio=0,
            negative=10,
            current_extra=[(2, fp(20))],
            negative_extra=[(2, fp(5))],
        )
        hp_runtime.set_lock_hp_records(
            sandbox.context.state, entity, [rec("a", 100, 80)]
        )
        result = execute_direct_damage(sandbox, entity, -50, negative_hp_gate=True)
        current = property_runtime.get_property_entry(
            sandbox.context.state, entity, CURRENT_HP_PROPERTY_ID
        )
        self.assertEqual(current.source_value[1], fp(20))
        self.assertTrue(current.source_active[1])
        negative = property_runtime.get_property_entry(
            sandbox.context.state, entity, NEGATIVE_HP_PROPERTY_ID
        )
        self.assertEqual(negative.source_value[1], fp(5))
        self.assertTrue(negative.source_active[1])
        self.assertTrue(result.negative_hp_written)

    def test_clone_isolation(self):
        sandbox = Sandbox(seed=1215)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        branch = sandbox.clone()
        execute_direct_damage(branch, entity, -30)
        original = property_runtime.get_property_entry(
            sandbox.context.state, entity, CURRENT_HP_PROPERTY_ID
        )
        self.assertTrue(fixpoint_equal(original.materialized, fp(100)))
        self.assertNotEqual(branch.state_hash(), sandbox.state_hash())

    def test_snapshot_roundtrip(self):
        sandbox = Sandbox(seed=1216)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0, negative=10)
        hp_runtime.set_lock_hp_records(
            sandbox.context.state, entity, [rec("a", 100, 80)]
        )
        snapshot = sandbox.snapshot()
        before = snapshot.to_dict()
        execute_direct_damage(sandbox, entity, -50, negative_hp_gate=True)
        restored = snapshot.restore_context()
        self.assertEqual(restored.state.to_dict(), before["battle_state"])
        current = property_runtime.get_property_entry(
            restored.state, entity, CURRENT_HP_PROPERTY_ID
        )
        self.assertTrue(fixpoint_equal(current.materialized, fp(100)))

    def test_deterministic_replay_and_stable_hash(self):
        def run() -> str:
            sandbox = Sandbox(seed=1217)
            entity = EntityRef(1)
            seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0, negative=10)
            hp_runtime.set_lock_hp_records(
                sandbox.context.state, entity, [rec("a", 100, 80)]
            )
            execute_direct_damage(sandbox, entity, -50, negative_hp_gate=True)
            return sandbox.state_hash()

        self.assertEqual(run(), run())


class TestUnsupported(unittest.TestCase):
    def test_unsupported_modes_reject_explicitly(self):
        sandbox = Sandbox(seed=1218)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        for mode in (4, 5, 6):
            with self.subTest(mode=mode):
                with self.assertRaises(
                    hp_runtime.UnsupportedDirectDamageHPModeError
                ):
                    sandbox.execute(
                        "battle.ir.hp.direct_damage.transition",
                        component=entity,
                        delta=fp(-30),
                        damage_kind=100,
                        context_token=None,
                        input_record=None,
                        mode=mode,
                        negative_hp_gate=False,
                    )

    def test_non_fixpoint_values_reject_explicitly(self):
        sandbox = Sandbox(seed=1219)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=100, max_hp=200, ratio=0)
        with self.assertRaises(TypeError):
            sandbox.execute(
                "battle.ir.hp.direct_damage.transition",
                component=entity,
                delta="not-a-fixpoint",
                damage_kind=100,
                context_token=None,
                input_record=None,
                mode=0,
                negative_hp_gate=False,
            )
        with self.assertRaises(ValueError):
            sandbox.execute(
                "battle.ir.hp.direct_damage.transition",
                component=entity,
                delta=2**64,
                damage_kind=100,
                context_token=None,
                input_record=None,
                mode=0,
                negative_hp_gate=False,
            )

    def test_positive_direct_change_hp_does_not_guess(self):
        from hsr_battle_agent.battle_runtime import hp as hp_runtime  # noqa: PLC0415

        sandbox = Sandbox(seed=1220)
        entity = EntityRef(1)
        seed_hp_state(sandbox, entity, current=50, max_hp=100, ratio=0)
        # ModifyValue=100, ratio=0 -> target=100, delta=+50 (positive).
        with self.assertRaises(hp_runtime.UnsupportedDirectChangeHPPositiveError):
            hp_runtime.direct_change_hp_mode1_negative(
                sandbox.context.state,
                entity,
                modify_value=fp(100),
                modify_ratio=fp(0),
            )


class TestRegistryExecutorComposition(unittest.TestCase):
    def test_set_hp_negative_delta_composition_through_executor(self):
        sandbox = Sandbox(seed=1301)
        entity = EntityRef(1)
        seed_hp_state(
            sandbox,
            entity,
            current=100,
            max_hp=200,
            ratio=0,
            negative=10,
        )
        hp_runtime.set_lock_hp_records(
            sandbox.context.state, entity, [rec("a", 100, 80)]
        )

        # SetHP config/input -> evaluate ratio/value:
        # target = ModifyValue + fp_mul(MaxHP, ModifyRatio).
        max_hp = property_runtime.get_property_entry(
            sandbox.context.state, entity, MAX_HP_PROPERTY_ID
        ).materialized
        product = sandbox.execute(
            "battle.ir.fixedpoint.multiply",
            left=max_hp,
            right=fp(0),
        ).value
        target = sandbox.execute(
            "battle.ir.fixedpoint.add",
            left=fp(50),
            right=product,
        ).value

        # DirectChangeHP mode=1 negative delta: target - CurrentHP.
        current = property_runtime.get_property_entry(
            sandbox.context.state, entity, CURRENT_HP_PROPERTY_ID
        ).materialized
        delta = sandbox.execute(
            "battle.ir.fixedpoint.subtract",
            left=target,
            right=current,
        ).value
        self.assertTrue(fixpoint_less(delta, fp(0)))

        # TryGetLockHP through the formal executor.
        lock = sandbox.execute(
            "battle.ir.hp.try_get_lock_hp",
            component=entity,
            damage_kind=100,
        ).value
        self.assertTrue(lock.success)
        self.assertEqual(lock.actions, ("a",))

        # DirectDamageHP mode 0 through the formal executor.
        result = sandbox.execute(
            "battle.ir.hp.direct_damage.transition",
            component=entity,
            delta=delta,
            damage_kind=100,
            context_token=None,
            input_record=None,
            mode=0,
            negative_hp_gate=True,
        ).value
        self.assertTrue(result.lock_hit)
        self.assertTrue(fixpoint_equal(result.new_current, fp(100)))
        self.assertTrue(result.negative_hp_written)
        self.assertTrue(fixpoint_equal(result.applied_delta, fp(50)))

        final_current = property_runtime.get_property_entry(
            sandbox.context.state, entity, CURRENT_HP_PROPERTY_ID
        )
        self.assertTrue(fixpoint_equal(final_current.materialized, fp(100)))
        final_negative = property_runtime.get_property_entry(
            sandbox.context.state, entity, NEGATIVE_HP_PROPERTY_ID
        )
        self.assertTrue(fixpoint_equal(final_negative.materialized, fp(60)))


def fixpoint_is_positive(value: int) -> bool:
    from hsr_battle_agent.battle_runtime.predicates import fixpoint_is_positive as _p

    return _p(value)


if __name__ == "__main__":
    unittest.main()
