# -*- coding: utf-8 -*-
"""Acceptance tests for the sealed G01-004 GateCertificate."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle  # noqa: E402
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue  # noqa: E402
from hsr_battle_agent.battle_sandbox.dependency_graph import DependencyGraph  # noqa: E402
from hsr_battle_agent.battle_sandbox.evidence_boundary import (  # noqa: E402
    EvidenceBoundaryError,
    ReferenceProfile,
    certify_native_contract,
)
from hsr_battle_agent.battle_sandbox.gate_certificate import (  # noqa: E402
    GateCertificate,
    GateCertificateError,
    certify_closed_preflight,
)
from hsr_battle_agent.battle_sandbox.preflight import (  # noqa: E402
    ChildObligationRef,
    DependencyObligation,
    ObligationAccess,
    ObligationResolution,
    PreflightResult,
)
from hsr_battle_agent.battle_sandbox.revision import StateRevision  # noqa: E402
from hsr_battle_agent.battle_sandbox.snapshot_v2 import SnapshotPolicyIdentity  # noqa: E402


def contract(
    name: str = "root",
    mode: EvidenceMode = EvidenceMode.NATIVE_EVIDENCED,
    *,
    schema_version: str = "1",
) -> ContractRef:
    return ContractRef(
        contract_id=name,
        namespace="tests.g01.certificate",
        schema_version=schema_version,
        evidence_mode=mode,
        content_sha256=(name.encode().hex() + "2" * 64)[:64],
        source_refs=(f"fixture://{name}",),
    )


def policy(
    *,
    mode: EvidenceMode = EvidenceMode.NATIVE_EVIDENCED,
    profile_id: str = "profile",
    profile_version: str = "1",
    rule_set_id: str = "rules",
) -> SnapshotPolicyIdentity:
    return SnapshotPolicyIdentity(
        evidence_mode=mode,
        evidence_vocabulary_version="1",
        profile_id=profile_id,
        profile_version=profile_version,
        profile_content_sha256="a" * 64,
        rule_set_id=rule_set_id,
        rule_set_version="1",
        rule_set_content_sha256="b" * 64,
    )


def result(
    *,
    mode: EvidenceMode = EvidenceMode.NATIVE_EVIDENCED,
    resolution: ObligationResolution = ObligationResolution.RESOLVED,
    reads: tuple[ObligationAccess, ...] = (),
    writes: tuple[ObligationAccess, ...] = (),
    handles: tuple[UnknownHandle, ...] = (),
    missing_child: bool = False,
) -> PreflightResult:
    root_contract = contract(mode=mode)
    child = (
        ChildObligationRef(owner="OWNER", contract_ref=contract("missing", mode))
        if missing_child
        else None
    )
    obligation = DependencyObligation(
        owner="OWNER",
        contract_ref=root_contract,
        evidence_mode=mode,
        resolution=resolution,
        reads=reads,
        writes=writes,
        children=() if child is None else (child,),
        unknown_handles=handles,
    )
    closure = DependencyGraph((obligation,)).close(
        (ChildObligationRef(owner="OWNER", contract_ref=root_contract),),
        expansion_budget=8,
    )
    return PreflightResult.from_closure(closure)


def unknown() -> UnknownHandle:
    return UnknownHandle(
        blocker_id="U",
        owner_family="TEST",
        payload={"items": []},
        provenance={"source": "fixture"},
        required_evidence=("evidence",),
    )


def bindings(**changes):
    values = {
        "native_contract": certify_native_contract("root"),
        "plan_identity": "plan-sha256:abc",
        "evidence_mode": EvidenceMode.NATIVE_EVIDENCED,
        "policy_identity": policy(),
        "input_identity": "input:42",
        "input_revision": "input-revision:7",
        "state_revision": StateRevision(counter=5, snapshot_id="S5", lineage="L"),
        "contract_ref": contract(),
        "contract_revision": "contract-revision:3",
    }
    values.update(changes)
    return values


class TestConstructionBoundary(unittest.TestCase):
    def test_valid_closed_native_result_constructs_certificate(self) -> None:
        certificate = certify_closed_preflight(result(), **bindings())
        self.assertIsInstance(certificate, GateCertificate)
        self.assertIs(certificate.evidence_mode, EvidenceMode.NATIVE_EVIDENCED)

    def test_direct_construction_is_impossible(self) -> None:
        closed = result()
        with self.assertRaises(GateCertificateError):
            GateCertificate(
                plan_identity="plan",
                evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
                policy_identity=policy(),
                input_identity="input",
                input_revision="1",
                state_revision=StateRevision.initial("S"),
                contract_ref=contract(),
                contract_revision="1",
                closure_identity="digest",
                allowed_reads=closed.closure.allowed_reads,
                allowed_writes=closed.closure.allowed_writes,
            )

    def test_rejected_result_cannot_construct(self) -> None:
        with self.assertRaises(GateCertificateError):
            certify_closed_preflight(result(missing_child=True), **bindings())

    def test_unknown_edge_cannot_construct(self) -> None:
        rejected = result(
            resolution=ObligationResolution.UNKNOWN,
            handles=(unknown(),),
        )
        with self.assertRaises(GateCertificateError):
            certify_closed_preflight(rejected, **bindings())

    def test_reference_closed_result_cannot_be_promoted(self) -> None:
        reference = result(mode=EvidenceMode.REFERENCE_MODEL)
        with self.assertRaises(GateCertificateError):
            certify_closed_preflight(
                reference,
                **bindings(
                    evidence_mode=EvidenceMode.REFERENCE_MODEL,
                    policy_identity=policy(mode=EvidenceMode.REFERENCE_MODEL),
                    contract_ref=contract(mode=EvidenceMode.REFERENCE_MODEL),
                ),
            )

    def test_reference_profile_cannot_substitute_for_native_contract(self) -> None:
        with self.assertRaises(EvidenceBoundaryError):
            certify_closed_preflight(
                result(),
                **bindings(native_contract=ReferenceProfile("reference")),
            )

    def test_historical_executable_boolean_cannot_substitute_for_preflight(self) -> None:
        with self.assertRaises(GateCertificateError):
            certify_closed_preflight(True, **bindings())  # type: ignore[arg-type]

    def test_contract_id_must_match_sealed_native_contract(self) -> None:
        with self.assertRaises(GateCertificateError):
            certify_closed_preflight(
                result(), **bindings(native_contract=certify_native_contract("other"))
            )

    def test_certificate_has_no_truthiness(self) -> None:
        certificate = certify_closed_preflight(result(), **bindings())
        with self.assertRaises(GateCertificateError):
            bool(certificate)


class TestExactBindings(unittest.TestCase):
    def setUp(self) -> None:
        self.result = result()
        self.base = bindings()
        self.certificate = certify_closed_preflight(self.result, **self.base)

    def assertChangedBindingInvalid(self, **changes) -> None:
        candidate = dict(self.base)
        candidate.update(changes)
        self.assertFalse(self.certificate.matches(self.result, **candidate))

    def test_equal_bindings_validate(self) -> None:
        self.assertTrue(self.certificate.matches(self.result, **self.base))

    def test_plan_identity_change_invalidates(self) -> None:
        self.assertChangedBindingInvalid(plan_identity="different-plan")

    def test_input_identity_change_invalidates(self) -> None:
        self.assertChangedBindingInvalid(input_identity="input:other")

    def test_input_revision_change_invalidates(self) -> None:
        self.assertChangedBindingInvalid(input_revision="input-revision:8")

    def test_state_revision_change_invalidates(self) -> None:
        self.assertChangedBindingInvalid(
            state_revision=StateRevision(counter=6, snapshot_id="S6", lineage="L")
        )

    def test_contract_revision_change_invalidates(self) -> None:
        self.assertChangedBindingInvalid(contract_revision="contract-revision:4")

    def test_contract_identity_change_invalidates(self) -> None:
        other = contract(schema_version="2")
        self.assertChangedBindingInvalid(contract_ref=other)

    def test_profile_identity_change_invalidates(self) -> None:
        self.assertChangedBindingInvalid(policy_identity=policy(profile_id="other"))

    def test_profile_version_change_invalidates(self) -> None:
        self.assertChangedBindingInvalid(policy_identity=policy(profile_version="2"))

    def test_rule_identity_change_invalidates(self) -> None:
        self.assertChangedBindingInvalid(policy_identity=policy(rule_set_id="other-rules"))

    def test_mode_change_invalidates(self) -> None:
        self.assertChangedBindingInvalid(evidence_mode=EvidenceMode.REFERENCE_MODEL)

    def test_read_change_invalidates_and_cannot_be_added_by_caller(self) -> None:
        changed = result(reads=(ObligationAccess("extra.read"),))
        self.assertFalse(self.certificate.matches(changed, **self.base))

    def test_write_change_invalidates_and_cannot_be_added_by_caller(self) -> None:
        changed = result(writes=(ObligationAccess("extra.write"),))
        self.assertFalse(self.certificate.matches(changed, **self.base))

    def test_tuple_and_list_accesses_have_distinct_bindings(self) -> None:
        tuple_result = result(
            reads=(ObligationAccess("read", PresenceValue.present((1, 2))),)
        )
        list_result = result(
            reads=(ObligationAccess("read", PresenceValue.present([1, 2])),)
        )
        tuple_certificate = certify_closed_preflight(tuple_result, **self.base)
        list_certificate = certify_closed_preflight(list_result, **self.base)
        self.assertNotEqual(tuple_certificate.identity(), list_certificate.identity())


class TestPermissionsAndIsolation(unittest.TestCase):
    def test_permissions_are_derived_with_order_and_duplicates(self) -> None:
        read = ObligationAccess("read", PresenceValue.present([None]))
        write = ObligationAccess("write", PresenceValue.present({"items": []}))
        closed = result(reads=(read, read), writes=(write, write))
        certificate = certify_closed_preflight(closed, **bindings())
        self.assertEqual([item.target for item in certificate.allowed_reads], ["read", "read"])
        self.assertEqual([item.target for item in certificate.allowed_writes], ["write", "write"])

    def test_construction_alias_cannot_mutate_certificate(self) -> None:
        payload = {"items": []}
        closed = result(
            writes=(ObligationAccess("write", PresenceValue.present(payload)),)
        )
        certificate = certify_closed_preflight(closed, **bindings())
        before = certificate.to_dict()
        payload["items"].append("MUTATED")
        self.assertEqual(certificate.to_dict(), before)

    def test_returned_nested_access_cannot_mutate_certificate(self) -> None:
        closed = result(
            writes=(
                ObligationAccess(
                    "write", PresenceValue.present({"items": [None]})
                ),
            )
        )
        certificate = certify_closed_preflight(closed, **bindings())
        before = certificate.to_dict()
        certificate.allowed_writes[0].extent.require_present()["items"].append("MUTATED")
        self.assertEqual(certificate.to_dict(), before)

    def test_returned_policy_contract_and_revision_are_detached(self) -> None:
        certificate = certify_closed_preflight(result(), **bindings())
        self.assertIsNot(certificate.policy_identity, certificate.policy_identity)
        self.assertIsNot(certificate.contract_ref, certificate.contract_ref)
        self.assertIsNot(certificate.state_revision, certificate.state_revision)

    def test_certification_does_not_mutate_result_or_inputs(self) -> None:
        closed = result()
        args = bindings()
        result_before = closed.to_dict()
        revision_before = args["state_revision"].to_dict()
        certify_closed_preflight(closed, **args)
        self.assertEqual(closed.to_dict(), result_before)
        self.assertEqual(args["state_revision"].to_dict(), revision_before)

    def test_certificate_exposes_no_execution_or_commit_surface(self) -> None:
        forbidden = {"execute", "apply", "commit", "mutate_state", "draw_rng", "allocate"}
        self.assertTrue(forbidden.isdisjoint(dir(GateCertificate)))


if __name__ == "__main__":
    unittest.main()
