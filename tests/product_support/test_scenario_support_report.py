"""Focused tests for the Scenario Support Report.

CR-P4-SCENARIO-SUPPORT-REPORT-20260929-001.

Three real 4.4.54 Scenario forms are exercised:

A. free Scenario  -- 1105, no source Stage, custom enemy wave;
B. stage-backed   -- 1105 with source_stage_id 420101;
C. M14-missing    -- 1508 (a real avatar with zero M14 rows).

Everything asserted here is descriptive product aggregation.  No battle is
executed, no legal action is created, no planner is invoked and no evidence is
promoted.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from hsr_battle_agent.content_planner import ADMISSION_OUTCOMES, NON_EFFECT_FIELDS
from hsr_battle_agent.content_support import load_registry
from hsr_battle_agent.game_data.nanoka_content import ContentDatabase, stable_hash
from hsr_battle_agent.game_data.scenario_compiler import ScenarioCompiler
from hsr_battle_agent.product_support import (
    ACCEPTED_M15_OUTCOME, FUTURE_OUTCOME_AUTO_EXTENSION,
    SCENARIO_SUPPORT_REPORT_SCHEMA, ContentVersionMismatchError,
    MalformedScenarioPackageError, MissingM14RegistryError,
    ScenarioSupportReporter, UnsupportedFutureAdmissionOutcomeError,
    UnsupportedScenarioSchemaError, build_scenario_support_report,
)
from hsr_battle_agent.product_support import scenario_report as report_module

LOCAL_DATABASE = (
    Path(__file__).resolve().parents[2] / "data" / "db" / "hsr_content_4.4.54.sqlite"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(report_module.__file__).read_text(encoding="utf-8")

NATASHA = "1105"
M14_MISSING_AVATAR = "1508"
STAGE_BACKED_STAGE = "420101"
NATASHA_LIGHTCONE = 21000
M14_MISSING_LIGHTCONE = 23037          # Mage-compatible for 1508
VARIANT_ENEMY = "100401401"

FORBIDDEN_IMPORT_TOKENS = (
    "reference_sandbox", "reference_battle_planner", "battle_sandbox",
    "reference_action_envelope",
)
FORBIDDEN_DOCUMENT_KEYS = (
    "battle_state", "envelope", "execution_trace", "golden_trace",
    "native_trace", "legal_actions", "transaction_plan", "gate_certificate",
)
PER_ENTITY_RUNTIME_KEYS = (
    "runtime_ready", "execution_ready", "executable", "executable_reference",
    "runtime_support_success", "planner_ready",
)


def _player(slot: int, avatar_id: str, lightcone_id: int) -> dict:
    return {
        "slot": str(slot),
        "avatar": {
            "avatar_id": avatar_id, "level": 80, "promotion": 6, "eidolon": 0,
            "skill_levels": {}, "trace_state": {"unlocked_trace_ids": []},
        },
        "lightcone": {"lightcone_id": lightcone_id, "level": 1, "promotion": 0, "superimposition": 1},
        "relics": [], "initial_state": {},
    }


def _request(scenario_id: str, avatar_id: str = NATASHA, lightcone_id: int = NATASHA_LIGHTCONE, **extra):
    request = {
        "game_version": "4.4.54",
        "scenario_id": scenario_id,
        "mode": "standard/free",
        "player_team": [_player(0, avatar_id, lightcone_id)],
        "enemy_waves": [{"wave_index": 1, "enemies": [
            {"instance_id": "e-a", "monster_id": 1002020, "level": 80},
        ]}],
        "buff_bindings": [],
        "rules": {"rng_seed": 7, "unsupported_policy": "reject"},
    }
    request.update(extra)
    return request


def _rehash(package: dict) -> dict:
    """Return a copy whose package_sha256 matches its (possibly malformed) content.

    Used to prove that structural shape validation is independent of hash
    integrity: every malformed fixture below carries a *correct* hash.
    """
    body = {k: v for k, v in package.items() if k != "package_sha256"}
    return {**body, "package_sha256": stable_hash(body)}


def _contains_value(value: object, needle: object) -> bool:
    """True when ``needle`` appears anywhere among the document's values."""
    if isinstance(value, dict):
        return any(_contains_value(item, needle) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_value(item, needle) for item in value)
    return value == needle


def _walk_keys(value: object):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_keys(item)


class _FutureAdmittedResult(SimpleNamespace):
    """A deliberately impossible admission result, used to prove fail-closed."""

    def __init__(
        self,
        *,
        outcome: str = "ADMITTED",
        rejected: bool = False,
        permission: bool = False,
        neutral: bool = True,
    ):
        super().__init__(
            outcome=outcome, rejected=rejected,
            may_create_reference_action_envelope=permission,
            may_enter_player_legal_actions=False,
            may_expand_planner_successor=False,
            may_mutate_state=False,
            non_effects=SimpleNamespace(is_neutral=lambda: neutral),
            to_dict=lambda: {"outcome": outcome},
        )


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class RegistryRequiredTest(unittest.TestCase):
    """Finding 1/2 -- an explicit M14 registry is mandatory; no authority seam."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.registry = load_registry("4.4.54")

    def test_reporter_without_registry_is_not_a_valid_call(self) -> None:
        with self.assertRaises(TypeError):
            ScenarioSupportReporter(self.database)

    def test_explicit_none_registry_fails_closed_immediately(self) -> None:
        with self.assertRaises(MissingM14RegistryError):
            ScenarioSupportReporter(self.database, registry=None)

    def test_convenience_function_without_registry_is_not_a_valid_call(self) -> None:
        import inspect

        parameters = inspect.signature(build_scenario_support_report).parameters
        self.assertIn("registry", parameters)
        self.assertIs(parameters["registry"].default, inspect.Parameter.empty)
        with self.assertRaises(TypeError):
            build_scenario_support_report({}, self.database)

    def test_registry_is_a_required_keyword_only_parameter(self) -> None:
        import inspect

        parameters = inspect.signature(ScenarioSupportReporter.__init__).parameters
        self.assertEqual(list(parameters), ["self", "database", "registry", "repository_root"])
        self.assertIs(parameters["registry"].default, inspect.Parameter.empty)
        self.assertEqual(parameters["registry"].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_product_service_cannot_be_injected(self) -> None:
        import inspect

        self.assertNotIn(
            "product_service", inspect.signature(ScenarioSupportReporter.__init__).parameters,
        )
        self.assertNotIn("product_service", SOURCE)
        with self.assertRaises(TypeError):
            ScenarioSupportReporter(
                self.database, registry=self.registry, product_service=object(),
            )

    def test_product_service_is_built_from_the_same_authorities(self) -> None:
        reporter = ScenarioSupportReporter(self.database, registry=self.registry)
        self.assertIs(reporter.products.database, self.database)
        self.assertEqual(reporter.products.game_version, self.database.game_version)
        self.assertTrue(reporter.products.m14_registry_supplied)
        self.assertEqual(reporter.registry.content_version, self.database.game_version)
        # The service honours the same registry, so a version-mixed pairing cannot
        # be constructed at all.
        with self.assertRaises(ContentVersionMismatchError):
            ScenarioSupportReporter(
                ContentDatabase(LOCAL_DATABASE, "4.4.55"), registry=self.registry,
            )

    def test_registry_not_supplied_is_not_a_reachable_report_state(self) -> None:
        document = ScenarioSupportReporter(self.database, registry=self.registry).build(
            ScenarioCompiler(self.database).compile(_request("p41-registry"))
        )
        self.assertTrue(document["avatar_content_support"]["registry_loaded"])
        for character in document["avatar_content_support"]["characters"]:
            self.assertTrue(character["capability"]["registry_loaded"])
            for skill in character["skills"]:
                self.assertNotEqual(skill["m14_status"], "M14_REGISTRY_NOT_SUPPLIED")
        # No report VALUE is ever that state; the token only appears in the
        # MissingM14RegistryError explanation of why it cannot occur here.
        self.assertFalse(_contains_value(document, "M14_REGISTRY_NOT_SUPPLIED"))


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class _ReportCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.registry = load_registry("4.4.54")
        cls.compiler = ScenarioCompiler(cls.database)
        cls.reporter = ScenarioSupportReporter(cls.database, registry=cls.registry)
        cls.free_package = cls.compiler.compile(_request("p4-free"))
        cls.stage_package = cls.compiler.compile(
            _request("p4-stage", source_stage_id=STAGE_BACKED_STAGE, enemy_waves=None)
        )
        cls.m14_missing_package = cls.compiler.compile(
            _request("p4-m14missing", avatar_id=M14_MISSING_AVATAR, lightcone_id=M14_MISSING_LIGHTCONE)
        )


class InputContractTest(_ReportCase):
    """Section 3/21 INPUT."""

    def test_scenario_package_v2_is_accepted(self) -> None:
        report = self.reporter.build(self.free_package)
        self.assertEqual(report["schema"], SCENARIO_SUPPORT_REPORT_SCHEMA)
        self.assertEqual(report["identity"]["scenario_package_schema"], "hsr_battle_agent.scenario_package/2")
        self.assertTrue(report["identity"]["scenario_package_hash_verified"])

    def test_scenario_package_v1_is_rejected_by_name(self) -> None:
        with self.assertRaises(UnsupportedScenarioSchemaError) as context:
            self.reporter.build({"schema": "hsr_battle_agent.scenario_package/1", "game_version": "4.4.54"})
        self.assertIn("scenario_package/1", str(context.exception))

    def test_unknown_schema_is_rejected(self) -> None:
        with self.assertRaises(UnsupportedScenarioSchemaError):
            self.reporter.build({"schema": "hsr_battle_agent.scenario_package/3", "game_version": "4.4.54"})

    def test_mixed_version_is_rejected(self) -> None:
        with self.assertRaises(ContentVersionMismatchError):
            self.reporter.build({**self.free_package, "game_version": "4.4.55"})

    def test_registry_database_version_mismatch_is_rejected_at_construction(self) -> None:
        other = ContentDatabase(LOCAL_DATABASE, "4.4.55")
        with self.assertRaises(ContentVersionMismatchError):
            ScenarioSupportReporter(other, registry=self.registry)

    def test_malformed_package_is_rejected(self) -> None:
        cases = {
            "not a mapping": "nope",
            "missing waves": {k: v for k, v in self.free_package.items() if k != "waves"},
            "no players": {**self.free_package, "players": []},
            "no rng seed": {**self.free_package, "rules": {"unsupported_policy": "reject"}},
            "tampered hash": {**self.free_package, "package_sha256": "0" * 64},
            "missing hash": {k: v for k, v in self.free_package.items() if k != "package_sha256"},
        }
        for label, package in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(MalformedScenarioPackageError):
                    self.reporter.build(package)

    def test_package_hash_is_verified_before_consumption(self) -> None:
        tampered = json.loads(json.dumps(self.free_package))
        tampered["scenario_id"] = "tampered-after-hash"
        with self.assertRaises(MalformedScenarioPackageError):
            self.reporter.build(tampered)

    def test_malformed_structure_fails_closed_with_a_correct_hash(self) -> None:
        """Shape validation must not depend on package_sha256.

        Each fixture below is re-hashed so its hash is correct; only its shape is
        wrong, so any failure proves structural validation is independent.
        """
        cases = {
            "waves is a mapping": {"waves": {}},
            "wave is a string": {"waves": ["garbage"]},
            "wave has no enemies key": {"waves": [{"wave_index": 1}]},
            "wave.enemies is a mapping": {"waves": [{"wave_index": 1, "enemies": {}}]},
            "enemy is a string": {"waves": [{"wave_index": 1, "enemies": ["garbage"]}]},
            "buff_bindings is a string": {"buff_bindings": "garbage"},
            "buff_bindings entry is a string": {"buff_bindings": ["garbage"]},
            "unresolved_behavior is a mapping": {"unresolved_behavior": {}},
            "unresolved_behavior entry is a string": {"unresolved_behavior": ["garbage"]},
            "players entry is a string": {"players": ["garbage"]},
            "rules is a list": {"rules": []},
            "source_stage is a string": {"source_stage": "nope"},
        }
        for label, override in cases.items():
            with self.subTest(label=label):
                candidate = _rehash({**self.free_package, **override})
                # The hash really is correct for this (malformed) content.
                self.assertEqual(
                    candidate["package_sha256"],
                    stable_hash({k: v for k, v in candidate.items() if k != "package_sha256"}),
                )
                with self.assertRaises(MalformedScenarioPackageError):
                    self.reporter.build(candidate)

    def test_structurally_valid_edges_are_accepted(self) -> None:
        # An explicit null source_stage and an empty (but well-typed) enemies list
        # are structurally fine; only the shapes are validated, not business rules.
        for label, override in (
            ("source_stage None", {"source_stage": None}),
            ("empty buff_bindings", {"buff_bindings": []}),
            ("empty unresolved_behavior", {"unresolved_behavior": []}),
            ("empty enemies", {"waves": [{"wave_index": 1, "enemies": []}]}),
        ):
            with self.subTest(label=label):
                report = self.reporter.build(_rehash({**self.free_package, **override}))
                self.assertEqual(report["schema"], SCENARIO_SUPPORT_REPORT_SCHEMA)

    def test_same_input_produces_the_same_report_hash(self) -> None:
        for label, package in (
            ("A free", self.free_package),
            ("B stage-backed", self.stage_package),
            ("C M14-missing", self.m14_missing_package),
        ):
            with self.subTest(fixture=label):
                first = self.reporter.build(package)
                second = ScenarioSupportReporter(self.database, registry=self.registry).build(package)
                self.assertEqual(first["report_sha256"], second["report_sha256"])
                self.assertEqual(self.reporter.build(package)["report_sha256"], first["report_sha256"])

    def test_caller_mutation_cannot_affect_another_result(self) -> None:
        first = self.reporter.build(self.free_package)
        baseline = self.reporter.build(self.free_package)["report_sha256"]
        first["summary"]["player_count"] = 99
        first["static_resolution"]["players"][0]["avatar_id"] = "tampered"
        first["monster_runtime_support"]["scope"] = "tampered"
        second = self.reporter.build(self.free_package)
        self.assertEqual(second["summary"]["player_count"], 1)
        self.assertEqual(second["static_resolution"]["players"][0]["avatar_id"], NATASHA)
        self.assertEqual(second["report_sha256"], baseline)

    def test_report_carries_no_wall_clock_timestamp(self) -> None:
        report = self.reporter.build(self.free_package)
        for key in _walk_keys(report):
            self.assertNotIn("timestamp", key.lower())
            self.assertNotIn("generated_at", key.lower())


class StaticResolutionTest(_ReportCase):
    """Section 6/10/21 STATIC."""

    def test_free_scenario_reports_no_stage_without_error(self) -> None:
        stage = self.reporter.build(self.free_package)["stage_static_support"]
        self.assertFalse(stage["source_stage_present"])
        self.assertTrue(stage["stage_absent_is_not_an_error"])
        self.assertIsNone(stage["stage_id"])
        self.assertIsNone(stage["stage_product_sha256"])
        summary = self.reporter.build(self.free_package)["summary"]
        self.assertEqual(summary["stage_unknown_reference_count"], 0)

    def test_stage_backed_scenario_resolves_the_stage_product(self) -> None:
        stage = self.reporter.build(self.stage_package)["stage_static_support"]
        self.assertTrue(stage["source_stage_present"])
        self.assertEqual(stage["stage_id"], STAGE_BACKED_STAGE)
        self.assertTrue(stage["stage_package_topology_present"])
        self.assertEqual(stage["encounter_source_modes"], ["boss"])
        self.assertEqual(
            stage["stage_buff_references"], [{"buff_id": "3110001", "resolution_status": "RESOLVED"}],
        )
        self.assertTrue(stage["rule_metadata_present"])
        self.assertFalse(stage["rule_metadata_interpreted"])
        self.assertEqual(stage["canonical_mode"], None)
        self.assertFalse(stage["canonical_mode_established"])
        self.assertTrue(stage["f9_retained_static_metadata_present"])
        self.assertGreater(len(stage["f9_fields_present"]), 0)
        product = self.reporter.products.get_stage(STAGE_BACKED_STAGE)
        self.assertEqual(stage["stage_product_sha256"], product["product_sha256"])

    def test_player_and_wave_identities_are_preserved(self) -> None:
        resolution = self.reporter.build(self.free_package)["static_resolution"]
        player = resolution["players"][0]
        self.assertEqual(player["instance_id"], "player:0")
        self.assertEqual(player["slot"], "0")
        self.assertEqual(player["avatar_id"], NATASHA)
        self.assertTrue(player["static_loadout_present"])
        self.assertEqual(player["static_loadout_schema"], "hsr_battle_agent.static_loadout/1")
        wave = resolution["waves"][0]
        self.assertEqual(wave["wave_index"], 1)
        self.assertIsNone(wave["wave_id"])          # a caller-added free wave, never fabricated
        self.assertEqual(wave["origin"], "CALLER")
        self.assertEqual(wave["enemies"][0]["requested_monster_id"], "1002020")
        self.assertEqual(wave["enemies"][0]["level"], 80)

    def test_stage_template_wave_identity_is_preserved(self) -> None:
        resolution = self.reporter.build(self.stage_package)["static_resolution"]
        wave = resolution["waves"][0]
        self.assertEqual(wave["wave_id"], "420101:1")
        self.assertEqual(wave["origin"], "TEMPLATE")

    def test_p0_variant_requested_id_is_preserved(self) -> None:
        resolution = self.reporter.build(self.stage_package)["static_resolution"]
        enemies = resolution["waves"][0]["enemies"]
        variant = [enemy for enemy in enemies if enemy["requested_monster_id"] == VARIANT_ENEMY][0]
        self.assertEqual(variant["resolution"]["resolved_kind"], "MONSTER_VARIANT")
        self.assertEqual(variant["resolution"]["variant_id"], VARIANT_ENEMY)
        self.assertEqual(variant["resolution"]["canonical_monster_id"], "1004014")
        self.assertNotEqual(variant["requested_monster_id"], variant["resolution"]["canonical_monster_id"])

    def test_stage_unknown_references_are_preserved_verbatim(self) -> None:
        report = self.reporter.build(self.stage_package)
        stage = report["stage_static_support"]
        product = self.reporter.products.get_stage(STAGE_BACKED_STAGE)
        self.assertEqual(stage["unknown_references"], product["topology"]["unknown_references"])
        self.assertEqual(stage["unknown_reference_count"], len(product["topology"]["unknown_references"]))
        self.assertEqual(
            report["unresolved_content"]["stage_unknown_references"]["count"],
            stage["unknown_reference_count"],
        )

    def test_rules_are_reported_as_records_not_reinterpreted(self) -> None:
        resolution = self.reporter.build(self.free_package)["static_resolution"]
        self.assertFalse(resolution["rule_records_reinterpreted"])
        rules = resolution["rules"]
        self.assertEqual(rules["victory_rule"]["resolution_status"], "UNSPECIFIED")
        self.assertIn("execution_semantics", rules["victory_rule"])
        self.assertEqual(rules["victory_rule"]["execution_semantics"], "NONE")

    def test_unresolved_behavior_is_not_a_missing_static_entity(self) -> None:
        report = self.reporter.build(self.free_package)
        category = report["unresolved_content"]["scenario_unresolved_behavior"]
        self.assertFalse(category["is_missing_static_entity"])
        self.assertTrue(all(
            entry["status"] == "BEHAVIOR_COMPILATION_REQUIRED" for entry in category["entries"]
        ))
        self.assertEqual(
            category["count"], len(self.free_package["unresolved_behavior"]),
        )

    def test_unapplied_loadout_effects_remain_unapplied_contextual(self) -> None:
        loadout = self.reporter.build(self.free_package)["loadout_static_support"]
        self.assertFalse(loadout["re_evaluated_here"])
        self.assertFalse(loadout["contextual_effects_applied_here"])
        player = loadout["players"][0]
        self.assertEqual(player["unapplied_contextual_count"], 1)
        self.assertTrue(player["all_unapplied_statuses_canonical"])
        self.assertEqual(player["unapplied_contextual_effects"][0]["status"], "UNAPPLIED_CONTEXTUAL")
        self.assertEqual(player["unapplied_contextual_effects"][0]["kind"], "lightcone_effect")
        self.assertEqual(player["final_properties"], self.free_package["players"][0]["loadout"]["final_properties"])


class M14AvatarSupportTest(_ReportCase):
    """Section 7/21 M14."""

    def test_linked_skills_copy_the_p2_capability(self) -> None:
        character = self.reporter.build(self.free_package)["avatar_content_support"]["characters"][0]
        product = self.reporter.products.get_character(NATASHA)
        self.assertEqual(character["character_product_sha256"], product["product_sha256"])
        self.assertEqual(character["capability"]["status"], "COMPLETE")
        self.assertEqual(character["capability"]["skills_with_m14_row"], 6)
        self.assertEqual(character["capability"]["skills_without_m14_row"], 0)
        self.assertEqual(
            [skill["skill_id"] for skill in character["skills"]],
            [skill["skill_id"] for skill in product["skills"]],
        )
        for skill, source in zip(character["skills"], product["skills"]):
            self.assertEqual(skill["m14_capability"], source["m14_capability"])
            self.assertFalse(skill["m14_capability"]["recomputed_by_product_layer"])
        self.assertFalse(character["capability_recomputed_here"])
        self.assertFalse(character["m13_raw_json_read"])

    def test_eligibility_is_copied_not_re_derived(self) -> None:
        character = self.reporter.build(self.free_package)["avatar_content_support"]["characters"][0]
        for skill in character["skills"]:
            eligibility = skill["m14_execution_eligibility"]
            self.assertIsNotNone(eligibility)
            self.assertEqual(
                eligibility["authority"],
                "content_support.real_content_execution_eligibility (M14)",
            )
            self.assertFalse(eligibility["recomputed_by_product_layer"])
            self.assertEqual(eligibility["outcome"], "NOT_ELIGIBLE")
            for not_a_source in ("execution_readiness", "support_status", "binding_level", "settlement_present"):
                self.assertNotIn(not_a_source, eligibility)

    def test_missing_m14_rows_stay_explicit(self) -> None:
        character = self.reporter.build(self.m14_missing_package)["avatar_content_support"]["characters"][0]
        self.assertEqual(character["avatar_id"], M14_MISSING_AVATAR)
        self.assertEqual(character["capability"]["status"], "NONE")
        self.assertEqual(character["capability"]["skills_with_m14_row"], 0)
        self.assertEqual(character["capability"]["skills_without_m14_row"], len(character["skills"]))
        for skill in character["skills"]:
            self.assertEqual(skill["m14_status"], "NO_M14_ROW")
            self.assertIsNone(skill["m14_capability"])
            self.assertIsNone(skill["m14_execution_eligibility"])
        report = self.reporter.build(self.m14_missing_package)
        missing = report["unresolved_content"]["character_static_skill_without_m14_row"]
        self.assertEqual(missing["count"], len(character["skills"]))
        self.assertTrue(all(entry["avatar_id"] == M14_MISSING_AVATAR for entry in missing["entries"]))


class M15AdmissionTest(_ReportCase):
    """Section 8/9/21 M15."""

    def test_every_admission_is_rejected(self) -> None:
        report = self.reporter.build(self.free_package)
        admission = report["real_content_execution_admission"]
        self.assertEqual(admission["outcome_counts"], {"REJECTED": len(admission["results"])})
        self.assertEqual(set(admission["admission_outcome_vocabulary"]), {"REJECTED"})
        self.assertEqual(admission["expected_outcome"], "REJECTED")
        for result in admission["results"]:
            self.assertEqual(result["outcome"], "REJECTED")
            self.assertIn(result["reason_code"], admission["reason_code_counts"])
            self.assertTrue(result["reason_detail"])

    def test_reason_values_match_the_public_api(self) -> None:
        from hsr_battle_agent.content_planner import (
            ContentPlannerAdmissionRequest, admit_content_for_planner,
        )

        report = self.reporter.build(self.free_package)
        by_skill = {result["skill_key"]: result for result in report["real_content_execution_admission"]["results"]}
        for skill_id, result in by_skill.items():
            authoritative = admit_content_for_planner(
                ContentPlannerAdmissionRequest(content_version="4.4.54", avatar_id=NATASHA, skill_id=skill_id.split(":")[1]),
                registry=self.registry,
            )
            self.assertEqual(result["reason_code"], authoritative.reason_code.value)
            self.assertEqual(result["reason_detail"], authoritative.reason_detail)
            self.assertEqual(result["m14_reason_code"], authoritative.m14_reason_code)
            self.assertEqual(
                result["blocker_classes"], [getattr(b, "value", b) for b in authoritative.blocker_classes],
            )
            self.assertEqual(
                result["reentry_hints"], [getattr(h, "value", h) for h in authoritative.reentry_hints],
            )

    def test_public_api_only_and_no_private_helper(self) -> None:
        report = self.reporter.build(self.free_package)
        admission = report["real_content_execution_admission"]
        self.assertEqual(admission["api_used"], "admit_content_for_planner")
        self.assertEqual(admission["private_helpers_used"], [])
        self.assertFalse(admission["planner_facade_referenced"])
        self.assertIn("admit_content_for_planner", SOURCE)
        for private in ("_admit_with_registry", "prepare_content_plan_request", "planner_callable"):
            self.assertNotIn(private, SOURCE, private)
        for result in admission["results"]:
            self.assertEqual(result["consumed_from_public_api"], "admit_content_for_planner")
            self.assertEqual(result["private_helpers_used"], [])

    def test_non_effects_remain_all_zero(self) -> None:
        for package in (self.free_package, self.stage_package, self.m14_missing_package):
            with self.subTest(scenario=package["scenario_id"]):
                report = self.reporter.build(package)
                non_effects = report["real_content_execution_admission"]["non_effects"]
                self.assertEqual(set(non_effects), set(NON_EFFECT_FIELDS))
                for name in NON_EFFECT_FIELDS:
                    self.assertEqual(non_effects[name], 0, name)
                self.assertTrue(report["non_claims"]["non_effects_are_all_zero"])
                for name in (
                    "may_create_reference_action_envelope", "may_enter_player_legal_actions",
                    "may_expand_planner_successor", "may_mutate_state",
                ):
                    self.assertFalse(report["real_content_execution_admission"]["permission_fields"][name], name)

    def test_m14_missing_avatar_is_distinct_from_m15_rejection(self) -> None:
        report = self.reporter.build(self.m14_missing_package)
        character = report["avatar_content_support"]["characters"][0]
        self.assertEqual({skill["m14_status"] for skill in character["skills"]}, {"NO_M14_ROW"})
        admission = report["real_content_execution_admission"]
        self.assertEqual(set(admission["reason_code_counts"]), {"SKILL_NOT_IN_REGISTRY"})
        self.assertTrue(all(result["m14_reason_code"] is None for result in admission["results"]))
        # The two vocabularies must not be conflated.
        self.assertNotIn("NO_M14_ROW", admission["reason_code_counts"])
        missing = report["unresolved_content"]["character_static_skill_without_m14_row"]
        self.assertEqual(missing["count"], len(character["skills"]))
        self.assertNotIn("m15", missing["source"].lower())

    def test_unexpected_future_positive_outcome_fails_closed(self) -> None:
        with mock.patch.object(
            report_module, "admit_content_for_planner",
            return_value=_FutureAdmittedResult(outcome="ADMITTED"),
        ):
            with self.assertRaises(UnsupportedFutureAdmissionOutcomeError):
                self.reporter.build(self.free_package)

    def test_non_false_permission_conclusion_fails_closed(self) -> None:
        with mock.patch.object(
            report_module, "admit_content_for_planner",
            return_value=_FutureAdmittedResult(outcome="REJECTED", rejected=True, permission=True),
        ):
            with self.assertRaises(UnsupportedFutureAdmissionOutcomeError):
                self.reporter.build(self.free_package)

    def test_non_neutral_non_effects_fails_closed(self) -> None:
        with mock.patch.object(
            report_module, "admit_content_for_planner",
            return_value=_FutureAdmittedResult(outcome="REJECTED", rejected=True, neutral=False),
        ):
            with self.assertRaises(UnsupportedFutureAdmissionOutcomeError):
                self.reporter.build(self.free_package)

    def test_exact_accepted_outcome_is_rejected_only(self) -> None:
        self.assertEqual(ACCEPTED_M15_OUTCOME, "REJECTED")
        self.assertFalse(FUTURE_OUTCOME_AUTO_EXTENSION)
        self.assertEqual(report_module.ACCEPTED_M15_OUTCOME, "REJECTED")
        self.assertFalse(report_module.FUTURE_OUTCOME_AUTO_EXTENSION)
        admission = self.reporter.build(self.free_package)["real_content_execution_admission"]
        self.assertEqual(admission["accepted_outcomes"], ["REJECTED"])
        self.assertEqual(admission["expected_outcome"], "REJECTED")
        self.assertFalse(admission["future_outcome_auto_extension"])
        # The vocabulary is reported as authority metadata, but only the reviewed
        # outcome is accepted.
        self.assertEqual(admission["admission_outcome_vocabulary"], list(ADMISSION_OUTCOMES))
        self.assertTrue(admission["outcome_vocabulary_is_authority_metadata_only"])
        self.assertNotIn("accepted_outcomes", admission["admission_outcome_vocabulary"])

    def test_future_outcome_added_to_the_vocabulary_is_still_refused(self) -> None:
        """A future token must not be auto-accepted merely by joining the enum."""
        fake = _FutureAdmittedResult(outcome="DEFERRED", rejected=True)
        with mock.patch.object(report_module, "admit_content_for_planner", return_value=fake):
            with mock.patch.object(
                report_module, "ADMISSION_OUTCOMES", ("REJECTED", "DEFERRED"),
            ):
                with self.assertRaises(UnsupportedFutureAdmissionOutcomeError):
                    self.reporter.build(self.free_package)
        # Even a rejected=True DEFERRED is refused without any vocabulary widening.
        with mock.patch.object(report_module, "admit_content_for_planner", return_value=fake):
            with self.assertRaises(UnsupportedFutureAdmissionOutcomeError):
                self.reporter.build(self.free_package)

    def test_no_planner_callback_exists(self) -> None:
        self.assertFalse(report_module.PLANNER_FACADE_REFERENCED)
        report = self.reporter.build(self.free_package)
        self.assertFalse(report["non_claims"]["planner_invoked"])


class MonsterAndStageRuntimeScopeTest(_ReportCase):
    """Section 11-14/21 MONSTER/STAGE RUNTIME."""

    def test_both_runtime_scopes_are_family_level_only(self) -> None:
        report = self.reporter.build(self.stage_package)
        for section in ("monster_runtime_support", "stage_runtime_support"):
            with self.subTest(section=section):
                block = report[section]
                self.assertEqual(block["scope"], "FAMILY_LEVEL_ONLY")
                self.assertFalse(block["per_entity_runtime_claim_available"])
                self.assertFalse(block["per_entity_claim_emitted"])

    def test_no_per_entity_runtime_ready_field_is_emitted(self) -> None:
        report = self.reporter.build(self.stage_package)
        occurrence = report["monster_static_support"]["occurrences"][0]
        for key in PER_ENTITY_RUNTIME_KEYS:
            self.assertNotIn(key, occurrence, key)
        for key in PER_ENTITY_RUNTIME_KEYS:
            self.assertNotIn(key, report["stage_static_support"], key)
        # The named forbidden keys must not appear anywhere at occurrence level.
        self.assertFalse(occurrence["runtime_support_success_implied"])
        self.assertTrue(occurrence["variant_identity_is_static_identity"])
        self.assertTrue(report["monster_static_support"]["occurrence_identity_kept_separate_from_monster_identity"])

    def test_family_facts_cite_their_source_artifact(self) -> None:
        report = self.reporter.build(self.free_package)
        for section, family in (
            ("monster_runtime_support", "Monster"),
            ("stage_runtime_support", "StageBuff"),
        ):
            with self.subTest(section=section):
                facts = report[section]["family_facts"]
                self.assertTrue(facts)
                matching = [fact for fact in facts if fact["family"] == family]
                self.assertTrue(matching)
                for fact in matching:
                    self.assertTrue(fact["artifact"])
                    self.assertTrue(fact["artifact_sha256"])
                    self.assertTrue(fact["report_id"])
                    self.assertTrue((REPOSITORY_ROOT / fact["artifact"]).is_file())
        monster_facts = [fact for fact in report["monster_runtime_support"]["family_facts"] if fact["family"] == "Monster"]
        census_fact = [fact for fact in monster_facts if "behavior_mapped" in fact][0]
        self.assertEqual(census_fact["behavior_mapped"], 0)
        self.assertEqual(report["monster_runtime_support"]["exact_static_entity_link_count"], 0)
        self.assertFalse(report["monster_runtime_support"]["per_static_monster_behavior_join_available"])

    def test_stage_runtime_declares_mechanisms_and_non_inference(self) -> None:
        block = self.reporter.build(self.free_package)["stage_runtime_support"]
        for mechanism in (
            "wave_spawn", "wave_progression_or_clear", "stage_buff_activation",
            "mode_rules", "score_rules", "special_terminal_rules",
            "boss_phase_or_body_part_handling",
        ):
            self.assertIn(mechanism, block["runtime_mechanisms_not_implemented"])
        self.assertIn("StagePackage presence", block["not_inferred_from"])
        self.assertFalse(block["stage_runtime_implemented"])

    def test_golden_block_reports_zero_without_holding_a_trace(self) -> None:
        block = self.reporter.build(self.free_package)["stage_runtime_support"]["golden_block"]
        self.assertTrue(block["available"])
        self.assertEqual(block["golden"], 0)
        self.assertEqual(block["native_trace_entry_count"], 0)
        self.assertEqual(block["native_trace_claim"], "NONE")
        self.assertEqual(set(block["source_field_names"]), {"golden", "native_trace"})
        # The report holds no key that could be mistaken for an execution artifact.
        self.assertNotIn("native_trace", block)
        self.assertTrue((REPOSITORY_ROOT / block["artifact"]).is_file())

    def test_monster_occurrence_identity_and_static_gaps(self) -> None:
        report = self.reporter.build(self.stage_package)
        occurrences = report["monster_static_support"]["occurrences"]
        self.assertEqual(len(occurrences), 2)
        first = occurrences[0]
        self.assertEqual(first["wave_index"], 1)
        self.assertEqual(first["wave_id"], "420101:1")
        self.assertEqual(first["requested_monster_id"], VARIANT_ENEMY)
        # The level comes from the Stage template placement (420101 uses level 60),
        # not from a caller-supplied enemy wave.
        self.assertEqual(first["level"], 60)
        self.assertTrue(first["level_supplied"])
        self.assertEqual(first["formation"], {"group_index": 0, "slot": "monster0"})
        self.assertEqual(first["resolved_kind"], "MONSTER_VARIANT")
        self.assertEqual(first["canonical_monster_id"], "1004014")
        self.assertEqual(first["variant_id"], VARIANT_ENEMY)
        self.assertTrue(first["monster_product_available"])
        self.assertFalse(report["monster_static_support"]["monster_ai_claimed"])
        self.assertFalse(report["monster_static_support"]["monster_skill_execution_claimed"])

    def test_stage_identity_is_separate_from_monster_identity(self) -> None:
        report = self.reporter.build(self.stage_package)
        self.assertEqual(report["stage_static_support"]["stage_id"], STAGE_BACKED_STAGE)
        self.assertEqual(report["summary"]["variant_enemy_occurrence_count"], 2)


class UnresolvedAndNonClaimsTest(_ReportCase):
    """Section 15-17/21."""

    def test_every_category_is_present_and_kept_distinct(self) -> None:
        report = self.reporter.build(self.stage_package)
        unresolved = report["unresolved_content"]
        self.assertEqual(set(unresolved["categories"]), set(report_module.UNRESOLVED_CONTENT_CATEGORIES))
        self.assertTrue(unresolved["categories_kept_distinct"])
        for category in unresolved["categories"]:
            self.assertIn(category, unresolved, category)
            self.assertIn("source", unresolved[category], category)
            self.assertIn("count", unresolved[category], category)

    def test_categories_are_not_flattened_into_one_error_list(self) -> None:
        unresolved = self.reporter.build(self.free_package)["unresolved_content"]
        self.assertNotIn("errors", unresolved)
        self.assertNotIn("error_count", unresolved)
        self.assertNotEqual(
            unresolved["scenario_unresolved_behavior"]["source"],
            unresolved["m15_rejection_reasons"]["source"],
        )
        self.assertEqual(unresolved["m15_rejection_reasons"]["count"], 6)
        self.assertEqual(unresolved["loadout_unapplied_contextual_effects"]["count"], 1)

    def test_non_claims_are_mechanical(self) -> None:
        report = self.reporter.build(self.stage_package)
        non_claims = report["non_claims"]
        self.assertFalse(non_claims["real_content_execution_performed"])
        self.assertEqual(non_claims["reference_action_envelopes_created"], 0)
        self.assertEqual(non_claims["player_legal_actions_created"], 0)
        self.assertFalse(non_claims["planner_invoked"])
        self.assertFalse(non_claims["battle_state_created"])
        self.assertFalse(non_claims["native_evidence_promoted"])
        self.assertFalse(non_claims["golden_claimed"])
        self.assertFalse(non_claims["scenario_is_executable"])
        self.assertFalse(non_claims["scenario_is_planner_ready"])
        self.assertFalse(non_claims["m15_rejection_proves_game_behavior"])
        self.assertFalse(
            non_claims["family_level_runtime_evidence_applies_to_an_individual_monster_or_stage"]
        )

    def test_no_readiness_score_or_execution_verdict(self) -> None:
        report = self.reporter.build(self.stage_package)
        for key in _walk_keys(report):
            lowered = key.lower()
            for forbidden in ("readiness_score", "support_percentage", "playable", "simulatable", "quality", "ranking"):
                self.assertNotIn(forbidden, lowered, key)
        # The Scenario's own static status fields are carried through, not invented.
        self.assertEqual(
            report["static_resolution"]["execution_status"],
            self.stage_package["execution_status"],
        )


class BoundaryTest(_ReportCase):
    """Section 21 BOUNDARY / 23 FROZEN LAYERS."""

    def test_module_does_not_import_execution_or_planner_layers(self) -> None:
        tree = ast.parse(SOURCE)
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
            elif isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
        for module in modules:
            for token in FORBIDDEN_IMPORT_TOKENS:
                self.assertNotIn(token, module, module)
        self.assertIn("content_planner", " ".join(modules))
        self.assertIn("content_support", " ".join(modules))

    def test_no_m13_raw_json_read(self) -> None:
        for token in ("registry_v1.json", "content_support_registry", "data/content_support", "open("):
            self.assertNotIn(token, SOURCE, token)

    def test_no_execution_artifact_keys_or_values(self) -> None:
        report = self.reporter.build(self.stage_package)
        keys = set(_walk_keys(report))
        for forbidden in FORBIDDEN_DOCUMENT_KEYS:
            self.assertNotIn(forbidden, keys, forbidden)
        self.assertFalse(report["runtime_semantics_added"])

    def test_frozen_layers_are_untouched(self) -> None:
        import subprocess

        result = subprocess.run(
            ["git", "status", "--short", "--",
             "src/hsr_battle_agent/reference_sandbox",
             "src/hsr_battle_agent/reference_battle_planner",
             "src/hsr_battle_agent/battle_sandbox",
             "src/hsr_battle_agent/content_support",
             "src/hsr_battle_agent/content_planner"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(REPOSITORY_ROOT),
        )
        self.assertEqual(result.stdout.strip(), "")

    def test_public_m14_m15_apis_are_imported_by_name(self) -> None:
        for name in (
            "admit_content_for_planner", "ContentPlannerAdmissionRequest",
            "NON_EFFECT_FIELDS", "ADMISSION_OUTCOMES",
        ):
            self.assertIn(name, SOURCE, name)


if __name__ == "__main__":
    unittest.main()
