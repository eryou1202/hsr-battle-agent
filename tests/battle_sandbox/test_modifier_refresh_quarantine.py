# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.contract_registry import (
    CORRECTED_REFRESH_CONTRACT_ID,
    LEGACY_REFRESH_FIXTURE_LABEL,
    REPLACE_CONTRACT_ID,
    ContractRegistryError,
    ContractSlotStatus,
    ModifierContractRegistry,
)
from hsr_battle_agent.battle_sandbox.evidence_boundary import (
    EvidenceBoundaryError,
    ReferenceProfile,
    certify_native_contract,
    issue_gate_certificate,
)
from tests.battle_sandbox.test_transaction_plan import make_state


class TestNativeRefreshQuarantine(unittest.TestCase):
    def test_native_refresh_rejects_before_any_mutation(self):
        state = make_state()
        before = state.to_dict()
        rejection = ModifierContractRegistry().reject_native_refresh(
            certify_native_contract(LEGACY_REFRESH_FIXTURE_LABEL)
        )
        self.assertEqual(rejection.reason_code, "FC_02_REFRESH_NATIVE_QUARANTINED")
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(state.rng_state.to_dict(), before["rng_state"])
        self.assertEqual(state.allocator.to_dict(), before["allocator"])

    def test_corrected_refresh_slot_exists_but_is_blocked(self):
        slot = ModifierContractRegistry().corrected_refresh_slot()
        self.assertEqual(slot.contract_id, CORRECTED_REFRESH_CONTRACT_ID)
        self.assertIs(slot.status, ContractSlotStatus.BLOCKED_NATIVE)
        self.assertIs(slot.evidence_mode, EvidenceMode.NATIVE_EVIDENCED)
        text = " ".join(slot.blockers)
        for distinction in ("Stacking", "Replace", "Layer", "Count", "provider", "caster", "lifecycle"):
            self.assertIn(distinction, text)
        self.assertFalse(hasattr(slot, "execute"))
        self.assertFalse(hasattr(slot, "issue_gate_certificate"))

    def test_even_corrected_slot_contract_does_not_unblock_this_quarantine(self):
        rejection = ModifierContractRegistry().reject_native_refresh(
            certify_native_contract(CORRECTED_REFRESH_CONTRACT_ID)
        )
        self.assertEqual(rejection.reason_code, "FC_02_REFRESH_NATIVE_QUARANTINED")


class TestReferencePreservation(unittest.TestCase):
    def test_reference_profile_preserves_exact_legacy_fixture_label(self):
        profile = ReferenceProfile("legacy-refresh", EvidenceMode.REFERENCE_MODEL)
        descriptor = ModifierContractRegistry().reference_refresh(profile)
        self.assertIs(descriptor.evidence_mode, EvidenceMode.REFERENCE_MODEL)
        self.assertEqual(descriptor.payload["legacy_fixture_label"], LEGACY_REFRESH_FIXTURE_LABEL)
        self.assertFalse(descriptor.payload["native_usable"])
        with self.assertRaises(EvidenceBoundaryError):
            issue_gate_certificate("native-refresh", descriptor)

    def test_extension_and_unsupported_are_not_collapsed_to_reference(self):
        registry = ModifierContractRegistry()
        for mode in (EvidenceMode.SANDBOX_EXTENSION, EvidenceMode.UNSUPPORTED):
            with self.assertRaises(ContractRegistryError):
                registry.reference_refresh(ReferenceProfile("not-reference", mode))


class TestReplaceSeparation(unittest.TestCase):
    def test_replace_is_not_granted_without_its_own_contract(self):
        slot = ModifierContractRegistry().replace_slot()
        self.assertIs(slot.status, ContractSlotStatus.BLOCKED_NATIVE)
        self.assertEqual(slot.blockers, ("separate Replace contract is required",))

    def test_replace_is_separate_only_when_exactly_certified(self):
        registry = ModifierContractRegistry()
        slot = registry.replace_slot(certify_native_contract(REPLACE_CONTRACT_ID))
        self.assertIs(slot.status, ContractSlotStatus.SEPARATELY_CERTIFIED)
        self.assertEqual(slot.operation, "Replace")
        self.assertFalse(hasattr(slot, "execute"))
        refresh = registry.reject_native_refresh(certify_native_contract(REPLACE_CONTRACT_ID))
        self.assertEqual(refresh.reason_code, "FC_02_REFRESH_NATIVE_QUARANTINED")

    def test_wrong_contract_cannot_certify_replace(self):
        with self.assertRaises(ContractRegistryError):
            ModifierContractRegistry().replace_slot(certify_native_contract("other"))


if __name__ == "__main__":
    unittest.main()
