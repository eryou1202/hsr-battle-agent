"""Offline fixtures for the version-locked Nanoka content database."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from hsr_battle_agent.game_data.nanoka_content import (
    CanonicalBuilder,
    ContentDatabase,
    _entity,
    build_from_snapshot,
    database_health_report,
    sqlite_logical_hash,
)


FIXTURE = Path(__file__).parent / "fixtures" / "nanoka_minimal_snapshot.json"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def materialize_snapshot(root: Path) -> None:
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
            "source_url": f"https://fixture.invalid/{relative_path}",
            "source_category": relative_path.split("/", 1)[0],
            "source_entity_id": path.stem if "/detail/" in f"/{relative_path}" else None,
            "locale": "zh" if relative_path.startswith("detail/") else None,
            "etag": None,
            "last_modified": None,
            "fetch_time": "2000-01-01T00:00:00Z",
            "raw_sha256": sha256(raw).hexdigest(),
            "raw_size": len(raw),
        }
    _write(root / "provenance" / "index.json", provenance)


class NanokaContentDatabaseTest(unittest.TestCase):
    def test_normalization_and_stage_package_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            snapshot = tmp_path / "snapshot"
            materialize_snapshot(snapshot)
            result = build_from_snapshot(
                "4.4.54",
                snapshot_root=snapshot,
                canonical_root=tmp_path / "canonical",
                database_path=tmp_path / "content.sqlite",
            )
            database = ContentDatabase(tmp_path / "content.sqlite", "4.4.54")
            self.assertEqual(result["coverage"]["families"]["avatar"], {
                "total": 2, "reconstruction_ready": 2, "partial": 0, "failed": 0
            })
            self.assertEqual(database.get_avatar(1105)["data"]["detail"]["sp_need"], 90)
            self.assertTrue(database.get_avatar(1105)["data"]["detail"]["unrecognized_future_field"]["preserved"])
            self.assertEqual(database.get_skill(110502)["data"]["owner_avatar_id"], 1105)
            self.assertIsNotNone(database.get_lightcone(21000))
            self.assertIsNotNone(database.get_relic_set(101))
            self.assertIsNotNone(database.get_monster(1002020))
            package = database.get_stage_package(420101)
            self.assertEqual(package["game_version"], "4.4.54")
            self.assertEqual([row["monster_id"] for row in package["waves"][0]["enemy_groups"]], [100202001, 100203001, 100401401])
            self.assertEqual(package["stage_buffs"], [{"buff_id": "3110001", "resolution_status": "RESOLVED"}])
            self.assertEqual(package["unknown_references"], [])
            maze_package = database.get_stage_package(30001011)
            self.assertEqual(maze_package["waves"][0]["enemy_groups"][0]["monster_id"], 100202001)
            story_package = database.get_stage_package(30319011)
            self.assertEqual(story_package["encounter_contexts"][0]["source_mode"], "story")
            self.assertEqual(story_package["waves"][0]["enemy_groups"][0]["monster_id"], 100203001)
            health = database_health_report(CanonicalBuilder(snapshot, "4.4.54").build())
            self.assertEqual(health["orphan_skill_ids"], [])
            self.assertEqual(health["unknown_monster_refs"], [])
            self.assertEqual(health["unknown_stage_buff_refs"], [])
            self.assertEqual(health["version_contamination"], {"entity_records": 0, "relations": 0})
            connection = sqlite3.connect(tmp_path / "content.sqlite")
            try:
                rank_count = connection.execute("SELECT count(*) FROM avatar_eidolons WHERE game_version='4.4.54'").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(rank_count, 12)

    def test_sqlite_rebuild_is_deterministic_and_version_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            snapshot = tmp_path / "snapshot"
            materialize_snapshot(snapshot)
            first = tmp_path / "first.sqlite"
            second = tmp_path / "second.sqlite"
            build_from_snapshot("4.4.54", snapshot_root=snapshot, canonical_root=tmp_path / "canonical-a", database_path=first)
            build_from_snapshot("4.4.54", snapshot_root=snapshot, canonical_root=tmp_path / "canonical-b", database_path=second)
            self.assertEqual(sqlite_logical_hash(first), sqlite_logical_hash(second))
            connection = sqlite3.connect(first)
            try:
                self.assertEqual(connection.execute("SELECT game_version FROM content_versions").fetchall(), [("4.4.54",)])
                gap_count = connection.execute("SELECT count(*) FROM content_gaps WHERE gap_kind='NANOKA_STATIC_GAPS'").fetchone()[0]
            finally:
                connection.close()
            self.assertGreaterEqual(gap_count, 1)

    def test_conflicts_preserve_the_original_canonical_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = Path(temporary) / "snapshot"
            materialize_snapshot(snapshot)
            builder = CanonicalBuilder(snapshot, "4.4.54")
            first = _entity("avatar", "1105", version="4.4.54", payload={"source": "first"}, provenance=[])
            conflicting = _entity("avatar", "1105", version="4.4.54", payload={"source": "second"}, provenance=[])
            builder._add(first)
            builder._add(conflicting)
            self.assertEqual(builder.records["avatar"], [first])
            self.assertEqual(builder.static_gaps[0]["status"], "CONFLICT")
