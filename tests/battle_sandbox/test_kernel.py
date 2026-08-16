# -*- coding: utf-8 -*-
"""Battle sandbox kernel infrastructure tests (Kernel 01)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.catalog import load_catalog_primitives  # noqa: E402
from hsr_battle_agent.battle_ir.model import (  # noqa: E402
    DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_ARRAY_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_MAP_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_NULL_PRIMITIVE_ID,
    DYNAMIC_VALUE_STRING_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_BOOL_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_DOUBLE_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_FLOAT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_LONG_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_UINT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TYPE_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_EQUAL_INT32_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_NOT_EQUAL_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FROM_FIXPOINT_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FROM_INT32_PRIMITIVE_ID,
    FIXPOINT_EQUAL_PRIMITIVE_ID,
    FIXPOINT_FROM_INT32_PRIMITIVE_ID,
    FIXPOINT_GREATER_EQUAL_PRIMITIVE_ID,
    FIXPOINT_GREATER_PRIMITIVE_ID,
    FIXPOINT_IS_NEGATIVE_PRIMITIVE_ID,
    FIXPOINT_IS_POSITIVE_PRIMITIVE_ID,
    FIXPOINT_IS_ZERO_PRIMITIVE_ID,
    FIXPOINT_LESS_EQUAL_PRIMITIVE_ID,
    FIXPOINT_LESS_PRIMITIVE_ID,
    FIXPOINT_NOT_EQUAL_PRIMITIVE_ID,
    PrimitiveCall,
)
from hsr_battle_agent.battle_ir.semantic_artifact import (  # noqa: E402
    load_vertical_slice_01,
)
from hsr_battle_agent.battle_ir.values import DynamicValue  # noqa: E402
from hsr_battle_agent.battle_runtime.values import dynamic_value_equals  # noqa: E402
from hsr_battle_agent.battle_sandbox.context import ExecutionContext  # noqa: E402
from hsr_battle_agent.battle_sandbox.errors import (  # noqa: E402
    DuplicatePrimitiveError,
    FrozenRegistryError,
    InvalidPrimitiveInputError,
    StubNotImplementedError,
    UnsupportedPrimitiveError,
    UnsupportedStateVersionError,
)
from hsr_battle_agent.battle_sandbox.executor import PrimitiveExecutor  # noqa: E402
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry  # noqa: E402
from hsr_battle_agent.battle_sandbox.rng import (  # noqa: E402
    CLIENT_RNG_ALGORITHM,
    SANDBOX_RNG,
    SANDBOX_RNG_ALGORITHM,
    SandboxRng,
)
from hsr_battle_agent.battle_sandbox.sandbox import Sandbox  # noqa: E402
from hsr_battle_agent.battle_sandbox.snapshot import (  # noqa: E402
    SandboxSnapshot,
    capture_snapshot,
)
from hsr_battle_agent.battle_sandbox.state import (  # noqa: E402
    BATTLE_STATE_SCHEMA_VERSION,
    BattleState,
)
from hsr_battle_agent.battle_sandbox.trace import (  # noqa: E402
    TRACE_SCHEMA,
    ExecutionTrace,
    PrimitiveFinished,
    PrimitiveStarted,
)


def _call(lhs: DynamicValue, rhs: DynamicValue) -> PrimitiveCall:
    return PrimitiveCall.create(DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID, lhs=lhs, rhs=rhs)


class TestDeterministicRng(unittest.TestCase):
    def test_same_seed_same_sequence(self):
        left = [SandboxRng(seed=123).next_u64() for _ in range(20)]
        right = [SandboxRng(seed=123).next_u64() for _ in range(20)]
        self.assertEqual(left, right)

    def test_different_seed_different_sequence(self):
        left = SandboxRng(seed=1)
        right = SandboxRng(seed=2)
        self.assertNotEqual(left.next_u64(), right.next_u64())

    def test_clone_continues_identical_sequence(self):
        source = SandboxRng(seed=99)
        source.next_u64()
        branch = source.clone()
        expected = [source.next_u64() for _ in range(10)]
        actual = [branch.next_u64() for _ in range(10)]
        self.assertEqual(expected, actual)

    def test_state_dict_roundtrip(self):
        source = SandboxRng(seed=77)
        for _ in range(3):
            source.next_u64()
        restored = SandboxRng.from_dict(source.to_dict())
        self.assertEqual(
            [source.next_u64() for _ in range(10)],
            [restored.next_u64() for _ in range(10)],
        )

    def test_next_u64_bounds(self):
        values = [SandboxRng(seed=5).next_u64() for _ in range(100)]
        self.assertTrue(all(0 <= value < 2**64 for value in values))

    def test_labels_are_recorded(self):
        self.assertEqual(CLIENT_RNG_ALGORITHM, "UNKNOWN")
        self.assertEqual(SANDBOX_RNG, "DETERMINISTIC_ABSTRACTION")
        self.assertEqual(SANDBOX_RNG_ALGORITHM, "PYTHON_RANDOM_MT19937")

    def test_reject_invalid_rng_state(self):
        with self.assertRaises(ValueError):
            SandboxRng.from_state((3, tuple(range(10)), None))
        with self.assertRaises(ValueError):
            SandboxRng.from_dict({"schema_version": 99, "algorithm": "x", "state": {}})


class TestBattleStateCloneSnapshotHash(unittest.TestCase):
    def test_clone_isolated_extensions(self):
        original = BattleState()
        original.set_extension("kernel_01_probe", {"nested": [1, 2]})
        branch = original.clone()
        branch.set_extension("kernel_01_probe", {"nested": [9]})
        self.assertEqual(original.extensions, {"kernel_01_probe": {"nested": [1, 2]}})
        self.assertEqual(branch.extensions, {"kernel_01_probe": {"nested": [9]}})

    def test_clone_hash_initially_identical(self):
        original = BattleState()
        original.set_extension("marker", 1)
        branch = original.clone()
        self.assertEqual(original.state_hash(), branch.state_hash())

    def test_modified_clone_hash_changes(self):
        original = BattleState()
        original.set_extension("marker", 1)
        branch = original.clone()
        branch.set_extension("marker", 2)
        self.assertNotEqual(original.state_hash(), branch.state_hash())

    def test_state_dict_roundtrip_and_stable_hash(self):
        original = BattleState()
        original.set_extension("k", {"b": 2, "a": 1})
        restored = BattleState.from_dict(original.to_dict())
        self.assertEqual(restored.extensions, original.extensions)
        # Hash is independent of dict insertion order in the serialized form.
        self.assertEqual(restored.state_hash(), original.state_hash())

    def test_unknown_state_version_rejected(self):
        with self.assertRaises(UnsupportedStateVersionError):
            BattleState.from_dict({"schema_version": 99, "extensions": {}})

    def test_non_json_extension_rejected(self):
        with self.assertRaises(TypeError):
            BattleState().set_extension("bad", object())

    def test_tuple_rejected_by_strict_json_model(self):
        with self.assertRaises(TypeError):
            BattleState().set_extension("x", (1, 2))
        with self.assertRaises(TypeError):
            BattleState(extensions={"x": (1, 2)})
        with self.assertRaises(TypeError):
            BattleState.from_dict(
                {"schema_version": BATTLE_STATE_SCHEMA_VERSION, "extensions": {"x": (1, 2)}}
            )

    def test_setter_input_has_no_alias_into_state(self):
        state = BattleState()
        nested = {"items": [{"v": 1}]}
        state.set_extension("nested", nested)
        nested["items"].append({"v": 2})
        self.assertEqual(state.extensions["nested"]["items"], [{"v": 1}])

    def test_clone_has_no_nested_alias_in_either_direction(self):
        original = BattleState()
        original.set_extension("nested", {"items": [{"v": 1}]})
        branch = original.clone()

        branch.extensions["nested"]["items"].append({"v": 2})
        self.assertEqual(original.extensions["nested"]["items"], [{"v": 1}])

        original.extensions["nested"]["items"][0]["v"] = 99
        self.assertEqual(branch.extensions["nested"]["items"][0]["v"], 1)

    def test_from_dict_has_no_alias_to_input_mapping(self):
        data = {
            "schema_version": BATTLE_STATE_SCHEMA_VERSION,
            "extensions": {"nested": {"items": [1]}},
        }
        state = BattleState.from_dict(data)
        data["extensions"]["nested"]["items"].append(2)  # type: ignore[index]
        self.assertEqual(state.extensions["nested"]["items"], [1])


class TestSnapshotAndContextHash(unittest.TestCase):
    def test_context_state_hash_ignores_trace(self):
        sandbox = Sandbox(seed=10)
        before = sandbox.state_hash()
        sandbox.execute(
            DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
            lhs=DynamicValue.int_value(1),
            rhs=DynamicValue.int_value(2),
        )
        self.assertEqual(sandbox.state_hash(), before)
        self.assertEqual(len(sandbox.context.trace), 2)

    def test_snapshot_roundtrip_restores_state_rng_and_trace(self):
        sandbox = Sandbox(seed=42)
        sandbox.context.state.set_extension("marker", "x")
        sandbox.context.rng.next_u64()
        sandbox.execute(
            DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
            lhs=DynamicValue.string_value("a"),
            rhs=DynamicValue.string_value("a"),
        )
        snapshot = sandbox.snapshot()
        restored = snapshot.restore_context()
        self.assertEqual(
            restored.state.to_dict(),
            sandbox.context.state.to_dict(),
        )
        self.assertEqual(
            restored.rng.to_dict(),
            sandbox.context.rng.to_dict(),
        )
        self.assertEqual(
            restored.trace.to_dict(),
            sandbox.context.trace.to_dict(),
        )
        self.assertEqual(
            [restored.rng.next_u64() for _ in range(5)],
            [sandbox.context.rng.next_u64() for _ in range(5)],
        )

    def test_snapshot_dict_roundtrip_and_hash(self):
        sandbox = Sandbox(seed=8)
        sandbox.context.rng.next_u64()
        snapshot = capture_snapshot(sandbox.context)
        data = snapshot.to_dict()
        restored_snapshot = type(snapshot).from_dict(data)
        self.assertEqual(restored_snapshot.to_dict(), data)
        self.assertEqual(restored_snapshot.state_hash(), snapshot.state_hash())

    def test_hash_stable_across_dict_reordering(self):
        from hsr_battle_agent.battle_sandbox.hash import stable_json_hash
        left = {"a": 1, "b": 2}
        right = {"b": 2, "a": 1}
        self.assertEqual(stable_json_hash(left), stable_json_hash(right))

    @staticmethod
    def _captured_snapshot_with_content(seed: int = 12) -> tuple[Sandbox, SandboxSnapshot]:
        sandbox = Sandbox(seed=seed)
        sandbox.context.state.set_extension("nested", {"items": [1, 2]})
        sandbox.context.rng.next_u64()
        sandbox.execute(
            DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
            lhs=DynamicValue.int_value(1),
            rhs=DynamicValue.int_value(1),
        )
        return sandbox, sandbox.snapshot()

    def test_capture_snapshot_is_isolated_from_later_context_mutation(self):
        sandbox, snapshot = self._captured_snapshot_with_content()
        before = snapshot.to_dict()

        sandbox.context.state.set_extension("nested", {"items": [9]})
        sandbox.context.rng.next_u64()
        sandbox.execute(
            DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
            lhs=DynamicValue.int_value(2),
            rhs=DynamicValue.int_value(2),
        )

        self.assertEqual(snapshot.to_dict(), before)
        self.assertEqual(snapshot.battle_state["extensions"]["nested"]["items"], [1, 2])

    def test_snapshot_public_properties_return_defensive_copies(self):
        _, snapshot = self._captured_snapshot_with_content()
        before = snapshot.to_dict()

        battle_view = snapshot.battle_state
        battle_view["extensions"]["nested"]["items"].append(99)

        rng_view = snapshot.rng_state
        rng_view["state"]["internal_state"][0] = -1

        trace_view = snapshot.trace_events
        trace_view[0]["primitive_id"] = "corrupted"

        self.assertEqual(snapshot.to_dict(), before)

    def test_snapshot_from_dict_has_no_alias_to_input(self):
        _, snapshot = self._captured_snapshot_with_content()
        data = snapshot.to_dict()
        restored = SandboxSnapshot.from_dict(data)
        before = restored.to_dict()

        data["battle_state"]["extensions"]["nested"]["items"].append(99)
        data["rng_state"]["state"]["internal_state"][0] = -1
        data["trace"][0]["primitive_id"] = "corrupted"

        self.assertEqual(restored.to_dict(), before)

    def test_snapshot_to_dict_returns_defensive_copy(self):
        _, snapshot = self._captured_snapshot_with_content()
        before = snapshot.to_dict()

        exported = snapshot.to_dict()
        exported["battle_state"]["extensions"]["nested"]["items"].append(99)
        exported["rng_state"]["state"]["internal_state"][0] = -1
        exported["trace"][0]["primitive_id"] = "corrupted"

        self.assertEqual(snapshot.to_dict(), before)


class TestTrace(unittest.TestCase):
    def _execute(self) -> ExecutionTrace:
        sandbox = Sandbox(seed=1)
        sandbox.execute(
            DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
            lhs=DynamicValue.float_value(1.0),
            rhs=DynamicValue.float_value(1.0),
        )
        return sandbox.context.trace

    def test_trace_is_deterministic(self):
        self.assertEqual(self._execute().to_dict(), self._execute().to_dict())

    def test_events_have_summary_fields(self):
        trace = self._execute()
        started, finished = trace.events
        self.assertIsInstance(started, PrimitiveStarted)
        self.assertIsInstance(finished, PrimitiveFinished)
        self.assertEqual(started.primitive_id, DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID)
        self.assertEqual(started.input_tags, ("DynamicValue:FLOAT", "DynamicValue:FLOAT"))
        self.assertEqual(finished.result, True)
        self.assertEqual(finished.result_type, "bool")
        self.assertEqual(finished.primitive_event_id, started.event_id)

    def test_trace_serialization_roundtrip(self):
        trace = self._execute()
        restored = ExecutionTrace.from_dict(trace.to_dict())
        self.assertEqual(restored.to_dict(), trace.to_dict())
        self.assertEqual(restored.to_dict()["schema"], TRACE_SCHEMA)

    def test_trace_rejects_object_dump_results(self):
        trace = ExecutionTrace()
        started = trace.started("p", ("tag",), None)
        with self.assertRaises(TypeError):
            trace.finished(started, {"huge": "object"})

    def test_trace_event_ids_continue_after_restore(self):
        trace = self._execute()
        restored = ExecutionTrace.from_dict(trace.to_dict())
        event = restored.started("next", ("t",), None)
        self.assertEqual(event.event_id, 3)


class TestRegistryAndExecutor(unittest.TestCase):
    def test_default_registry_has_all_recovered_primitives(self):
        registry = PrimitiveRegistry.create_default()
        catalog_ids = tuple(
            primitive.spec.primitive_id for primitive in load_catalog_primitives()
        )
        self.assertEqual(registry.known_primitive_ids, catalog_ids)
        self.assertTrue(registry.frozen)

    def test_default_registry_spec_and_provenance_come_from_artifact(self):
        registry = PrimitiveRegistry.create_default()
        recovered = load_vertical_slice_01()
        self.assertEqual(
            registry.get_spec(DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID),
            recovered.spec,
        )
        self.assertEqual(
            registry.resolve(DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID).provenance_ref,
            recovered.provenance.source_reference(),
        )

    def test_default_registry_is_bootstrapped_once(self):
        self.assertIs(
            PrimitiveRegistry.create_default(),
            PrimitiveRegistry.create_default(),
        )

    def test_execution_hot_path_never_loads_semantic_catalog(self):
        registry = PrimitiveRegistry.create_default()
        context = ExecutionContext()
        executor = PrimitiveExecutor(registry)
        with mock.patch(
            "hsr_battle_agent.battle_sandbox.registry.load_catalog_primitives",
            side_effect=AssertionError("catalog disk read on hot execution path"),
        ):
            result = executor.execute(
                _call(DynamicValue.int_value(1), DynamicValue.int_value(1)),
                context,
            )
        self.assertTrue(result.value)

    def test_unknown_primitive_fails_explicitly(self):
        sandbox = Sandbox(seed=1)
        with self.assertRaises(UnsupportedPrimitiveError):
            sandbox.execute("battle.ir.value.not_registered", lhs=1, rhs=1)

    def test_executor_validates_input_names(self):
        sandbox = Sandbox()
        with self.assertRaises(InvalidPrimitiveInputError):
            sandbox.execute(
                DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
                lhs=DynamicValue.int_value(1),
            )
        with self.assertRaises(InvalidPrimitiveInputError):
            sandbox.execute(
                DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
                lhs=DynamicValue.int_value(1),
                rhs=DynamicValue.int_value(1),
                extra=1,
            )

    def test_executor_dispatch_path_and_result(self):
        context = ExecutionContext()
        executor = PrimitiveExecutor(PrimitiveRegistry.create_default())
        result = executor.execute(
            _call(DynamicValue.int_value(3), DynamicValue.int_value(3)),
            context,
        )
        self.assertTrue(result.value)
        self.assertEqual(result.semantic_result_type, "boolean")
        self.assertEqual(result.runtime_result_type, "bool")
        self.assertEqual(len(context.trace), 2)

    def test_registry_rejects_duplicate_and_frozen_registration(self):
        spec = PrimitiveRegistry.create_default().get_spec(
            DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID
        )
        registry = PrimitiveRegistry()
        registry.register(spec, lambda context, inputs: True)
        with self.assertRaises(DuplicatePrimitiveError):
            registry.register(spec, lambda context, inputs: True)

        frozen = PrimitiveRegistry()
        frozen.freeze()
        with self.assertRaises(FrozenRegistryError):
            frozen.register(spec, lambda context, inputs: True)

    def test_semantic_artifact_registers_into_registry(self):
        recovered = load_vertical_slice_01()
        registry = PrimitiveRegistry()

        def impl(context, inputs):
            del context
            return dynamic_value_equals(inputs["lhs"], inputs["rhs"])

        registry.bind_recovered_primitive(recovered, impl)
        registry.freeze()
        sandbox = Sandbox(registry=registry, seed=3)
        result = sandbox.execute(
            recovered.spec.primitive_id,
            lhs=DynamicValue.bool_value(1),
            rhs=DynamicValue.bool_value(2),
        )
        self.assertFalse(result.value)
        self.assertEqual(result.semantic_result_type, "boolean")
        started = sandbox.context.trace.events[0]
        self.assertEqual(
            started.semantic_provenance_ref,
            "4.4.54:RPG.GameCore.DynamicValue.Equals:74632",
        )


class TestSandboxFacade(unittest.TestCase):
    def test_string_and_primitive_call_execute_forms_agree(self):
        sandbox = Sandbox(seed=1)
        call = _call(DynamicValue.int_value(1), DynamicValue.int_value(1))
        self.assertEqual(
            sandbox.execute(call).value,
            sandbox.execute(
                DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
                lhs=DynamicValue.int_value(1),
                rhs=DynamicValue.int_value(1),
            ).value,
        )

    def test_clone_isolates_rng_and_trace(self):
        sandbox = Sandbox(seed=31)
        branch = sandbox.clone()
        branch.context.rng.next_u64()
        self.assertNotEqual(
            sandbox.context.rng.to_dict()["state"]["internal_state"],
            branch.context.rng.to_dict()["state"]["internal_state"],
        )
        branch.execute(
            DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
            lhs=DynamicValue.null_value(),
            rhs=DynamicValue.null_value(),
        )
        self.assertEqual(len(sandbox.context.trace), 0)
        self.assertEqual(len(branch.context.trace), 2)

    def test_reset_replaces_context(self):
        sandbox = Sandbox(seed=7)
        sandbox.execute(
            DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
            lhs=DynamicValue.int_value(1),
            rhs=DynamicValue.int_value(1),
        )
        sandbox.reset(seed=7)
        self.assertEqual(len(sandbox.context.trace), 0)
        self.assertEqual(sandbox.context.state.to_dict()["schema_version"], BATTLE_STATE_SCHEMA_VERSION)

    def test_restore_replaces_context(self):
        sandbox = Sandbox(seed=11)
        sandbox.context.state.set_extension("x", 1)
        snapshot = sandbox.snapshot()
        sandbox.context.state.set_extension("x", 2)
        sandbox.restore(snapshot)
        self.assertEqual(sandbox.context.state.extensions, {"x": 1})

    def test_future_surface_is_explicitly_not_implemented(self):
        sandbox = Sandbox()
        for method, args in (
            (sandbox.legal_actions, ()),
            (sandbox.step, (None,)),
            (sandbox.is_terminal, ()),
        ):
            with self.subTest(method=method):
                with self.assertRaises(StubNotImplementedError) as raised:
                    method(*args)
                self.assertIn("NOT_IMPLEMENTED", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
