# -*- coding: utf-8 -*-
"""F01-001 tests: canonical EvidenceMode and VersionRelation vocabulary.

These tests pin the frozen vocabulary, strict serialization, the
non-equivalence of close-version and exact-native, and the rule that an
evidence mode is provenance rather than an executability boolean.  They also
prove that exactly one ``EvidenceMode`` class definition exists in the source
tree, so no equal-valued but identity-unequal enum can reappear.
"""
from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import (  # noqa: E402
    EVIDENCE_MODE_SPELLINGS,
    READINESS_CLASS_SPELLINGS,
    VERSION_RELATION_SPELLINGS,
    EvidenceMode,
    EvidenceVocabularyError,
    ReadinessClass,
    VersionRelation,
    parse_evidence_mode,
    parse_readiness_class,
    parse_version_relation,
)

SRC = REPO / "src"
EVIDENCE_MODULE = SRC / "hsr_battle_agent" / "battle_ir" / "evidence.py"

# Values that must never be accepted as a serialized vocabulary member.
UNKNOWN_SPELLINGS = (
    "NATIVE_PROOF",
    "native_evidenced",
    "Native_Evidenced",
    "EXECUTABLE_REFERENCE",
    "REFERENCE",
    "SANDBOX",
    "UNKNOWN",
    "SUCCESS",
    "TRUE",
    "FALSE",
    "true",
    "1",
    "0",
    " ",
    "NATIVE_EVIDENCED ",
    " NATIVE_EVIDENCED",
)


def evidence_mode_class_definitions() -> list[Path]:
    """Every source file that defines a class named ``EvidenceMode``."""
    found: list[Path] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "EvidenceMode":
                found.append(path)
    return found


class TestEvidenceModeVocabulary(unittest.TestCase):
    def test_exact_frozen_spellings(self):
        self.assertEqual(
            EVIDENCE_MODE_SPELLINGS,
            (
                "NATIVE_EVIDENCED",
                "REFERENCE_MODEL",
                "SANDBOX_EXTENSION",
                "UNSUPPORTED",
            ),
        )
        self.assertEqual(
            EvidenceMode.spellings(),
            EVIDENCE_MODE_SPELLINGS,
        )

    def test_members_are_the_four_frozen_modes(self):
        self.assertEqual(
            {mode.value for mode in EvidenceMode},
            set(EVIDENCE_MODE_SPELLINGS),
        )
        self.assertEqual(len(EVIDENCE_MODE_SPELLINGS), 4)

    def test_every_mode_round_trips_by_identity(self):
        for spelling in EVIDENCE_MODE_SPELLINGS:
            with self.subTest(spelling=spelling):
                member = parse_evidence_mode(spelling)
                self.assertIs(member, EvidenceMode(spelling))
                self.assertEqual(member.value, spelling)
                self.assertEqual(member.serialize(), spelling)
                self.assertIs(parse_evidence_mode(member), member)
                self.assertIs(
                    parse_evidence_mode(json.dumps(spelling).strip('"')), member
                )

    def test_json_serialization_is_explicit(self):
        # Serializing a member directly must fail loudly rather than silently
        # emitting a bare string: callers use .serialize() / .value.
        for member in EvidenceMode:
            with self.subTest(member=member.name):
                with self.assertRaises(TypeError):
                    json.dumps(member)
                self.assertEqual(
                    json.dumps(member.serialize()), json.dumps(member.value)
                )
                self.assertEqual(
                    json.loads(json.dumps(member.serialize())), member.value
                )
                self.assertIs(
                    parse_evidence_mode(
                        json.loads(json.dumps(member.serialize()))
                    ),
                    member,
                )

    def test_members_are_not_accidentally_string_equal(self):
        # No str mixin: a member never equals its own spelling by accident.
        for member in EvidenceMode:
            with self.subTest(member=member.name):
                self.assertNotEqual(member, member.value)
                self.assertNotEqual(member, str(member.value))
                self.assertNotEqual(member, member.name)

    def test_unknown_and_mistyped_values_are_rejected(self):
        for value in UNKNOWN_SPELLINGS:
            with self.subTest(value=value):
                with self.assertRaises(EvidenceVocabularyError):
                    parse_evidence_mode(value)

    def test_absent_and_non_string_values_are_rejected(self):
        for value in (None, 0, 1, True, False, 1.0, object(), [], {}, b"NATIVE_EVIDENCED"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    parse_evidence_mode(value)


class TestVersionRelation(unittest.TestCase):
    def test_declared_spellings(self):
        # AUTHORITY_REQUIRED: exact/native and close-version are the only
        # directly supported relation claims; absence represents unasserted.
        self.assertEqual(
            VERSION_RELATION_SPELLINGS,
            ("EXACT_NATIVE", "CLOSE_VERSION"),
        )

    def test_every_relation_round_trips_by_identity(self):
        for spelling in VERSION_RELATION_SPELLINGS:
            with self.subTest(spelling=spelling):
                member = parse_version_relation(spelling)
                self.assertIs(member, VersionRelation(spelling))
                self.assertEqual(member.serialize(), spelling)

    def test_close_and_exact_native_never_compare_or_merge(self):
        exact = VersionRelation.EXACT_NATIVE
        close = VersionRelation.CLOSE_VERSION
        self.assertIsNot(exact, close)
        self.assertNotEqual(exact, close)
        self.assertNotEqual(exact.value, close.value)
        self.assertNotEqual(hash(exact), hash(close))
        # Grouping them must not collapse them.
        self.assertEqual({exact, close}, {exact, close})
        self.assertEqual(len({exact, close}), 2)
        # A close-version source is never exact-native proof.
        self.assertNotEqual(close, VersionRelation.EXACT_NATIVE)

    def test_unknown_relation_is_rejected(self):
        for value in (
            "NOT_ESTABLISHED",
            "CLOSE_4.4.0_TO_4.4.54",
            "NATIVE",
            "EXACT",
            "close_version",
            "",
            None,
            True,
            "EXACT_NATIVE_PROOF",
        ):
            with self.subTest(value=value):
                with self.assertRaises(EvidenceVocabularyError):
                    parse_version_relation(value)


class TestReadinessClass(unittest.TestCase):
    def test_declared_spellings(self):
        # AUTHORITY_REQUIRED: copied verbatim from freeze.readiness_classes.
        self.assertEqual(
            READINESS_CLASS_SPELLINGS,
            (
                "SAFE_TO_IMPLEMENT",
                "SAFE_TO_REPRESENT_ONLY",
                "SAFE_REFERENCE_MODEL_ONLY",
                "STRICT_REJECT_UNTIL_NEW_EVIDENCE",
            ),
        )

    def test_every_readiness_class_round_trips(self):
        for spelling in READINESS_CLASS_SPELLINGS:
            with self.subTest(spelling=spelling):
                member = parse_readiness_class(spelling)
                self.assertIs(member, ReadinessClass(spelling))
                self.assertEqual(member.serialize(), spelling)

    def test_readiness_and_evidence_are_distinct_types(self):
        self.assertIsNot(ReadinessClass, EvidenceMode)
        self.assertFalse(issubclass(ReadinessClass, EvidenceMode))
        self.assertFalse(issubclass(EvidenceMode, ReadinessClass))
        # An evidence mode is not a readiness class and vice versa.
        self.assertNotIsInstance(
            EvidenceMode.NATIVE_EVIDENCED, ReadinessClass
        )
        self.assertNotIsInstance(
            ReadinessClass.SAFE_TO_IMPLEMENT, EvidenceMode
        )
        # Their spellings do not overlap, so neither can be silently swapped.
        self.assertEqual(
            set(EVIDENCE_MODE_SPELLINGS) & set(READINESS_CLASS_SPELLINGS),
            set(),
        )

    def test_readiness_vocabulary_rejects_the_other_vocabulary(self):
        with self.assertRaises(EvidenceVocabularyError):
            parse_readiness_class("NATIVE_EVIDENCED")
        with self.assertRaises(EvidenceVocabularyError):
            parse_evidence_mode("SAFE_TO_IMPLEMENT")

    def test_unknown_readiness_class_is_rejected(self):
        for value in ("SAFE", "EXECUTABLE_REFERENCE", "", None, False):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    parse_readiness_class(value)


class TestEvidenceModeIsNotBoolean(unittest.TestCase):
    def test_ordinary_enum_truthiness_is_not_an_execution_api(self):
        # API_DESIGN_LOCAL: normal Enum truthiness is harmless because no gate
        # consumes it and the vocabulary exposes no execution helper.
        for member in EvidenceMode:
            with self.subTest(member=member.name):
                self.assertTrue(bool(member))
        self.assertNotIn("__bool__", EvidenceMode.__mro__[1].__dict__)

    def test_no_executability_helpers_exist(self):
        forbidden = (
            "executable",
            "is_executable",
            "can_execute",
            "implies_execution",
            "implies_executability",
            "as_bool",
            "to_bool",
            "is_native",
            "promote",
            "upgrade",
        )
        for vocabulary in (EvidenceMode, VersionRelation, ReadinessClass):
            for name in forbidden:
                with self.subTest(vocabulary=vocabulary.__name__, name=name):
                    self.assertFalse(
                        hasattr(vocabulary, name),
                        f"{vocabulary.__name__} must not expose {name!r}",
                    )
        for member in EvidenceMode:
            with self.subTest(member=member.name):
                for name in forbidden:
                    self.assertFalse(
                        hasattr(member, name),
                        f"{member!r} must not expose {name!r}",
                    )

    def test_no_ordering_or_promotion_comparison(self):
        # API_DESIGN_LOCAL: plain Enum supplies equality/identity but no order.
        # Modes are unordered: no member is "less" or "greater" than another,
        # so no vocabulary can express a promotion ladder.
        for vocabulary in (EvidenceMode, VersionRelation, ReadinessClass):
            members = list(vocabulary)
            with self.subTest(vocabulary=vocabulary.__name__):
                for left in members:
                    for right in members:
                        with self.assertRaises(TypeError):
                            left < right
                        with self.assertRaises(TypeError):
                            left > right

    def test_members_are_hashable_and_stable_in_sets(self):
        for vocabulary in (EvidenceMode, VersionRelation, ReadinessClass):
            members = list(vocabulary)
            with self.subTest(vocabulary=vocabulary.__name__):
                self.assertEqual(len(set(members)), len(members))
                for member in members:
                    self.assertIs(next(m for m in members if m == member), member)

    def test_native_and_reference_are_distinct_members(self):
        self.assertIsNot(
            EvidenceMode.NATIVE_EVIDENCED, EvidenceMode.REFERENCE_MODEL
        )
        self.assertNotEqual(
            EvidenceMode.NATIVE_EVIDENCED, EvidenceMode.REFERENCE_MODEL
        )
        self.assertNotEqual(
            EvidenceMode.NATIVE_EVIDENCED.value,
            EvidenceMode.REFERENCE_MODEL.value,
        )

    def test_members_are_never_stringly_confusable(self):
        # Every mode is only equal to its own spelling, so a mode cannot be
        # confused with a readiness class or an arbitrary label.
        for member in EvidenceMode:
            with self.subTest(member=member.name):
                self.assertNotEqual(member, "REFERENCE")
                self.assertNotEqual(member, "TRUE")
                self.assertNotEqual(member, "1")


class TestSingleCanonicalDefinition(unittest.TestCase):
    def test_exactly_one_evidence_mode_class_definition_in_src(self):
        found = evidence_mode_class_definitions()
        self.assertEqual(
            found,
            [EVIDENCE_MODULE],
            "EvidenceMode must be defined exactly once, in battle_ir/evidence.py",
        )

    def test_evidence_module_is_the_canonical_home(self):
        self.assertTrue(EVIDENCE_MODULE.is_file())
        source = EVIDENCE_MODULE.read_text(encoding="utf-8")
        for spelling in EVIDENCE_MODE_SPELLINGS:
            self.assertIn(f'"{spelling}"', source)

    def test_scan_actually_covers_the_source_tree(self):
        scanned = list(SRC.rglob("*.py"))
        self.assertGreater(len(scanned), 50, "source scan looks too small")
        names = {p.name for p in scanned}
        self.assertIn("evidence_boundary.py", names)
        self.assertIn("reference_boundary.py", names)


if __name__ == "__main__":
    unittest.main()
