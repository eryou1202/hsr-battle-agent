# -*- coding: utf-8 -*-
"""Fail-closed admission boundary between real content identities and the planner.

Public surface
--------------

* :class:`ContentPlannerAdmissionRequest` — one concrete ``AvatarID:SkillID``.
* :func:`admit_content_for_planner` — typed, deterministic, preflight-only.
* :func:`prepare_content_plan_request` — optional facade that stops on rejection.
* :func:`admission_accepts_battle_state` — mechanically reports the purity design.

Every current 4.4.54 real content skill is rejected with
``ContentPlannerAdmissionOutcome.REJECTED`` before any ``ReferenceActionEnvelope``,
planner successor, state mutation, RNG draw or allocator ticket can exist.

This milestone does **not** make content executable and implements no
SkillID/EntryAbility -> ``ReferenceActionEnvelope`` binder.  M10 synthetic/local
action envelopes remain unchanged and keep their own explicitly scoped path.
"""
from __future__ import annotations

from .admission import (
    ADMISSION_ACCEPTS_BATTLE_STATE,
    FACADE_POSITIVE_PATH,
    REJECTION_IS_PURE,
    admission_accepts_battle_state,
    admit_content_for_planner,
    prepare_content_plan_request,
)
from .models import (
    ADMISSION_OUTCOMES,
    ADMISSION_REASON_CODES,
    ADMISSION_SCHEMA,
    ENGINEERING_CONCLUSIONS,
    M14_REASON_TO_ADMISSION_REASON,
    NON_EFFECT_FIELDS,
    POSITIVE_CONTENT_ADMISSION_MEANING,
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
    # entrypoints
    "admit_content_for_planner",
    "prepare_content_plan_request",
    "admission_accepts_battle_state",
    # model
    "ContentPlannerAdmissionRequest",
    "ContentPlannerAdmissionResult",
    "ContentPlanPreparation",
    "ContentPlannerAdmissionOutcome",
    "AdmissionReasonCode",
    "NonEffects",
    # errors
    "ContentPlannerAdmissionError",
    "PositiveContentAdmissionNotImplementedError",
    # vocabulary / invariants
    "ADMISSION_SCHEMA",
    "ADMISSION_OUTCOMES",
    "ADMISSION_REASON_CODES",
    "M14_REASON_TO_ADMISSION_REASON",
    "ENGINEERING_CONCLUSIONS",
    "NON_EFFECT_FIELDS",
    "REJECTION_IS_PURE",
    "ADMISSION_ACCEPTS_BATTLE_STATE",
    "FACADE_POSITIVE_PATH",
    "POSITIVE_CONTENT_ADMISSION_MEANING",
]
