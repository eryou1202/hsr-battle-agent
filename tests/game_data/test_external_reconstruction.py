"""Offline tests for the pinned external reconstruction layer."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from hsr_battle_agent.game_data.external_reconstruction import (
    EXTERNAL_SOURCES,
    ExternalReferenceError,
    ReferenceEvaluator,
    build_external_reconstruction,
)
from hsr_battle_agent.game_data.nanoka_content import ContentDatabase, build_from_snapshot, sqlite_logical_hash


FIXTURE = Path(__file__).parent / "fixtures" / "nanoka_minimal_snapshot.json"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _materialize_nanoka_snapshot(root: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payloads: dict[str, object] = {"manifest.json": fixture["manifest"]}
    payloads.update({f"collections/{name}.json": value for name, value in fixture["collections"].items()})
    for category, records in fixture["details"].items():
        for entity_id, payload in records.items():
            payloads[f"detail/{category}/{entity_id}.json"] = payload
    payloads.update({f"auxiliary/{name}.json": value for name, value in fixture["auxiliary"].items()})
    provenance: dict[str, dict[str, object]] = {}
    for relative_path, payload in sorted(payloads.items()):
        path = root / relative_path
        _write(path, payload)
        raw = path.read_bytes()
        provenance[relative_path] = {
            "source_url": f"https://fixture.invalid/{relative_path}", "source_category": relative_path.split("/", 1)[0],
            "source_entity_id": path.stem if "/detail/" in f"/{relative_path}" else None,
            "locale": "zh" if relative_path.startswith("detail/") else None,
            "etag": None, "last_modified": None, "fetch_time": "2000-01-01T00:00:00Z",
            "raw_sha256": sha256(raw).hexdigest(), "raw_size": len(raw),
        }
    _write(root / "provenance" / "index.json", provenance)


def _materialize_external_snapshot(root: Path) -> None:
    """Write a tiny pinned-source fixture; the build itself never reaches the network."""
    files: dict[str, dict[str, object]] = {
        "TurnBasedGameData": {
            "ExcelOutput/RelicConfig.json": [{"ID": 31011, "SetID": 101, "Type": "HEAD", "MaxLevel": 15, "MainAffixGroup": 53, "SubAffixGroup": 5}],
            "ExcelOutput/RelicMainAffixConfig.json": [
                {"GroupID": 53, "AffixID": 1, "Property": "HPDelta", "BaseValue": {"Value": 100}, "LevelAdd": {"Value": 10}},
                {"GroupID": 53, "AffixID": 6, "Property": "HealRatioBase", "BaseValue": {"Value": 0.05}, "LevelAdd": {"Value": 0.01}},
            ],
            "ExcelOutput/RelicSubAffixConfig.json": [{"GroupID": 5, "AffixID": 8, "Property": "CriticalChanceBase", "BaseValue": {"Value": 0.02}, "StepValue": {"Value": 0.01}, "StepNum": 3}],
            "ExcelOutput/EliteGroup.json": [{"ID": 1, "MonsterList": [100202001]}],
            "ExcelOutput/HardLevelGroup.json": [{"ID": 2, "MonsterList": [100203001]}],
            "ExcelOutput/MazeBuff.json": [{"MazeBuffID": 3110001, "FixtureEffect": "external-only-detail"}],
            "ExcelOutput/MonsterConfig.json": [{"MonsterID": 4034020, "MonsterTemplateID": 8001}],
            "ExcelOutput/MonsterTemplateConfig.json": [{"MonsterID": 4034020, "TemplateID": 8001}],
        },
        "StarRailRes": {
            "index_new/cn/relic_main_affixes.json": {"53": {"affixes": {"1": {"property": "HPDelta", "base": 100, "step": 10}, "6": {"property": "HealRatioBase", "base": 0.05, "step": 0.01}}}},
        },
    }
    for source in EXTERNAL_SOURCES:
        source_files = files.get(source.name, {})
        metadata: dict[str, object] = {}
        for relative_path, payload in source_files.items():
            path = root / source.name / "files" / relative_path
            _write(path, payload)
            raw = path.read_bytes()
            metadata[relative_path] = {
                "download_url": f"https://fixture.invalid/{source.name}/{relative_path}",
                "git_blob_sha": "fixture", "raw_sha256": sha256(raw).hexdigest(), "raw_size": len(raw),
            }
        _write(root / source.name / "manifest.json", {
            "selected_commit": source.selected_commit, "local_snapshot_path": str(root / source.name),
            "manifest_sha256": "fixture", "files": metadata,
        })


class ExternalReconstructionTest(unittest.TestCase):
    def _build(self, temporary: Path, name: str) -> tuple[Path, Path]:
        snapshot = temporary / f"nanoka-{name}"
        external = temporary / "external"
        database = temporary / f"{name}.sqlite"
        _materialize_nanoka_snapshot(snapshot)
        _materialize_external_snapshot(external)
        build_from_snapshot("4.4.54", snapshot_root=snapshot, canonical_root=temporary / f"canonical-{name}", database_path=database)
        build_external_reconstruction(
            "4.4.54", source_root=external, canonical_root=temporary / f"external-canonical-{name}",
            artifact_root=temporary / f"artifacts-{name}", database_path=database,
        )
        return database, external

    def test_external_records_stage_detail_and_static_loadout_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path, _ = self._build(Path(temporary), "content")
            database = ContentDatabase(database_path, "4.4.54")
            affix = database.get_relic_affix("main:53:1")
            self.assertEqual(affix["data"]["property"], "HPDelta")
            self.assertEqual(database.get_relic_template(31011)["data"]["slot"], "HEAD")
            package = database.get_stage_package(420101)
            self.assertEqual(package["stage_buffs"][0]["detail_source"], "EXTERNAL_CLOSE")
            self.assertEqual(database.get_stage_buff(3110001)["confidence"], "C0_EXTERNAL_ONLY")
            self.assertEqual(database.get_external_stage_buff(3110001)["confidence"], "R1_CLIENT_DUMP_DERIVED")
            evaluator = ReferenceEvaluator(database)
            materialized = evaluator.materialize_loadout({
                "avatar_id": 1105, "level": 1, "promotion": 0,
                "lightcone_id": 21000, "lightcone_level": 1, "lightcone_promotion": 0,
                "relics": [{"template_id": 31011, "level": 15, "main_affix_id": "main:53:1", "sub_affixes": [{"affix_id": "sub:5:8", "roll_tiers": [0, 2]}]}],
            })
            self.assertEqual(materialized["relics"][0]["slot"], "HEAD")
            self.assertEqual(materialized["final_properties"]["hp"], 414.0)
            self.assertAlmostEqual(materialized["final_properties"]["crit_rate"], 0.06)
            self.assertGreater(ReferenceEvaluator.evaluate_damage({"atk": 1000, "enemy_level": 80, "enemy_res": 0, "atk_scaling": 1, "crit_mode": "expected", "crit_rate": 0.5, "crit_dmg": 1})["value"], 0)
            self.assertGreater(ReferenceEvaluator.evaluate_heal({"hp": 1000, "hp_scaling": 0.1})["value"], 0)
            self.assertGreater(ReferenceEvaluator.evaluate_break({"enemy_level": 80, "enemy_res": 0})["value"], 0)
            self.assertGreater(ReferenceEvaluator.evaluate_super_break({"enemy_level": 80, "enemy_res": 0, "toughness_damage": 30, "super_break_modifier": 1})["value"], 0)
            self.assertGreater(ReferenceEvaluator.evaluate_shield({"def": 1000, "def_scaling": 0.1})["value"], 0)

    def test_rebuild_is_deterministic_and_refuses_other_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, external = self._build(root, "first")
            second_snapshot = root / "nanoka-second"
            second = root / "second.sqlite"
            _materialize_nanoka_snapshot(second_snapshot)
            build_from_snapshot("4.4.54", snapshot_root=second_snapshot, canonical_root=root / "canonical-second", database_path=second)
            build_external_reconstruction("4.4.54", source_root=external, canonical_root=root / "external-canonical-second", artifact_root=root / "artifacts-second", database_path=second)
            self.assertEqual(sqlite_logical_hash(first), sqlite_logical_hash(second))
            with self.assertRaisesRegex(ExternalReferenceError, "pinned to 4.4.54"):
                build_external_reconstruction("4.4.55", source_root=external, database_path=second)
