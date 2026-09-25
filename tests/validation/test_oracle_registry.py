from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.validation.oracles import (
    OracleAssessment, OracleError, OracleExpectation, OracleKind, OracleRegistry,
    OracleValidationStatus, payload_sha256,
)


def expectation(*, oracle_id="test-oracle", expectation_identity="expectation:test:1",
                kind=OracleKind.INDEPENDENT_NATIVE,
                mode=EvidenceMode.NATIVE_EVIDENCED, version="4.4.54",
                provenance=("independent-capture://fixture",), payload=None):
    if payload is None:
        payload = {"hp": 17, "targets": ["a", None]}
    return OracleExpectation(
        oracle_id=oracle_id, game_version=version,
        expectation_identity=expectation_identity, source_identity="capture:test:1",
        source_sha256="a" * 64, independent_provenance=provenance,
        expected_payload_sha256=payload_sha256(payload), kind=kind, evidence_mode=mode,
    )


class OracleRegistryTests(unittest.TestCase):
    def test_self_generated_output_is_rejected(self):
        registry = OracleRegistry("4.4.54")
        item = expectation(kind=OracleKind.EXECUTOR_GENERATED)
        self.assertIs(registry.assess(item)[0], OracleAssessment.REJECTED)
        with self.assertRaises(OracleError):
            registry.register(item)

    def test_same_code_path_reference_and_custom_are_rejected(self):
        registry = OracleRegistry("4.4.54")
        cases = ((OracleKind.SAME_CODE_PATH, EvidenceMode.NATIVE_EVIDENCED),
                 (OracleKind.REFERENCE_MODEL, EvidenceMode.REFERENCE_MODEL),
                 (OracleKind.SANDBOX_EXTENSION, EvidenceMode.SANDBOX_EXTENSION))
        for kind, mode in cases:
            with self.subTest(kind=kind), self.assertRaises(OracleError):
                registry.register(expectation(kind=kind, mode=mode))

    def test_unqualified_version_and_missing_provenance_reject(self):
        registry = OracleRegistry("4.4.54")
        for item in (expectation(version="4.5.0"), expectation(provenance=())):
            with self.subTest(item=item), self.assertRaises(OracleError):
                registry.register(item)

    def test_deliberate_mismatch_is_detected(self):
        registry = OracleRegistry("4.4.54", (expectation(payload={"hp": 17}),))
        result = registry.validate("test-oracle", {"hp": 18})
        self.assertIs(result.status, OracleValidationStatus.MISMATCH)
        self.assertNotEqual(result.expected_sha256, result.actual_sha256)

    def test_matching_independent_test_record_passes_gate_mechanics(self):
        payload = {"hp": 17}
        registry = OracleRegistry("4.4.54", (expectation(payload=payload),))
        self.assertIs(registry.validate("test-oracle", payload).status,
                      OracleValidationStatus.MATCH)
        self.assertEqual(registry.golden_count, 1)

    def test_duplicate_expectation_identity_cannot_double_count(self):
        first = expectation(oracle_id="oracle-a", expectation_identity="expectation-x")
        second = expectation(oracle_id="oracle-b", expectation_identity="expectation-x")
        registry = OracleRegistry("4.4.54", (first,))
        with self.assertRaises(OracleError):
            registry.register(second)
        self.assertEqual(registry.golden_count, 1)

    def test_duplicate_oracle_id_also_rejects(self):
        first = expectation(oracle_id="oracle-a", expectation_identity="expectation-a")
        second = expectation(oracle_id="oracle-a", expectation_identity="expectation-b")
        registry = OracleRegistry("4.4.54", (first,))
        with self.assertRaises(OracleError):
            registry.register(second)

    def test_repository_ledger_has_no_qualifying_oracle_and_golden_zero(self):
        path = REPO / "data/semantics/4.4.54/full_reconstruction/terra_golden_ledger_v1.json"
        ledger = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["qualifying_independent_native_oracles"], [])
        self.assertEqual(ledger["golden"], 0)
        self.assertEqual(ledger["native_trace"], [])
        self.assertEqual(ledger["m7_status"], "BLOCKED")

    def test_registry_exposes_no_permission_or_execution_surface(self):
        registry = OracleRegistry("4.4.54")
        for name in ("gate_certificate", "execute", "commit", "promote_reference"):
            self.assertFalse(hasattr(registry, name))


if __name__ == "__main__":
    unittest.main()
