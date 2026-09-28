"""Focused tests for the Stage / Encounter product projections.

CR-P3-STAGE-ENCOUNTER-PRODUCT-20260928-001.

``stage_package/1`` remains the single topology authority: these tests prove the
Stage product *preserves* the package rather than rebuilding it, and that the
product layer invents neither a canonical game mode (audit F10) nor any runtime
behavior.

Everything asserted here is static product packaging.
"""
from __future__ import annotations

import ast
from pathlib import Path
import sqlite3
import unittest

from hsr_battle_agent.game_data.content_product import (
    CANONICAL_STAGE_MODE_ESTABLISHED, ENCOUNTER_COMMON_FIELDS,
    ENCOUNTER_PRODUCT_SCHEMA, ENCOUNTER_SOURCE_MODE_FIELDS,
    ENCOUNTER_SUMMARY_SCHEMA, STAGE_LOCALE_STATUS, STAGE_NON_INTERPRETED_FIELDS,
    STAGE_PACKAGE_SCHEMA, STAGE_PRODUCT_SCHEMA, STAGE_RAW_METADATA_FIELDS,
    STAGE_SUMMARY_SCHEMA, ContentProductService,
)
from hsr_battle_agent.game_data.nanoka_content import ContentDatabase

LOCAL_DATABASE = (
    Path(__file__).resolve().parents[2] / "data" / "db" / "hsr_content_4.4.54.sqlite"
)
PRODUCT_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src" / "hsr_battle_agent" / "game_data" / "content_product.py"
).read_text(encoding="utf-8")

#: Real acceptance fixtures.
BOSS_STAGE = "420101"          # Stage Buff + P0 variant-only Monster placements + win/lose
MAZE_STAGE = "30001011"        # multiple enemy slots, no win/lose condition
STORY_STAGE = "30319011"       # different enemy layout, no win/lose condition
BOSS_ENCOUNTER = "boss:3001:30011:event_id_list1:0"
MAZE_ENCOUNTER = "maze:1001:2001:event_id_list1:0"
STORY_ENCOUNTER = "story:2001:20011:event_id_list1:0"
UNKNOWN_STAGE = "999999999"
UNKNOWN_ENCOUNTER = "nope:nope"

EXPECTED_STAGES = 1459
EXPECTED_ENCOUNTERS = 1543
EXPECTED_STAGES_WITH_UNKNOWN_REFERENCES = 8

FORBIDDEN_DOCUMENT_KEYS = (
    "battle_state", "envelope", "execution_trace", "golden_trace",
    "native_trace", "legal_actions", "admission", "evidence_mode",
)


def _walk_keys(value: object):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_keys(item)


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class StageEnumerationTest(unittest.TestCase):
    """Section 3/8 -- enumeration authority and browse rows."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.service = ContentProductService(cls.database)

    def test_facade_enumeration(self) -> None:
        stage_ids = self.database.list_stage_ids()
        encounter_ids = self.database.list_encounter_ids()
        self.assertEqual(len(stage_ids), EXPECTED_STAGES)
        self.assertEqual(len(encounter_ids), EXPECTED_ENCOUNTERS)
        self.assertEqual(stage_ids, self.database.list_stage_ids())
        self.assertEqual(encounter_ids[0], BOSS_ENCOUNTER)
        self.assertEqual(
            self.database.ENUMERABLE_ENTITY_TABLES,
            ("avatars", "monsters", "stages", "encounters"),
        )
        # No generic table-name API is exposed.
        self.assertFalse(hasattr(self.database, "list_entity_ids"))

    def test_facade_enumeration_is_version_scoped(self) -> None:
        other = ContentDatabase(LOCAL_DATABASE, "4.4.55")
        self.assertEqual(other.list_stage_ids(), [])
        self.assertEqual(other.list_encounter_ids(), [])

    def test_list_stages(self) -> None:
        rows = self.service.list_stages()
        self.assertEqual(len(rows), EXPECTED_STAGES)
        self.assertEqual(
            set(rows[0]),
            {"schema", "game_version", "stage_id", "stage_name", "stage_name_kind",
             "raw_stage_type", "encounter_source_modes", "topology_counts_included",
             "wave_count", "enemy_placement_count", "stage_buff_count", "unknown_reference_count"},
        )
        self.assertEqual(rows[0]["schema"], STAGE_SUMMARY_SCHEMA)
        self.assertEqual(rows[0]["game_version"], "4.4.54")

    def test_list_encounters(self) -> None:
        rows = self.service.list_encounters()
        self.assertEqual(len(rows), EXPECTED_ENCOUNTERS)
        self.assertEqual(
            set(rows[0]),
            {"schema", "game_version", "encounter_id", "source_mode",
             "related_stage_count", "related_stage_ids", "static_display_text"},
        )
        self.assertEqual(rows[0]["schema"], ENCOUNTER_SUMMARY_SCHEMA)

    def test_enumeration_order_is_deterministic(self) -> None:
        self.assertEqual(self.service.list_stages(), ContentProductService(self.database).list_stages())
        self.assertEqual(self.service.list_encounters(), ContentProductService(self.database).list_encounters())
        stage_ids = [row["stage_id"] for row in self.service.list_stages()]
        self.assertEqual(stage_ids, sorted(stage_ids, key=int))
        encounter_ids = [row["encounter_id"] for row in self.service.list_encounters()]
        self.assertEqual(encounter_ids[:3], [
            "boss:3001:30011:event_id_list1:0",
            "boss:3001:30011:event_id_list2:0",
            "boss:3001:30012:event_id_list1:0",
        ])

    def test_summary_topology_counts_are_opt_in_and_never_guessed(self) -> None:
        from unittest import mock

        light = {row["stage_id"]: row for row in self.service.list_stages()}
        self.assertFalse(light[BOSS_STAGE]["topology_counts_included"])
        for field in ("wave_count", "enemy_placement_count", "stage_buff_count", "unknown_reference_count"):
            self.assertIsNone(light[BOSS_STAGE][field], field)
        # The opt-in path is exercised on one Stage so the suite stays cheap.
        with mock.patch.object(self.service, "_stage_ids", return_value=[BOSS_STAGE]):
            row = self.service.list_stages(include_package_topology=True)[0]
        self.assertTrue(row["topology_counts_included"])
        package = self.database.get_stage_package(BOSS_STAGE)
        self.assertEqual(row["wave_count"], len(package["waves"]))
        self.assertEqual(
            row["enemy_placement_count"],
            sum(len(wave["enemy_groups"]) for wave in package["waves"]),
        )
        self.assertEqual(row["stage_buff_count"], len(package["stage_buffs"]))
        self.assertEqual(row["unknown_reference_count"], len(package["unknown_references"]))

    def test_product_layer_contains_no_sql(self) -> None:
        self.assertNotIn("sqlite3", PRODUCT_SOURCE)
        self.assertNotIn("database_path", PRODUCT_SOURCE)
        self.assertNotIn("_entity_ids", PRODUCT_SOURCE)
        for keyword in ("SELECT", "FROM", "WHERE", "INSERT", "CREATE", "ORDER BY"):
            self.assertNotIn(keyword, PRODUCT_SOURCE, keyword)
        for table in ("stages", "encounters", "avatars", "monsters"):
            self.assertNotIn(f'"{table}"', PRODUCT_SOURCE, table)

    def test_product_layer_module_imports_are_clean(self) -> None:
        tree = ast.parse(PRODUCT_SOURCE)
        modules = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
            elif isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
        self.assertEqual(modules, {"__future__", "copy", "typing", "nanoka_content"})

    def test_unknown_ids_return_none(self) -> None:
        self.assertIsNone(self.service.get_stage(UNKNOWN_STAGE))
        self.assertIsNone(self.service.get_encounter(UNKNOWN_ENCOUNTER))


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class StageProductTest(unittest.TestCase):
    """Sections 4/5/6 -- topology preservation, F9 retention, F10 honesty."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.service = ContentProductService(cls.database)

    def test_schema_and_identity(self) -> None:
        document = self.service.get_stage(BOSS_STAGE)
        self.assertEqual(document["schema"], STAGE_PRODUCT_SCHEMA)
        identity = document["identity"]
        self.assertEqual(identity["stage_id"], BOSS_STAGE)
        self.assertEqual(identity["stage_package_id"], BOSS_STAGE)
        self.assertEqual(identity["game_id_status"], "PRESERVED")
        self.assertTrue(identity["entity_sha256"])

    def test_topology_equals_the_stage_package_authority(self) -> None:
        for stage_id in (BOSS_STAGE, MAZE_STAGE, STORY_STAGE):
            with self.subTest(stage_id=stage_id):
                package = self.database.get_stage_package(stage_id)
                topology = self.service.get_stage(stage_id)["topology"]
                self.assertEqual(topology["authority"], "hsr_battle_agent.stage_package/1 (ContentDatabase.get_stage_package)")
                self.assertEqual(topology["package_schema"], STAGE_PACKAGE_SCHEMA)
                self.assertEqual(topology["package_sha256"], package["package_sha256"])
                self.assertEqual(topology["waves"], package["waves"])
                self.assertEqual(topology["stage_buffs"], package["stage_buffs"])
                self.assertEqual(topology["encounter_contexts"], package["encounter_contexts"])
                self.assertEqual(topology["unknown_references"], package["unknown_references"])
                self.assertEqual(topology["wave_count"], len(package["waves"]))
                self.assertEqual(
                    topology["enemy_placement_count"],
                    sum(len(wave["enemy_groups"]) for wave in package["waves"]),
                )

    def test_wave_identity_slots_monsters_and_levels_are_retained(self) -> None:
        document = self.service.get_stage(BOSS_STAGE)
        waves = document["topology"]["waves"]
        self.assertEqual([wave["wave_id"] for wave in waves], ["420101:1"])
        self.assertEqual([wave["wave_index"] for wave in waves], [1])
        placements = document["monster_placements"]
        self.assertEqual(len(placements), document["topology"]["enemy_placement_count"])
        self.assertEqual(
            [(row["group_index"], row["slot"]) for row in placements],
            [(0, "monster0"), (0, "monster1")],
        )
        self.assertEqual([row["monster_id"] for row in placements], ["100401401", "100402601"])
        self.assertEqual([row["level"] for row in placements], [60, 60])
        self.assertTrue(all(row["resolution_status"] == "RESOLVED" for row in placements))

    def test_p0_requested_variant_identity_is_unchanged_in_topology(self) -> None:
        document = self.service.get_stage(BOSS_STAGE)
        by_id = {row["monster_id"]: row for row in document["monster_placements"]}
        row = by_id["100401401"]
        # The requested variant ID is preserved, and the P0 identity is reported
        # alongside it -- never normalised into the canonical parent.
        self.assertEqual(row["resolved_kind"], "MONSTER_VARIANT")
        self.assertEqual(row["canonical_monster_id"], "1004014")
        self.assertNotEqual(row["monster_id"], row["canonical_monster_id"])
        self.assertEqual(row["monster_product_ref"], {
            "service": "ContentProductService.get_monster", "monster_id": "100401401",
        })
        # No full MonsterProduct is embedded.
        self.assertNotIn("monster", row)

    def test_stage_buff_and_encounter_context_references_are_retained(self) -> None:
        document = self.service.get_stage(BOSS_STAGE)
        buffs = document["topology"]["stage_buffs"]
        self.assertEqual([buff["buff_id"] for buff in buffs], ["3110001"])
        self.assertEqual(document["topology"]["stage_buff_count"], 1)
        contexts = document["topology"]["encounter_contexts"]
        self.assertEqual(
            [context["encounter_id"] for context in contexts], [BOSS_ENCOUNTER],
        )
        self.assertEqual([context["source_mode"] for context in contexts], ["boss"])

    def test_rule_metadata_is_preserved_and_never_interpreted(self) -> None:
        package = self.database.get_stage_package(BOSS_STAGE)
        rules = self.service.get_stage(BOSS_STAGE)["rules"]
        self.assertEqual(rules["rule_metadata"], package["rule_metadata"])
        self.assertEqual(rules["win_condition_count"], 1)
        self.assertEqual(rules["lose_condition_count"], 1)
        self.assertFalse(rules["win_conditions_interpreted"])
        self.assertFalse(rules["mapped_to_scenario_rule_ids"])
        self.assertEqual(rules["execution_semantics"], "NOT_SUPPLIED")
        # The stage's own opaque tokens are not turned into scenario rule ids.
        self.assertEqual(rules["rule_metadata"]["win_conditions"], [
            "[CDT_WaitCustomString:Level_SpecialWin]",
        ])

    def test_f9_raw_fields_are_retained_from_get_stage(self) -> None:
        raw = self.database.get_stage(BOSS_STAGE)["data"]
        metadata = self.service.get_stage(BOSS_STAGE)["static_source_metadata"]
        self.assertEqual(metadata["classification"], "STATIC_SOURCE_METADATA_ONLY")
        self.assertEqual(set(metadata["field_values"]), set(STAGE_RAW_METADATA_FIELDS))
        for name in STAGE_RAW_METADATA_FIELDS:
            self.assertEqual(metadata["field_values"][name], raw.get(name), name)
        for name in ("stage_name", "monster_list", "forbid_exit_battle", "hard_level_group",
                     "monster_warning_ratio", "level_graph_path", "stage_ability_config",
                     "sub_level_graphs", "trial_avatar_list"):
            self.assertIn(name, metadata["fields_present"] + metadata["fields_absent"], name)
        # The non-interpreted fields are labelled, and stage_ability_config is
        # carried verbatim as an empty list rather than read as behavior.
        self.assertEqual(list(metadata["non_interpreted_fields"]), list(STAGE_NON_INTERPRETED_FIELDS))
        self.assertEqual(metadata["field_values"]["stage_ability_config"], raw["stage_ability_config"])
        self.assertEqual(metadata["field_values"]["level_graph_path"], "Config/Level/StageCommonTemplate.json")

    def test_missing_raw_fields_remain_explicitly_missing(self) -> None:
        metadata = self.service.get_stage(BOSS_STAGE)["static_source_metadata"]
        # 420101 supplies no release value, so it is reported absent, not invented.
        self.assertIn("release", metadata["fields_absent"])
        self.assertIsNone(metadata["field_values"]["release"])
        # An "absent" field is one the record does not supply a value for: it is
        # either missing entirely or empty, never fabricated.
        for name in metadata["fields_absent"]:
            self.assertIn(metadata["field_values"][name], (None, "", [], {}), name)
        self.assertEqual(
            metadata["fields_absent"],
            [name for name in STAGE_RAW_METADATA_FIELDS if name not in metadata["fields_present"]],
        )

    def test_f10_does_not_invent_a_canonical_mode(self) -> None:
        for stage_id in (BOSS_STAGE, MAZE_STAGE, STORY_STAGE):
            with self.subTest(stage_id=stage_id):
                mode = self.service.get_stage(stage_id)["mode"]
                self.assertEqual(mode["raw_stage_type"], "Challenge")
                self.assertIsNone(mode["canonical_mode"])
                self.assertFalse(mode["canonical_mode_established"])
                self.assertFalse(mode["inference_performed"])
                self.assertFalse(CANONICAL_STAGE_MODE_ESTABLISHED)
                self.assertIn("must never be read as", mode["note"])
        self.assertEqual(self.service.get_stage(BOSS_STAGE)["mode"]["encounter_source_modes"], ["boss"])
        self.assertEqual(self.service.get_stage(MAZE_STAGE)["mode"]["encounter_source_modes"], ["maze"])
        self.assertEqual(self.service.get_stage(STORY_STAGE)["mode"]["encounter_source_modes"], ["story"])

    def test_raw_stage_type_and_source_modes_stay_separate(self) -> None:
        document = self.service.get_stage(STORY_STAGE)
        self.assertEqual(document["mode"]["raw_stage_type"], "Challenge")
        self.assertEqual(document["mode"]["encounter_source_modes"], ["story"])
        self.assertNotEqual(document["mode"]["raw_stage_type"], "story")
        # win/lose metadata is genuinely absent for this stage and stays absent.
        self.assertEqual(document["rules"]["win_condition_count"], 0)
        self.assertEqual(document["rules"]["lose_condition_count"], 0)
        self.assertEqual(document["rules"]["rule_metadata"]["win_conditions"], [])

    def test_locale_is_not_fabricated(self) -> None:
        document = self.service.get_stage(BOSS_STAGE)
        display = document["display"]
        self.assertFalse(display["localized"])
        self.assertEqual(display["locale_vocabulary"], [])
        self.assertEqual(display["locale_status"], STAGE_LOCALE_STATUS)
        # stage_name is a static numeric identifier, not a localized string.
        self.assertEqual(display["stage_name_kind"], "STATIC_NUMERIC_ID")
        self.assertIsInstance(display["stage_name"], int)
        import inspect

        for name in ("get_stage", "list_stages", "get_encounter", "list_encounters"):
            self.assertNotIn("locale", inspect.signature(getattr(self.service, name)).parameters, name)

    def test_provenance_is_reused_not_invented(self) -> None:
        package = self.database.get_stage_package(BOSS_STAGE)
        raw = self.database.get_stage(BOSS_STAGE)
        provenance = self.service.get_stage(BOSS_STAGE)["provenance"]
        self.assertEqual(provenance["package_source_refs"], package["source_refs"])
        self.assertEqual(
            provenance["raw_stage_entity_provenance"], raw["provenance"],
        )
        self.assertEqual(provenance["raw_stage_entity_provenance_count"], len(raw["provenance"]))
        self.assertFalse(provenance["invented_source_relationships"])

    def test_runtime_non_claims(self) -> None:
        document = self.service.get_stage(BOSS_STAGE)
        self.assertFalse(document["runtime_semantics_added"])
        self.assertIn("unknown", document)
        self.assertTrue(document["unknown"]["limitations"])
        keys = set(_walk_keys(document))
        for forbidden in FORBIDDEN_DOCUMENT_KEYS:
            self.assertNotIn(forbidden, keys)
        # No per-stage readiness vocabulary is present anywhere.
        for readiness in ("execution_readiness", "golden_eligible", "execution_status"):
            self.assertNotIn(readiness, keys)

    def test_determinism_and_copy_isolation(self) -> None:
        first = self.service.get_stage(BOSS_STAGE)
        second = ContentProductService(self.database).get_stage(BOSS_STAGE)
        self.assertEqual(first["product_sha256"], second["product_sha256"])
        self.assertIsNot(first, second)
        first["identity"]["stage_id"] = "tampered"
        first["topology"]["waves"][0]["wave_id"] = "tampered"
        fresh = self.service.get_stage(BOSS_STAGE)
        self.assertEqual(fresh["identity"]["stage_id"], BOSS_STAGE)
        self.assertEqual(fresh["topology"]["waves"][0]["wave_id"], "420101:1")


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class EncounterProductTest(unittest.TestCase):
    """Section 7 -- Encounter projection."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.service = ContentProductService(cls.database)

    def test_schema_and_identity(self) -> None:
        entity = self.database.get_encounter(BOSS_ENCOUNTER)
        document = self.service.get_encounter(BOSS_ENCOUNTER)
        self.assertEqual(document["schema"], ENCOUNTER_PRODUCT_SCHEMA)
        identity = document["identity"]
        self.assertEqual(identity["encounter_id"], BOSS_ENCOUNTER)
        self.assertEqual(identity["source_mode"], "boss")
        # Identity fields are reused verbatim from the canonical envelope.
        self.assertEqual(identity["game_id_status"], entity["game_id_status"])
        self.assertTrue(identity["game_id_status"])
        self.assertEqual(identity["entity_sha256"], entity["canonical_sha256"])
        self.assertTrue(identity["entity_sha256"])

    def test_source_mode_vocabulary_is_preserved(self) -> None:
        for encounter_id, mode in (
            (BOSS_ENCOUNTER, "boss"), (MAZE_ENCOUNTER, "maze"), (STORY_ENCOUNTER, "story"),
        ):
            with self.subTest(encounter_id=encounter_id):
                document = self.service.get_encounter(encounter_id)
                self.assertEqual(document["identity"]["source_mode"], mode)
                self.assertEqual(document["static_context"]["source_mode"], mode)
                self.assertEqual(document["static_context"]["context_merged_across_encounters"], False)

    def test_mode_context_fields_are_classified_not_dropped(self) -> None:
        boss = self.service.get_encounter(BOSS_ENCOUNTER)["static_context"]
        self.assertEqual(boss["mode_context_fields_present"], ["boss_id", "difficulty_id", "difficulty_name"])
        self.assertEqual(boss["common_fields_present"], sorted(ENCOUNTER_COMMON_FIELDS))
        self.assertEqual(boss["unrecognised_fields"], [])
        self.assertEqual(
            boss["static_context"],
            self.database.get_encounter(BOSS_ENCOUNTER)["data"],
        )
        self.assertEqual(
            ENCOUNTER_SOURCE_MODE_FIELDS["story"],
            ("story_id", "story_level_id", "story_level_index", "story_name",
             "story_level_context", "story_metadata"),
        )

    def test_related_stage_identity_is_preserved(self) -> None:
        for encounter_id in (BOSS_ENCOUNTER, MAZE_ENCOUNTER, STORY_ENCOUNTER):
            with self.subTest(encounter_id=encounter_id):
                payload = self.database.get_encounter(encounter_id)["data"]
                expected_stage = str(payload["stage_id"])
                document = self.service.get_encounter(encounter_id)
                self.assertEqual(document["related_stage_ids"], [expected_stage])
                related = document["related_stages"][0]
                self.assertEqual(related["stage_id"], expected_stage)
                self.assertTrue(related["stage_exists_in_content"])
                self.assertFalse(related["order_supplied"])
                self.assertEqual(
                    related["stage_product_ref"],
                    {"service": "ContentProductService.get_stage", "stage_id": expected_stage},
                )
                self.assertIsNotNone(self.service.get_stage(expected_stage))

    def test_static_display_text_is_verbatim_and_unlocalized(self) -> None:
        boss = self.service.get_encounter(BOSS_ENCOUNTER)["display"]
        self.assertFalse(boss["localized"])
        self.assertEqual(boss["locale_vocabulary"], [])
        self.assertEqual(boss["locale_status"], STAGE_LOCALE_STATUS)
        self.assertEqual(
            boss["static_display_text"]["difficulty_name"], "冽风骑士·难度<unbreak>01</unbreak>",
        )
        self.assertEqual(boss["static_text_fields_present"], ["difficulty_name"])
        self.assertIsNone(boss["static_display_text"]["story_name"])
        story = self.service.get_encounter(STORY_ENCOUNTER)["display"]
        self.assertIn("story_name", story["static_text_fields_present"])
        maze = self.service.get_encounter(MAZE_ENCOUNTER)["display"]
        self.assertIn("maze_context_desc", maze["static_text_fields_present"])

    def test_provenance_is_reused_and_no_runtime_is_invented(self) -> None:
        entity = self.database.get_encounter(BOSS_ENCOUNTER)
        document = self.service.get_encounter(BOSS_ENCOUNTER)
        provenance = document["provenance"]
        self.assertEqual(provenance["entity_provenance"], entity["provenance"])
        self.assertGreater(provenance["entity_provenance_count"], 0)
        self.assertFalse(provenance["invented_provenance"])
        self.assertFalse(document["runtime_semantics_added"])
        self.assertEqual(document["unknown"]["context_merged_across_encounters"], False)
        self.assertFalse(document["unknown"]["multiple_stage_identities_supplied"])
        keys = set(_walk_keys(document))
        for forbidden in FORBIDDEN_DOCUMENT_KEYS:
            self.assertNotIn(forbidden, keys)

    def test_determinism_and_copy_isolation(self) -> None:
        first = self.service.get_encounter(BOSS_ENCOUNTER)
        second = ContentProductService(self.database).get_encounter(BOSS_ENCOUNTER)
        self.assertEqual(first["product_sha256"], second["product_sha256"])
        self.assertIsNot(first, second)
        first["identity"]["encounter_id"] = "tampered"
        self.assertEqual(
            self.service.get_encounter(BOSS_ENCOUNTER)["identity"]["encounter_id"], BOSS_ENCOUNTER,
        )


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class StageEncounterCensusTest(unittest.TestCase):
    """Section 14 -- static product census, not execution coverage."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.service = ContentProductService(cls.database)

    def test_every_stage_and_encounter_projects(self) -> None:
        stage_failures = [
            stage_id for stage_id in self.database.list_stage_ids()
            if self.service.get_stage(stage_id) is None
        ]
        self.assertEqual(stage_failures, [])
        encounter_failures = [
            encounter_id for encounter_id in self.database.list_encounter_ids()
            if self.service.get_encounter(encounter_id) is None
        ]
        self.assertEqual(encounter_failures, [])

    def test_stage_type_and_source_mode_vocabularies(self) -> None:
        connection = sqlite3.connect(LOCAL_DATABASE)
        try:
            stage_types = {
                row[0] for row in connection.execute(
                    "SELECT DISTINCT json_extract(payload_json,'$.stage_type') FROM stages WHERE game_version='4.4.54'"
                )
            }
            source_modes = {
                row[0] for row in connection.execute(
                    "SELECT DISTINCT json_extract(payload_json,'$.source_mode') FROM encounters WHERE game_version='4.4.54'"
                )
            }
        finally:
            connection.close()
        self.assertEqual(stage_types, {"Challenge"})
        self.assertEqual(source_modes, {"boss", "maze", "story"})

    def test_census_against_the_package_authority(self) -> None:
        with_win = without_win = with_buffs = with_unknown = variant_only = 0
        for stage_id in self.database.list_stage_ids():
            document = self.service.get_stage(stage_id)
            if document["rules"]["win_condition_count"]:
                with_win += 1
            else:
                without_win += 1
            if document["topology"]["stage_buff_count"]:
                with_buffs += 1
            if document["topology"]["unknown_reference_count"]:
                with_unknown += 1
            if any(row["resolved_kind"] == "MONSTER_VARIANT" for row in document["monster_placements"]):
                variant_only += 1
        self.assertEqual(with_win + without_win, EXPECTED_STAGES)
        self.assertEqual(with_win, 162)
        self.assertEqual(with_buffs, 160)
        # 8 packaged Stages carry Stage-Package unknown references (recorded data
        # fact, cross-checked by the P3 census artifact).
        self.assertEqual(with_unknown, EXPECTED_STAGES_WITH_UNKNOWN_REFERENCES)
        self.assertGreater(variant_only, 0)


if __name__ == "__main__":
    unittest.main()
