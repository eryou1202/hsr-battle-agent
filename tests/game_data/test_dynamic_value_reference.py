"""Tests for the DynamicValue formula decoder and store semantics."""
from __future__ import annotations

from decimal import Decimal
import unittest

from hsr_battle_agent.game_data.dynamic_value_reference import (
    DynamicValueSemanticError,
    DynamicValueStore,
    decode_postfix_program,
    dynamic_key_from_payload,
    value_spec_from_payload,
)


class PostfixProgramTest(unittest.TestCase):
    def test_direct_dynamic_load(self) -> None:
        program = decode_postfix_program("AQAR", [], [-77764014])
        self.assertEqual(program.to_infix(), "DYNAMIC[0]")
        self.assertEqual(program.evaluate(lambda key: Decimal("42")), Decimal("42"))

    def test_fixed_plus_dynamic_and_fixed_minus_dynamic(self) -> None:
        plus = decode_postfix_program("AAABAAIR", [{"Value": 1}], [178084397])
        self.assertEqual(plus.to_infix(), "(FIXED[0] ADD DYNAMIC[0])")
        self.assertEqual(plus.evaluate(lambda key: Decimal("5")), Decimal("6"))
        minus = decode_postfix_program("AAABAAMR", [{"Value": 0}], [2128130574])
        self.assertEqual(minus.to_infix(), "(FIXED[0] SUB DYNAMIC[0])")
        self.assertEqual(minus.evaluate(lambda key: Decimal("0.25")), Decimal("-0.25"))

    def test_mul_div_and_negate(self) -> None:
        mul = decode_postfix_program("AQABAQQR", [], [1, 2])
        self.assertEqual(mul.evaluate(lambda key: Decimal(10)), Decimal("100"))
        div = decode_postfix_program("AQABAQQBAgUR", [], [1, 2, 3])
        self.assertEqual(div.evaluate(lambda key: Decimal(12)), Decimal("12"))
        neg = decode_postfix_program("AAAOAQAEEQ==", [{"Value": 1}], [462955996])
        self.assertEqual(neg.to_infix(), "((NEG FIXED[0]) MUL DYNAMIC[0])")
        self.assertEqual(neg.evaluate(lambda key: Decimal("5")), Decimal("-5"))

    def test_malformed_and_unsupported_programs_reject(self) -> None:
        with self.assertRaises(DynamicValueSemanticError):
            decode_postfix_program("AQ", [], [1])
        with self.assertRaises(DynamicValueSemanticError):
            decode_postfix_program("AAAR", [], [])
        with self.assertRaises(DynamicValueSemanticError):
            decode_postfix_program("AAAQAR", [{"Value": 1}], [])


class DynamicValueStoreTest(unittest.TestCase):
    def test_define_set_read_are_deterministic(self) -> None:
        store = DynamicValueStore.empty()
        defined = store.define("caster", "Layer", {"Value": 0})
        self.assertEqual(defined.action, "DEFINE_INITIALIZED")
        existing = defined.store.define("caster", "Layer", {"Value": 5})
        self.assertEqual(existing.action, "DEFINE_ALREADY_PRESENT")
        set_result = existing.store.set_value("caster", "Layer", Decimal("3"))
        self.assertEqual(set_result.store.read("caster", "Layer"), Decimal("3"))
        self.assertEqual(set_result.store.snapshot(), {"caster": {"Layer": "3"}})

    def test_value_spec_and_dynamic_key_extraction(self) -> None:
        fixed = value_spec_from_payload({"IsDynamic": False, "FixedValue": {"Value": 2}})
        self.assertEqual(fixed.evaluate(lambda key: Decimal(1)), Decimal("2"))
        formula = value_spec_from_payload({
            "IsDynamic": True,
            "PostfixExpr": {"OpCodes": "AQAR", "DynamicHashes": [-77764014], "FixedValues": []},
        })
        self.assertEqual(formula.evaluate(lambda key: Decimal("9")), Decimal("9"))
        self.assertEqual(dynamic_key_from_payload({"Value": "Layer"}), "Layer")
        self.assertEqual(dynamic_key_from_payload("Layer"), "Layer")


if __name__ == "__main__":
    unittest.main()
