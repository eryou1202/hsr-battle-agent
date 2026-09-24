import copy
import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.game_data.reference_damage_adapters import (
    ReferenceCombatState, ReferenceDamageError, ReferenceEntityState, apply_reference_packet,
)
from hsr_battle_agent.game_data.reference_operation_adapters import ReferenceAdapterGate

HASH = "b" * 64


def gate():
    return ReferenceAdapterGate("damage/1", "4.4.54", HASH, ("ordinary",), ("actor-a",))


def state():
    return ReferenceCombatState(
        (ReferenceEntityState("target", Decimal("100"), Decimal("100"), Decimal("10"), Decimal("30")),),
        "actor-a", Decimal("5"), "timeline-unchanged")


def packet(kind="ORDINARY_DAMAGE"):
    marker = kind == "TASK_MARKER"
    return {
        "packet_schema": "ordinary_reference_packet/1", "kind": kind,
        "source_id": "actor-a", "targets": [] if marker else ["target"],
        "base_value": "0" if marker else "10",
        "factors": [] if marker else [{"name": "boost", "value": "2"}, {"name": "res", "value": "0.5"}],
        "resource_cost": "0" if marker else "2", "resource_owner": "actor-a",
        "toughness_delta": "0" if marker or kind == "EXPLICIT_HEAL" else "4",
        "survival_closed": True, "events_closed": True,
        "task_id": "damage-finish" if marker else None,
        "task_owner": "actor-a" if marker else None,
    }


class ReferenceDamageV2Tests(unittest.TestCase):
    def test_hand_computed_ordinary_damage(self):
        result = apply_reference_packet(gate(), state(), packet(), version="4.4.54",
                                        sha256=HASH, scope="ordinary")
        self.assertEqual(result.amount, Decimal("10"))
        self.assertEqual(result.after.entity("target").shield, Decimal("0"))
        self.assertEqual(result.after.entity("target").hp, Decimal("100"))
        self.assertEqual(result.after.entity("target").toughness, Decimal("26"))
        self.assertEqual(result.after.resource_current, Decimal("3"))
        self.assertIs(result.evidence_mode, EvidenceMode.REFERENCE_MODEL)

    def test_explicit_heal_is_separate(self):
        wounded = ReferenceCombatState(
            (ReferenceEntityState("target", Decimal("70"), Decimal("100"), Decimal("2"), Decimal("30")),),
            "actor-a", Decimal("5"), "timeline-unchanged")
        result = apply_reference_packet(gate(), wounded, packet("EXPLICIT_HEAL"),
                                        version="4.4.54", sha256=HASH, scope="ordinary")
        self.assertEqual(result.after.entity("target").hp, Decimal("80"))
        self.assertEqual(result.after.entity("target").shield, Decimal("2"))

    def test_late_special_field_rejects_whole_step_without_resource_debit(self):
        before = state(); bad = packet(); bad["SPHitRatio"] = "0.5"
        with self.assertRaises(ReferenceDamageError):
            apply_reference_packet(gate(), before, bad, version="4.4.54", sha256=HASH, scope="ordinary")
        self.assertEqual(before, state())

    def test_each_unclosed_special_or_random_surface_rejects(self):
        for field in ("HitSplitRatio", "DamageValue", "DamageBehavior", "Nonlethal",
                      "RandomCrit", "SpecialFormula", "UnknownTargetCardinality", "UnknownEventCallback"):
            bad = packet(); bad[field] = True
            with self.subTest(field=field), self.assertRaises(ReferenceDamageError):
                apply_reference_packet(gate(), state(), bad, version="4.4.54", sha256=HASH, scope="ordinary")

    def test_task_marker_never_mutates_hp_resource_or_timeline(self):
        before = state()
        result = apply_reference_packet(gate(), before, packet("TASK_MARKER"),
                                        version="4.4.54", sha256=HASH, scope="ordinary")
        self.assertIs(result.after, before)
        self.assertEqual(result.task_marker, ("damage-finish", "actor-a"))
        self.assertEqual(result.after.timeline_token, "timeline-unchanged")

    def test_marker_owner_mismatch_rejects(self):
        bad = packet("TASK_MARKER"); bad["task_owner"] = "other"
        with self.assertRaises(ReferenceDamageError):
            apply_reference_packet(gate(), state(), bad, version="4.4.54", sha256=HASH, scope="ordinary")

    def test_unknown_or_duplicate_target_cardinality_rejects(self):
        for targets in ([], ["target", "target"]):
            bad = packet(); bad["targets"] = targets
            with self.subTest(targets=targets), self.assertRaises(ReferenceDamageError):
                apply_reference_packet(gate(), state(), bad, version="4.4.54", sha256=HASH, scope="ordinary")

    def test_input_packet_is_not_mutated(self):
        raw = packet(); before = copy.deepcopy(raw)
        apply_reference_packet(gate(), state(), raw, version="4.4.54", sha256=HASH, scope="ordinary")
        self.assertEqual(raw, before)

    def test_no_native_certificate_or_rng_surface(self):
        result = apply_reference_packet(gate(), state(), packet(), version="4.4.54",
                                        sha256=HASH, scope="ordinary")
        for name in ("gate_certificate", "native_contract", "draw", "roll_crit", "execute"):
            self.assertFalse(hasattr(result, name))


if __name__ == "__main__":
    unittest.main()
