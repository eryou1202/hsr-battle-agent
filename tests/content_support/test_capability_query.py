# -*- coding: utf-8 -*-
"""M14 content-capability query layer over the frozen M13 4.4.54 registry.

These tests are read-only: they load the committed M13 artifacts, exercise the
typed query surface, and assert that nothing promotes execution support.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from hsr_battle_agent.content_support import (  # noqa: E402
    BindingLevel,
    BlockerClass,
    ContentSkillKey,
    EvidenceMode,
    ExecutionEligibilityOutcome,
    PlannerVisibilityMode,
    Readiness,
    ReentryHint,
    RegistryIntegrityError,
    RegistryUnavailableError,
    SupportStatus,
    UnboundReason,
    UnknownSkillError,
    UnknownVocabularyError,
    UnknownVocabularyValue,
    VersionRelation,
    available_content_versions,
    describe_registry,
    get_all_skills,
    get_avatar_skills,
    get_bound_skills,
    get_by_binding_level,
    get_by_blocker_class,
    get_by_reentry_hint,
    get_by_support_status,
    get_second_hop_skills,
    get_settlement_skills,
    get_skill,
    get_unbound_skills,
    load_registry,
    parse_closed,
    planner_content_visibility,
    real_content_execution_eligibility,
    require_skill,
)

VERSION = "4.4.54"
SPECIAL_FOUR = ("1220:122014", "1510:151014", "8001:800103", "8002:800203")
REGISTRY_DIR = REPO / "data" / "content_support" / VERSION


def _artifact_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for name in sorted(p.name for p in directory.glob("*.json")):
        digest.update(name.encode("utf-8"))
        digest.update((directory / name).read_bytes())
    return digest.hexdigest()


class RegistryLoadTests(unittest.TestCase):
    """Population and integrity invariants of the frozen M13 registry."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)

    def test_content_version_is_explicit(self) -> None:
        self.assertEqual(self.registry.content_version, VERSION)
        self.assertTrue(self.registry.registry_path.is_file())

    def test_620_canonical_skills_load(self) -> None:
        self.assertEqual(len(self.registry.records), 620)
        self.assertEqual(len(set(self.registry.keys)), 620)

    def test_population_counts(self) -> None:
        counts = self.registry.counts()
        self.assertEqual(counts["canonical_records"], 620)
        self.assertEqual(counts["bound"], 524)
        self.assertEqual(counts["unbound"], 96)
        self.assertEqual(counts["binding_STATIC_ONLY"], 96)
        self.assertEqual(counts["status_UNBOUND_STATIC_SKILL"], 96)

    def test_trigger_name_joined_and_bound_counts(self) -> None:
        joined = [r for r in self.registry.records if r.skill_trigger_key]
        self.assertEqual(len(joined), 528)
        bound = [r for r in self.registry.records if r.entry_ability]
        self.assertEqual(len(bound), 524)

    def test_unbound_reason_breakdown(self) -> None:
        empty = [r for r in self.registry.records
                 if r.unbound_reason is UnboundReason.EMPTY_TRIGGER_KEY]
        no_entry = [r for r in self.registry.records
                    if r.unbound_reason is UnboundReason.TRIGGER_MATCHED_BUT_NO_ENTRY_ABILITY]
        self.assertEqual(len(empty), 92)
        self.assertEqual(len(no_entry), 4)
        self.assertEqual(len(empty) + len(no_entry), 96)

    def test_settlement_counts_preserved(self) -> None:
        full = [r for r in self.registry.records
                if r.closure.settlement_scope == "FULL_ACTION_CLOSURE"
                and r.closure.settlement_present]
        root_only = [r for r in self.registry.records
                     if r.closure.settlement_scope == "ROOT_RECORD_ONLY"
                     and r.closure.settlement_present]
        self.assertEqual(len(full), 293)
        self.assertEqual(len(root_only), 65)
        any_settlement = [r for r in self.registry.records if r.closure.settlement_present]
        self.assertEqual(len(any_settlement), 358)

    def test_second_hop_count_preserved(self) -> None:
        self.assertEqual(len(get_second_hop_skills(self.registry)), 20)
        self.assertEqual(
            sum(r.closure.second_hop_occurrence_count for r in self.registry.records), 23
        )

    def test_load_twice_is_equivalent(self) -> None:
        again = load_registry(VERSION)
        self.assertEqual(self.registry.records, again.records)
        self.assertEqual(self.registry.counts(), again.counts())

    def test_version_relation_maps_onto_frozen_vocabulary(self) -> None:
        for record in self.registry.records:
            self.assertIs(record.version_relation, VersionRelation.CLOSE_VERSION)
            self.assertFalse(record.version_provenance_qualified)

    def test_explicit_version_required_and_no_cross_version_fallback(self) -> None:
        with self.assertRaises(RegistryUnavailableError):
            load_registry("4.5.54")
        with self.assertRaises(RegistryUnavailableError):
            load_registry("")

    def test_available_versions_is_read_only_discovery(self) -> None:
        found = available_content_versions()
        self.assertIn(VERSION, found)


class ClosedVocabularyTests(unittest.TestCase):
    """Future or corrupted vocabulary values must fail closed."""

    def test_unknown_binding_level_fails_closed(self) -> None:
        with self.assertRaises(UnknownVocabularyError):
            parse_closed(BindingLevel, "SUPER_BOUND")

    def test_unknown_value_can_be_preserved_explicitly(self) -> None:
        preserved = parse_closed(BindingLevel, "SUPER_BOUND", preserve_unknown=True)
        self.assertIsInstance(preserved, UnknownVocabularyValue)
        self.assertEqual(preserved.raw, "SUPER_BOUND")
        self.assertNotEqual(preserved, BindingLevel.BEHAVIOR_ROOT_BOUND)

    def test_none_maps_to_none(self) -> None:
        self.assertIsNone(parse_closed(BindingLevel, None))

    def test_execution_has_no_eligible_outcome_member(self) -> None:
        self.assertEqual(
            [m.value for m in ExecutionEligibilityOutcome], ["NOT_ELIGIBLE"]
        )

    def test_planner_modes_exclude_execution_language(self) -> None:
        values = {m.value for m in PlannerVisibilityMode}
        self.assertEqual(values, {"REPRESENTABLE", "HAS_SETTLEMENT", "BLOCKED_WITH_REASON"})
        for forbidden in ("PLAYABLE", "LEGAL_ACTION", "EXECUTABLE_ACTION"):
            self.assertNotIn(forbidden, values)

    def test_readiness_reuses_the_frozen_vocabulary(self) -> None:
        from hsr_battle_agent.battle_ir.evidence import ReadinessClass
        self.assertIs(Readiness, ReadinessClass)
        for record in self.registry_records():
            self.assertIsInstance(record.readiness, ReadinessClass)

    def registry_records(self):
        return load_registry(VERSION).records


class TypedIdentityTests(unittest.TestCase):
    def test_canonical_form_is_avatar_colon_skill(self) -> None:
        key = ContentSkillKey(VERSION, "1208", "120801")
        self.assertEqual(key.canonical, "1208:120801")
        self.assertEqual(key.qualified, "4.4.54/1208:120801")
        self.assertEqual(str(key), "1208:120801")

    def test_key_rejects_blank_components(self) -> None:
        with self.assertRaises(ValueError):
            ContentSkillKey(VERSION, "", "120801")
        with self.assertRaises(ValueError):
            ContentSkillKey(VERSION, "1208", "  ")

    def test_identities_are_not_conflated(self) -> None:
        registry = load_registry(VERSION)
        first = registry.records[0]
        self.assertNotEqual(first.key.skill_id, first.skill_trigger_key or "")
        self.assertIsInstance(first.skill_trigger_key, str)
        self.assertTrue(first.entry_ability is None or isinstance(first.entry_ability, str))


class QueryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)

    def test_get_skill_returns_capability(self) -> None:
        capability = get_skill(self.registry, "1208", "120801")
        self.assertIsNotNone(capability)
        self.assertEqual(capability.key.canonical, "1208:120801")

    def test_get_skill_accepts_canonical_token(self) -> None:
        capability = get_skill(self.registry, "1208:120801")
        self.assertEqual(capability.key.skill_id, "120801")

    def test_unknown_skill_returns_explicit_absent_result(self) -> None:
        self.assertIsNone(get_skill(self.registry, "9999", "999999"))

    def test_require_skill_raises_documented_exception(self) -> None:
        with self.assertRaises(UnknownSkillError):
            require_skill(self.registry, "9999", "999999")

    def test_avatar_queries(self) -> None:
        skills = get_avatar_skills(self.registry, "1208")
        self.assertTrue(skills)
        self.assertTrue(all(c.key.avatar_id == "1208" for c in skills))
        self.assertEqual(get_avatar_skills(self.registry, "9999"), ())

    def test_bulk_filters_reconcile_with_counts(self) -> None:
        self.assertEqual(len(get_all_skills(self.registry)), 620)
        self.assertEqual(len(get_unbound_skills(self.registry)), 96)
        self.assertEqual(len(get_bound_skills(self.registry)), 524)
        self.assertEqual(len(get_settlement_skills(self.registry)), 358)
        self.assertEqual(len(get_second_hop_skills(self.registry)), 20)
        self.assertEqual(
            len(get_by_binding_level(self.registry, BindingLevel.STATIC_ONLY)), 96
        )
        self.assertEqual(
            len(get_by_support_status(self.registry, SupportStatus.UNBOUND_STATIC_SKILL)), 96
        )
        self.assertEqual(
            len(get_by_blocker_class(self.registry, BlockerClass.DAMAGE_PACKET)), 231
        )
        self.assertEqual(
            len(get_by_reentry_hint(self.registry, ReentryHint.WAITANIMSTATE_LOCAL_POLICY_REVIEW)),
            len([c for c in get_all_skills(self.registry)
                 if ReentryHint.WAITANIMSTATE_LOCAL_POLICY_REVIEW in c.reentry_hints]),
        )

    def test_string_filters_are_accepted_and_closed(self) -> None:
        by_enum = get_by_binding_level(self.registry, BindingLevel.STATIC_ONLY)
        by_str = get_by_binding_level(self.registry, "STATIC_ONLY")
        self.assertEqual(by_enum, by_str)
        with self.assertRaises(UnknownVocabularyError):
            get_by_binding_level(self.registry, "NOT_A_LEVEL")

    def test_ordering_is_stable_avatar_then_skill(self) -> None:
        skills = get_all_skills(self.registry)
        observed = [(c.key.avatar_id, c.key.skill_id) for c in skills]
        expected = sorted(
            observed,
            key=lambda pair: (
                (0, int(pair[0]), "") if pair[0].isdigit() else (1, 0, pair[0]),
                (0, int(pair[1]), "") if pair[1].isdigit() else (1, 0, pair[1]),
            ),
        )
        self.assertEqual(observed, expected)
        self.assertEqual(get_all_skills(self.registry), skills)

    def test_bulk_results_are_immutable_tuples(self) -> None:
        skills = get_all_skills(self.registry)
        self.assertIsInstance(skills, tuple)
        with self.assertRaises(Exception):
            skills[0] = skills[0]  # type: ignore[index]

    def test_describe_registry_reports_denial_boundary(self) -> None:
        described = describe_registry(self.registry)
        self.assertFalse(described["registry_satisfies_gate_certificate"])
        self.assertFalse(described["registry_satisfies_native_evidenced"])


class ExecutionEligibilityTests(unittest.TestCase):
    """Every 4.4.54 M13 skill must be NOT_ELIGIBLE, for registry-derived reasons."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)

    def test_all_620_are_not_eligible(self) -> None:
        outcomes = set()
        for record in self.registry.records:
            result = real_content_execution_eligibility(self.registry, record.key.canonical)
            outcomes.add(result.outcome)
            self.assertIs(result.outcome, ExecutionEligibilityOutcome.NOT_ELIGIBLE)
            self.assertFalse(result.eligible)
            self.assertFalse(result.satisfies_gate_certificate)
            self.assertFalse(result.satisfies_native_evidenced)
            self.assertIs(result.execution_evidence_mode, EvidenceMode.UNSUPPORTED)
            self.assertIs(result.representation_evidence_mode, EvidenceMode.REFERENCE_MODEL)
            self.assertTrue(result.reason_code)
            self.assertTrue(result.reason_detail)
        self.assertEqual(outcomes, {ExecutionEligibilityOutcome.NOT_ELIGIBLE})

    def test_reason_derives_from_registry_evidence(self) -> None:
        unbound = real_content_execution_eligibility(self.registry, "1220:122014")
        self.assertEqual(unbound.reason_code, "NO_BEHAVIOR_ROOT")
        self.assertIn("unbound_reason=", unbound.reason_detail)

        # A bound row whose represented closure records no settlement.
        no_settlement_token = next(
            r.key.canonical for r in self.registry.records
            if r.is_bound and not r.closure.settlement_present
        )
        no_settlement = real_content_execution_eligibility(self.registry, no_settlement_token)
        self.assertEqual(no_settlement.reason_code, "NO_SETTLEMENT_OBSERVED")
        self.assertIn("nothing to settle", no_settlement.reason_detail)

        blocked = real_content_execution_eligibility(self.registry, "1208:120801")
        self.assertEqual(blocked.reason_code, "BLOCKED_STATUS_BLOCKED_BY_EVIDENCE")
        self.assertIn("DAMAGE_PACKET", blocked.reason_detail)
        self.assertIn("WAIT_ANIM_STATE", blocked.reason_detail)

    def test_unknown_skill_raises(self) -> None:
        with self.assertRaises(UnknownSkillError):
            real_content_execution_eligibility(self.registry, "9999:999999")

    def test_reference_model_readiness_never_becomes_permission(self) -> None:
        for capability in get_by_support_status(self.registry, SupportStatus.REPRESENTABLE_BLOCKED):
            result = real_content_execution_eligibility(self.registry, capability.key.canonical)
            self.assertIs(result.outcome, ExecutionEligibilityOutcome.NOT_ELIGIBLE)


class PlannerVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)

    def test_modes(self) -> None:
        representable = planner_content_visibility(self.registry, PlannerVisibilityMode.REPRESENTABLE)
        has_settlement = planner_content_visibility(self.registry, "HAS_SETTLEMENT")
        blocked = planner_content_visibility(self.registry, "BLOCKED_WITH_REASON")
        self.assertEqual(len(representable), 620)
        self.assertEqual(len(has_settlement), 358)
        self.assertTrue(blocked)
        self.assertTrue(all(c.blocker_classes for c in blocked))

    def test_filter_is_descriptive_only(self) -> None:
        with self.assertRaises(UnknownVocabularyError):
            planner_content_visibility(self.registry, "EXECUTABLE_ACTION")


class SpecialRowsTests(unittest.TestCase):
    """The four trigger-matched rows without an EntryAbility stay unbound."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)

    def test_four_rows_are_static_only_and_unbound(self) -> None:
        for token in SPECIAL_FOUR:
            with self.subTest(token=token):
                record = self.registry.record(token)
                self.assertIsNotNone(record)
                self.assertIs(record.binding_level, BindingLevel.STATIC_ONLY)
                self.assertIs(record.support_status, SupportStatus.UNBOUND_STATIC_SKILL)
                self.assertIs(
                    record.unbound_reason, UnboundReason.TRIGGER_MATCHED_BUT_NO_ENTRY_ABILITY
                )
                self.assertTrue(record.skill_trigger_key)
                self.assertTrue(record.trigger_key_matched_owner_skill_name)
                self.assertIsNone(record.entry_ability)

    def test_prepare_ability_is_preserved_but_never_promotes_binding(self) -> None:
        expected_prepare = {
            "1220:122014": None,
            "1510:151014": None,
            "8001:800103": "Avatar_PlayerBoy_Skill03_EnterReady",
            "8002:800203": "Avatar_PlayerGirl_Skill03_EnterReady",
        }
        for token, prepare in expected_prepare.items():
            with self.subTest(token=token):
                record = self.registry.record(token)
                self.assertEqual(record.prepare_ability, prepare)
                # A *_EnterReady PrepareAbility is not an action root.
                self.assertIsNone(record.entry_ability)
                self.assertIs(record.binding_level, BindingLevel.STATIC_ONLY)
                self.assertFalse(record.closure.settlement_present)

    def test_four_rows_are_not_execution_eligible(self) -> None:
        for token in SPECIAL_FOUR:
            result = real_content_execution_eligibility(self.registry, token)
            self.assertEqual(result.reason_code, "NO_BEHAVIOR_ROOT")

    def test_no_other_row_is_unbound_by_trigger_match(self) -> None:
        matches = [
            r.key.canonical for r in self.registry.records
            if r.unbound_reason is UnboundReason.TRIGGER_MATCHED_BUT_NO_ENTRY_ABILITY
        ]
        self.assertEqual(sorted(matches), sorted(SPECIAL_FOUR))


class FuXuanFrontierTests(unittest.TestCase):
    """The strongest M12 frontier skill keeps its exact evidence shape."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(VERSION)
        cls.capability = require_skill(cls.registry, "1208", "120801")
        cls.record = cls.registry.record("1208:120801")

    def test_full_action_represented_and_settlement_present(self) -> None:
        self.assertIs(self.capability.binding_level, BindingLevel.FULL_ACTION_REPRESENTED)
        self.assertTrue(self.capability.settlement_present)
        self.assertIn("DAMAGE_REQUEST", [k.value for k in self.capability.settlement_kinds])
        self.assertEqual(self.record.closure.settlement_scope, "FULL_ACTION_CLOSURE")

    def test_sphitratio_metadata_is_retained(self) -> None:
        packet = self.record.minimum_frontier_packet_field
        self.assertIsNotNone(packet)
        self.assertEqual(packet.field, "SPHitRatio")
        self.assertIn("SPHitRatio", packet.extra_attack_fields)
        self.assertFalse(packet.deterministic_transition)
        self.assertEqual(packet.reference_contract_status, "NOT_CLOSED")
        self.assertIn(ReentryHint.NEW_NATIVE_SPHITRATIO_EVIDENCE, self.capability.reentry_hints)

    def test_wait_anim_state_blocker_is_retained(self) -> None:
        self.assertIs(self.capability.primary_blocker, BlockerClass.DAMAGE_PACKET)
        self.assertIn(BlockerClass.WAIT_ANIM_STATE, self.capability.blocker_classes)
        self.assertIn(ReentryHint.WAITANIMSTATE_LOCAL_POLICY_REVIEW, self.capability.reentry_hints)

    def test_not_executable(self) -> None:
        result = real_content_execution_eligibility(self.registry, "1208:120801")
        self.assertIs(result.outcome, ExecutionEligibilityOutcome.NOT_ELIGIBLE)
        self.assertEqual(result.reason_code, "BLOCKED_STATUS_BLOCKED_BY_EVIDENCE")


class ReadOnlyTests(unittest.TestCase):
    """Queries must not mutate the registry or the artifacts on disk."""

    def test_queries_do_not_mutate_artifacts(self) -> None:
        before = _artifact_digest(REGISTRY_DIR)
        registry = load_registry(VERSION)
        get_all_skills(registry)
        get_settlement_skills(registry)
        get_by_blocker_class(registry, BlockerClass.DAMAGE_PACKET)
        for record in registry.records[:25]:
            real_content_execution_eligibility(registry, record.key.canonical)
        planner_content_visibility(registry, PlannerVisibilityMode.REPRESENTABLE)
        self.assertEqual(_artifact_digest(REGISTRY_DIR), before)

    def test_mutating_a_returned_mapping_is_impossible(self) -> None:
        registry = load_registry(VERSION)
        with self.assertRaises(TypeError):
            registry.population["canonical_records"] = 0  # type: ignore[index]
        with self.assertRaises(TypeError):
            registry.record("1208:120801").raw_record["entry_ability"] = "x"  # type: ignore[index]

    def test_same_result_across_reloads(self) -> None:
        first = load_registry(VERSION)
        second = load_registry(VERSION)
        self.assertEqual(get_settlement_skills(first), get_settlement_skills(second))
        self.assertEqual(
            real_content_execution_eligibility(first, "1208:120801"),
            real_content_execution_eligibility(second, "1208:120801"),
        )


class TamperedRegistryTests(unittest.TestCase):
    """Fail-closed behaviour on a future or damaged registry."""

    def _copy_with(self, mutate) -> Path:
        target = Path(tempfile.mkdtemp(prefix="m14-registry-"))
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        version_dir = target / "data" / "content_support" / VERSION
        version_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(REGISTRY_DIR, version_dir)
        payload = json.loads((version_dir / "content_support_registry_v1.json").read_text("utf-8"))
        mutate(payload)
        (version_dir / "content_support_registry_v1.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        return target

    def test_unknown_binding_level_fails_closed_on_load(self) -> None:
        def mutate(payload):
            payload["records"][0]["binding_level"] = "SUPER_BOUND"
        root = self._copy_with(mutate)
        with self.assertRaises(UnknownVocabularyError):
            load_registry(VERSION, root=root)

    def test_dropped_record_fails_integrity(self) -> None:
        def mutate(payload):
            payload["records"] = payload["records"][:-1]
        root = self._copy_with(mutate)
        with self.assertRaises(RegistryIntegrityError):
            load_registry(VERSION, root=root)

    def test_index_dangling_key_fails_integrity(self) -> None:
        def mutate(payload):
            payload["indexes"]["by_blocker_class"]["DAMAGE_PACKET"].append("9999:999999")
        root = self._copy_with(mutate)
        with self.assertRaises(RegistryIntegrityError):
            load_registry(VERSION, root=root)

    def test_version_mismatch_fails_integrity(self) -> None:
        def mutate(payload):
            payload["content_version"] = "9.9.9"
        root = self._copy_with(mutate)
        with self.assertRaises(RegistryIntegrityError):
            load_registry(VERSION, root=root)


if __name__ == "__main__":
    unittest.main()
