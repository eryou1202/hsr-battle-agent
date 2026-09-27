"""Static Monster resolution-parity tests.

CR-P0-SCENARIO-ENTITY-RESOLUTION-PARITY-20260927-001 (audited defect F1).

The offline fixture reproduces the audited defect exactly: Stage ``420101``
places MonsterVariant IDs (``100202001``, ``100203001``, ``100401401``) whose
parent Monster records (``1002020``, ``1002030``, ``1004014``) are also
present.  ``get_stage_package`` recognised those placements as ``RESOLVED``
while the static Scenario compiler rejected them, because the two paths used
different static identity rules.

Both paths now consume ``ContentDatabase.resolve_monster`` only.

Everything asserted here is static identity resolution.  A resolved Monster
variant is still not an executable Monster AI or skill, and no runtime,
evidence or execution status is promoted by these tests.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from hsr_battle_agent.game_data.nanoka_content import (
    MONSTER_RESOLUTION_IDENTITY_FIELDS,
    MONSTER_RESOLUTION_KINDS,
    ContentDatabase,
    build_from_snapshot,
)
from hsr_battle_agent.game_data.scenario_compiler import (
    ScenarioCompileError,
    ScenarioCompiler,
)
from tests.game_data.test_nanoka_content_database import materialize_snapshot


#: Entity envelope keys every resolved Canonical record must carry.
ENTITY_ENVELOPE_FIELDS = {
    "game_version", "entity_id", "original_game_id", "game_id_status",
    "confidence", "reconstruction_status", "data", "provenance",
    "canonical_sha256",
}

#: Frozen runtime packages that must never depend on the static resolver.
FROZEN_RUNTIME_PACKAGES = (
    "reference_sandbox", "reference_battle_planner", "battle_sandbox",
    "content_support", "content_planner",
)

#: Audited 4.4.54 real-database denominators.
EXPECTED_STAGE_PLACEMENTS = 6717
EXPECTED_VARIANT_ONLY_PLACEMENTS = 823
EXPECTED_VARIANT_ONLY_PLACEMENT_IDS = 188
EXPECTED_MONSTER_VARIANTS = 2648
#: Stages sampled when comparing the Stage Package verdict to the resolver.
REAL_PARITY_STAGE_SAMPLE = 40

LOCAL_DATABASE = (
    Path(__file__).resolve().parents[2] / "data" / "db" / "hsr_content_4.4.54.sqlite"
)


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


def _request(**overrides: object) -> dict:
    """A minimal valid free-scenario request with one canonical Monster."""
    request: dict = {
        "game_version": "4.4.54", "scenario_id": "resolution-parity",
        "mode": "standard/free",
        "player_team": [{
            "slot": "0",
            "avatar": {"avatar_id": 1105, "level": 1, "promotion": 0, "eidolon": 0,
                       "trace_state": {"unlocked_trace_ids": []}},
            "relics": [],
        }],
        "enemy_waves": [{"wave_index": 1, "enemies": [
            {"instance_id": "enemy-a", "monster_id": 1002020, "level": 1},
        ]}],
        "buff_bindings": [],
        "rules": {"rng_seed": 42},
    }
    request.update(overrides)
    return request


class ResolutionParityTest(unittest.TestCase):
    """Offline A-H parity proofs against the shared fixture database."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.database, cls.compiler = _build_fixture_compiler(Path(cls._temporary.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_a_canonical_monster_id_still_resolves(self) -> None:
        resolution = self.database.resolve_monster("1002020")
        self.assertIsNotNone(resolution)
        self.assertEqual(resolution["requested_id"], "1002020")
        self.assertEqual(resolution["resolved_kind"], "MONSTER")
        self.assertEqual(resolution["canonical_monster_id"], "1002020")
        self.assertIsNone(resolution["variant_id"])
        self.assertEqual(set(resolution["entity"]), ENTITY_ENVELOPE_FIELDS)
        self.assertEqual(resolution["entity"]["entity_id"], "1002020")

        package = self.compiler.compile(_request())
        enemy = package["waves"][0]["enemies"][0]
        self.assertEqual(enemy["monster_id"], "1002020")
        self.assertEqual(enemy["resolution"]["resolved_kind"], "MONSTER")
        self.assertEqual(enemy["monster"]["entity_id"], "1002020")

    def test_b_variant_only_ids_resolve_exactly_as_the_stage_package_does(self) -> None:
        stage = self.database.get_stage_package(420101)
        placements = [group for wave in stage["waves"] for group in wave["enemy_groups"]]
        self.assertTrue(placements)

        variant_only = 0
        for group in placements:
            placement_id = str(group["monster_id"])
            resolved = self.database.resolve_monster(placement_id) is not None
            expected = "RESOLVED" if resolved else "UNKNOWN"
            self.assertEqual(group["resolution_status"], expected, placement_id)
            self.assertTrue(resolved, placement_id)
            if self.database.get_monster(placement_id) is None:
                variant_only += 1
        # The fixture genuinely reproduces F1: every placement is variant-only.
        self.assertEqual(variant_only, len(placements))

        resolution = self.database.resolve_monster("100202001")
        self.assertEqual(resolution["resolved_kind"], "MONSTER_VARIANT")
        self.assertEqual(resolution["canonical_monster_id"], "1002020")
        self.assertEqual(resolution["variant_id"], "100202001")
        self.assertEqual(set(resolution["entity"]), ENTITY_ENVELOPE_FIELDS)

    def test_c_requested_variant_identity_is_never_rewritten(self) -> None:
        package = self.compiler.compile(_request(enemy_waves=[
            {"wave_index": 1, "enemies": [
                {"instance_id": "svarog", "monster_id": 100401401, "level": 66},
            ]},
        ]))
        enemy = package["waves"][0]["enemies"][0]
        # The caller ID is preserved verbatim, not silently replaced by the parent.
        self.assertEqual(enemy["monster_id"], "100401401")
        self.assertEqual(enemy["resolution"]["requested_id"], "100401401")
        self.assertEqual(enemy["resolution"]["variant_id"], "100401401")
        self.assertEqual(enemy["resolution"]["canonical_monster_id"], "1004014")
        # The embedded record is the variant entity, and the canonical parent is
        # reported as identity only: it is never substituted for the variant.
        self.assertEqual(enemy["monster"]["entity_id"], "100401401")
        self.assertNotEqual(enemy["monster"]["entity_id"], enemy["resolution"]["canonical_monster_id"])
        parent = self.database.get_monster("1004014")
        self.assertEqual(parent["entity_id"], "1004014")

    def test_d_unknown_monster_and_variant_ids_are_still_rejected(self) -> None:
        for unknown in ("999999999", 100202002999, "not-a-monster"):
            with self.subTest(unknown=unknown):
                self.assertIsNone(self.database.resolve_monster(unknown))
                with self.assertRaises(ScenarioCompileError):
                    self.compiler.compile(_request(enemy_waves=[
                        {"wave_index": 1, "enemies": [{"monster_id": unknown, "level": 1}]},
                    ]))
        # The same rejection applies when a Stage template is present.
        with self.assertRaises(ScenarioCompileError):
            self.compiler.compile(_request(
                source_stage_id=420101,
                enemy_waves=[{"wave_index": 1, "enemies": [{"monster_id": "999999999", "level": 1}]}],
            ))

    def test_e_cross_version_behaviour_is_unchanged(self) -> None:
        with self.assertRaises(ScenarioCompileError):
            self.compiler.compile(_request(game_version="4.4.55"))
        # The resolver is database-scoped: a 4.4.55-scoped facade offers no
        # fallback into the 4.4.54 content.
        wrong_version = ContentDatabase(self.database.database_path, "4.4.55")
        self.assertIsNone(wrong_version.resolve_monster("100202001"))
        self.assertIsNone(wrong_version.resolve_monster("1002020"))

    def test_f_free_scenario_without_a_stage_template_still_works(self) -> None:
        request = _request(enemy_waves=[
            {"wave_index": 2, "enemies": [{"instance_id": "parent", "monster_id": 1002030, "level": 33}]},
            {"wave_index": 1, "enemies": [{"instance_id": "variant", "monster_id": 100203001, "level": 44}]},
        ])
        first = self.compiler.compile(request)
        second = self.compiler.compile(request)
        self.assertEqual(first["package_sha256"], second["package_sha256"])
        self.assertIsNone(first["source_stage"])
        self.assertEqual([wave["wave_index"] for wave in first["waves"]], [1, 2])
        self.assertEqual(
            {enemy["resolution"]["resolved_kind"] for wave in first["waves"] for enemy in wave["enemies"]},
            {"MONSTER", "MONSTER_VARIANT"},
        )

    def test_g_stage_420101_now_compiles_statically(self) -> None:
        package = self.compiler.compile(_request(source_stage_id=420101, enemy_waves=None))
        self.assertEqual(package["source_stage"]["stage_id"], "420101")
        enemies = [enemy for wave in package["waves"] for enemy in wave["enemies"]]
        self.assertEqual(
            [enemy["monster_id"] for enemy in enemies],
            ["100202001", "100203001", "100401401"],
        )
        self.assertEqual(
            {enemy["resolution"]["resolved_kind"] for enemy in enemies},
            {"MONSTER_VARIANT"},
        )
        self.assertEqual(
            [enemy["resolution"]["canonical_monster_id"] for enemy in enemies],
            ["1002020", "1002030", "1004014"],
        )
        self.assertIn("3110001", [binding["buff_id"] for binding in package["buff_bindings"]])
        self.assertEqual(
            package["package_sha256"],
            self.compiler.compile(_request(source_stage_id=420101, enemy_waves=None))["package_sha256"],
        )

    def test_h_no_runtime_or_evidence_status_is_promoted(self) -> None:
        package = self.compiler.compile(_request(source_stage_id=420101, enemy_waves=None))
        self.assertEqual(package["execution_status"], "STATIC_READY_BEHAVIOR_COMPILATION_REQUIRED")
        self.assertFalse(package["golden_eligible"])
        self.assertEqual(package["reconstruction_status"], "STATIC_RECONSTRUCTION_READY")
        self.assertTrue(package["unresolved_behavior"])
        self.assertTrue(all(
            gap["status"] == "BEHAVIOR_COMPILATION_REQUIRED"
            for gap in package["unresolved_behavior"]
        ))
        for forbidden in (
            "evidence_mode", "golden_trace", "native_trace", "legal_actions",
            "battle_state", "envelope", "execution_trace",
        ):
            self.assertNotIn(forbidden, package)

        for wave in package["waves"]:
            for enemy in wave["enemies"]:
                self.assertEqual(tuple(enemy["resolution"]), MONSTER_RESOLUTION_IDENTITY_FIELDS)
                self.assertIn(enemy["resolution"]["resolved_kind"], MONSTER_RESOLUTION_KINDS)
                self.assertEqual(set(enemy["monster"]), ENTITY_ENVELOPE_FIELDS)
                # A variant entity record is a static Canonical record, not a
                # behavior, AI or execution artifact.
                self.assertIn(
                    enemy["monster"]["reconstruction_status"],
                    ("RECONSTRUCTION_READY", "PARTIAL"),
                )

    def test_frozen_runtime_layers_do_not_depend_on_the_resolver(self) -> None:
        source_root = Path(__file__).resolve().parents[2] / "src" / "hsr_battle_agent"
        offenders: list[str] = []
        for package in FROZEN_RUNTIME_PACKAGES:
            for path in sorted((source_root / package).rglob("*.py")):
                if "resolve_monster" in path.read_text(encoding="utf-8"):
                    offenders.append(str(path.relative_to(source_root)))
        self.assertEqual(offenders, [])


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class RealStagePlacementParityTest(unittest.TestCase):
    """Mechanical parity sweep over the pinned 4.4.54 stage placements."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.compiler = ScenarioCompiler(cls.database)

    @classmethod
    def _placements(cls) -> list[dict]:
        connection = sqlite3.connect(LOCAL_DATABASE)
        try:
            return [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload_json FROM wave_monsters WHERE game_version='4.4.54'"
                )
            ]
        finally:
            connection.close()

    @classmethod
    def _variants(cls) -> list[tuple[str, dict]]:
        connection = sqlite3.connect(LOCAL_DATABASE)
        try:
            return [
                (row[0], json.loads(row[1]))
                for row in connection.execute(
                    "SELECT entity_id, payload_json FROM monster_variants WHERE game_version='4.4.54'"
                )
            ]
        finally:
            connection.close()

    @classmethod
    def _canonical_monster_ids(cls) -> set[str]:
        connection = sqlite3.connect(LOCAL_DATABASE)
        try:
            return {
                row[0]
                for row in connection.execute(
                    "SELECT entity_id FROM monsters WHERE game_version='4.4.54'"
                )
            }
        finally:
            connection.close()

    def test_every_known_placement_resolves_with_the_shared_rule(self) -> None:
        placements = self._placements()
        self.assertEqual(len(placements), EXPECTED_STAGE_PLACEMENTS)
        canonical_ids = self._canonical_monster_ids()

        # Exercise the resolver once per distinct placement identity, then prove
        # the sweep covers every one of the known placements.
        placement_ids = {str(placement["monster_id"]) for placement in placements}
        unresolved = sorted(
            placement_id for placement_id in placement_ids
            if self.database.resolve_monster(placement_id) is None
        )
        self.assertEqual(unresolved, [])

        variant_only_ids = placement_ids - canonical_ids
        self.assertEqual(len(variant_only_ids), EXPECTED_VARIANT_ONLY_PLACEMENT_IDS)
        self.assertEqual(
            sum(
                1 for placement in placements
                if str(placement["monster_id"]) in variant_only_ids
            ),
            EXPECTED_VARIANT_ONLY_PLACEMENTS,
        )

        # Every variant proves its parent through the static relationship, so
        # no placement depends on a guessed parent.
        variants = self._variants()
        self.assertEqual(len(variants), EXPECTED_MONSTER_VARIANTS)
        unproven = sorted(
            variant_id for variant_id, payload in variants
            if str(payload.get("monster_id")) not in canonical_ids
        )
        self.assertEqual(unproven, [])

    def test_stage_package_and_scenario_resolver_agree_on_variant_bearing_stages(self) -> None:
        placements = self._placements()
        canonical_ids = self._canonical_monster_ids()
        variant_only_ids = {
            str(placement["monster_id"]) for placement in placements
            if str(placement["monster_id"]) not in canonical_ids
        }
        stage_ids = sorted(
            {
                str(placement["stage_id"]) for placement in placements
                if str(placement["monster_id"]) in variant_only_ids
            },
            key=lambda value: int(value),
        )[:REAL_PARITY_STAGE_SAMPLE]
        self.assertTrue(stage_ids)

        compared = 0
        for stage_id in stage_ids:
            package = self.database.get_stage_package(stage_id)
            self.assertIsNotNone(package, stage_id)
            for wave in package["waves"]:
                for group in wave["enemy_groups"]:
                    placement_id = str(group["monster_id"])
                    resolvable = self.database.resolve_monster(placement_id) is not None
                    self.assertEqual(
                        group["resolution_status"],
                        "RESOLVED" if resolvable else "UNKNOWN",
                        f"{stage_id}:{placement_id}",
                    )
                    compared += 1
        self.assertGreater(compared, 0)

    def test_real_stage_420101_compiles_with_proven_variant_parents(self) -> None:
        package = self.compiler.compile(_request(source_stage_id=420101, enemy_waves=None))
        self.assertEqual(package["source_stage"]["stage_id"], "420101")
        enemies = [enemy for wave in package["waves"] for enemy in wave["enemies"]]
        self.assertTrue(enemies)
        for enemy in enemies:
            self.assertEqual(enemy["resolution"]["resolved_kind"], "MONSTER_VARIANT")
            self.assertEqual(enemy["resolution"]["variant_id"], enemy["monster_id"])
            self.assertIsNotNone(enemy["resolution"]["canonical_monster_id"])
            self.assertIsNotNone(self.database.get_monster(enemy["resolution"]["canonical_monster_id"]))
        self.assertFalse(package["golden_eligible"])
        self.assertEqual(package["execution_status"], "STATIC_READY_BEHAVIOR_COMPILATION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
