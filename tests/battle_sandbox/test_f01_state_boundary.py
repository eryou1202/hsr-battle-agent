# -*- coding: utf-8 -*-
"""F01-009: explicit lossless compatibility seam at state/hash boundary."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import (  # noqa: E402
    ContractRef,
    EvidenceMode,
    UnknownHandle,
)
from hsr_battle_agent.battle_ir.lossless_value import (  # noqa: E402
    LosslessNumber,
    PresenceValue,
)
from hsr_battle_agent.battle_ir.provenance import (  # noqa: E402
    SOURCE_PROVENANCE_SCHEMA_V2,
    SourceProvenance,
)
from hsr_battle_agent.battle_sandbox.errors import StructuredRejection  # noqa: E402
from hsr_battle_agent.battle_sandbox.hash import (  # noqa: E402
    F01_STATE_BOUNDARY_SCHEMA,
    stable_f01_envelope_hash,
    stable_json_hash,
)
from hsr_battle_agent.battle_sandbox.state import (  # noqa: E402
    BATTLE_STATE_SCHEMA_VERSION,
    BattleState,
    F01StateBoundaryError,
    F01StateEnvelope,
)

SHA = "06e62fa808390ac4f58af4164bb4f8d3b5151b0cbd3ab76bf203d9e8c2010396"
COMMIT = "b11066beacc4de454b625fafc7ea3dd540c5bbf3"
STATE_MODULE = REPO / "src/hsr_battle_agent/battle_sandbox/state.py"


def provenance() -> SourceProvenance:
    return SourceProvenance(
        game_version="4.4.54",
        runtime_type="RPG.GameCore.MonsterAI",
        method="Decide",
        method_index=None,
        native_rva="0xDEAD",
        evidence_level="E4_STATIC_MACHINE_CODE",
        schema_version=SOURCE_PROVENANCE_SCHEMA_V2,
        source_commit=COMMIT,
        version_relation="CLOSE_VERSION",
        content_sha256=SHA,
        profile="f01-state-boundary",
        unknown_fields={"future": {"ordered": [2, 1]}},
    )


def contract() -> ContractRef:
    return ContractRef(
        contract_id="battle.ir.value.dynamic_value_equals",
        namespace="battle.ir.value",
        schema_version="battle_semantics_batch/1",
        evidence_mode=EvidenceMode.REFERENCE_MODEL,
        content_sha256=SHA,
        source_refs=("a.json", "b.json"),
    )


def unknown(payload=None) -> UnknownHandle:
    if payload is None:
        payload = {"tuple": (1, 2), "list": [1, 2], "nulls": [None]}
    return UnknownHandle(
        blocker_id="D8-Q2",
        owner_family="MONSTER_AI",
        payload=payload,
        provenance=provenance(),
        required_evidence=("pinned observed transition",),
    )


def rejection() -> StructuredRejection:
    return StructuredRejection(
        reason_code="UNKNOWN_WAVE_ADVANCE_PREDICATE",
        obligation_owner="MONSTER_AI",
        evidence_request="pinned observed wave advance transition",
        contract_refs=(contract(),),
        unknown_handles=(unknown(),),
        diagnostics={"message": "human detail"},
    )


class TestExplicitBoundary(unittest.TestCase):
    def test_schema_and_boundary_kind_are_explicit(self):
        envelope = F01StateEnvelope(PresenceValue.absent())
        self.assertEqual(envelope.boundary_kind, "F01_LOSSLESS")
        self.assertEqual(envelope.to_dict()["schema"], F01_STATE_BOUNDARY_SCHEMA)

    def test_raw_legacy_state_document_is_not_an_f01_envelope(self):
        legacy = BattleState().to_dict()
        with self.assertRaises(F01StateBoundaryError):
            F01StateEnvelope.from_dict(legacy)
        with self.assertRaises(ValueError):
            stable_f01_envelope_hash(legacy)

    def test_battle_state_object_has_no_implicit_conversion(self):
        with self.assertRaises(F01StateBoundaryError):
            F01StateEnvelope(BattleState())

    def test_missing_payload_and_null_payload_are_not_collapsed(self):
        with self.assertRaises(F01StateBoundaryError):
            F01StateEnvelope.from_dict({"schema": F01_STATE_BOUNDARY_SCHEMA})
        null_envelope = F01StateEnvelope(None)
        self.assertIsNone(F01StateEnvelope.from_dict(null_envelope.to_dict()).value)

    def test_unsupported_values_fail_closed(self):
        with self.assertRaises(F01StateBoundaryError):
            F01StateEnvelope(object())
        with self.assertRaises(F01StateBoundaryError):
            F01StateEnvelope({1: "non-string key"})

    def test_new_boundary_uses_no_default_lookup(self):
        source = STATE_MODULE.read_text(encoding="utf-8")
        seam = source.split("# F01 lossless compatibility seam", 1)[1]
        self.assertNotIn(".get(", seam)
        self.assertNotIn("setdefault(", seam)


class TestLosslessStateRoundTrip(unittest.TestCase):
    def test_presence_matrix_survives(self):
        values = {
            "absent": PresenceValue.absent(),
            "null": PresenceValue.null(),
            "false": PresenceValue.present(False),
            "zero": PresenceValue.present(0),
            "empty_string": PresenceValue.present(""),
            "empty_list": PresenceValue.present([]),
            "list_null": PresenceValue.present([None]),
            "empty_mapping": PresenceValue.present({}),
        }
        restored = F01StateEnvelope.from_dict(F01StateEnvelope(values).to_dict()).value
        self.assertEqual(
            {key: value.to_dict() for key, value in restored.items()},
            {key: value.to_dict() for key, value in values.items()},
        )

    def test_f01_objects_survive_with_exact_types(self):
        values = {
            "mode": EvidenceMode.REFERENCE_MODEL,
            "provenance": provenance(),
            "contract": contract(),
            "unknown": unknown(),
            "number": LosslessNumber.from_lexeme("9007199254740993"),
            "rejection": rejection(),
        }
        restored = F01StateEnvelope.from_dict(F01StateEnvelope(values).to_dict()).value
        self.assertIs(restored["mode"], EvidenceMode.REFERENCE_MODEL)
        self.assertEqual(restored["provenance"].to_dict(), provenance().to_dict())
        self.assertEqual(restored["contract"], contract())
        self.assertEqual(restored["unknown"], unknown())
        self.assertEqual(restored["number"].lexeme, "9007199254740993")
        self.assertEqual(restored["rejection"], rejection())

    def test_tuple_and_list_remain_distinct(self):
        restored = F01StateEnvelope.from_dict(
            F01StateEnvelope({"tuple": (1, 2), "list": [1, 2]}).to_dict()
        ).value
        self.assertIsInstance(restored["tuple"], tuple)
        self.assertIsInstance(restored["list"], list)
        self.assertNotEqual(
            F01StateEnvelope((1, 2)).state_hash(),
            F01StateEnvelope([1, 2]).state_hash(),
        )

    def test_json_transport_preserves_the_envelope(self):
        original = F01StateEnvelope(rejection())
        document = json.loads(json.dumps(original.to_dict(), sort_keys=True))
        restored = F01StateEnvelope.from_dict(document)
        self.assertEqual(restored, original)
        self.assertEqual(restored.state_hash(), original.state_hash())

    def test_clone_and_exports_do_not_alias(self):
        source = {"nested": [1], "unknown": unknown()}
        original = F01StateEnvelope(source)
        source["nested"].append(2)
        exported = original.to_dict()
        exported["payload"]["items"]["nested"]["items"].append(
            {"kind": "int", "lexeme": "3"}
        )
        clone = original.clone()
        self.assertEqual(original.value["nested"], [1])
        self.assertEqual(clone, original)

    def test_mapping_order_does_not_change_canonical_hash(self):
        left = F01StateEnvelope({"a": 1, "b": 2})
        right = F01StateEnvelope({"b": 2, "a": 1})
        self.assertEqual(left.state_hash(), right.state_hash())


class TestFC19Compatibility(unittest.TestCase):
    def test_legacy_tuple_coercion_is_quarantined_not_rewritten(self):
        # Historical helper behavior remains byte/behavior compatible.
        self.assertEqual(stable_json_hash((1, 2)), stable_json_hash([1, 2]))
        # The new boundary never shares that equality.
        self.assertNotEqual(
            F01StateEnvelope((1, 2)).state_hash(),
            F01StateEnvelope([1, 2]).state_hash(),
        )

    def test_legacy_missing_store_default_is_unchanged(self):
        legacy_v1 = {"schema_version": 1}
        restored = BattleState.from_dict(legacy_v1)
        self.assertEqual(restored.extensions, {})
        self.assertEqual(restored.schema_version, BATTLE_STATE_SCHEMA_VERSION)

    def test_legacy_v4_fixture_is_unchanged(self):
        fixture = {
            "schema_version": 4,
            "extensions": {"marker": [1, None]},
            "modifier_state_by_entity": {},
            "entity_property_entries": {},
            "modifier_property_contributions": {},
            "component_lock_hp_records": {},
            "turn_timeline": {},
        }
        self.assertEqual(BattleState.from_dict(fixture).to_dict(), fixture)

    def test_hash_boundary_rejects_untagged_tuple(self):
        malformed = {
            "schema": F01_STATE_BOUNDARY_SCHEMA,
            "payload": (1, 2),
        }
        with self.assertRaises(TypeError):
            stable_f01_envelope_hash(malformed)

    def test_no_battle_state_v2_aggregate_was_created(self):
        import hsr_battle_agent.battle_sandbox.state as state_module

        self.assertFalse(hasattr(state_module, "TerraBattleState"))
        self.assertEqual(BATTLE_STATE_SCHEMA_VERSION, 4)


if __name__ == "__main__":
    unittest.main()
