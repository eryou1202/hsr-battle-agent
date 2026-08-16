# -*- coding: utf-8 -*-
"""Battle IR model hardening tests: PrimitiveCall and PrimitiveResult."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.model import (  # noqa: E402
    PrimitiveArgument,
    PrimitiveCall,
    PrimitiveResult,
)


class TestPrimitiveCallValidation(unittest.TestCase):
    def test_create_accepts_ordered_arguments(self):
        call = PrimitiveCall.create("p", lhs=1, rhs=2)
        self.assertEqual(call.as_input_mapping(), {"lhs": 1, "rhs": 2})

    def test_empty_primitive_id_rejected_on_create(self):
        with self.assertRaises(ValueError):
            PrimitiveCall.create("", lhs=1)

    def test_non_string_primitive_id_rejected_on_construction(self):
        with self.assertRaises(ValueError):
            PrimitiveCall(123, ())  # type: ignore[arg-type]

    def test_empty_argument_name_rejected(self):
        with self.assertRaises(ValueError):
            PrimitiveArgument("", 1)
        with self.assertRaises(ValueError):
            PrimitiveCall("p", (PrimitiveArgument("", 1),))

    def test_duplicate_argument_names_rejected(self):
        with self.assertRaises(ValueError) as raised:
            PrimitiveCall(
                "p",
                (
                    PrimitiveArgument("lhs", 1),
                    PrimitiveArgument("lhs", 2),
                ),
            )
        self.assertIn("duplicate", str(raised.exception))

    def test_arguments_must_be_tuple_of_primitive_arguments(self):
        with self.assertRaises(TypeError):
            PrimitiveCall("p", [PrimitiveArgument("lhs", 1)])  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            PrimitiveCall("p", (("lhs", 1),))  # type: ignore[arg-type]

    def test_as_input_mapping_does_not_overwrite_distinct_names(self):
        call = PrimitiveCall(
            "p",
            (
                PrimitiveArgument("lhs", 1),
                PrimitiveArgument("rhs", 2),
            ),
        )
        self.assertEqual(call.as_input_mapping(), {"lhs": 1, "rhs": 2})


class TestPrimitiveResultTypes(unittest.TestCase):
    def test_semantic_and_runtime_types_are_distinct_fields(self):
        result = PrimitiveResult(
            primitive_id="p",
            value=True,
            semantic_result_type="boolean",
            runtime_result_type="bool",
        )
        self.assertEqual(result.semantic_result_type, "boolean")
        self.assertEqual(result.runtime_result_type, "bool")

    def test_runtime_type_is_optional_debug_metadata(self):
        result = PrimitiveResult(
            primitive_id="p",
            value=True,
            semantic_result_type="boolean",
        )
        self.assertIsNone(result.runtime_result_type)

    def test_invalid_type_fields_rejected(self):
        with self.assertRaises(ValueError):
            PrimitiveResult("", True, "boolean")
        with self.assertRaises(ValueError):
            PrimitiveResult("p", True, "")
        with self.assertRaises(ValueError):
            PrimitiveResult("p", True, "boolean", runtime_result_type="")


if __name__ == "__main__":
    unittest.main()
