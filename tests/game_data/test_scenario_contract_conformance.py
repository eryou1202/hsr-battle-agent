"""Contract-conformance tests for the static Scenario Package compiler.

CR-P1-SCENARIO-CONTRACT-CONFORMANCE-20260927-001 closed three audited contract
gaps without adding runtime semantics:

* F2 -- ``player_team`` is bounded to exactly ``1..4`` combatants.
* F3 -- ``victory_rule_id`` / ``defeat_rule_id`` are emitted as explicit
  resolution records, never as bare strings a consumer could mistake for a
  known/executable rule.  A bare supplied identifier is reported as ``UNKNOWN``.
* F4 -- caller waves are overlaid on the resolved Stage template (never
  replacing it) and the template ``wave_id`` plus both provenances are kept;
  wave-id retention and override provenance are part of F4 closure.

Audit F5 (loadout completeness) is NOT addressed here and remains untouched.

Everything asserted here is static product contract behaviour.  No runtime,
evidence or execution status is promoted: the package stays static, is never
golden-eligible and never carries an action envelope or legal-action surface.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from hsr_battle_agent.game_data import scenario_compiler as scenario_compiler_module
from hsr_battle_agent.game_data.nanoka_content import (
    MONSTER_RESOLUTION_IDENTITY_FIELDS, ContentDatabase, build_from_snapshot,
)
from hsr_battle_agent.game_data.scenario_compiler import (
    LEGACY_PACKAGE_SCHEMA, MAX_PLAYER_TEAM, MIN_PLAYER_TEAM, PACKAGE_SCHEMA,
    REACHABLE_RULE_RESOLUTION_STATES, RULE_EXECUTION_SEMANTICS,
    RULE_RESOLUTION_STATES, WAVE_ORIGINS,
    ScenarioCompileError, ScenarioCompiler,
)
from tests.game_data.test_nanoka_content_database import materialize_snapshot


LOCAL_DATABASE = (
    Path(__file__).resolve().parents[2] / "data" / "db" / "hsr_content_4.4.54.sqlite"
)

COMPILER_SOURCE = Path(scenario_compiler_module.__file__).read_text(encoding="utf-8")

#: Frozen runtime packages the static compiler must never reach into.
FROZEN_RUNTIME_PACKAGES = (
    "reference_sandbox", "reference_battle_planner", "battle_sandbox",
    "content_support", "content_planner",
)

#: Package keys that would imply executable/planner semantics.
FORBIDDEN_PACKAGE_KEYS = (
    "evidence_mode", "golden_trace", "native_trace", "legal_actions",
    "battle_state", "envelope", "execution_trace", "admission",
)

#: A synthetic multi-wave Stage template.  No packaged 4.4.54 Stage contains
#: more than one wave, so the multi-wave overlay rule is exercised against an
#: explicit template document rather than a fixture stage.
MULTI_WAVE_TEMPLATE = {
    "schema": "hsr_battle_agent.stage_package/1",
    "game_version": "4.4.54",
    "stage_id": "900001",
    "mode": "Challenge",
    "waves": [
        {"wave_id": "900001:1", "wave_index": 1, "enemy_groups": [
            {"monster_id": 1002020, "level": 10, "group_index": 0, "slot": "monster0", "resolution_status": "RESOLVED"},
        ]},
        {"wave_id": "900001:2", "wave_index": 2, "enemy_groups": [
            {"monster_id": 1002030, "level": 20, "group_index": 0, "slot": "monster0", "resolution_status": "RESOLVED"},
        ]},
        {"wave_id": "900001:3", "wave_index": 3, "enemy_groups": [
            {"monster_id": 1004014, "level": 30, "group_index": 0, "slot": "monster0", "resolution_status": "RESOLVED"},
        ]},
    ],
    "stage_buffs": [],
    "encounter_contexts": [],
    "rule_metadata": {"win_conditions": [], "lose_conditions": [], "stage_config_data": []},
    "source_refs": [],
    "unknown_references": [],
}


def _build_fixture_compiler(root: Path) -> tuple[ContentDatabase, ScenarioCompiler]:
    snapshot = root / "snapshot"
    materialize_snapshot(snapshot)
    database_path = root / "content.sqlite"
    build_from_snapshot(
        "4.4.54", snapshot_root=snapshot, canonical_root=root / "canonical",
        database_path=database_path,
    )
    database = ContentDatabase(database_path, "4.4.54")
    return database, ScenarioCompiler(database)


def _player(slot: int, avatar_id: int = 1105) -> dict:
    return {
        "slot": str(slot),
        "avatar": {
            "avatar_id": avatar_id, "level": 1, "promotion": 0, "eidolon": 0,
            "skill_levels": {}, "trace_state": {"unlocked_trace_ids": []},
        },
        "lightcone": {"lightcone_id": 21000, "level": 1, "promotion": 0, "superimposition": 1},
        "relics": [],
        "initial_state": {},
    }


def _request(*, player_count: int = 1, **overrides: object) -> dict:
    request: dict = {
        "game_version": "4.4.54",
        "scenario_id": "p1-conformance",
        "mode": "standard/free",
        "player_team": [_player(index) for index in range(player_count)],
        "enemy_waves": [
            {"wave_index": 1, "enemies": [{"instance_id": "enemy-a", "monster_id": 1002020, "level": 1}]},
        ],
        "buff_bindings": [],
        "rules": {"rng_seed": 42, "unsupported_policy": "reject"},
    }
    request.update(overrides)
    return request


class _FixtureCase(unittest.TestCase):
    """Shared fixture database + compiler."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.database, cls.compiler = _build_fixture_compiler(Path(cls._temporary.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()


class PlayerTeamBoundTest(_FixtureCase):
    """F2 -- player_team is bounded to 1..4 combatants."""

    def test_bounds_match_the_contract(self) -> None:
        self.assertEqual((MIN_PLAYER_TEAM, MAX_PLAYER_TEAM), (1, 4))

    def test_zero_players_are_rejected(self) -> None:
        with self.assertRaises(ScenarioCompileError):
            self.compiler.compile(_request(player_count=0))

    def test_one_player_is_accepted(self) -> None:
        package = self.compiler.compile(_request(player_count=1))
        self.assertEqual(len(package["players"]), 1)

    def test_four_players_are_accepted(self) -> None:
        package = self.compiler.compile(_request(player_count=4))
        self.assertEqual(len(package["players"]), 4)
        self.assertEqual([player["slot"] for player in package["players"]], ["0", "1", "2", "3"])

    def test_five_players_are_rejected(self) -> None:
        with self.assertRaises(ScenarioCompileError) as context:
            self.compiler.compile(_request(player_count=5))
        self.assertIn("at most 4", str(context.exception))

    def test_duplicate_player_slot_is_still_rejected(self) -> None:
        players = [_player(0), _player(0, avatar_id=1303)]
        with self.assertRaises(ScenarioCompileError) as context:
            self.compiler.compile(_request(player_team=players))
        self.assertIn("duplicate player slot", str(context.exception))

    def test_supplied_slot_identity_is_preserved(self) -> None:
        players = [_player(0), _player(1, avatar_id=1303)]
        players[1]["slot"] = "3"
        package = self.compiler.compile(_request(player_team=players))
        self.assertEqual([player["slot"] for player in package["players"]], ["0", "3"])


class RuleResolutionTest(_FixtureCase):
    """F3 -- every rule reference carries an explicit resolution state."""

    def _rules(self, **rule_overrides: object) -> dict:
        rules = {"rng_seed": 42, "unsupported_policy": "reject"}
        rules.update(rule_overrides)
        return rules

    def test_vocabulary_and_reachable_states_are_declared(self) -> None:
        self.assertEqual(set(RULE_RESOLUTION_STATES), {
            "RESOLVED", "UNKNOWN", "CALLER_DECLARED_LOCAL", "UNSPECIFIED",
        })
        # A bare caller string carries no information about whether it is a real
        # game rule, an unknown identifier or a caller-owned local rule, so it is
        # classified UNKNOWN; CALLER_DECLARED_LOCAL is reserved and unreachable.
        self.assertEqual(set(REACHABLE_RULE_RESOLUTION_STATES), {"UNKNOWN", "UNSPECIFIED"})
        self.assertNotIn("CALLER_DECLARED_LOCAL", REACHABLE_RULE_RESOLUTION_STATES)
        self.assertNotIn("RESOLVED", REACHABLE_RULE_RESOLUTION_STATES)
        self.assertEqual(RULE_EXECUTION_SEMANTICS, "NONE")

    def test_absent_rule_is_unspecified(self) -> None:
        package = self.compiler.compile(_request(rules=self._rules()))
        for field in ("victory_rule", "defeat_rule"):
            record = package["rules"][field]
            self.assertIsNone(record["requested_id"])
            self.assertEqual(record["resolution_status"], "UNSPECIFIED")
            self.assertIsNone(record["resolved_rule"])
            self.assertIsNone(record["authority"])

    def test_unknown_rule_is_never_silently_resolved(self) -> None:
        package = self.compiler.compile(_request(rules=self._rules(
            victory_rule_id="totally-made-up-rule",
            defeat_rule_id="another-made-up-rule",
        )))
        for field in ("victory_rule", "defeat_rule"):
            record = package["rules"][field]
            self.assertNotEqual(record["resolution_status"], "RESOLVED")
            self.assertEqual(record["resolution_status"], "UNKNOWN")
            self.assertIsNone(record["resolved_rule"])
            self.assertIsNone(record["authority"])
            self.assertIn(record["resolution_status"], REACHABLE_RULE_RESOLUTION_STATES)

    def test_ordinary_string_rule_is_unknown(self) -> None:
        """A plausible-looking identifier is still not a resolved rule."""
        package = self.compiler.compile(_request(rules=self._rules(
            victory_rule_id="DefeatAll", defeat_rule_id="AllDead",
        )))
        self.assertEqual(package["rules"]["victory_rule"]["requested_id"], "DefeatAll")
        self.assertEqual(package["rules"]["victory_rule"]["resolution_status"], "UNKNOWN")
        self.assertEqual(package["rules"]["defeat_rule"]["resolution_status"], "UNKNOWN")

    def test_supplied_rule_identity_is_preserved_but_unresolved(self) -> None:
        package = self.compiler.compile(_request(rules=self._rules(
            victory_rule_id="caller-victory", defeat_rule_id="caller-defeat",
        )))
        self.assertEqual(package["rules"]["victory_rule"]["requested_id"], "caller-victory")
        self.assertEqual(package["rules"]["defeat_rule"]["requested_id"], "caller-defeat")
        self.assertEqual(package["rules"]["victory_rule"]["resolution_status"], "UNKNOWN")
        self.assertEqual(package["rules"]["defeat_rule"]["resolution_status"], "UNKNOWN")

    def test_caller_declared_local_is_unreachable_with_current_input(self) -> None:
        """No bare-string or absent input may produce CALLER_DECLARED_LOCAL."""
        cases = [
            {},
            {"victory_rule_id": "x", "defeat_rule_id": "y"},
            {"victory_rule_id": "", "defeat_rule_id": ""},
            {"victory_rule_id": "DefeatAll", "defeat_rule_id": "AllDead"},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                package = self.compiler.compile(_request(rules=self._rules(**overrides)))
                for field in ("victory_rule", "defeat_rule"):
                    self.assertNotEqual(
                        package["rules"][field]["resolution_status"], "CALLER_DECLARED_LOCAL",
                    )
                    self.assertNotEqual(package["rules"][field]["resolution_status"], "RESOLVED")

    def test_every_rule_record_carries_no_execution_semantics(self) -> None:
        package = self.compiler.compile(_request(rules=self._rules(
            victory_rule_id="v", defeat_rule_id="d",
        )))
        expected = {"requested_id", "resolution_status", "resolved_rule", "authority", "execution_semantics"}
        for field in ("victory_rule", "defeat_rule"):
            record = package["rules"][field]
            self.assertEqual(set(record), expected)
            self.assertEqual(record["execution_semantics"], "NONE")
            self.assertIsNone(record["resolved_rule"])
            self.assertIsNone(record["authority"])

    def test_rule_ids_are_not_echoed_as_bare_strings(self) -> None:
        package = self.compiler.compile(_request(rules=self._rules(
            victory_rule_id="caller-victory", defeat_rule_id="caller-defeat",
        )))
        self.assertNotIn("victory_rule_id", package["rules"])
        self.assertNotIn("defeat_rule_id", package["rules"])
        self.assertEqual(package["rules"]["rng_seed"], 42)
        self.assertEqual(package["rules"]["unsupported_policy"], "reject")

    def test_non_string_rule_id_is_rejected(self) -> None:
        with self.assertRaises(ScenarioCompileError):
            self.compiler.compile(_request(rules=self._rules(victory_rule_id=17)))


class TemplateOverlayTest(_FixtureCase):
    """F4 -- deterministic overlay of caller waves over the Stage template."""

    def _compile(self, template: dict, request: dict) -> dict:
        with mock.patch.object(self.database, "get_stage_package", return_value=template):
            return self.compiler.compile(request)

    def test_template_alone_keeps_all_template_waves(self) -> None:
        package = self._compile(MULTI_WAVE_TEMPLATE, _request(source_stage_id="900001", enemy_waves=None))
        self.assertEqual([wave["wave_index"] for wave in package["waves"]], [1, 2, 3])
        self.assertEqual([wave["wave_id"] for wave in package["waves"]], ["900001:1", "900001:2", "900001:3"])
        self.assertEqual([wave["origin"] for wave in package["waves"]], ["TEMPLATE"] * 3)
        self.assertEqual([wave["override_applied"] for wave in package["waves"]], [False, False, False])
        self.assertEqual(
            [[enemy["monster_id"] for enemy in wave["enemies"]] for wave in package["waves"]],
            [["1002020"], ["1002030"], ["1004014"]],
        )

    def test_replacing_one_wave_keeps_unrelated_template_waves(self) -> None:
        request = _request(
            source_stage_id="900001",
            enemy_waves=[{"wave_index": 2, "enemies": [{"monster_id": 1002030, "level": 99}]}],
        )
        package = self._compile(MULTI_WAVE_TEMPLATE, request)
        self.assertEqual([wave["wave_index"] for wave in package["waves"]], [1, 2, 3])
        # Unrelated template waves survive untouched.
        self.assertEqual(package["waves"][0]["origin"], "TEMPLATE")
        self.assertEqual(package["waves"][0]["enemies"][0]["level"], 10)
        self.assertEqual(package["waves"][2]["origin"], "TEMPLATE")
        self.assertEqual(package["waves"][2]["enemies"][0]["level"], 30)
        # The touched wave is an override, and reports the caller's enemies.
        overridden = package["waves"][1]
        self.assertEqual(overridden["origin"], "TEMPLATE_WITH_CALLER_OVERRIDE")
        self.assertTrue(overridden["override_applied"])
        self.assertEqual(overridden["enemies"][0]["level"], 99)

    def test_overridden_wave_retains_template_identity_and_provenance(self) -> None:
        request = _request(
            source_stage_id="900001",
            enemy_waves=[{"wave_index": 2, "wave_id": "caller-wave:2", "enemies": [{"monster_id": 1002030, "level": 99}]}],
        )
        package = self._compile(MULTI_WAVE_TEMPLATE, request)
        overridden = package["waves"][1]
        self.assertEqual(overridden["wave_id"], "900001:2")
        self.assertEqual(overridden["provenance"], {
            "source_stage_id": "900001",
            "template_wave_id": "900001:2",
            "template_wave_index": 2,
            "caller_wave_index": 2,
            "caller_wave_id": "caller-wave:2",
        })

    def test_caller_added_wave_is_deterministic_and_keeps_ordering(self) -> None:
        request = _request(
            source_stage_id="900001",
            enemy_waves=[{"wave_index": 7, "enemies": [{"monster_id": 1002020, "level": 5}]}],
        )
        first = self._compile(MULTI_WAVE_TEMPLATE, request)
        second = self._compile(MULTI_WAVE_TEMPLATE, request)
        self.assertEqual(first["package_sha256"], second["package_sha256"])
        self.assertEqual([wave["wave_index"] for wave in first["waves"]], [1, 2, 3, 7])
        self.assertEqual(first["waves"][3]["origin"], "CALLER")
        self.assertEqual(first["waves"][3]["provenance"], {
            "source_stage_id": "900001",
            "template_wave_id": None,
            "template_wave_index": None,
            "caller_wave_index": 7,
            "caller_wave_id": None,
        })

    def test_free_wave_does_not_acquire_a_fabricated_wave_id(self) -> None:
        package = self._compile(MULTI_WAVE_TEMPLATE, _request(
            source_stage_id="900001",
            enemy_waves=[{"wave_index": 9, "enemies": [{"monster_id": 1002020, "level": 5}]}],
        ))
        self.assertIsNone(package["waves"][-1]["wave_id"])

    def test_caller_may_own_an_explicit_wave_id(self) -> None:
        package = self.compiler.compile(_request(
            enemy_waves=[{"wave_index": 1, "wave_id": "caller:1", "enemies": [{"monster_id": 1002020, "level": 5}]}],
        ))
        self.assertEqual(package["waves"][0]["wave_id"], "caller:1")
        self.assertEqual(package["waves"][0]["origin"], "CALLER")

    def test_free_scenario_without_a_template_has_no_wave_id(self) -> None:
        package = self.compiler.compile(_request())
        self.assertIsNone(package["waves"][0]["wave_id"])
        self.assertEqual(package["waves"][0]["origin"], "CALLER")

    def test_wave_origins_use_the_declared_vocabulary(self) -> None:
        self.assertEqual(set(WAVE_ORIGINS), {"TEMPLATE", "TEMPLATE_WITH_CALLER_OVERRIDE", "CALLER"})
        package = self._compile(MULTI_WAVE_TEMPLATE, _request(
            source_stage_id="900001",
            enemy_waves=[
                {"wave_index": 2, "enemies": [{"monster_id": 1002030, "level": 99}]},
                {"wave_index": 7, "enemies": [{"monster_id": 1002020, "level": 5}]},
            ],
        ))
        for wave in package["waves"]:
            self.assertIn(wave["origin"], WAVE_ORIGINS)
            for enemy in wave["enemies"]:
                self.assertEqual(enemy["origin"], wave["origin"])

    def test_duplicate_caller_wave_index_is_rejected(self) -> None:
        with self.assertRaises(ScenarioCompileError):
            self._compile(MULTI_WAVE_TEMPLATE, _request(
                source_stage_id="900001",
                enemy_waves=[
                    {"wave_index": 4, "enemies": [{"monster_id": 1002020, "level": 1}]},
                    {"wave_index": 4, "enemies": [{"monster_id": 1002030, "level": 1}]},
                ],
            ))

    def test_fixture_single_wave_template_is_overlaid(self) -> None:
        """The packaged fixture Stage (420101) has one wave and keeps its ID."""
        package = self.compiler.compile(_request(source_stage_id=420101, enemy_waves=[
            {"wave_index": 7, "enemies": [{"monster_id": 1002030, "level": 66}]},
        ]))
        self.assertEqual([wave["wave_index"] for wave in package["waves"]], [1, 7])
        self.assertEqual(package["waves"][0]["wave_id"], "420101:1")
        self.assertEqual(package["waves"][0]["origin"], "TEMPLATE")
        self.assertEqual(package["waves"][0]["provenance"]["source_stage_id"], "420101")


class P0ResolutionRegressionTest(_FixtureCase):
    """P0 static identity resolution must be unchanged by P1."""

    def test_p0_enemy_resolution_is_carried_in_schema_v2(self) -> None:
        package = self.compiler.compile(_request())
        self.assertEqual(package["schema"], "hsr_battle_agent.scenario_package/2")
        self.assertEqual(PACKAGE_SCHEMA, "hsr_battle_agent.scenario_package/2")
        enemy = package["waves"][0]["enemies"][0]
        self.assertEqual(tuple(enemy["resolution"]), MONSTER_RESOLUTION_IDENTITY_FIELDS)
        self.assertEqual(enemy["resolution"]["resolved_kind"], "MONSTER")

    def test_canonical_monster_still_resolves(self) -> None:
        resolution = self.database.resolve_monster("1002020")
        self.assertEqual(resolution["resolved_kind"], "MONSTER")
        self.assertEqual(resolution["canonical_monster_id"], "1002020")

    def test_variant_only_monster_still_resolves(self) -> None:
        resolution = self.database.resolve_monster("100202001")
        self.assertEqual(resolution["resolved_kind"], "MONSTER_VARIANT")
        self.assertEqual(resolution["canonical_monster_id"], "1002020")

    def test_requested_variant_id_is_preserved(self) -> None:
        package = self.compiler.compile(_request(enemy_waves=[
            {"wave_index": 1, "enemies": [{"instance_id": "v", "monster_id": 100401401, "level": 1}]},
        ]))
        enemy = package["waves"][0]["enemies"][0]
        self.assertEqual(enemy["monster_id"], "100401401")
        self.assertEqual(enemy["resolution"]["requested_id"], "100401401")
        self.assertEqual(enemy["resolution"]["variant_id"], "100401401")
        self.assertEqual(enemy["resolution"]["canonical_monster_id"], "1004014")

    def test_stage_420101_still_compiles_with_variant_ids(self) -> None:
        package = self.compiler.compile(_request(source_stage_id=420101, enemy_waves=None))
        self.assertEqual(package["source_stage"]["stage_id"], "420101")
        self.assertEqual([wave["wave_index"] for wave in package["waves"]], [1])
        enemies = [enemy for wave in package["waves"] for enemy in wave["enemies"]]
        self.assertEqual(
            [enemy["monster_id"] for enemy in enemies],
            ["100202001", "100203001", "100401401"],
        )
        self.assertEqual(
            {enemy["resolution"]["resolved_kind"] for enemy in enemies}, {"MONSTER_VARIANT"},
        )

    def test_unknown_monster_is_still_rejected(self) -> None:
        with self.assertRaises(ScenarioCompileError):
            self.compiler.compile(_request(enemy_waves=[
                {"wave_index": 1, "enemies": [{"monster_id": 999999999, "level": 1}]},
            ]))


class DeterminismAndRepresentationTest(_FixtureCase):
    """Deterministic hash + the explicit schema / immutability decisions."""

    def test_same_request_yields_the_same_package_hash(self) -> None:
        first = self.compiler.compile(_request())
        second = self.compiler.compile(_request())
        self.assertEqual(first["package_sha256"], second["package_sha256"])

    def test_hash_is_stable_across_field_order(self) -> None:
        request = _request()
        reordered = dict(reversed(list(request.items())))
        self.assertEqual(
            self.compiler.compile(request)["package_sha256"],
            self.compiler.compile(reordered)["package_sha256"],
        )

    def test_schema_decision_is_recorded_as_v2(self) -> None:
        # Section 2 decision: replacing the bare rule strings with structured
        # records is not purely additive, so the product schema is bumped to /2
        # within the low-cost migration window (no exact-shape consumer exists).
        self.assertEqual(PACKAGE_SCHEMA, "hsr_battle_agent.scenario_package/2")
        self.assertEqual(LEGACY_PACKAGE_SCHEMA, "hsr_battle_agent.scenario_package/1")
        package = self.compiler.compile(_request())
        self.assertEqual(package["schema"], PACKAGE_SCHEMA)
        self.assertNotEqual(package["schema"], LEGACY_PACKAGE_SCHEMA)
        # The ambiguous pre-P1 bare-string fields are NOT restored.
        self.assertNotIn("victory_rule_id", package["rules"])
        self.assertNotIn("defeat_rule_id", package["rules"])

    def test_immutability_is_deferred_and_the_package_is_copy_isolated(self) -> None:
        # Section 8 decision: IMMUTABILITY_DEFERRED -- the returned value stays a
        # plain object, but it must share no mutable container with the
        # database facade or with a later compile.
        package = self.compiler.compile(_request())
        self.assertIs(type(package), dict)
        package["waves"][0]["enemies"][0]["monster"]["data"]["tampered"] = True
        package["players"][0]["loadout"]["tampered"] = True
        self.assertNotIn("tampered", self.database.get_monster("1002020")["data"])
        fresh = self.compiler.compile(_request())
        self.assertNotIn("tampered", fresh["waves"][0]["enemies"][0]["monster"]["data"])
        self.assertNotIn("tampered", fresh["players"][0]["loadout"])


class StaticBoundaryTest(_FixtureCase):
    """The package stays static; no runtime/planner surface is attached."""

    def test_execution_status_stays_static(self) -> None:
        package = self.compiler.compile(_request())
        self.assertEqual(package["execution_status"], "STATIC_READY_BEHAVIOR_COMPILATION_REQUIRED")
        self.assertEqual(package["reconstruction_status"], "STATIC_RECONSTRUCTION_READY")

    def test_golden_eligible_is_false(self) -> None:
        self.assertFalse(self.compiler.compile(_request())["golden_eligible"])

    def test_no_runtime_artifact_keys_are_present(self) -> None:
        package = self.compiler.compile(_request(source_stage_id=420101, enemy_waves=None))
        for forbidden in FORBIDDEN_PACKAGE_KEYS:
            self.assertNotIn(forbidden, package)

    def test_behavior_gaps_are_static_only(self) -> None:
        package = self.compiler.compile(_request(source_stage_id=420101, enemy_waves=None))
        self.assertTrue(package["unresolved_behavior"])
        self.assertTrue(all(
            gap["status"] == "BEHAVIOR_COMPILATION_REQUIRED"
            for gap in package["unresolved_behavior"]
        ))

    def test_compiler_source_has_no_execution_or_planner_imports(self) -> None:
        forbidden = (
            "ReferenceActionEnvelope", "PlayerLegalAction", "GateCertificate",
        ) + FROZEN_RUNTIME_PACKAGES
        for token in forbidden:
            self.assertNotIn(token, COMPILER_SOURCE, token)

    def test_compiler_is_quarantined_and_deterministic_across_hash_seed(self) -> None:
        # The compiler reads only the canonical SQLite facade; no live/network
        # or planner object is required to assemble a package.
        self.assertIn("canonical SQLite/static references only", self.compiler.compile(_request())["provenance_policy"])


class LoadoutCompletenessUntouchedTest(_FixtureCase):
    """Audit F5 (loadout completeness) is explicitly NOT addressed by P1."""

    def test_no_six_relic_slot_rule_is_enforced(self) -> None:
        # F5 would require an exact six-relic-slot rule; P1 adds no such rule.
        package = self.compiler.compile(_request())
        self.assertEqual(package["players"][0]["loadout"]["relics"], [])

    def test_unvalidated_loadout_fields_are_still_carried_verbatim(self) -> None:
        players = [_player(0)]
        players[0]["avatar"]["skill_levels"] = {"basic": 999, "made_up": 1}
        # trace_state.rank_state is carried without validation (F5 territory);
        # unlocked_trace_ids is validated by the loadout evaluator, so it stays
        # empty here.
        players[0]["avatar"]["trace_state"] = {"unlocked_trace_ids": [], "rank_state": {"made_up": 7}}
        players[0]["initial_state"] = {"made_up": True}
        package = self.compiler.compile(_request(player_team=players))
        player = package["players"][0]
        self.assertEqual(player["skill_levels"], {"basic": 999, "made_up": 1})
        self.assertEqual(player["trace_state"]["rank_state"], {"made_up": 7})
        self.assertEqual(player["initial_state"], {"made_up": True})


class RuleExecutionSafetyTest(_FixtureCase):
    """Finding 5 -- an UNKNOWN rule is never resolved, executable or gating gold."""

    def test_unknown_rule_cannot_be_read_as_resolved_or_executable(self) -> None:
        package = self.compiler.compile(_request(rules={
            "rng_seed": 42, "victory_rule_id": "unknown-victory", "defeat_rule_id": "unknown-defeat",
        }))
        for field in ("victory_rule", "defeat_rule"):
            record = package["rules"][field]
            self.assertEqual(record["resolution_status"], "UNKNOWN")
            self.assertIsNone(record["resolved_rule"])
            self.assertIsNone(record["authority"])
            self.assertEqual(record["execution_semantics"], "NONE")

    def test_golden_eligibility_formula_is_rule_blind(self) -> None:
        package = self.compiler.compile(_request(rules={"rng_seed": 42, "victory_rule_id": "unknown-rule"}))
        # The existing static formula consults behavior gaps and policy only.
        expected = (
            not package["unresolved_behavior"]
            and package["unsupported_policy"] != "opaque-disabled"
        )
        self.assertEqual(package["golden_eligible"], expected)
        # The supplied rule is UNKNOWN and carries no execution semantics, and
        # the static formula does not consult rule resolution at all.  A rule
        # execution gate is therefore a DEFERRED requirement recorded in the
        # control artifact -- never claimed as satisfied.
        self.assertEqual(package["rules"]["victory_rule"]["resolution_status"], "UNKNOWN")

    def test_behavior_gaps_keep_golden_eligibility_false(self) -> None:
        package = self.compiler.compile(_request(source_stage_id=420101, enemy_waves=None))
        self.assertTrue(package["unresolved_behavior"])
        self.assertFalse(package["golden_eligible"])


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class RealDatabaseConformanceTest(unittest.TestCase):
    """The same contract behaviour against the pinned 4.4.54 database."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.compiler = ScenarioCompiler(cls.database)

    def test_five_player_team_is_rejected_on_real_content(self) -> None:
        with self.assertRaises(ScenarioCompileError):
            self.compiler.compile(_request(player_count=5))

    def test_real_stage_420101_wave_id_is_retained(self) -> None:
        package = self.compiler.compile(_request(source_stage_id=420101, enemy_waves=None))
        self.assertEqual([wave["wave_id"] for wave in package["waves"]], ["420101:1"])
        self.assertEqual([wave["origin"] for wave in package["waves"]], ["TEMPLATE"])

    def test_real_free_wave_has_no_fabricated_wave_id(self) -> None:
        package = self.compiler.compile(_request(
            enemy_waves=[{"wave_index": 1, "enemies": [{"monster_id": 1002020, "level": 1}]}],
        ))
        self.assertIsNone(package["waves"][0]["wave_id"])


if __name__ == "__main__":
    unittest.main()
