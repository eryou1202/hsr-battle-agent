import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.game_data.reference_operation_adapters import (
    ArithmeticOperator, OwnedValueStore, ReferenceAdapterGate, ReferenceOperationError,
    TeamResourceState, apply_named_team_sp_contribution, evaluate_arithmetic,
)

HASH = "a" * 64


def gate():
    return ReferenceAdapterGate("dynamic-value/1", "4.4.54", HASH,
                                ("caster", "team_post_commit"), ("actor-a", "team-a"))


class ReferenceValuesResourcesV2Tests(unittest.TestCase):
    def test_independent_arithmetic_table(self):
        cases = ((ArithmeticOperator.ADD, "7", "2", Decimal("9")),
                 (ArithmeticOperator.SUBTRACT, "7", "2", Decimal("5")),
                 (ArithmeticOperator.MULTIPLY, "7", "2", Decimal("14")),
                 (ArithmeticOperator.DIVIDE, "7", "2", Decimal("3.5")))
        for operation, left, right, expected in cases:
            with self.subTest(operation=operation):
                result = evaluate_arithmetic(gate(), version="4.4.54", sha256=HASH,
                                             scope="caster", owner="actor-a",
                                             operator=operation, left=left, right=right)
                self.assertEqual(result.value, expected)
                self.assertIs(result.evidence_mode, EvidenceMode.REFERENCE_MODEL)

    def test_division_by_zero_rejects(self):
        with self.assertRaisesRegex(ReferenceOperationError, "division by zero"):
            evaluate_arithmetic(gate(), version="4.4.54", sha256=HASH, scope="caster",
                                owner="actor-a", operator=ArithmeticOperator.DIVIDE,
                                left=1, right=0)

    def test_version_hash_scope_and_owner_are_all_gated(self):
        valid = dict(version="4.4.54", sha256=HASH, scope="caster", owner="actor-a",
                     operator=ArithmeticOperator.ADD, left=1, right=2)
        for field, bad in (("version", "4.4.55"), ("sha256", "b" * 64),
                           ("scope", "target"), ("owner", "actor-b")):
            request = dict(valid); request[field] = bad
            with self.subTest(field=field), self.assertRaises(ReferenceOperationError):
                evaluate_arithmetic(gate(), **request)

    def test_owner_scoped_store_cannot_duplicate_ai_flag_cross_store(self):
        actor = OwnedValueStore.from_mapping("actor-a", {"AIFlag": 1})
        with self.assertRaises(ReferenceOperationError):
            actor.with_value(owner="team-a", key="AIFlag", value=2)
        self.assertEqual(actor.as_mapping(), {"AIFlag": Decimal("1")})

    def test_named_negative_resource_is_discarded_not_spend(self):
        before = TeamResourceState("team-a", Decimal("2"), Decimal("5"))
        result = apply_named_team_sp_contribution(
            gate(), before, version="4.4.54", sha256=HASH, scope="team_post_commit",
            target_owner="team-a", source_name="MCommon_HOT_SP", argument_name="AddValue",
            evaluated_contribution="-3")
        self.assertEqual(result.after, before)
        self.assertEqual(result.applied_contribution, 0)

    def test_named_zero_resource_is_noop(self):
        before = TeamResourceState("team-a", Decimal("2"), Decimal("5"))
        result = apply_named_team_sp_contribution(
            gate(), before, version="4.4.54", sha256=HASH, scope="team_post_commit",
            target_owner="team-a", source_name="MCommon_HOT_SP", argument_name="AddValue",
            evaluated_contribution=0)
        self.assertEqual(result.after, before)

    def test_positive_named_resource_clamps_and_does_not_alias(self):
        before = TeamResourceState("team-a", Decimal("2"), Decimal("5"))
        result = apply_named_team_sp_contribution(
            gate(), before, version="4.4.54", sha256=HASH, scope="team_post_commit",
            target_owner="team-a", source_name="MCommon_HOT_SP", argument_name="AddValue",
            evaluated_contribution=9)
        self.assertEqual(result.after.current, Decimal("5"))
        self.assertEqual(before.current, Decimal("2"))
        self.assertIs(result.evidence_mode, EvidenceMode.REFERENCE_MODEL)

    def test_unknown_resource_policy_rejects(self):
        before = TeamResourceState("team-a", Decimal("2"), Decimal("5"))
        with self.assertRaises(ReferenceOperationError):
            apply_named_team_sp_contribution(
                gate(), before, version="4.4.54", sha256=HASH, scope="team_post_commit",
                target_owner="team-a", source_name="Unknown", argument_name="AddValue",
                evaluated_contribution=1)

    def test_reference_objects_expose_no_native_permission(self):
        for value in (gate(), TeamResourceState("team-a", Decimal("1"), Decimal("5"))):
            for name in ("gate_certificate", "native_contract", "execute", "commit"):
                self.assertFalse(hasattr(value, name))

    def test_gate_owns_detached_scope_and_owner_sequences(self):
        scopes = ["caster"]
        owners = ["actor-a"]
        value = ReferenceAdapterGate("detached/1", "4.4.54", HASH, scopes, owners)
        scopes.append("mutated")
        owners.append("mutated")
        self.assertEqual(value.allowed_scopes, ("caster",))
        self.assertEqual(value.allowed_owners, ("actor-a",))


if __name__ == "__main__":
    unittest.main()
