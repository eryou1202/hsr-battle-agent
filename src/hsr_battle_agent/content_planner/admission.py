# -*- coding: utf-8 -*-
"""Fail-closed content-to-planner admission boundary.

Core invariant
--------------

A rejected real-content admission happens **before** anything that could carry
execution: no ``ReferenceActionEnvelope``, no ``PlayerLegalAction``, no planner
action candidate, no ``TransactionPlan``, no ``GateCertificate``, no staged
delta, no new battle state, no RNG draw, no allocator ticket, no scheduler entry
and no trace claiming execution.

The denial is achieved structurally rather than by a runtime check: admission is
a **pure function of real content identity** that

* accepts no mutable battle state at all (see :func:`admission_accepts_battle_state`),
* imports and constructs none of the execution artifacts, and
* consumes the committed M14 query layer as the single content-capability
  interpretation layer.

M14 remains the only place that reads the M13 registry or derives support
status, blocker precedence and readiness.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable, Optional

from hsr_battle_agent.content_support import (
    ContentSupportRegistry,
    RegistryUnavailableError,
    UnknownSkillError,
    real_content_execution_eligibility,
    require_skill,
)

from .models import (
    FACADE_POSITIVE_PATH,
    M14_REASON_TO_ADMISSION_REASON,
    AdmissionReasonCode,
    ContentPlanPreparation,
    ContentPlannerAdmissionError,
    ContentPlannerAdmissionOutcome,
    ContentPlannerAdmissionRequest,
    ContentPlannerAdmissionResult,
    NonEffects,
    PositiveContentAdmissionNotImplementedError,
)

__all__ = [
    "REJECTION_IS_PURE",
    "ADMISSION_ACCEPTS_BATTLE_STATE",
    "FACADE_POSITIVE_PATH",
    "admission_accepts_battle_state",
    "admit_content_for_planner",
    "prepare_content_plan_request",
]

#: M15 design facts, asserted mechanically by the M15 tests.
REJECTION_IS_PURE = True
ADMISSION_ACCEPTS_BATTLE_STATE = False

_STATE_PARAMETER_HINTS = ("state", "session", "snapshot", "rng", "allocator", "scheduler")

_NEUTRAL = NonEffects()


def _rejected(
    *,
    content_version: str,
    skill_key: Optional[str],
    reason_code: AdmissionReasonCode,
    reason_detail: str,
    capability: Any = None,
    frontier_packet_field: Optional[str] = None,
    m14_reason_code: Optional[str] = None,
) -> ContentPlannerAdmissionResult:
    return ContentPlannerAdmissionResult(
        content_version=content_version,
        skill_key=skill_key,
        outcome=ContentPlannerAdmissionOutcome.REJECTED,
        reason_code=reason_code,
        reason_detail=reason_detail,
        binding_level=None if capability is None else capability.binding_level,
        support_status=None if capability is None else capability.support_status,
        blocker_classes=() if capability is None else tuple(capability.blocker_classes),
        reentry_hints=() if capability is None else tuple(capability.reentry_hints),
        frontier_packet_field=frontier_packet_field,
        m14_reason_code=m14_reason_code,
        non_effects=_NEUTRAL,
    )


def admission_accepts_battle_state() -> bool:
    """Mechanically report whether the admission API takes mutable battle state.

    Returns ``False``: no admission or facade entrypoint declares a state,
    session, snapshot, RNG, allocator or scheduler parameter.  This is the
    stronger design -- purity is structural, not merely observed.
    """
    for func in (admit_content_for_planner, prepare_content_plan_request, _admit_with_registry):
        for name in inspect.signature(func).parameters:
            lowered = name.lower()
            if any(hint in lowered for hint in _STATE_PARAMETER_HINTS):
                return True
    return False


def _map_reason(m14_reason_code: Optional[str]) -> AdmissionReasonCode:
    """Rename an M14 denial reason into the admission vocabulary.

    M14 stays authoritative; this only renames.  An unrecognised M14 reason is
    surfaced as ``UNMAPPED_M14_REASON`` rather than silently mapped.
    """
    if m14_reason_code is None:
        return AdmissionReasonCode.UNMAPPED_M14_REASON
    mapped = M14_REASON_TO_ADMISSION_REASON.get(m14_reason_code)
    if mapped is None:
        return AdmissionReasonCode.UNMAPPED_M14_REASON
    return AdmissionReasonCode(mapped)


def _admit_with_registry(
    registry: ContentSupportRegistry,
    request: ContentPlannerAdmissionRequest,
) -> ContentPlannerAdmissionResult:
    """Pure admission against an already loaded M14 registry."""
    try:
        capability = require_skill(registry, request.avatar_id, request.skill_id)
    except UnknownSkillError:
        return _rejected(
            content_version=request.content_version,
            skill_key=request.skill_key,
            reason_code=AdmissionReasonCode.SKILL_NOT_IN_REGISTRY,
            reason_detail=(
                f"{request.skill_key} is absent from the {registry.content_version} "
                "canonical content-support registry; no behavior root, closure or "
                "settlement can be referenced."
            ),
        )

    # M14 is the single interpretation layer for the denial reason.
    eligibility = real_content_execution_eligibility(registry, request.skill_key)
    reason_code = _map_reason(eligibility.reason_code)

    record = registry.record(request.skill_key)
    packet = getattr(record, "minimum_frontier_packet_field", None)

    return _rejected(
        content_version=request.content_version,
        skill_key=request.skill_key,
        reason_code=reason_code,
        reason_detail=eligibility.reason_detail,
        capability=capability,
        frontier_packet_field=None if packet is None else packet.field,
        m14_reason_code=eligibility.reason_code,
    )


def admit_content_for_planner(
    request: ContentPlannerAdmissionRequest,
    *,
    registry: Optional[ContentSupportRegistry] = None,
    registry_root: Optional[Path] = None,
) -> ContentPlannerAdmissionResult:
    """Decide whether one real content skill may become a planner action candidate.

    The content version is always explicit; there is no "latest" resolution and
    no cross-version fallback.  An unknown version is rejected with
    ``CONTENT_VERSION_UNAVAILABLE``.

    No mutable battle state is accepted by this function.
    """
    if not isinstance(request, ContentPlannerAdmissionRequest):
        raise ContentPlannerAdmissionError("request must be a ContentPlannerAdmissionRequest")

    active = registry
    if active is None:
        try:
            from hsr_battle_agent.content_support import load_registry
            active = load_registry(request.content_version, root=registry_root)
        except RegistryUnavailableError as exc:
            return _rejected(
                content_version=request.content_version,
                skill_key=request.skill_key,
                reason_code=AdmissionReasonCode.CONTENT_VERSION_UNAVAILABLE,
                reason_detail=(
                    f"no content-support registry for {request.content_version}: {exc}. "
                    "Content versions are never substituted across versions."
                ),
            )
    if active.content_version != request.content_version:
        return _rejected(
            content_version=request.content_version,
            skill_key=request.skill_key,
            reason_code=AdmissionReasonCode.CONTENT_VERSION_UNAVAILABLE,
            reason_detail=(
                f"supplied registry is for {active.content_version} but the request names "
                f"{request.content_version}; cross-version records are never merged"
            ),
        )
    return _admit_with_registry(active, request)


def prepare_content_plan_request(
    request: ContentPlannerAdmissionRequest,
    *,
    planner_callable: Optional[Callable[..., Any]] = None,
    registry: Optional[ContentSupportRegistry] = None,
    registry_root: Optional[Path] = None,
) -> ContentPlanPreparation:
    """Optional facade: admit, and only then hand off to a planner.

    On rejection this returns the structured rejection and **stops**.  The
    planner callable is not invoked, no plan request is built, and
    ``planner_invocations`` stays ``0``.

    The positive path is **not implemented** (:data:`FACADE_POSITIVE_PATH` is
    ``NOT_IMPLEMENTED_FAIL_CLOSED``).  If the ``REJECTED``-only admission
    invariant were ever broken upstream, this facade raises
    :class:`PositiveContentAdmissionNotImplementedError` instead of entering a
    planner.  M15 still requires content capability/identity, an authorized
    content binder, runtime evidence/readiness and ``GateCertificate`` /
    preflight closure before any planner entry could exist.

    ``planner_callable`` is retained purely as an inert test/spy parameter: no
    branch of this facade may invoke it.
    """
    admission = admit_content_for_planner(request, registry=registry, registry_root=registry_root)
    if admission.rejected:
        return ContentPlanPreparation(
            admission=admission,
            admitted=False,
            planner_invocations=0,
            plan_request=None,
        )
    # Fail closed.  M15 implements no positive planner handoff, so this branch
    # must never hand off to a planner -- not even if a caller supplied one.
    raise PositiveContentAdmissionNotImplementedError(
        "facade observed a non-rejected admission; M15 implements no positive "
        "content planner handoff (positive_facade_path=NOT_IMPLEMENTED_FAIL_CLOSED); "
        "a future positive path requires an authorized content binder plus runtime "
        "evidence/readiness and GateCertificate/preflight closure"
    )
