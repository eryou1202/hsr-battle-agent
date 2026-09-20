# -*- coding: utf-8 -*-
"""F01-005 tests: PresenceValue envelope.

Acceptance criteria: the absent/null/false/0/[]/[null]/{}/"" matrix round-trips
with every state still distinguishable, and invalid ABSENT-with-value forms are
rejected.  A source check also proves the module performs no default-based
presence decoding.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.lossless_value import (  # noqa: E402
    PRESENCE_STATES,
    PRESENCE_VALUE_SCHEMA,
    PresenceState,
    PresenceValue,
    PresenceValueError,
    is_no_value,
)

MODULE_PATH = (
    REPO / "src" / "hsr_battle_agent" / "battle_ir" / "lossless_value.py"
)

#: The required presence matrix: every entry must stay distinguishable.
PRESENT_PAYLOADS = (False, True, 0, 1, -1, "", "text", [], [None], [None, None],
                    {}, {"a": None}, [0], [False], [""], (1, 2))


class TestPresenceMatrixRoundTrip(unittest.TestCase):
    def test_absent_null_matrix_round_trips(self):
        for original in (PresenceValue.absent(), PresenceValue.null()):
            with self.subTest(state=original.state.value):
                restored = PresenceValue.from_dict(original.to_dict())
                self.assertEqual(restored, original)
                self.assertIs(restored.state, original.state)
                self.assertEqual(restored.to_dict(), original.to_dict())

    def test_falsey_present_payloads_round_trip_as_present(self):
        for payload in PRESENT_PAYLOADS:
            with self.subTest(payload=repr(payload)):
                original = PresenceValue.present(payload)
                restored = PresenceValue.from_dict(original.to_dict())
                self.assertTrue(restored.is_present())
                self.assertEqual(restored.require_present(), payload)
                self.assertIs(type(restored.require_present()), type(payload))
                self.assertEqual(restored.to_dict(), original.to_dict())

    def test_false_zero_empty_list_nested_null_empty_mapping_stay_distinct(self):
        encodings = {
            "absent": PresenceValue.absent(),
            "null": PresenceValue.null(),
            "false": PresenceValue.present(False),
            "zero": PresenceValue.present(0),
            "empty_list": PresenceValue.present([]),
            "list_with_null": PresenceValue.present([None]),
            "empty_mapping": PresenceValue.present({}),
            "empty_string": PresenceValue.present(""),
        }
        serialized = {
            name: json.dumps(value.to_dict(), sort_keys=True)
            for name, value in encodings.items()
        }
        self.assertEqual(
            len(set(serialized.values())), len(encodings),
            "every presence state and falsey payload must serialize distinctly",
        )
        for name, value in encodings.items():
            with self.subTest(name=name):
                restored = PresenceValue.from_dict(value.to_dict())
                self.assertEqual(restored.to_dict(), value.to_dict())

    def test_list_containing_null_is_not_the_empty_list(self):
        with_null = PresenceValue.present([None])
        empty = PresenceValue.present([])
        self.assertNotEqual(with_null.to_dict(), empty.to_dict())
        self.assertEqual(
            PresenceValue.from_dict(with_null.to_dict()).require_present(), [None]
        )

    def test_json_round_trip_for_json_representable_payloads(self):
        for payload in (False, 0, "", [], [None], {}, {"a": [None, 0, False]}):
            with self.subTest(payload=repr(payload)):
                original = PresenceValue.present(payload)
                text = json.dumps(original.to_dict(), sort_keys=True)
                restored = PresenceValue.from_dict(json.loads(text))
                self.assertEqual(restored.require_present(), payload)

    def test_tuples_are_not_converted_to_lists(self):
        original = PresenceValue.present((1, 2))
        self.assertIsInstance(original.require_present(), tuple)
        restored = PresenceValue.from_dict(original.to_dict())
        self.assertIsInstance(restored.require_present(), tuple)
        self.assertEqual(restored.require_present(), (1, 2))

    def test_nested_structures_are_preserved_exactly(self):
        payload = {"a": [None, {"b": []}], "c": {}}
        restored = PresenceValue.from_dict(
            PresenceValue.present(payload).to_dict()
        )
        self.assertEqual(restored.require_present(), payload)

    def test_serialization_does_not_alias_the_model(self):
        original = PresenceValue.present({"raw": [1, 2]})
        returned = original.to_dict()
        returned["value"]["raw"].append(99)
        self.assertEqual(original.require_present(), {"raw": [1, 2]})
        self.assertEqual(original.to_dict()["value"], {"raw": [1, 2]})

    def test_constructor_input_does_not_alias_the_model(self):
        source = {"raw": [1]}
        original = PresenceValue.present(source)
        source["raw"].append(2)
        self.assertEqual(original.require_present(), {"raw": [1]})


class TestInvalidEncodings(unittest.TestCase):
    def test_absent_with_payload_is_rejected(self):
        for payload in (None, 0, False, "", [], {}, [None]):
            with self.subTest(payload=repr(payload)):
                with self.assertRaises(PresenceValueError):
                    PresenceValue(state=PresenceState.ABSENT, value=payload)

    def test_absent_with_payload_is_rejected_from_a_document(self):
        document = {
            "schema": PRESENCE_VALUE_SCHEMA,
            "presence": "ABSENT",
            "value": 1,
        }
        with self.assertRaises(PresenceValueError):
            PresenceValue.from_dict(document)

    def test_null_with_non_null_payload_is_rejected(self):
        for payload in (0, False, "", [], {}, [None], "x"):
            with self.subTest(payload=repr(payload)):
                with self.assertRaises(PresenceValueError):
                    PresenceValue(state=PresenceState.NULL, value=payload)

    def test_null_with_non_null_payload_is_rejected_from_a_document(self):
        document = {
            "schema": PRESENCE_VALUE_SCHEMA,
            "presence": "NULL",
            "value": 0,
        }
        with self.assertRaises(PresenceValueError):
            PresenceValue.from_dict(document)

    def test_null_may_omit_or_explicitly_carry_null(self):
        omitted = PresenceValue(state=PresenceState.NULL)
        explicit = PresenceValue(state=PresenceState.NULL, value=None)
        self.assertTrue(omitted.is_null())
        self.assertTrue(explicit.is_null())
        self.assertEqual(omitted, explicit)
        self.assertNotIn("value", omitted.to_dict())

    def test_present_none_is_rejected(self):
        # AUTHORITY_REQUIRED: NULL is the sole present-null representation;
        # PRESENT(None) would create two encodings for one presence state.
        with self.assertRaises(PresenceValueError):
            PresenceValue.present(None)
        with self.assertRaises(PresenceValueError):
            PresenceValue(state=PresenceState.PRESENT, value=None)

    def test_present_without_a_payload_is_rejected(self):
        with self.assertRaises(PresenceValueError):
            PresenceValue(state=PresenceState.PRESENT)

    def test_unknown_states_are_rejected(self):
        for value in ("MAYBE", "", "absent", None, 0, True, [], {}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(PresenceValueError):
                    PresenceValue(state=value)

    def test_malformed_documents_are_rejected(self):
        with self.assertRaises(PresenceValueError):
            PresenceValue.from_dict(None)
        with self.assertRaises(PresenceValueError):
            PresenceValue.from_dict([])
        with self.assertRaises(PresenceValueError):
            PresenceValue.from_dict({"presence": "PRESENT"})
        with self.assertRaises(PresenceValueError):
            PresenceValue.from_dict({"schema": "presence_value/2",
                                     "presence": "ABSENT"})
        # presence is required; its absence is not a null
        with self.assertRaises(PresenceValueError):
            PresenceValue.from_dict({})
        # unknown state
        with self.assertRaises(PresenceValueError):
            PresenceValue.from_dict({"presence": "MAYBE"})


class TestNoDefaultingApi(unittest.TestCase):
    def test_no_defaulting_helpers_exist(self):
        for name in (
            "or_else",
            "value_or",
            "unwrap_or",
            "get",
            "get_or",
            "default",
            "fallback",
            "or_default",
            "as_bool",
            "is_truthy",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(PresenceValue, name))
                self.assertFalse(hasattr(PresenceValue.absent(), name))

    def test_require_present_never_defaults(self):
        with self.assertRaises(PresenceValueError):
            PresenceValue.absent().require_present()
        with self.assertRaises(PresenceValueError):
            PresenceValue.null().require_present()

    def test_missing_payload_refuses(self):
        with self.assertRaises(PresenceValueError):
            PresenceValue.absent().missing_payload()

    def test_presence_value_has_no_truthiness(self):
        for value in (
            PresenceValue.absent(),
            PresenceValue.null(),
            PresenceValue.present(0),
            PresenceValue.present([]),
            PresenceValue.present(False),
        ):
            with self.subTest(payload=repr(value.to_dict())):
                with self.assertRaises(PresenceValueError):
                    bool(value)

    def test_presence_state_has_no_truthiness(self):
        for state in PresenceState:
            with self.subTest(state=state.name):
                with self.assertRaises(PresenceValueError):
                    bool(state)

    def test_state_queries_are_explicit_booleans(self):
        self.assertTrue(PresenceValue.absent().is_absent())
        self.assertFalse(PresenceValue.absent().is_present())
        self.assertTrue(PresenceValue.null().is_null())
        self.assertFalse(PresenceValue.null().is_present())
        self.assertTrue(PresenceValue.present(0).is_present())
        self.assertFalse(PresenceValue.present(0).is_absent())
        self.assertFalse(PresenceValue.present(0).is_null())

    def test_module_has_no_default_based_presence_decoding(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        code = "\n".join(
            line for line in source.splitlines()
            if not line.lstrip().startswith("#")
        )
        self.assertNotIn(
            ".get(",
            code,
            "presence decoding must never use data.get(key, default)",
        )
        self.assertNotIn(".setdefault(", code)
        self.assertNotIn("is not None else", code)

    def test_source_guard_would_catch_a_regression(self):
        # Sanity: the scan must be looking at a real, non-empty module.
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("class PresenceValue", source)
        self.assertIn("def from_mapping", source)


class TestMappingDecoding(unittest.TestCase):
    def test_absent_null_present_are_all_decoded_correctly(self):
        source = {"a": None, "b": 0, "c": [], "d": [None], "e": {}, "f": ""}
        self.assertTrue(PresenceValue.from_mapping(source, "missing").is_absent())
        self.assertTrue(PresenceValue.from_mapping(source, "a").is_null())
        for key in ("b", "c", "d", "e", "f"):
            with self.subTest(key=key):
                decoded = PresenceValue.from_mapping(source, key)
                self.assertTrue(decoded.is_present())
                self.assertEqual(decoded.require_present(), source[key])

    def test_mapping_decoding_uses_membership_not_defaults(self):
        # A key explicitly present with a falsey value is PRESENT, never ABSENT.
        for payload in (False, 0, "", [], {}, None):
            with self.subTest(payload=repr(payload)):
                decoded = PresenceValue.from_mapping({"k": payload}, "k")
                self.assertFalse(decoded.is_absent())
                if payload is None:
                    self.assertTrue(decoded.is_null())
                else:
                    self.assertTrue(decoded.is_present())

    def test_mapping_decoding_does_not_alias_the_source(self):
        source = {"k": [1]}
        decoded = PresenceValue.from_mapping(source, "k")
        source["k"].append(2)
        self.assertEqual(decoded.require_present(), [1])

    def test_matrix_helper_preserves_key_order(self):
        matrix = PresenceValue.matrix(
            ["c", "a", "b"], {"a": 1, "b": None}
        )
        self.assertEqual(list(matrix), ["c", "a", "b"])
        self.assertTrue(matrix["c"].is_absent())
        self.assertTrue(matrix["b"].is_null())
        self.assertEqual(matrix["a"].require_present(), 1)

    def test_non_mapping_source_is_rejected(self):
        for value in (None, [], "x", 1, True):
            with self.subTest(value=repr(value)):
                with self.assertRaises(PresenceValueError):
                    PresenceValue.from_mapping(value, "k")


class TestVocabularyConstants(unittest.TestCase):
    def test_declared_states(self):
        self.assertEqual(PRESENCE_STATES, ("ABSENT", "NULL", "PRESENT"))
        self.assertEqual(PresenceState.spellings(), PRESENCE_STATES)

    def test_schema_constant(self):
        self.assertEqual(PRESENCE_VALUE_SCHEMA, "presence_value/1")
        self.assertEqual(
            PresenceValue.absent().to_dict()["schema"], PRESENCE_VALUE_SCHEMA
        )

    def test_no_value_marker_is_recognized(self):
        self.assertTrue(is_no_value(PresenceValue.absent().value))
        self.assertFalse(is_no_value(None))
        self.assertFalse(is_no_value(0))


if __name__ == "__main__":
    unittest.main()
