# -*- coding: utf-8 -*-
"""M15: real content is fail-closed *before* the reference battle planner.

The boundary must reject every concrete 4.4.54 real content skill before any
``ReferenceActionEnvelope``, ``PlayerLegalAction``, planner successor, state
mutation, RNG draw or allocator ticket can exist.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from hsr_battle_agent.content_planner import (  # noqa: E402
    ADMISSION_OUTCOMES,
    ADMISSION_REASON_CODES,
    ENGINEERING_CONCLUSIONS,
    FACADE_POSITIVE_PATH,
    NON_EFFECT_FIELDS,
    POSITIVE_CONTENT_ADMISSION_MEANING,
    REJECTION_IS_PURE,
    AdmissionReasonCode,
    ContentPlanPreparation,
    ContentPlannerAdmissionError,
    ContentPlannerAdmissionOutcome,
    ContentPlannerAdmissionRequest,
    ContentPlannerAdmissionResult,
    NonEffects,
    PositiveContentAdmissionNotImplementedError,
    admission_accepts_battle_state,
    admit_content_for_planner,
    prepare_content_plan_request,
)
from hsr_battle_agent.content_planner import admission as admission_module  # noqa: E402
from hsr_battle_agent.content_support import (  # noqa: E402
    BlockerClass,
    ReentryHint,
    SupportStatus,
    load_registry,
)
from hsr_battle_agent.reference_sandbox import ReferenceBattleSession  # noqa: E402
from hsr_battle_agent.reference_battle_planner import (  # noqa: E402
    HORIZON_ENTITY,
    HORIZON_RESOURCE,
    search_battle_plans,
)

from tests.reference_battle_planner.test_battle_planner import (  # noqa: E402
    fixture as m11_fixture,
    objective as m11_objective,
    policy as m11_policy,
)
from tests.reference_sandbox.test_local_session import fixture as m10_fixture  # noqa: E402

VERSION = "4.4.54"
SPECIAL_FOUR = ("1220:122014", "1510:151014", "8001:800103", "8002:800203")
REGISTRY_DIR = REPO / "data" / "content_support" / VERSION


def request(skill_key: str, *, version: str = VERSION, **kw) -> ContentPlannerAdmissionRequest:
    avatar_id, skill_id = skill_key.split(":")
    return ContentPlannerAdmissionRequest(version, avatar_id, skill_id, **kw)


def artifact_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for name in sorted(p.name for p in directory.glob("*.json")):
        digest.update(name.encode("utf-8"))
        digest.update((directory / name).read_bytes())
    return digest.hexdigest()


class TypedModelTests(unittest.TestCase):
    def test_request_rejects_blank_identity(self) -> None:
        with self.assertRaises(ContentPlannerAdmissionError):
            ContentPlannerAdmissionRequest(VERSION, "", "120801")
        with self.assertRaises(ContentPlannerAdmissionError):
            ContentPlannerAdmissionRequest(VERSION, "1208", " ")

    def test_request_requires_a_real_request_object(self) -> None:
        with self.assertRaises(ContentPlannerAdmissionError):
            admit_content_for_planner("1208:120801")  # type: ignore[arg-type]

    def test_context_is_marked_non_authoritative(self) -> None:
        payload = request("1208:120801", actor_id="someone-else", target_ids=("actor-b",)).to_dict()
        context = payload["non_authoritative_context"]
        self.assertFalse(context["used_for_decision"])
        self.assertEqual(context["actor_id"], "someone-else")
        self.assertEqual(ContentPlannerAdmissionRequest.AUTHORITATIVE_FIELDS,
                         ("content_version", "avatar_id", "skill_id"))

    def test_context_does_not_change_the_decision(self) -> None:
        registry = load_registry(VERSION)
        plain = admit_content_for_planner(request("1208:120801"), registry=registry)
        with_context = admit_content_for_planner(
            request("1208:120801", actor_id="someone-else", target_ids=("actor-b",),
                    note="descriptive only"),
            registry=registry,
        )
        self.assertEqual(plain, with_context)

    def test_outcome_vocabulary_has_no_positive_member(self) -> None:
        self.assertEqual(ADMISSION_OUTCOMES, ("REJECTED",))
        self.assertEqual([m.value for m in ContentPlannerAdmissionOutcome], ["REJECTED"])

    def test_non_effects_are_all_zero(self) -> None:
        neutral = NonEffects()
        self.assertTrue(neutral.is_neutral())
        for name in NON_EFFECT_FIELDS:
            self.assertEqual(getattr(neutral, name), 0)


class PurityDesignTests(unittest.TestCase):
    """The denial is structural: admission takes no mutable battle state."""

    def test_admission_api_accepts_no_battle_state(self) -> None:
        self.assertFalse(admission_accepts_battle_state())
        self.assertTrue(REJECTION_IS_PURE)
        for func in (admit_content_for_planner, prepare_content_plan_request):
            params = set(inspect.signature(func).parameters)
            for forbidden in ("state", "session", "snapshot", "rng", "allocator", "scheduler"):
                self.assertNotIn(forbidden, params)

    def test_boundary_does_not_import_execution_artifacts(self) -> None:
        source = Path(admission_module.__file__).read_text("utf-8")
        for forbidden in ("reference_sandbox", "reference_battle_planner", "battle_sandbox",
                          "ReferenceActionEnvelope", "GateCertificate", "TransactionPlan"):
            self.assertNotIn(
                f"import {forbidden}", source, f"boundary must not import {forbidden}"
            )
            self.assertNotIn(
                f"from hsr_battle_agent.{forbidden}", source, f"must not import {forbidden}"
            )

    def test_admission_leaves_an_existing_m10_session_unchanged(self) -> None:
        session = ReferenceBattleSession.create(m10_fixture())
        before = session.snapshot().to_dict()
        registry = load_registry(VERSION)
        for skill_key in ("1208:120801", "1220:122014", "1001:100101"):
            result = admit_content_for_planner(request(skill_key), registry=registry)
            self.assertTrue(result.rejected)
            self.assertTrue(result.non_effects.is_neutral())
        self.assertEqual(session.snapshot().to_dict(), before)


class AllContentRejectedTests(unittest.TestCase):
    """Section 15: every canonical skill rejects with zero exceptions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)

    def test_all_620_reject_with_all_permissions_false(self) -> None:
        outcomes = set()
        reason_codes = set()
        checked = 0
        for record in self.registry.records:
            result = admit_content_for_planner(
                request(record.key.canonical), registry=self.registry
            )
            checked += 1
            outcomes.add(result.outcome)
            reason_codes.add(result.reason_code)
            self.assertIs(result.outcome, ContentPlannerAdmissionOutcome.REJECTED)
            self.assertFalse(result.may_create_reference_action_envelope)
            self.assertFalse(result.may_enter_player_legal_actions)
            self.assertFalse(result.may_expand_planner_successor)
            self.assertFalse(result.may_mutate_state)
            self.assertTrue(result.non_effects.is_neutral())
            self.assertTrue(result.reason_detail)
            self.assertIsNotNone(result.m14_reason_code)
        self.assertEqual(checked, 620)
        self.assertEqual(outcomes, {ContentPlannerAdmissionOutcome.REJECTED})
        self.assertNotIn(AdmissionReasonCode.UNMAPPED_M14_REASON, reason_codes)

    def test_every_reason_code_is_in_the_closed_vocabulary(self) -> None:
        for record in self.registry.records:
            result = admit_content_for_planner(
                request(record.key.canonical), registry=self.registry
            )
            self.assertIn(result.reason_code.value, ADMISSION_REASON_CODES)

    def test_result_is_deterministic(self) -> None:
        first = admit_content_for_planner(request("1208:120801"), registry=self.registry)
        second = admit_content_for_planner(request("1208:120801"), registry=self.registry)
        self.assertEqual(first, second)
        self.assertEqual(json.dumps(first.to_dict(), sort_keys=True),
                         json.dumps(second.to_dict(), sort_keys=True))


class VersionAndIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_registry(VERSION)

    def test_4_5_54_unavailable_without_fallback(self) -> None:
        result = admit_content_for_planner(
            request("1208:120801", version="4.5.54"), registry_root=REPO
        )
        self.assertIs(result.outcome, ContentPlannerAdmissionOutcome.REJECTED)
        self.assertIs(result.reason_code, AdmissionReasonCode.CONTENT_VERSION_UNAVAILABLE)
        self.assertIn("never substituted", result.reason_detail)

    def test_registry_version_mismatch_is_rejected(self) -> None:
        result = admit_content_for_planner(
            request("1208:120801", version="4.5.54"), registry=self.registry
        )
        self.assertIs(result.reason_code, AdmissionReasonCode.CONTENT_VERSION_UNAVAILABLE)

    def test_unknown_skill_rejected(self) -> None:
        result = admit_content_for_planner(request("9999:999999"), registry=self.registry)
        self.assertIs(result.reason_code, AdmissionReasonCode.SKILL_NOT_IN_REGISTRY)
        self.assertIsNone(result.binding_level)
        self.assertEqual(result.blocker_classes, ())

    def test_no_implicit_latest_version(self) -> None:
        with self.assertRaises(ContentPlannerAdmissionError):
            ContentPlannerAdmissionRequest("", "1208", "120801")


class ReasonMappingTests(unittest.TestCase):
    """Section 14: cover the major content classes, not one happy record."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)

    def _admit(self, skill_key: str):
        return admit_content_for_planner(request(skill_key), registry=self.registry)

    def test_full_action_represented_with_settlement_still_rejected(self) -> None:
        result = self._admit("1208:120801")
        self.assertIs(result.reason_code, AdmissionReasonCode.BLOCKED_BY_EVIDENCE)
        self.assertEqual(result.binding_level.value, "FULL_ACTION_REPRESENTED")
        self.assertIs(result.support_status, SupportStatus.BLOCKED_BY_EVIDENCE)

    def test_bound_skill_without_settlement_rejected(self) -> None:
        token = next(r.key.canonical for r in self.registry.records
                     if r.is_bound and not r.closure.settlement_present)
        self.assertIs(self._admit(token).reason_code, AdmissionReasonCode.NO_SETTLEMENT_OBSERVED)

    def test_second_hop_skill_rejected_with_continuation_reason(self) -> None:
        token = next(r.key.canonical for r in self.registry.records
                     if r.closure.second_hop_continuation_present)
        result = self._admit(token)
        self.assertIs(result.reason_code, AdmissionReasonCode.SECOND_HOP_CONTINUATION_UNRESOLVED)
        self.assertIn(BlockerClass.SECOND_HOP_CONTINUATION, result.blocker_classes)

    def test_static_only_skill_rejected_without_root(self) -> None:
        token = next(r.key.canonical for r in self.registry.records if r.is_unbound)
        self.assertIs(self._admit(token).reason_code, AdmissionReasonCode.NO_BEHAVIOR_ROOT)

    def test_blocked_by_reference_support_skill_rejected(self) -> None:
        token = next(r.key.canonical for r in self.registry.records
                     if r.support_status is SupportStatus.BLOCKED_BY_REFERENCE_SUPPORT)
        result = self._admit(token)
        self.assertIs(result.reason_code, AdmissionReasonCode.BLOCKED_BY_REFERENCE_SUPPORT)

    def test_representable_blocked_maps_to_representable_but_not_executable(self) -> None:
        token = next(r.key.canonical for r in self.registry.records
                     if r.support_status is SupportStatus.REPRESENTABLE_BLOCKED)
        self.assertIs(self._admit(token).reason_code,
                      AdmissionReasonCode.REPRESENTABLE_BUT_NOT_EXECUTABLE)

    def test_no_reason_promotes_a_cleaner_status(self) -> None:
        for record in self.registry.records:
            result = self._admit(record.key.canonical)
            self.assertIs(result.outcome, ContentPlannerAdmissionOutcome.REJECTED)
            self.assertEqual(result.support_status, record.support_status)


class FuXuanFrontierTests(unittest.TestCase):
    """Section 6: preserve the 120801 frontier without interpreting SPHitRatio."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)
        cls.result = admit_content_for_planner(request("1208:120801"), registry=cls.registry)

    def test_rejected(self) -> None:
        self.assertIs(self.result.outcome, ContentPlannerAdmissionOutcome.REJECTED)
        self.assertFalse(self.result.may_expand_planner_successor)

    def test_frontier_blockers_preserved(self) -> None:
        self.assertIn(BlockerClass.DAMAGE_PACKET, self.result.blocker_classes)
        self.assertIn(BlockerClass.WAIT_ANIM_STATE, self.result.blocker_classes)

    def test_sphitratio_reentry_evidence_preserved_as_name_only(self) -> None:
        self.assertIn(ReentryHint.NEW_NATIVE_SPHITRATIO_EVIDENCE, self.result.reentry_hints)
        self.assertEqual(self.result.frontier_packet_field, "SPHitRatio")
        # The name is carried, never interpreted: no numeric or semantic field
        # derived from it appears anywhere in the result.
        payload = json.dumps(self.result.to_dict())
        self.assertNotIn("deterministic_transition", payload)
        self.assertNotIn("SPHitRatio=", payload)


class SpecialRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)

    def test_four_rows_reject_with_no_behavior_root(self) -> None:
        for token in SPECIAL_FOUR:
            with self.subTest(token=token):
                result = admit_content_for_planner(request(token), registry=self.registry)
                self.assertIs(result.outcome, ContentPlannerAdmissionOutcome.REJECTED)
                self.assertIs(result.reason_code, AdmissionReasonCode.NO_BEHAVIOR_ROOT)

    def test_prepare_ability_visible_but_does_not_change_admission(self) -> None:
        for token in ("8001:800103", "8002:800203"):
            with self.subTest(token=token):
                record = self.registry.record(token)
                self.assertIsNotNone(record.prepare_ability)
                self.assertIsNone(record.entry_ability)
                result = admit_content_for_planner(request(token), registry=self.registry)
                self.assertIs(result.reason_code, AdmissionReasonCode.NO_BEHAVIOR_ROOT)

    def test_no_other_row_is_trigger_matched_without_entry(self) -> None:
        matched = [r.key.canonical for r in self.registry.records
                   if getattr(r.unbound_reason, "value", None)
                   == "TRIGGER_MATCHED_BUT_NO_ENTRY_ABILITY"]
        self.assertEqual(sorted(matched), sorted(SPECIAL_FOUR))


class PrePlannerBoundaryTests(unittest.TestCase):
    """Section 7/10/11: nothing downstream may be touched."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)

    def test_planner_callback_not_invoked_after_rejection(self) -> None:
        calls = []

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("planner must never be entered for rejected content")

        for record in self.registry.records:
            preparation = prepare_content_plan_request(
                request(record.key.canonical), planner_callable=spy, registry=self.registry
            )
            self.assertFalse(preparation.admitted)
            self.assertEqual(preparation.planner_invocations, 0)
            self.assertIsNone(preparation.plan_request)
            self.assertTrue(preparation.stopped_before_planner)
        self.assertEqual(calls, [])

    def test_m11_search_never_called_for_content_requests(self) -> None:
        with mock.patch(
            "hsr_battle_agent.reference_battle_planner.search_battle_plans"
        ) as search:
            for record in self.registry.records[:200]:
                admit_content_for_planner(request(record.key.canonical), registry=self.registry)
                prepare_content_plan_request(request(record.key.canonical), registry=self.registry)
            search.assert_not_called()

    def test_typed_permission_flags_are_all_false(self) -> None:
        result = admit_content_for_planner(request("1208:120801"), registry=self.registry)
        for name in ENGINEERING_CONCLUSIONS:
            with self.subTest(flag=name):
                self.assertTrue(hasattr(result, name))
                self.assertIs(getattr(result, name), False)
        self.assertFalse(result.admitted)
        self.assertTrue(result.rejected)

    def test_non_effects_record_is_zeroed_for_every_skill(self) -> None:
        for record in self.registry.records:
            result = admit_content_for_planner(
                request(record.key.canonical), registry=self.registry
            )
            self.assertEqual(result.non_effects, NonEffects())
            self.assertTrue(result.non_effects.is_neutral())


class M10SyntheticRegressionTests(unittest.TestCase):
    """Section 9: existing M10 local envelopes remain a valid separate path."""

    def test_m10_fixture_session_still_commits(self) -> None:
        session = ReferenceBattleSession.create(m10_fixture())
        before = session.snapshot().to_dict()
        legal = [a.action_id for a in session.legal_actions().actions]
        self.assertTrue(legal)
        stepped = session.step(legal[0])
        self.assertNotEqual(stepped.session.snapshot().to_dict(), before)

    def test_m10_path_does_not_require_a_content_skill_key(self) -> None:
        # The synthetic path is built, queried and stepped without any
        # ContentSkillKey, admission request or content version.
        session = ReferenceBattleSession.create(m10_fixture())
        legal = session.legal_actions().actions
        self.assertTrue(legal)
        self.assertTrue(all(isinstance(a.action_id, str) for a in legal))
        committed = session.step(legal[0].action_id)
        self.assertIsNot(committed.session, session)
        self.assertTrue(committed.session.snapshot().to_dict())

    def test_synthetic_envelopes_are_not_content_bound(self) -> None:
        # M10 envelopes carry a local namespace, never an AvatarID/SkillID.
        for envelope in m10_fixture().envelopes:
            self.assertTrue(envelope.namespace.startswith("local."))
            self.assertNotIn(":", envelope.namespace)


class M11PlannerRegressionTests(unittest.TestCase):
    """Section 9: M11 planner keeps working over M10 local sessions."""

    def test_search_still_finds_plans(self) -> None:
        session = ReferenceBattleSession.create(m11_fixture())
        original = session.snapshot().to_dict()
        result = search_battle_plans(session, m11_objective(HORIZON_ENTITY, direction="MINIMIZE"),
                                     m11_policy())
        self.assertEqual(result.plans[0].to_dict()["action_ids"], ["a-heavy"])
        self.assertEqual(session.snapshot().to_dict(), original)

    def test_resource_objective_still_works(self) -> None:
        session = ReferenceBattleSession.create(m11_fixture())
        result = search_battle_plans(
            session,
            m11_objective(HORIZON_RESOURCE, "REFERENCE_TEAM_RESOURCE", direction="MAXIMIZE"),
            m11_policy(),
        )
        self.assertTrue(result.plans)

    def test_planner_does_not_consult_the_admission_boundary(self) -> None:
        session = ReferenceBattleSession.create(m11_fixture())
        with mock.patch.object(admission_module, "admit_content_for_planner") as admit:
            search_battle_plans(session, m11_objective(HORIZON_ENTITY, direction="MINIMIZE"),
                                m11_policy())
            admit.assert_not_called()


class FacadeHardeningTests(unittest.TestCase):
    """The facade's positive path is not implemented and fails closed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)

    def test_positive_path_is_declared_not_implemented(self) -> None:
        self.assertEqual(FACADE_POSITIVE_PATH, "NOT_IMPLEMENTED_FAIL_CLOSED")
        self.assertEqual(POSITIVE_CONTENT_ADMISSION_MEANING,
                         "POSITIVE_CONTENT_ADMISSION_NOT_IMPLEMENTED")
        self.assertTrue(issubclass(PositiveContentAdmissionNotImplementedError,
                                   ContentPlannerAdmissionError))

    def test_facade_source_contains_no_positive_planner_handoff(self) -> None:
        source = Path(admission_module.__file__).read_text("utf-8")
        facade = source[source.index("def prepare_content_plan_request"):]
        # The spy parameter must never be invoked, and no positive return exists.
        self.assertNotIn("planner_callable(", facade)
        self.assertNotIn("planner_invocations=1", facade)
        self.assertNotIn("admitted=True", facade)
        self.assertIn("raise PositiveContentAdmissionNotImplementedError", facade)

    def test_all_620_still_rejected_through_the_facade(self) -> None:
        calls = []

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("planner must never be entered by the M15 facade")

        rejected = 0
        for record in self.registry.records:
            preparation = prepare_content_plan_request(
                request(record.key.canonical), planner_callable=spy, registry=self.registry
            )
            self.assertIsInstance(preparation, ContentPlanPreparation)
            self.assertFalse(preparation.admitted)
            self.assertEqual(preparation.planner_invocations, 0)
            self.assertIsNone(preparation.plan_request)
            self.assertTrue(preparation.stopped_before_planner)
            rejected += 1
        self.assertEqual(rejected, 620)
        self.assertEqual(calls, [], "planner callable was invoked by the facade")

    def test_non_rejected_like_condition_cannot_reach_the_planner(self) -> None:
        """Monkeypatch a non-rejected admission; the facade must still not plan."""

        class _NotRejectedStub:
            rejected = False
            admitted = True

        calls = []

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("planner invoked despite fail-closed facade")

        with mock.patch.object(admission_module, "admit_content_for_planner",
                               return_value=_NotRejectedStub()):
            with self.assertRaises(PositiveContentAdmissionNotImplementedError) as ctx:
                prepare_content_plan_request(
                    request("1208:120801"), planner_callable=spy, registry=self.registry
                )
        self.assertEqual(ctx.exception.reason_code,
                         "POSITIVE_CONTENT_ADMISSION_NOT_IMPLEMENTED")
        self.assertEqual(calls, [], "facade handed off to the planner")
        self.assertIn("NOT_IMPLEMENTED_FAIL_CLOSED", str(ctx.exception))

    def test_patched_result_property_cannot_reach_the_planner(self) -> None:
        """Even if `rejected` is forced False on the real result type."""
        calls = []

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("planner invoked despite fail-closed facade")

        with mock.patch.object(ContentPlannerAdmissionResult, "rejected",
                               property(lambda self: False)):
            with self.assertRaises(PositiveContentAdmissionNotImplementedError):
                prepare_content_plan_request(
                    request("1208:120801"), planner_callable=spy, registry=self.registry
                )
        self.assertEqual(calls, [])

    def test_no_admitted_outcome_exists_and_none_can_be_smuggled_in(self) -> None:
        """Widening the outcome enum alone must not create a planner handoff."""
        self.assertEqual(list(ContentPlannerAdmissionOutcome), [ContentPlannerAdmissionOutcome.REJECTED])
        for smuggled in ("ADMITTED", "ELIGIBLE", "ALLOWED", "SUCCESS"):
            with self.subTest(smuggled=smuggled):
                with self.assertRaises(ValueError):
                    ContentPlannerAdmissionOutcome(smuggled)

    def test_facade_raises_for_any_non_rejected_result_type(self) -> None:
        """A future result type that reports non-rejection still fails closed."""

        class _FutureNonRejected:
            rejected = False
            admitted = True

        calls = []

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("planner invoked despite fail-closed facade")

        for stub in (_FutureNonRejected(), type("S", (), {"rejected": False})()):
            with self.subTest(stub=type(stub).__name__):
                with mock.patch.object(admission_module, "admit_content_for_planner",
                                       return_value=stub):
                    with self.assertRaises(PositiveContentAdmissionNotImplementedError):
                        prepare_content_plan_request(
                            request("1208:120801"), planner_callable=spy, registry=self.registry
                        )
        self.assertEqual(calls, [])

    def test_facade_without_a_planner_callable_also_fails_closed(self) -> None:
        class _NotRejectedStub:
            rejected = False
            admitted = True

        with mock.patch.object(admission_module, "admit_content_for_planner",
                               return_value=_NotRejectedStub()):
            with self.assertRaises(PositiveContentAdmissionNotImplementedError):
                prepare_content_plan_request(request("1208:120801"), registry=self.registry)

    def test_rejection_path_is_unchanged_by_the_hardening(self) -> None:
        for token in ("1208:120801", "1220:122014", "9999:999999"):
            with self.subTest(token=token):
                direct = admit_content_for_planner(request(token), registry=self.registry)
                through = prepare_content_plan_request(request(token), registry=self.registry)
                self.assertEqual(through.admission, direct)
                self.assertFalse(through.admitted)
                self.assertEqual(through.planner_invocations, 0)


class RegressionImportTests(unittest.TestCase):
    """M10/M11/M14 remain importable and unchanged by the hardening."""

    def test_m10_m11_m14_surfaces_still_import(self) -> None:
        import hsr_battle_agent.content_support as content_support
        import hsr_battle_agent.reference_battle_planner as planner
        import hsr_battle_agent.reference_sandbox as sandbox

        self.assertTrue(callable(sandbox.ReferenceBattleSession.create))
        self.assertTrue(callable(planner.search_battle_plans))
        self.assertIsNotNone(content_support.load_registry(VERSION))

    def test_hardening_did_not_touch_registry_artifacts(self) -> None:
        before = artifact_digest(REGISTRY_DIR)
        registry = load_registry(VERSION)
        prepare_content_plan_request(request("1208:120801"), registry=registry)
        self.assertEqual(artifact_digest(REGISTRY_DIR), before)


class ArtifactIntegrityTests(unittest.TestCase):
    def test_m14_registry_artifacts_unchanged_by_admission(self) -> None:
        before = artifact_digest(REGISTRY_DIR)
        registry = load_registry(VERSION)
        for record in registry.records[:50]:
            admit_content_for_planner(request(record.key.canonical), registry=registry)
            prepare_content_plan_request(request(record.key.canonical), registry=registry)
        self.assertEqual(artifact_digest(REGISTRY_DIR), before)

    def test_no_m12_m13_m14_file_is_written(self) -> None:
        before = artifact_digest(REGISTRY_DIR)
        registry = load_registry(VERSION)
        admit_content_for_planner(request("1208:120801"), registry=registry)
        self.assertEqual(artifact_digest(REGISTRY_DIR), before)


if __name__ == "__main__":
    unittest.main()
