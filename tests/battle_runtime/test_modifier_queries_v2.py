import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_runtime_v2.modifier_queries import (
    CasterFilterKind, LookupState, ModifierCandidate, ModifierLookupQuery,
    ModifierQueryError, StackingDecision, first_matching_modifier, plan_stacking,
)


def candidate(occurrence, *, caster="caster-a", provider="provider-a", flag=7):
    return ModifierCandidate(occurrence, "Burn", LookupState.ALIVE, flag,
                             "direct-a", caster, provider)


class ModifierLookupV2Tests(unittest.TestCase):
    def test_caster_wildcard_bypasses_provider(self):
        query = ModifierLookupQuery("Burn", LookupState.ALIVE, 7,
                                    CasterFilterKind.NATIVE_ANY,
                                    provider_id="different-provider")
        self.assertEqual(first_matching_modifier([candidate("one")], query).match.occurrence_id, "one")

    def test_concrete_caster_and_provider_are_exact(self):
        query = ModifierLookupQuery("Burn", LookupState.ALIVE, 7,
                                    CasterFilterKind.EXACT_EFFECTIVE, "caster-a", "provider-a")
        records = [candidate("wrong-caster", caster="caster-b"),
                   candidate("wrong-provider", provider="provider-b"), candidate("right")]
        self.assertEqual(first_matching_modifier(records, query).match.occurrence_id, "right")

    def test_flag_100_is_only_explicit_wildcard(self):
        query = ModifierLookupQuery("Burn", LookupState.ALIVE, 100,
                                    CasterFilterKind.NATIVE_ANY)
        self.assertEqual(first_matching_modifier([candidate("one", flag=44)], query).match.occurrence_id, "one")
        with self.assertRaises(ModifierQueryError):
            ModifierLookupQuery("Burn", LookupState.ALIVE, True, CasterFilterKind.NATIVE_ANY)

    def test_lookup_is_first_or_none_and_preserves_source_order(self):
        query = ModifierLookupQuery("Burn", LookupState.ALIVE, 7, CasterFilterKind.NATIVE_ANY)
        result = first_matching_modifier([candidate("a"), candidate("b")], query)
        self.assertEqual(result.match.occurrence_id, "a")
        self.assertEqual(result.inspected_occurrences, ("a",))

    def test_multiple_creates_distinct_even_when_found(self):
        query = ModifierLookupQuery("Burn", LookupState.ALIVE, 7, CasterFilterKind.NATIVE_ANY)
        result = first_matching_modifier([candidate("existing")], query)
        plan = plan_stacking(4, result)
        self.assertIs(plan.decision, StackingDecision.CREATE_DISTINCT)
        self.assertFalse(plan.mutates_found_instance)
        self.assertEqual(plan.matched_occurrence_id, "existing")

    def test_refresh_is_not_replace(self):
        query = ModifierLookupQuery("Burn", LookupState.ALIVE, 7, CasterFilterKind.NATIVE_ANY)
        plan = plan_stacking(2, first_matching_modifier([], query))
        self.assertIs(plan.decision, StackingDecision.BLOCKED_REFRESH)
        self.assertNotIn("Replace", plan.reason)

    def test_replace_ordinals_and_missing_policy_block(self):
        query = ModifierLookupQuery("Burn", LookupState.ALIVE, 7, CasterFilterKind.NATIVE_ANY)
        lookup = first_matching_modifier([candidate("existing")], query)
        for policy in (5, 7, 8, 12, None, 999):
            with self.subTest(policy=policy):
                self.assertIs(plan_stacking(policy, lookup).decision,
                              StackingDecision.BLOCKED_UNSUPPORTED)

    def test_layer_and_count_are_not_exposed_as_writes(self):
        query = ModifierLookupQuery("Burn", LookupState.ALIVE, 7, CasterFilterKind.NATIVE_ANY)
        plan = plan_stacking(4, first_matching_modifier([candidate("existing")], query))
        self.assertFalse(hasattr(plan, "layer"))
        self.assertFalse(hasattr(plan, "count"))

    def test_query_is_pure_and_has_no_permission_or_rng_surface(self):
        records = [candidate("a")]
        before = repr(records)
        query = ModifierLookupQuery("Burn", LookupState.ALIVE, 7, CasterFilterKind.NATIVE_ANY)
        first_matching_modifier(records, query)
        self.assertEqual(repr(records), before)
        for name in ("draw", "commit", "apply", "execute", "gate_certificate", "allocate"):
            self.assertFalse(hasattr(query, name))


if __name__ == "__main__":
    unittest.main()
