# -*- coding: utf-8 -*-
"""F01-002 tests: SourceProvenance v2 envelope and explicit v1 reads.

Covers the acceptance criteria:

* a v1 migration fixture reads and round-trips byte-for-byte in content;
* a v2 envelope round-trips losslessly, including unknown fields and absence;
* hash and version-relation validation rejects malformed values;
* runtime dispatch never branches on RVA or method index.
"""
from __future__ import annotations

import ast
import copy
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import (  # noqa: E402
    VersionRelation,
    parse_version_relation,
)
from hsr_battle_agent.battle_ir.provenance import (  # noqa: E402
    KNOWN_FIELD_NAMES,
    PROVENANCE_NOTE_DEFAULT,
    REQUIRED_V1_FIELD_NAMES,
    SOURCE_PROVENANCE_SCHEMA_V1,
    SOURCE_PROVENANCE_SCHEMA_V2,
    V1_FIELD_NAMES,
    V2_ENVELOPE_FIELD_NAMES,
    SourceProvenance,
    SourceProvenanceError,
)

SRC = REPO / "src"
SANDBOX_DIR = SRC / "hsr_battle_agent" / "battle_sandbox"

COMMIT = "b11066beacc4de454b625fafc7ea3dd540c5bbf3"
SHA256 = "06e62fa808390ac4f58af4164bb4f8d3b5151b0cbd3ab76bf203d9e8c2010396"

#: A v1 document exactly as the legacy loaders serialize one.
V1_FIXTURE = {
    "game_version": "4.4.54",
    "runtime_type": "RPG.GameCore.DynamicValue",
    "method": "Evaluate",
    "method_index": 42,
    "native_rva": "0x1A2B3C",
    "evidence_level": "E4_STATIC_MACHINE_CODE",
    "note": PROVENANCE_NOTE_DEFAULT,
}

#: The same document upgraded to the v2 envelope.
V2_FIXTURE = {
    "schema_version": SOURCE_PROVENANCE_SCHEMA_V2,
    "game_version": "4.4.54",
    "runtime_type": "RPG.GameCore.DynamicValue",
    "method": "Evaluate",
    "method_index": 42,
    "native_rva": "0x1A2B3C",
    "evidence_level": "E4_STATIC_MACHINE_CODE",
    "note": PROVENANCE_NOTE_DEFAULT,
    "source_commit": COMMIT,
    "version_relation": VersionRelation.CLOSE_VERSION.serialize(),
    "content_sha256": SHA256,
    "profile": "explicit-reference-v1",
}


def sandbox_attribute_names() -> dict[str, list[str]]:
    """Attribute names accessed anywhere under battle_sandbox, by file."""
    seen: dict[str, list[str]] = {}
    for path in sorted(SANDBOX_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                # as_posix() keeps keys identical on Windows and POSIX.
                seen.setdefault(
                    path.relative_to(REPO).as_posix(), []
                ).append(node.attr)
    return seen


class TestV1MigrationFixture(unittest.TestCase):
    def test_v1_fixture_reads_through_the_dispatcher(self):
        provenance = SourceProvenance.from_dict(V1_FIXTURE)
        self.assertEqual(provenance.effective_schema_version(),
                         SOURCE_PROVENANCE_SCHEMA_V1)
        self.assertEqual(provenance.game_version, "4.4.54")
        self.assertEqual(provenance.method_index, 42)
        self.assertIsNone(provenance.source_commit)
        self.assertIsNone(provenance.version_relation)
        self.assertIsNone(provenance.content_sha256)
        self.assertIsNone(provenance.profile)

    def test_v1_fixture_round_trips_exactly(self):
        provenance = SourceProvenance.from_dict(V1_FIXTURE)
        self.assertEqual(provenance.to_dict(), V1_FIXTURE)

    def test_v1_field_set_and_order_are_unchanged(self):
        provenance = SourceProvenance.from_dict(V1_FIXTURE)
        self.assertEqual(list(provenance.to_dict()), list(V1_FIELD_NAMES))
        self.assertEqual(
            SourceProvenance(
                game_version="4.4.54",
                runtime_type="T",
                method="M",
                method_index=None,
                native_rva="0x0",
                evidence_level="E4",
            ).to_dict()["note"],
            PROVENANCE_NOTE_DEFAULT,
        )

    def test_explicit_v1_read_accepts_a_v1_document(self):
        provenance = SourceProvenance.from_dict_v1(V1_FIXTURE)
        self.assertEqual(provenance.to_dict(), V1_FIXTURE)

    def test_explicit_v1_read_rejects_v2_content(self):
        with self.assertRaises(SourceProvenanceError):
            SourceProvenance.from_dict_v1(V2_FIXTURE)

    def test_v1_read_rejects_a_missing_required_field(self):
        broken = dict(V1_FIXTURE)
        del broken["evidence_level"]
        with self.assertRaises(SourceProvenanceError):
            SourceProvenance.from_dict_v1(broken)
        with self.assertRaises(SourceProvenanceError):
            SourceProvenance.from_dict(broken)

    def test_v1_validation_behaviour_is_preserved(self):
        # Legacy behaviour: negative index -> ValueError, wrong type -> TypeError.
        with self.assertRaises(ValueError):
            SourceProvenance.from_dict({**V1_FIXTURE, "method_index": -1})
        with self.assertRaises(TypeError):
            SourceProvenance.from_dict({**V1_FIXTURE, "method_index": "42"})
        for field in ("game_version", "runtime_type", "method"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    SourceProvenance.from_dict({**V1_FIXTURE, field: ""})

    def test_source_reference_is_unchanged(self):
        provenance = SourceProvenance.from_dict(V1_FIXTURE)
        self.assertEqual(
            provenance.source_reference(),
            "4.4.54:RPG.GameCore.DynamicValue.Evaluate:42",
        )
        unregistered = SourceProvenance.from_dict(
            {**V1_FIXTURE, "method_index": None}
        )
        self.assertEqual(
            unregistered.source_reference(),
            "4.4.54:RPG.GameCore.DynamicValue.Evaluate:unregistered@0x1A2B3C",
        )


class TestV2LosslessRoundTrip(unittest.TestCase):
    def test_v2_fixture_round_trips_exactly(self):
        provenance = SourceProvenance.from_dict(V2_FIXTURE)
        self.assertEqual(provenance.effective_schema_version(),
                         SOURCE_PROVENANCE_SCHEMA_V2)
        self.assertEqual(provenance.to_dict(), V2_FIXTURE)

    def test_v2_parses_the_version_relation_to_the_canonical_enum(self):
        provenance = SourceProvenance.from_dict_v2(V2_FIXTURE)
        self.assertIsInstance(provenance.version_relation, VersionRelation)
        self.assertIs(
            provenance.version_relation, VersionRelation.CLOSE_VERSION
        )
        self.assertEqual(
            provenance.to_dict()["version_relation"], "CLOSE_VERSION"
        )

    def test_unknown_fields_are_preserved_verbatim(self):
        document = {
            **V2_FIXTURE,
            "future_envelope_key": {"nested": [1, 2, {"deep": None}]},
            "another_unknown": ["a", None, 0, False],
        }
        provenance = SourceProvenance.from_dict_v2(document)
        self.assertEqual(
            provenance.unknown_fields,
            {
                "future_envelope_key": {"nested": [1, 2, {"deep": None}]},
                "another_unknown": ["a", None, 0, False],
            },
        )
        self.assertEqual(provenance.to_dict(), document)
        self.assertEqual(list(provenance.to_dict()), list(document))

    def test_unknown_fields_do_not_shadow_known_fields(self):
        provenance = SourceProvenance.from_dict_v2(V2_FIXTURE)
        for name in KNOWN_FIELD_NAMES:
            self.assertNotIn(name, provenance.unknown_fields)

    def test_absence_is_observable_and_never_filled(self):
        # A v2 document that omits source_commit and profile stays absent.
        document = {
            key: value
            for key, value in V2_FIXTURE.items()
            if key not in ("source_commit", "profile")
        }
        provenance = SourceProvenance.from_dict_v2(document)
        self.assertIsNone(provenance.source_commit)
        self.assertIsNone(provenance.profile)
        serialized = provenance.to_dict()
        self.assertNotIn("source_commit", serialized)
        self.assertNotIn("profile", serialized)
        self.assertEqual(serialized, document)
        self.assertIn("source_commit", provenance.absent_field_names())
        self.assertFalse(provenance.is_field_present("source_commit"))
        self.assertTrue(provenance.is_field_present("content_sha256"))

    def test_absent_is_distinct_from_present_null(self):
        without = {
            key: value
            for key, value in V2_FIXTURE.items()
            if key != "source_commit"
        }
        with_null = {**V2_FIXTURE, "source_commit": None}
        absent_provenance = SourceProvenance.from_dict_v2(without)
        null_provenance = SourceProvenance.from_dict_v2(with_null)
        self.assertNotIn("source_commit", absent_provenance.to_dict())
        self.assertIn("source_commit", null_provenance.to_dict())
        self.assertIsNone(null_provenance.to_dict()["source_commit"])
        self.assertNotEqual(
            absent_provenance.to_dict(), null_provenance.to_dict()
        )

    def test_absent_optional_v1_field_stays_absent(self):
        document = {
            key: value for key, value in V1_FIXTURE.items() if key != "note"
        }
        provenance = SourceProvenance.from_dict_v1(document)
        self.assertNotIn("note", provenance.to_dict())
        self.assertEqual(set(provenance.to_dict()), set(document))

    def test_directly_constructed_objects_serialize_the_v1_key_set(self):
        provenance = SourceProvenance(
            game_version="4.4.54",
            runtime_type="T",
            method="M",
            method_index=None,
            native_rva="0x0",
            evidence_level="E4",
        )
        self.assertEqual(list(provenance.to_dict()), list(V1_FIELD_NAMES))

    def test_effective_schema_upgrades_when_a_v2_field_is_present(self):
        provenance = SourceProvenance(
            game_version="4.4.54",
            runtime_type="T",
            method="M",
            method_index=None,
            native_rva="0x0",
            evidence_level="E4",
            source_commit=COMMIT,
        )
        self.assertEqual(
            provenance.effective_schema_version(), SOURCE_PROVENANCE_SCHEMA_V2
        )
        self.assertEqual(
            provenance.to_dict()["schema_version"], SOURCE_PROVENANCE_SCHEMA_V2
        )

    def test_rejected_combination_of_v1_schema_and_v2_field(self):
        with self.assertRaises(SourceProvenanceError):
            SourceProvenance(
                game_version="4.4.54",
                runtime_type="T",
                method="M",
                method_index=None,
                native_rva="0x0",
                evidence_level="E4",
                schema_version=SOURCE_PROVENANCE_SCHEMA_V1,
                source_commit=COMMIT,
            )

    def test_serialization_does_not_alias_the_model(self):
        provenance = SourceProvenance.from_dict_v2(V2_FIXTURE)
        first = provenance.to_dict()
        first["game_version"] = "mutated"
        first["source_commit"] = "0" * 40
        second = provenance.to_dict()
        self.assertEqual(second, V2_FIXTURE)
        self.assertEqual(provenance.game_version, "4.4.54")
        self.assertEqual(provenance.source_commit, COMMIT)

    def test_unknown_payload_is_deep_copied_on_serialization(self):
        document = {**V2_FIXTURE, "opaque": {"list": [1, 2]}}
        provenance = SourceProvenance.from_dict_v2(document)
        returned = provenance.to_dict()
        returned["opaque"]["list"].append(99)
        self.assertEqual(
            provenance.to_dict()["opaque"], {"list": [1, 2]}
        )

    def test_unknown_payload_cannot_alias_constructor_input(self):
        unknown = {"opaque": {"list": [1]}}
        provenance = SourceProvenance(
            game_version="4.4.54",
            runtime_type="T",
            method="M",
            method_index=None,
            native_rva="0x0",
            evidence_level="E4",
            schema_version=SOURCE_PROVENANCE_SCHEMA_V2,
            unknown_fields=unknown,
        )
        unknown["opaque"]["list"].append(2)
        self.assertEqual(provenance.to_dict()["opaque"], {"list": [1]})

    def test_non_string_unknown_key_is_rejected_not_coerced(self):
        with self.assertRaises(SourceProvenanceError):
            SourceProvenance.from_dict_v2({**V2_FIXTURE, 7: "opaque"})

    def test_json_round_trip(self):
        provenance = SourceProvenance.from_dict_v2(V2_FIXTURE)
        text = json.dumps(provenance.to_dict(), sort_keys=True)
        restored = SourceProvenance.from_dict(json.loads(text))
        self.assertEqual(restored.to_dict(), provenance.to_dict())


class TestHashAndVersionRelationValidation(unittest.TestCase):
    def test_valid_v2_accepts_a_real_commit_and_hash(self):
        provenance = SourceProvenance.from_dict_v2(V2_FIXTURE)
        self.assertEqual(provenance.source_commit, COMMIT)
        self.assertEqual(provenance.content_sha256, SHA256)

    def test_malformed_source_commit_is_rejected(self):
        for value in (
            "b11066be",
            COMMIT.upper(),
            COMMIT + "0",
            "g" * 40,
            "",
            "0x" + "a" * 38,
            12345,
            ["a"] * 40,
        ):
            with self.subTest(value=repr(value)):
                with self.assertRaises(SourceProvenanceError):
                    SourceProvenance.from_dict_v2(
                        {**V2_FIXTURE, "source_commit": value}
                    )

    def test_malformed_content_sha256_is_rejected(self):
        for value in (
            SHA256[:32],
            SHA256.upper(),
            SHA256 + "0",
            "z" * 64,
            "",
            0,
        ):
            with self.subTest(value=repr(value)):
                with self.assertRaises(SourceProvenanceError):
                    SourceProvenance.from_dict_v2(
                        {**V2_FIXTURE, "content_sha256": value}
                    )

    def test_unknown_version_relation_is_rejected(self):
        for value in (
            "CLOSE_4.4.0_TO_4.4.54",
            "NATIVE",
            "EXACT",
            "close_version",
            "",
            True,
            1,
            ["CLOSE_VERSION"],
        ):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    SourceProvenance.from_dict_v2(
                        {**V2_FIXTURE, "version_relation": value}
                    )

    def test_accepts_every_canonical_version_relation(self):
        for member in VersionRelation:
            with self.subTest(member=member.name):
                provenance = SourceProvenance.from_dict_v2(
                    {**V2_FIXTURE, "version_relation": member.serialize()}
                )
                self.assertIs(provenance.version_relation, member)

    def test_close_version_never_reads_as_exact_native(self):
        close = SourceProvenance.from_dict_v2(
            {**V2_FIXTURE, "version_relation": "CLOSE_VERSION"}
        )
        exact = SourceProvenance.from_dict_v2(
            {**V2_FIXTURE, "version_relation": "EXACT_NATIVE"}
        )
        self.assertIsNot(close.version_relation, exact.version_relation)
        self.assertNotEqual(close.to_dict(), exact.to_dict())
        self.assertIs(
            parse_version_relation(close.to_dict()["version_relation"]),
            VersionRelation.CLOSE_VERSION,
        )

    def test_unknown_schema_version_is_rejected(self):
        with self.assertRaises(SourceProvenanceError):
            SourceProvenance.from_dict(
                {**V2_FIXTURE, "schema_version": "source_provenance/3"}
            )
        with self.assertRaises(SourceProvenanceError):
            SourceProvenance.from_dict(
                {**V2_FIXTURE, "schema_version": "SOURCE_PROVENANCE/2"}
            )

    def test_v2_read_requires_the_v2_marker(self):
        with self.assertRaises(SourceProvenanceError):
            SourceProvenance.from_dict_v2(V1_FIXTURE)
        with self.assertRaises(SourceProvenanceError):
            SourceProvenance.from_dict_v2(
                {**V2_FIXTURE, "schema_version": None}
            )

    def test_non_mapping_documents_are_rejected(self):
        for value in (None, [], "x", 1, True):
            with self.subTest(value=repr(value)):
                with self.assertRaises(SourceProvenanceError):
                    SourceProvenance.from_dict(value)
                with self.assertRaises(SourceProvenanceError):
                    SourceProvenance.from_dict_v1(value)
                with self.assertRaises(SourceProvenanceError):
                    SourceProvenance.from_dict_v2(value)


class TestProvenanceIsNotDispatch(unittest.TestCase):
    def test_dispatch_key_refuses(self):
        provenance = SourceProvenance.from_dict(V1_FIXTURE)
        with self.assertRaises(SourceProvenanceError):
            provenance.dispatch_key()

    def test_dispatch_key_refuses_for_v2_objects_too(self):
        provenance = SourceProvenance.from_dict_v2(V2_FIXTURE)
        with self.assertRaises(SourceProvenanceError):
            provenance.dispatch_key()

    def test_no_sandbox_module_reads_rva_or_method_index(self):
        accessed = sandbox_attribute_names()
        offenders = sorted(
            {
                f"{path}:{name}"
                for path, names in accessed.items()
                for name in names
                if name in ("native_rva", "method_index")
            }
        )
        self.assertEqual(
            offenders,
            [],
            "runtime dispatch must not branch on RVA or method index",
        )

    def test_sandbox_scan_actually_covers_the_package(self):
        accessed = sandbox_attribute_names()
        self.assertGreaterEqual(len(accessed), 10)
        self.assertIn(
            "src/hsr_battle_agent/battle_sandbox/registry.py", accessed
        )
        self.assertIn(
            "src/hsr_battle_agent/battle_sandbox/executor.py", accessed
        )


class TestFixtureInvariants(unittest.TestCase):
    def test_required_v1_fields_are_the_documented_set(self):
        self.assertEqual(
            REQUIRED_V1_FIELD_NAMES,
            (
                "game_version",
                "runtime_type",
                "method",
                "method_index",
                "native_rva",
                "evidence_level",
            ),
        )

    def test_envelope_field_names_are_the_documented_set(self):
        self.assertEqual(
            V2_ENVELOPE_FIELD_NAMES,
            ("source_commit", "version_relation", "content_sha256", "profile"),
        )

    def test_fixtures_are_not_shared_mutable_aliases(self):
        first = copy.deepcopy(V1_FIXTURE)
        second = SourceProvenance.from_dict(V1_FIXTURE).to_dict()
        first["game_version"] = "changed"
        self.assertEqual(second["game_version"], "4.4.54")


if __name__ == "__main__":
    unittest.main()
