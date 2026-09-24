# -*- coding: utf-8 -*-
"""FC-02 modifier lifecycle contract quarantine (G01-014).

This registry records availability only.  It cannot execute a lifecycle
operation or issue a GateCertificate.  The contradicted legacy Refresh label
is retained solely on the reference side, while the future corrected native
slot stays visibly blocked until its complete contract is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NoReturn

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.evidence_boundary import (
    NativeContract,
    ReferenceDescriptor,
    ReferenceProfile,
    require_native_contract,
)
from hsr_battle_agent.battle_sandbox.errors import StructuredRejection

__all__ = [
    "CORRECTED_REFRESH_CONTRACT_ID",
    "LEGACY_REFRESH_FIXTURE_LABEL",
    "REPLACE_CONTRACT_ID",
    "ContractRegistryError",
    "ContractSlot",
    "ContractSlotStatus",
    "ModifierContractRegistry",
]

LEGACY_REFRESH_FIXTURE_LABEL = "battle.ir.modifier.lifecycle_process_redd:Refresh"
CORRECTED_REFRESH_CONTRACT_ID = "terra.modifier.refresh.corrected/1"
REPLACE_CONTRACT_ID = "terra.modifier.replace/1"

_REFRESH_BLOCKERS = (
    "missing Stacking remains UNKNOWN",
    "Refresh is distinct from Replace-family Count/OnReplace writes",
    "Layer is distinct from Count and application count",
    "provider identity is distinct from caster identity",
    "lifecycle callback/property ordering is unresolved",
)


class ContractRegistryError(ValueError):
    pass


class ContractSlotStatus(Enum):
    BLOCKED_NATIVE = "BLOCKED_NATIVE"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    SEPARATELY_CERTIFIED = "SEPARATELY_CERTIFIED"

    def __bool__(self) -> NoReturn:
        raise ContractRegistryError("ContractSlotStatus has no truthiness")


@dataclass(frozen=True)
class ContractSlot:
    operation: str
    contract_id: str
    evidence_mode: EvidenceMode
    status: ContractSlotStatus
    blockers: tuple[str, ...] = ()
    legacy_fixture_label: str | None = None

    def __post_init__(self) -> None:
        if self.status is ContractSlotStatus.BLOCKED_NATIVE:
            if self.evidence_mode is not EvidenceMode.NATIVE_EVIDENCED or not self.blockers:
                raise ContractRegistryError("blocked native slots require explicit blockers")
        elif self.status is ContractSlotStatus.REFERENCE_ONLY:
            if self.evidence_mode is not EvidenceMode.REFERENCE_MODEL or not self.legacy_fixture_label:
                raise ContractRegistryError("reference slots require the preserved legacy label")
        elif self.status is ContractSlotStatus.SEPARATELY_CERTIFIED:
            if self.evidence_mode is not EvidenceMode.NATIVE_EVIDENCED or self.blockers:
                raise ContractRegistryError("separately certified slots cannot carry blockers")

    def __bool__(self) -> NoReturn:
        raise ContractRegistryError("ContractSlot is representation, not permission")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "terra_modifier_contract_slot/1",
            "operation": self.operation,
            "contract_id": self.contract_id,
            "evidence_mode": self.evidence_mode.value,
            "status": self.status.value,
            "blockers": list(self.blockers),
            "legacy_fixture_label": self.legacy_fixture_label,
        }


class ModifierContractRegistry:
    """Separate Refresh quarantine and separately certified Replace slot."""

    __slots__ = ()

    def corrected_refresh_slot(self) -> ContractSlot:
        return ContractSlot(
            operation="Refresh",
            contract_id=CORRECTED_REFRESH_CONTRACT_ID,
            evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
            status=ContractSlotStatus.BLOCKED_NATIVE,
            blockers=_REFRESH_BLOCKERS,
        )

    def reject_native_refresh(self, contract: NativeContract | None = None) -> StructuredRejection:
        if contract is not None:
            require_native_contract(contract, role="FC-02 Refresh quarantine")
        return StructuredRejection(
            reason_code="FC_02_REFRESH_NATIVE_QUARANTINED",
            obligation_owner="MODIFIER_REFRESH",
            evidence_request=(
                "complete corrected Refresh contract with independent stacking, "
                "lifetime, source-role and lifecycle-hook bindings"
            ),
            diagnostics={
                "legacy_fixture_label": LEGACY_REFRESH_FIXTURE_LABEL,
                "corrected_slot": CORRECTED_REFRESH_CONTRACT_ID,
                "blockers": list(_REFRESH_BLOCKERS),
            },
        )

    def reference_refresh(self, profile: ReferenceProfile) -> ReferenceDescriptor:
        if not isinstance(profile, ReferenceProfile):
            raise ContractRegistryError("reference Refresh requires ReferenceProfile")
        if profile.evidence_mode is not EvidenceMode.REFERENCE_MODEL:
            raise ContractRegistryError(
                "legacy Refresh fixture is REFERENCE_MODEL only; other non-native modes stay distinct"
            )
        return ReferenceDescriptor(
            descriptor_id="fc-02.legacy-refresh-reference",
            profile=profile,
            payload={
                "operation": "Refresh",
                "legacy_fixture_label": LEGACY_REFRESH_FIXTURE_LABEL,
                "native_usable": False,
            },
        )

    def replace_slot(self, contract: NativeContract | None = None) -> ContractSlot:
        if contract is None:
            return ContractSlot(
                operation="Replace",
                contract_id=REPLACE_CONTRACT_ID,
                evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
                status=ContractSlotStatus.BLOCKED_NATIVE,
                blockers=("separate Replace contract is required",),
            )
        native = require_native_contract(contract, role="separate Replace slot")
        if native.contract_id != REPLACE_CONTRACT_ID:
            raise ContractRegistryError("native contract does not bind the separate Replace slot")
        return ContractSlot(
            operation="Replace",
            contract_id=REPLACE_CONTRACT_ID,
            evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
            status=ContractSlotStatus.SEPARATELY_CERTIFIED,
        )
