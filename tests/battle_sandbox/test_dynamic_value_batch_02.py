# -*- coding: utf-8 -*-
"""Sandbox-level DynamicValue Batch 02 integration tests."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

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
    PrimitiveCall,
)
from hsr_battle_agent.battle_ir.semantic_batch import (  # noqa: E402
    load_dynamic_value_batch_02,
)
from hsr_battle_agent.battle_ir.values import (  # noqa: E402
    DynamicValue,
    ObjectRef,
)
from hsr_battle_agent.battle_sandbox.errors import (  # noqa: E402
    UnsupportedPrimitiveError,
)
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry  # noqa: E402
from hsr_battle_agent.battle_sandbox.sandbox import Sandbox  # noqa: E402

BATCH_PRIMITIVE_IDS = (
    DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_UINT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_LONG_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_FLOAT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_DOUBLE_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_BOOL_PRIMITIVE_ID,
    DYNAMIC_VALUE_TYPE_PRIMITIVE_ID,
    DYNAMIC_VALUE_STRING_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_ARRAY_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_MAP_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_NULL_PRIMITIVE_ID,
)


class TestBatch02Registry(unittest.TestCase):
    def test_default_registry_specs_come_from_batch_artifact(self):
        registry = PrimitiveRegistry.create_default()
        recovered = {
            primitive.spec.primitive_id: primitive
            for primitive in load_dynamic_value_batch_02()
        }
        for primitive_id in BATCH_PRIMITIVE_IDS:
            with self.subTest(primitive_id=primitive_id):
                self.assertEqual(
                    registry.get_spec(primitive_id),
                    recovered[primitive_id].spec,
                )
                self.assertEqual(
                    registry.resolve(primitive_id).provenance_ref,
                    recovered[primitive_id].provenance.source_reference(),
                )

    def test_vertical_slice_primitive_is_still_present(self):
        registry = PrimitiveRegistry.create_default()
        self.assertEqual(
            registry.resolve(DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID).spec.primitive_id,
            DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
        )


class TestBatch02Executor(unittest.TestCase):
    def test_every_batch_primitive_dispatches_and_traces(self):
        sandbox = Sandbox(seed=1)
        ref = ObjectRef(7)
        cases = {
            DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID: DynamicValue.float_value(-1.9),
            DYNAMIC_VALUE_TO_UINT_PRIMITIVE_ID: DynamicValue.int_value(-1),
            DYNAMIC_VALUE_TO_LONG_PRIMITIVE_ID: DynamicValue.bool_value(1),
            DYNAMIC_VALUE_TO_FLOAT_PRIMITIVE_ID: DynamicValue.int_value(16777219),
            DYNAMIC_VALUE_TO_DOUBLE_PRIMITIVE_ID: DynamicValue.int_value(3),
            DYNAMIC_VALUE_TO_BOOL_PRIMITIVE_ID: DynamicValue.bool_value(2),
            DYNAMIC_VALUE_TYPE_PRIMITIVE_ID: DynamicValue.null_value(),
            DYNAMIC_VALUE_STRING_PRIMITIVE_ID: DynamicValue.string_value("abc"),
            DYNAMIC_VALUE_IS_ARRAY_PRIMITIVE_ID: DynamicValue.array_ref(ref),
            DYNAMIC_VALUE_IS_MAP_PRIMITIVE_ID: DynamicValue.map_ref(ref),
            DYNAMIC_VALUE_IS_NULL_PRIMITIVE_ID: DynamicValue.null_value(),
        }
        for primitive_id, cell in cases.items():
            with self.subTest(primitive_id=primitive_id):
                result = sandbox.execute(primitive_id, value=cell)
                spec = sandbox.registry.get_spec(primitive_id)
                self.assertEqual(result.primitive_id, primitive_id)
                self.assertEqual(result.semantic_result_type, spec.result)
                events = sandbox.context.trace.events
                self.assertEqual(events[-2].primitive_id, primitive_id)
                self.assertEqual(events[-2].input_tags, (f"DynamicValue:{cell.tag_name}",))
                self.assertEqual(events[-1].primitive_id, primitive_id)

    def test_primitive_call_and_string_forms_agree(self):
        sandbox = Sandbox(seed=2)
        call = PrimitiveCall.create(
            DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID,
            value=DynamicValue.int_value(7),
        )
        self.assertEqual(
            sandbox.execute(call).value,
            sandbox.execute(
                DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID,
                value=DynamicValue.int_value(7),
            ).value,
        )

    def test_batch_primitives_do_not_change_battle_state(self):
        sandbox = Sandbox(seed=3)
        before = sandbox.state_hash()
        sandbox.execute(
            DYNAMIC_VALUE_TO_FLOAT_PRIMITIVE_ID,
            value=DynamicValue.float_value(float("nan")),
        )
        sandbox.execute(
            DYNAMIC_VALUE_TO_BOOL_PRIMITIVE_ID,
            value=DynamicValue.int_value(9),
        )
        sandbox.execute(
            DYNAMIC_VALUE_STRING_PRIMITIVE_ID,
            value=DynamicValue.string_value("abc"),
        )
        self.assertEqual(sandbox.state_hash(), before)

    def test_result_types_and_values(self):
        sandbox = Sandbox(seed=4)
        self.assertEqual(
            sandbox.execute(
                DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID,
                value=DynamicValue.float_value(-1.9),
            ).value,
            -1,
        )
        self.assertEqual(
            sandbox.execute(
                DYNAMIC_VALUE_TO_UINT_PRIMITIVE_ID,
                value=DynamicValue.int_value(-1),
            ).value,
            2**32 - 1,
        )
        self.assertTrue(
            math.isnan(
                sandbox.execute(
                    DYNAMIC_VALUE_TO_FLOAT_PRIMITIVE_ID,
                    value=DynamicValue.float_value(float("nan")),
                ).value
            )
        )
        self.assertIsNone(
            sandbox.execute(
                DYNAMIC_VALUE_STRING_PRIMITIVE_ID,
                value=DynamicValue.int_value(1),
            ).value
        )

    def test_unknown_primitive_still_fails_explicitly(self):
        sandbox = Sandbox()
        with self.assertRaises(UnsupportedPrimitiveError):
            sandbox.execute("battle.ir.value.dynamic_value_not_batch_02", value=1)


if __name__ == "__main__":
    unittest.main()
