"""Offline tests for SCENARIO-FREE-001 static ScenarioPackage assembly."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from hsr_battle_agent.game_data.nanoka_content import ContentDatabase, build_from_snapshot
from hsr_battle_agent.game_data.scenario_compiler import ScenarioCompileError, ScenarioCompiler
from tests.game_data.test_nanoka_content_database import materialize_snapshot


class ScenarioCompilerTest(unittest.TestCase):
    def _compiler(self, temporary: Path) -> ScenarioCompiler:
        snapshot = temporary / "snapshot"
        materialize_snapshot(snapshot)
        database_path = temporary / "content.sqlite"
        build_from_snapshot("4.4.54", snapshot_root=snapshot, canonical_root=temporary / "canonical", database_path=database_path)
        return ScenarioCompiler(ContentDatabase(database_path, "4.4.54"))

    @staticmethod
    def _request() -> dict:
        return {
            "game_version": "4.4.54", "scenario_id": "free-fixture", "mode": "standard/free",
            "player_team": [{"slot": "0", "avatar": {"avatar_id": 1105, "level": 1, "promotion": 0, "eidolon": 0, "skill_levels": {"basic": 1}, "trace_state": {"unlocked_trace_ids": []}}, "lightcone": {"lightcone_id": 21000, "level": 1, "promotion": 0, "superimposition": 1}, "relics": [], "initial_state": {"hp": 100}}],
            "enemy_waves": [{"wave_index": 1, "enemies": [{"instance_id": "enemy-a", "monster_id": 1002020, "level": 1}]}, {"wave_index": 2, "enemies": [{"instance_id": "enemy-b", "monster_id": 1002030, "level": 2}]}],
            "buff_bindings": [{"binding_id": "battle-buff", "buff_id": 3110001, "scope": "battle", "activation": "battle_start"}],
            "rules": {"rng_seed": 42, "unsupported_policy": "reject"},
        }

    def test_free_static_scenario_is_identity_preserving_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            compiler = self._compiler(Path(temporary))
            first = compiler.compile(self._request())
            second = compiler.compile(self._request())
            self.assertEqual(first["package_sha256"], second["package_sha256"])
            self.assertEqual([wave["wave_index"] for wave in first["waves"]], [1, 2])
            self.assertEqual(first["waves"][0]["enemies"][0]["monster_id"], "1002020")
            self.assertEqual(first["buff_bindings"][0]["buff_id"], "3110001")
            self.assertFalse(first["golden_eligible"])
            self.assertEqual(first["execution_status"], "STATIC_READY_BEHAVIOR_COMPILATION_REQUIRED")

    def test_stage_template_can_be_overridden_without_flattening_waves(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            compiler = self._compiler(Path(temporary))
            request = self._request()
            request["source_stage_id"] = 420101
            request["enemy_waves"] = [{"wave_index": 7, "enemies": [{"monster_id": 1002030, "level": 66}]}]
            package = compiler.compile(request)
            self.assertEqual(package["source_stage"]["stage_id"], "420101")
            self.assertEqual([wave["wave_index"] for wave in package["waves"]], [7])
            self.assertTrue(any(binding["binding_id"].startswith("template:420101") for binding in package["buff_bindings"]))

    def test_unknown_ids_and_missing_seed_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            compiler = self._compiler(Path(temporary))
            request = self._request()
            del request["rules"]["rng_seed"]
            with self.assertRaises(ScenarioCompileError):
                compiler.compile(request)
            request = self._request()
            request["enemy_waves"][0]["enemies"][0]["monster_id"] = 999
            with self.assertRaises(ScenarioCompileError):
                compiler.compile(request)
