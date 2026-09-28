"""Focused tests for the Character / Monster product projections.

CR-P2-CONTENT-PRODUCT-PROJECTION-20260928-001.

Two tiers of coverage:

* offline tests over the packaged minimal fixture (robustness + explicit
  unavailable reporting), and
* real 4.4.54 acceptance fixtures (Natasha 1105, Hyacine 1409, Rin Tohsaka 1508,
  monsters 1002020 and 1002020's variant 100202001) skipped when the local
  content database is absent.

Everything asserted here is static product packaging.  No skill execution, no
Monster AI and no per-entity runtime readiness is claimed anywhere.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from hsr_battle_agent.game_data.content_product import (
    CHARACTER_PRODUCT_SCHEMA, DEFAULT_LOCALE, LOCALE_VOCABULARY,
    MONSTER_PRODUCT_SCHEMA, MONSTER_RUNTIME_SUPPORT,
    MONSTER_STATIC_STAT_FIELDS, ContentProductError, ContentProductService,
    UnknownLocaleError,
)
from hsr_battle_agent.game_data.nanoka_content import (
    ContentDatabase, build_from_snapshot,
)
from tests.game_data.test_nanoka_content_database import materialize_snapshot

#: The product module must not reach into any execution layer.
FORBIDDEN_SOURCE_TOKENS = (
    "ReferenceActionEnvelope", "PlayerLegalAction", "GateCertificate",
    "battle_sandbox", "reference_sandbox", "reference_battle_planner",
    "content_planner",
)

#: Keys that would imply executable / planner / battle semantics.
FORBIDDEN_DOCUMENT_KEYS = (
    "battle_state", "envelope", "execution_trace", "golden_trace",
    "native_trace", "legal_actions", "admission", "evidence_mode",
)

LOCAL_DATABASE = (
    Path(__file__).resolve().parents[2] / "data" / "db" / "hsr_content_4.4.54.sqlite"
)
PRODUCT_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src" / "hsr_battle_agent" / "game_data" / "content_product.py"
).read_text(encoding="utf-8")

#: Real acceptance fixtures (4.4.54).
NATASHA = "1105"          # 4*, Priest, Physical, no memosprite
HYACINE = "1409"          # 5*, Memory, Wind, memosprite present  (contrasting profile)
RIN_TOHSAKA = "1508"      # 5*, Mage, Quantum, zero M14 capability rows
VAGRANT = "1002020"       # canonical Monster, weaknesses + resistances + 2 skills
VAGRANT_VARIANT = "100202001"  # variant-only ID resolved by the P0 resolver
UNKNOWN_MONSTER = "999999999"


def _build_fixture_database(root: Path) -> ContentDatabase:
    snapshot = root / "snapshot"
    materialize_snapshot(snapshot)
    database_path = root / "content.sqlite"
    build_from_snapshot(
        "4.4.54", snapshot_root=snapshot, canonical_root=root / "canonical",
        database_path=database_path,
    )
    return ContentDatabase(database_path, "4.4.54")


def _walk_keys(value: object):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_keys(item)


def _fake_capability_record(*, avatar_id: str, skill_id: str, content_version: str) -> SimpleNamespace:
    """A minimal SkillRecord-shaped stand-in carrying a chosen content version."""
    from hsr_battle_agent.content_support import ContentSkillKey

    return SimpleNamespace(
        key=ContentSkillKey(content_version=content_version, avatar_id=avatar_id, skill_id=skill_id),
        binding_level="STATIC_ONLY",
        support_status="UNBOUND_STATIC_SKILL",
        representation_readiness=None,
        execution_readiness="NOT_EXECUTABLE_NO_SETTLEMENT",
        closure=SimpleNamespace(settlement_present=False, settlement_kinds=()),
        blocker_classes=(),
        primary_blocker=None,
        reentry_hints=(),
        entry_ability=None,
        prepare_ability=None,
        version_relation=None,
        is_unbound=True,
        unbound_reason="NO_ENTRY_ABILITY",
    )


def _fake_registry(content_version: str, records: list) -> SimpleNamespace:
    """The narrow slice of the M14 registry surface the product layer touches."""
    lookup = {record.key.canonical: record for record in records}
    return SimpleNamespace(
        content_version=content_version,
        records=tuple(records),
        record=lambda token: lookup.get(str(token)),
    )


class LocalePolicyTest(unittest.TestCase):
    """F11 -- explicit locale selection with no hidden fallback."""

    def test_locale_vocabulary_is_the_observed_one(self) -> None:
        self.assertEqual(LOCALE_VOCABULARY, ("en", "ja", "ko", "zh"))

    def test_there_is_no_backend_default_locale(self) -> None:
        self.assertIsNone(DEFAULT_LOCALE)


class MinimalFixtureRobustnessTest(unittest.TestCase):
    """The projections must degrade to explicit 'unavailable', never crash."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.database = _build_fixture_database(Path(cls._temporary.name))
        cls.service = ContentProductService(cls.database)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_character_projection_reports_missing_sections_explicitly(self) -> None:
        document = self.service.get_character(NATASHA)
        self.assertIsNotNone(document)
        self.assertEqual(document["schema"], CHARACTER_PRODUCT_SCHEMA)
        self.assertEqual(document["identity"]["avatar_id"], NATASHA)
        # No M14 authority was supplied, so capability is explicitly unknown.
        self.assertFalse(document["capability"]["registry_loaded"])
        self.assertEqual(document["capability"]["status"], "M14_REGISTRY_NOT_SUPPLIED")
        self.assertIsNone(document["capability"]["skills_with_m14_row"])
        self.assertIsNone(document["unknown"]["static_skills_without_m14_row"])
        self.assertIn("m14_capability", document["unknown"]["unavailable_sections"])
        for skill in document["skills"]:
            self.assertEqual(skill["m14_status"], "M14_REGISTRY_NOT_SUPPLIED")
            self.assertIsNone(skill["m14_capability"])

    def test_minimal_payload_locale_absent_is_not_substituted(self) -> None:
        document = self.service.get_character(NATASHA, locale="en")
        display = document["display"]
        # The minimal fixture carries no localized names at all.
        self.assertEqual(display["names"], {})
        self.assertIsNone(display["localized_name"])
        self.assertEqual(display["locale_status"], "ABSENT")
        self.assertFalse(display["locale_fallback_used"])
        self.assertEqual(sorted(display["missing_locales"]), sorted(LOCALE_VOCABULARY))

    def test_minimal_monster_reports_missing_stats_explicitly(self) -> None:
        document = self.service.get_monster(VAGRANT)
        self.assertIsNotNone(document)
        self.assertEqual(document["schema"], MONSTER_PRODUCT_SCHEMA)
        for field in MONSTER_STATIC_STAT_FIELDS:
            self.assertIn(field, document["static_stats"])
        # The minimal fixture uses different field names, so nothing is invented.
        self.assertTrue(document["unknown"]["missing_static_stats"])

    def test_unknown_monster_and_character_return_none(self) -> None:
        self.assertIsNone(self.service.get_monster(UNKNOWN_MONSTER))
        self.assertIsNone(self.service.get_character("999999"))

    def test_unsupported_locale_token_is_rejected(self) -> None:
        for locale in ("fr", "de", "", 7):
            with self.subTest(locale=locale):
                with self.assertRaises(UnknownLocaleError):
                    self.service.get_character(NATASHA, locale=locale)


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class CharacterProductTest(unittest.TestCase):
    """Section 10 acceptance fixtures."""

    @classmethod
    def setUpClass(cls) -> None:
        from hsr_battle_agent.content_support import load_registry

        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.registry = load_registry("4.4.54")
        cls.service = ContentProductService(cls.database, registry=cls.registry)
        cls.service_without_m14 = ContentProductService(cls.database)

    def test_identity(self) -> None:
        identity = self.service.get_character(NATASHA)["identity"]
        self.assertEqual(identity["avatar_id"], NATASHA)
        self.assertEqual(identity["original_game_id"], NATASHA)
        self.assertEqual(identity["game_id_status"], "PRESERVED")
        self.assertTrue(identity["entity_sha256"])

    def test_path_element_rarity(self) -> None:
        display = self.service.get_character(NATASHA)["display"]
        self.assertEqual(display["rarity"], 4)
        self.assertEqual(display["rarity_code"], "CombatPowerAvatarRarityType4")
        self.assertEqual(display["path"], "Priest")
        self.assertEqual(display["element"], "Physical")

    def test_localized_display_data(self) -> None:
        display = self.service.get_character(NATASHA)["display"]
        self.assertEqual(display["names"], {
            "en": "Natasha", "ja": "ナターシャ", "ko": "나타샤", "zh": "娜塔莎",
        })
        self.assertEqual(display["locale_status"], "MULTI")
        self.assertIsNone(display["localized_name"])
        self.assertEqual(display["missing_locales"], [])

    def test_requested_locale_semantics(self) -> None:
        cases = {"en": "Natasha", "zh": "娜塔莎", "ja": "ナターシャ", "ko": "나타샤"}
        for locale, expected in cases.items():
            with self.subTest(locale=locale):
                display = self.service.get_character(NATASHA, locale=locale)["display"]
                self.assertEqual(display["locale"], locale)
                self.assertEqual(display["locale_status"], "PRESENT")
                self.assertEqual(display["localized_name"], expected)
                self.assertFalse(display["locale_fallback_used"])

    def test_skills(self) -> None:
        skills = self.service.get_character(NATASHA)["skills"]
        self.assertEqual([entry["skill_id"] for entry in skills], [
            "110501", "110502", "110503", "110504", "110506", "110507",
        ])
        first = skills[0]
        self.assertEqual(first["name"], "仁慈的背面")
        self.assertEqual(first["sp_base"], 20)
        self.assertEqual(first["max_level"], 10)
        self.assertEqual(len(first["levels"]), 10)
        self.assertEqual(first["levels"][0]["param_list"], [0.5])

    def test_traces(self) -> None:
        traces = self.service.get_character(NATASHA)["traces"]
        self.assertEqual(len(traces), 50)
        first = traces[0]
        self.assertEqual(first["trace_id"], "1105:point01:1")
        self.assertEqual(first["point"], "point01")
        self.assertEqual(first["level"], 1)
        self.assertEqual(first["point_id"], 1105001)
        self.assertIn("pre_point", first)
        self.assertIn("status_add_list", first)
        self.assertEqual(first["max_level"], 6)
        # prerequisite structure is retained, not flattened
        self.assertTrue(any(entry["pre_point"] for entry in traces))

    def test_eidolons(self) -> None:
        eidolons = self.service.get_character(NATASHA)["eidolons"]
        self.assertEqual([entry["rank"] for entry in eidolons], [1, 2, 3, 4, 5, 6])
        self.assertEqual(eidolons[0]["eidolon_id"], "110501")
        self.assertEqual(eidolons[0]["name"], "遍识药理")
        self.assertTrue(eidolons[0]["desc"])
        self.assertEqual(eidolons[0]["param_list"], [0.3, 0.15, 400])

    def test_compatible_lightcones(self) -> None:
        equipment = self.service.get_character(NATASHA)["equipment"]
        self.assertEqual(equipment["compatible_lightcone_ids"], ["21000", "21007", "21021"])
        self.assertEqual(equipment["compatible_lightcone_count"], 3)

    def test_provenance_is_reused_not_invented(self) -> None:
        provenance = self.service.get_character(NATASHA)["provenance"]
        self.assertGreater(provenance["entity_provenance_count"], 0)
        self.assertFalse(provenance["invented_provenance"])
        self.assertTrue(all("raw_relative_path" in entry for entry in provenance["entity_provenance"]))

    def test_m14_linkage_is_verbatim(self) -> None:
        from hsr_battle_agent.content_support import get_skill

        document = self.service.get_character(NATASHA)
        self.assertEqual(document["capability"]["status"], "COMPLETE")
        self.assertEqual(document["capability"]["skills_with_m14_row"], 6)
        self.assertEqual(document["capability"]["skills_without_m14_row"], 0)
        linked = {skill["skill_id"]: skill for skill in document["skills"]}
        for skill_id in ("110501", "110506"):
            capability = get_skill(self.registry, NATASHA, skill_id)
            payload = linked[skill_id]["m14_capability"]
            self.assertEqual(payload["binding_level"], capability.binding_level.value)
            self.assertEqual(payload["support_status"], capability.support_status.value)
            self.assertEqual(payload["execution_readiness"], capability.execution_readiness)
            self.assertEqual(payload["entry_ability"], capability.entry_ability)
            self.assertEqual(payload["settlement_present"], capability.settlement_present)
            self.assertFalse(payload["recomputed_by_product_layer"])

    def test_contrasting_avatar_profile(self) -> None:
        document = self.service.get_character(HYACINE)
        display = document["display"]
        self.assertEqual(display["names"]["en"], "Hyacine")
        self.assertEqual(display["rarity"], 5)
        self.assertEqual(display["path"], "Memory")
        self.assertEqual(display["element"], "Wind")
        self.assertGreater(len(document["traces"]), 50)
        self.assertEqual(document["equipment"]["compatible_lightcone_ids"], ["23042", "24005"])
        self.assertTrue(document["memosprite"]["present"])
        self.assertEqual(document["memosprite"]["m14_coverage"], "NOT_COVERED_BY_AVATAR_SKILL_M14_LINKAGE")

    def test_missing_capability_stays_explicit(self) -> None:
        document = self.service.get_character(RIN_TOHSAKA)
        self.assertEqual(document["capability"]["status"], "NONE")
        self.assertEqual(document["capability"]["skills_with_m14_row"], 0)
        self.assertEqual(document["capability"]["skills_without_m14_row"], len(document["skills"]))
        self.assertEqual(
            document["unknown"]["static_skills_without_m14_row"],
            [skill["skill_id"] for skill in document["skills"]],
        )
        self.assertTrue(all(skill["m14_status"] == "NO_M14_ROW" for skill in document["skills"]))
        self.assertTrue(all(skill["m14_capability"] is None for skill in document["skills"]))
        self.assertFalse(document["capability"]["execution_claimed"])

    def test_without_m14_authority_linkage_is_explicitly_unknown(self) -> None:
        document = self.service_without_m14.get_character(NATASHA)
        capability = document["capability"]
        self.assertFalse(capability["registry_loaded"])
        self.assertFalse(capability["counts_available"])
        self.assertEqual(capability["status"], "M14_REGISTRY_NOT_SUPPLIED")
        self.assertIsNone(capability["skills_with_m14_row"])
        self.assertIsNone(capability["skills_without_m14_row"])
        self.assertIsNone(document["unknown"]["static_skills_without_m14_row"])

    def test_deterministic_output(self) -> None:
        first = self.service.get_character(NATASHA)
        second = self.service.get_character(NATASHA)
        self.assertEqual(first["product_sha256"], second["product_sha256"])
        self.assertEqual(
            first["product_sha256"],
            ContentProductService(self.database, registry=self.registry)
            .get_character(NATASHA)["product_sha256"],
        )

    def test_output_is_copy_isolated(self) -> None:
        first = self.service.get_character(NATASHA)
        second = self.service.get_character(NATASHA)
        self.assertIsNot(first, second)
        self.assertIsNot(first["identity"], second["identity"])
        first["identity"]["avatar_id"] = "tampered"
        first["skills"][0]["name"] = "tampered"
        fresh = self.service.get_character(NATASHA)
        self.assertEqual(fresh["identity"]["avatar_id"], NATASHA)
        self.assertNotEqual(fresh["skills"][0]["name"], "tampered")


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class MonsterProductTest(unittest.TestCase):
    """Section 11 acceptance fixtures A-H."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.service = ContentProductService(cls.database)

    def test_a_canonical_monster(self) -> None:
        document = self.service.get_monster(VAGRANT)
        identity = document["identity"]
        self.assertEqual(document["schema"], MONSTER_PRODUCT_SCHEMA)
        self.assertEqual(identity["requested_id"], VAGRANT)
        self.assertEqual(identity["resolved_kind"], "MONSTER")
        self.assertEqual(identity["canonical_monster_id"], VAGRANT)
        self.assertIsNone(identity["variant_id"])
        self.assertEqual(document["static_stats_basis"], "SELF")
        self.assertEqual(document["display"]["names"]["en"], "Vagrant")
        self.assertEqual(document["display"]["rank"], "MinionLv2")

    def test_b_variant_only_id_is_resolved_and_preserved(self) -> None:
        document = self.service.get_monster(VAGRANT_VARIANT)
        identity = document["identity"]
        self.assertEqual(identity["requested_id"], VAGRANT_VARIANT)
        self.assertEqual(identity["resolved_kind"], "MONSTER_VARIANT")
        self.assertEqual(identity["canonical_monster_id"], VAGRANT)
        self.assertEqual(identity["variant_id"], VAGRANT_VARIANT)
        # The requested variant ID is never normalised away into the parent.
        self.assertNotEqual(identity["requested_id"], identity["canonical_monster_id"])
        self.assertEqual(document["static_stats_basis"], "CANONICAL_PARENT")
        self.assertEqual(document["static_stats_source_monster_id"], VAGRANT)
        self.assertEqual(document["display"]["names_source"], "CANONICAL_PARENT")

    def test_c_unknown_id_returns_none(self) -> None:
        self.assertIsNone(self.service.get_monster(UNKNOWN_MONSTER))
        self.assertIsNone(self.service.get_monster("not-a-monster"))

    def test_d_weakness_and_resistance(self) -> None:
        document = self.service.get_monster(VAGRANT)
        descriptors = document["combat_descriptors"]
        self.assertEqual(descriptors["weaknesses"], ["Fire", "Ice", "Imaginary"])
        self.assertEqual(descriptors["weaknesses_source"], "SELF_COLLECTION")
        self.assertTrue(descriptors["damage_type_resistance"])
        self.assertTrue(all(
            set(entry) == {"damage_type", "value"} for entry in descriptors["damage_type_resistance"]
        ))
        variant = self.service.get_monster(VAGRANT_VARIANT)
        self.assertEqual(
            variant["combat_descriptors"]["weaknesses"], ["Fire", "Ice", "Quantum", "Imaginary"],
        )
        self.assertEqual(variant["combat_descriptors"]["weaknesses_source"], "VARIANT_STANCE_WEAK_LIST")

    def test_e_multiple_static_skill_references(self) -> None:
        document = self.service.get_monster(VAGRANT)
        skill_ids = [entry["skill_id"] for entry in document["skills"]]
        self.assertEqual(skill_ids, ["100202001", "100202002"])
        self.assertEqual(document["skills"][0]["skill_name"], "铲击")
        self.assertEqual(document["skills"][0]["damage_type"], "Physical")
        self.assertEqual(document["skills"][0]["sp_hit_base"], 10)

    def test_f_explicit_placement_level_and_formation(self) -> None:
        document = self.service.get_monster(
            VAGRANT_VARIANT, level=80, formation={"group_index": 0, "slot": "monster1"},
        )
        self.assertEqual(document["context"]["level"], 80)
        self.assertEqual(document["context"]["level_source"], "CALLER")
        self.assertEqual(document["context"]["formation"], {"group_index": 0, "slot": "monster1"})

    def test_g_no_level_supplied(self) -> None:
        document = self.service.get_monster(VAGRANT_VARIANT)
        self.assertIsNone(document["context"]["level"])
        self.assertEqual(document["context"]["level_source"], "NOT_SUPPLIED")
        self.assertIsNone(document["context"]["formation"])
        self.assertIn("never stored on the base Monster record", document["context"]["note"])

    def test_h_deterministic_projection(self) -> None:
        self.assertEqual(
            self.service.get_monster(VAGRANT)["product_sha256"],
            ContentProductService(self.database).get_monster(VAGRANT)["product_sha256"],
        )
        self.assertEqual(
            self.service.get_monster(VAGRANT_VARIANT, level=80)["product_sha256"],
            self.service.get_monster(VAGRANT_VARIANT, level=80)["product_sha256"],
        )
        self.assertNotEqual(
            self.service.get_monster(VAGRANT_VARIANT, level=80)["product_sha256"],
            self.service.get_monster(VAGRANT_VARIANT, level=81)["product_sha256"],
        )

    def test_static_stats_are_complete_and_typed(self) -> None:
        stats = self.service.get_monster(VAGRANT)["static_stats"]
        self.assertEqual(set(stats), set(MONSTER_STATIC_STAT_FIELDS))
        self.assertEqual(stats["hp_base"], 139.5)
        self.assertEqual(stats["attack_base"], 18)
        self.assertEqual(stats["defence_base"], 210)
        self.assertEqual(stats["speed_base"], 100)
        self.assertEqual(stats["critical_damage_base"], 0.2)
        self.assertEqual(stats["stance_base"], 60)
        self.assertEqual(stats["stance_count"], 1)
        self.assertEqual(stats["status_resistance_base"], 0.1)
        self.assertEqual(stats["initial_delay_ratio"], 1)
        self.assertEqual(stats["minimum_fatigue_ratio"], 0.2)
        self.assertEqual(self.service.get_monster(VAGRANT)["unknown"]["missing_static_stats"], [])

    def test_variant_descriptors_keep_static_identity(self) -> None:
        identifiers = [
            entry["variant_id"] for entry in self.service.get_monster(VAGRANT)["variant_descriptors"]
        ]
        self.assertIn(VAGRANT, identifiers)  # the base self-variant descriptor
        self.assertIn(VAGRANT_VARIANT, identifiers)
        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_runtime_support_is_family_level_only(self) -> None:
        document = self.service.get_monster(VAGRANT)
        self.assertEqual(document["runtime_support"], MONSTER_RUNTIME_SUPPORT)
        self.assertEqual(document["runtime_support"]["evidence_scope"], "FAMILY_LEVEL_ONLY")
        for field in ("monster_ai", "monster_skill_execution", "phase_or_body_part_runtime"):
            self.assertEqual(document["runtime_support"][field], "NOT_SUPPLIED_BY_THIS_PRODUCT")
        self.assertFalse(document["runtime_semantics_added"])

    def test_provenance_is_reused_not_invented(self) -> None:
        provenance = self.service.get_monster(VAGRANT)["provenance"]
        self.assertGreater(provenance["entity_provenance_count"], 0)
        self.assertFalse(provenance["invented_provenance"])


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class EnumerationTest(unittest.TestCase):
    """Section 5 -- deterministic enumeration (closing the relevant part of F8)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.service = ContentProductService(cls.database)

    def test_character_enumeration(self) -> None:
        rows = self.service.list_characters(locale="en")
        self.assertEqual(len(rows), 97)
        self.assertEqual(rows[0]["avatar_id"], "1001")
        self.assertEqual(rows[-1]["avatar_id"], "8010")
        for row in rows:
            self.assertEqual(
                set(row),
                {"schema", "game_version", "avatar_id", "names", "localized_name",
                 "locale", "locale_status", "rarity", "rarity_code", "path", "element"},
            )
            self.assertEqual(row["game_version"], "4.4.54")
            self.assertTrue(row["localized_name"])
            self.assertIsInstance(row["rarity"], int)
            self.assertTrue(row["path"])
            self.assertTrue(row["element"])

    def test_monster_enumeration(self) -> None:
        rows = self.service.list_monsters(locale="en")
        self.assertEqual(len(rows), 628)
        for row in rows:
            self.assertEqual(
                set(row),
                {"schema", "game_version", "monster_id", "names", "localized_name",
                 "locale", "locale_status", "rank", "monster_camp_id", "weaknesses",
                 "variant_count", "declared_child_count"},
            )
            self.assertEqual(row["game_version"], "4.4.54")
            self.assertGreaterEqual(row["declared_child_count"], 1)
            self.assertGreaterEqual(row["variant_count"], 0)

    def test_enumeration_is_stable_and_deterministic(self) -> None:
        first = self.service.list_characters()
        second = ContentProductService(self.database).list_characters()
        self.assertEqual(first, second)
        self.assertEqual(self.service.list_monsters(), ContentProductService(self.database).list_monsters())

    def test_enumeration_locale_selection(self) -> None:
        english = {row["avatar_id"]: row["localized_name"] for row in self.service.list_characters(locale="en")}
        chinese = {row["avatar_id"]: row["localized_name"] for row in self.service.list_characters(locale="zh")}
        self.assertEqual(english[NATASHA], "Natasha")
        self.assertEqual(chinese[NATASHA], "娜塔莎")
        with self.assertRaises(UnknownLocaleError):
            self.service.list_characters(locale="fr")

    def test_variant_count_matches_the_declared_child_list(self) -> None:
        rows = {row["monster_id"]: row for row in self.service.list_monsters()}
        row = rows[VAGRANT]
        self.assertEqual(row["declared_child_count"], 21)
        self.assertEqual(row["variant_count"], 20)  # excludes the base self identity

    def test_no_latest_version_resolution(self) -> None:
        # The version is fixed by the explicitly versioned database; the service
        # exposes no version parameter and no "latest" fallback anywhere.
        self.assertEqual(self.service.game_version, "4.4.54")
        import inspect

        for name in ("list_characters", "list_monsters", "get_character", "get_monster"):
            parameters = inspect.signature(getattr(self.service, name)).parameters
            self.assertNotIn("version", parameters)
            self.assertNotIn("content_version", parameters)


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class ProductCensusTest(unittest.TestCase):
    """Section 17 -- cheap product census, not execution coverage."""

    @classmethod
    def setUpClass(cls) -> None:
        from hsr_battle_agent.content_support import load_registry

        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.service = ContentProductService(cls.database, registry=load_registry("4.4.54"))

    @staticmethod
    def _variant_ids() -> list[str]:
        connection = sqlite3.connect(LOCAL_DATABASE)
        try:
            return sorted(
                str(row[0]) for row in connection.execute(
                    "SELECT entity_id FROM monster_variants WHERE game_version='4.4.54'"
                )
            )
        finally:
            connection.close()

    def test_every_character_projects(self) -> None:
        failures = []
        without_m14 = 0
        for row in self.service.list_characters():
            document = self.service.get_character(row["avatar_id"])
            if document is None:
                failures.append(row["avatar_id"])
                continue
            self.assertEqual(document["product_sha256"], self.service.get_character(row["avatar_id"])["product_sha256"])
            without_m14 += len(document["unknown"]["static_skills_without_m14_row"] or [])
        self.assertEqual(failures, [])
        self.assertEqual(without_m14, 44)

    def test_every_monster_and_variant_projects(self) -> None:
        character_failures = []
        for row in self.service.list_monsters():
            if self.service.get_monster(row["monster_id"]) is None:
                character_failures.append(row["monster_id"])
        self.assertEqual(character_failures, [])

        variant_failures = []
        for variant_id in self._variant_ids():
            document = self.service.get_monster(variant_id)
            if document is None or document["identity"]["requested_id"] != variant_id:
                variant_failures.append(variant_id)
        self.assertEqual(variant_failures, [])


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class StaticBoundaryTest(unittest.TestCase):
    """Sections 12/13 -- static product packaging only."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.service = ContentProductService(cls.database)

    def test_no_runtime_artifact_keys(self) -> None:
        for document in (
            self.service.get_character(NATASHA),
            self.service.get_monster(VAGRANT),
            self.service.get_monster(VAGRANT_VARIANT),
        ):
            keys = set(_walk_keys(document))
            for forbidden in FORBIDDEN_DOCUMENT_KEYS:
                self.assertNotIn(forbidden, keys)
            self.assertFalse(document["runtime_semantics_added"])

    def test_module_does_not_import_execution_layers(self) -> None:
        import ast

        tree = ast.parse(PRODUCT_SOURCE)
        module_level = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                module_level.add(node.module)
            elif isinstance(node, ast.Import):
                module_level.update(alias.name for alias in node.names)
        self.assertEqual(module_level, {"__future__", "copy", "typing", "nanoka_content"})
        # No import anywhere in the file may reach an execution/planner layer.
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                for token in FORBIDDEN_SOURCE_TOKENS:
                    self.assertNotIn(token, name, name)

    def test_m14_dependency_is_lazy_and_explicit(self) -> None:
        # The content_support import exists, but only inside a function, so the
        # static module-level import graph keeps game_data independent of it.
        hits = [
            line for line in PRODUCT_SOURCE.splitlines()
            if "from hsr_battle_agent.content_support import get_avatar_skills" in line
        ]
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0].startswith("        "), hits[0])

    def test_frozen_layers_are_untouched_by_this_module(self) -> None:
        # The product layer only ever imported the canonical content facade and
        # (lazily, when a registry is supplied) the public content_support API.
        self.assertIn("from .nanoka_content import ContentDatabase, stable_hash", PRODUCT_SOURCE)
        self.assertIn("content_support.get_avatar_skills", PRODUCT_SOURCE)

    def test_summary_and_product_schemas_are_declared(self) -> None:
        self.assertEqual(CHARACTER_PRODUCT_SCHEMA, "hsr_battle_agent.character_product/1")
        self.assertEqual(MONSTER_PRODUCT_SCHEMA, "hsr_battle_agent.monster_product/1")
        self.assertEqual(self.service.list_characters()[0]["schema"], "hsr_battle_agent.character_summary/1")
        self.assertEqual(self.service.list_monsters()[0]["schema"], "hsr_battle_agent.monster_summary/1")


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class M14ExecutionEligibilityTest(unittest.TestCase):
    """Finding 1 -- eligibility is the authoritative M14 result, never inferred."""

    @classmethod
    def setUpClass(cls) -> None:
        from hsr_battle_agent.content_support import load_registry

        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.registry = load_registry("4.4.54")
        cls.service = ContentProductService(cls.database, registry=cls.registry)
        cls.service_without_m14 = ContentProductService(cls.database)

    def test_linked_skill_carries_the_authoritative_eligibility(self) -> None:
        from hsr_battle_agent.content_support import real_content_execution_eligibility

        document = self.service.get_character(NATASHA)
        self.assertTrue(all(skill["m14_status"] == "LINKED" for skill in document["skills"]))
        for skill in document["skills"]:
            with self.subTest(skill=skill["skill_id"]):
                authoritative = real_content_execution_eligibility(
                    self.registry, NATASHA, skill["skill_id"],
                )
                payload = skill["m14_execution_eligibility"]
                self.assertIsNotNone(payload)
                self.assertEqual(payload["outcome"], authoritative.outcome.value)
                self.assertEqual(payload["reason_code"], authoritative.reason_code)
                self.assertEqual(payload["reason_detail"], authoritative.reason_detail)
                self.assertEqual(
                    payload["execution_evidence_mode"], authoritative.execution_evidence_mode.value,
                )
                self.assertEqual(
                    payload["representation_evidence_mode"],
                    authoritative.representation_evidence_mode.value,
                )
                self.assertEqual(
                    payload["satisfies_gate_certificate"], authoritative.satisfies_gate_certificate,
                )
                self.assertEqual(
                    payload["satisfies_native_evidenced"], authoritative.satisfies_native_evidenced,
                )
                self.assertEqual(payload["content_version"], self.service.game_version)
                self.assertEqual(
                    payload["authority"],
                    "content_support.real_content_execution_eligibility (M14)",
                )
                self.assertFalse(payload["recomputed_by_product_layer"])

    def test_eligibility_is_never_inferred_from_other_fields(self) -> None:
        for skill in self.service.get_character(NATASHA)["skills"]:
            payload = skill["m14_execution_eligibility"]
            # The four named non-sources must not appear in the eligibility record.
            for not_a_source in (
                "execution_readiness", "support_status", "binding_level", "settlement_present",
            ):
                self.assertNotIn(not_a_source, payload, not_a_source)

    def test_eligibility_vocabulary_is_the_canonical_machine_vocabulary(self) -> None:
        document = self.service.get_character(NATASHA)
        outcomes = {skill["m14_execution_eligibility"]["outcome"] for skill in document["skills"]}
        self.assertEqual(outcomes, {"NOT_ELIGIBLE"})
        self.assertEqual(document["capability"]["execution_eligibility_outcomes"], ["NOT_ELIGIBLE"])
        self.assertEqual(
            document["capability"]["execution_eligibility_source"],
            "content_support.real_content_execution_eligibility",
        )
        self.assertEqual(
            document["capability"]["skills_with_execution_eligibility"], len(document["skills"]),
        )
        self.assertTrue(document["capability"]["execution_eligibility_available"])

    def test_no_m14_row_has_no_fabricated_eligibility(self) -> None:
        document = self.service.get_character(RIN_TOHSAKA)
        self.assertTrue(all(skill["m14_status"] == "NO_M14_ROW" for skill in document["skills"]))
        self.assertTrue(all(skill["m14_execution_eligibility"] is None for skill in document["skills"]))
        self.assertEqual(
            document["unknown"]["skills_without_execution_eligibility"],
            [skill["skill_id"] for skill in document["skills"]],
        )
        self.assertEqual(document["capability"]["skills_with_execution_eligibility"], 0)

    def test_no_registry_supplied_has_no_fabricated_eligibility(self) -> None:
        document = self.service_without_m14.get_character(NATASHA)
        self.assertTrue(all(skill["m14_execution_eligibility"] is None for skill in document["skills"]))
        self.assertFalse(document["capability"]["execution_eligibility_available"])
        self.assertIsNone(document["capability"]["skills_with_execution_eligibility"])
        self.assertEqual(document["capability"]["execution_eligibility_outcomes"], [])
        self.assertFalse(document["unknown"]["execution_eligibility_available"])

    def test_product_never_derives_eligibility_itself(self) -> None:
        """A spy that substitutes M14's answer proves the product only copies it."""
        from hsr_battle_agent.content_support import (
            EvidenceMode, ExecutionEligibility, ExecutionEligibilityOutcome, get_skill,
        )

        spy_reason = "SPY_REASON_SUPPLIED_BY_M14"

        def spy(registry, avatar_id, skill_id=None):
            capability = get_skill(registry, avatar_id, skill_id)
            return ExecutionEligibility(
                key=capability.key,
                outcome=ExecutionEligibilityOutcome.NOT_ELIGIBLE,
                reason_code=spy_reason,
                reason_detail="supplied by the M14 spy, not computed by the product layer",
                execution_evidence_mode=EvidenceMode.UNSUPPORTED,
                representation_evidence_mode=EvidenceMode.REFERENCE_MODEL,
            )

        with mock.patch(
            "hsr_battle_agent.content_support.real_content_execution_eligibility", spy,
        ):
            document = self.service.get_character(NATASHA)
        for skill in document["skills"]:
            payload = skill["m14_execution_eligibility"]
            self.assertEqual(payload["reason_code"], spy_reason)
            self.assertEqual(
                payload["reason_detail"], "supplied by the M14 spy, not computed by the product layer",
            )


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class M14VersionCoherenceTest(unittest.TestCase):
    """Finding 2 -- mixed versions fail closed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")

    def test_registry_version_mismatch_fails_closed(self) -> None:
        with self.assertRaises(ContentProductError) as context:
            ContentProductService(self.database, registry=_fake_registry("4.4.55", []))
        self.assertIn("mixed-version", str(context.exception))

    def test_real_registry_against_other_database_version_fails_closed(self) -> None:
        from hsr_battle_agent.content_support import load_registry

        other = ContentDatabase(LOCAL_DATABASE, "4.4.55")
        with self.assertRaises(ContentProductError):
            ContentProductService(other, registry=load_registry("4.4.54"))

    def test_matching_registry_version_is_accepted(self) -> None:
        service = ContentProductService(self.database, registry=_fake_registry("4.4.54", []))
        self.assertTrue(service.m14_registry_supplied)
        self.assertEqual(service.game_version, "4.4.54")

    def test_capability_version_mismatch_fails_closed(self) -> None:
        registry = _fake_registry("4.4.54", [
            _fake_capability_record(avatar_id=NATASHA, skill_id="110501", content_version="4.4.55"),
        ])
        service = ContentProductService(self.database, registry=registry)
        with self.assertRaises(ContentProductError) as context:
            service.get_character(NATASHA)
        self.assertIn("content_version", str(context.exception))

    def test_matching_capability_version_is_accepted(self) -> None:
        registry = _fake_registry("4.4.54", [
            _fake_capability_record(avatar_id=NATASHA, skill_id="110501", content_version="4.4.54"),
        ])
        document = ContentProductService(self.database, registry=registry).get_character(NATASHA)
        linked = [skill for skill in document["skills"] if skill["m14_status"] == "LINKED"]
        self.assertEqual([skill["skill_id"] for skill in linked], ["110501"])
        self.assertEqual(
            linked[0]["m14_execution_eligibility"]["content_version"], self.database.game_version,
        )

    def test_no_bypass_seam_exists(self) -> None:
        import inspect

        parameters = inspect.signature(ContentProductService.__init__).parameters
        self.assertEqual(list(parameters), ["self", "database", "registry"])
        self.assertNotIn("skill_capability_lookup", PRODUCT_SOURCE)


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class EnumerationBoundaryTest(unittest.TestCase):
    """Finding 4 -- enumeration authority lives in ContentDatabase."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")

    def test_product_service_source_contains_no_sql_or_storage_schema(self) -> None:
        self.assertNotIn("sqlite3", PRODUCT_SOURCE)
        self.assertNotIn("database_path", PRODUCT_SOURCE)
        for keyword in ("SELECT", "FROM", "WHERE", "INSERT", "CREATE", "ORDER BY"):
            self.assertNotIn(keyword, PRODUCT_SOURCE, keyword)
        for table in ("avatars", "monsters"):
            self.assertNotIn(f'"{table}"', PRODUCT_SOURCE, table)

    def test_facade_exposes_narrow_enumeration_apis(self) -> None:
        ids = self.database.list_avatar_ids()
        self.assertEqual(len(ids), 97)
        self.assertEqual(ids, self.database.list_avatar_ids())
        self.assertEqual(ids[0], "1001")
        self.assertEqual(ids[-1], "8010")
        monsters = self.database.list_monster_ids()
        self.assertEqual(len(monsters), 628)
        self.assertEqual(monsters, self.database.list_monster_ids())
        self.assertEqual(monsters[0], "1002011")
        # No generic table-name API is exposed.
        self.assertFalse(hasattr(self.database, "list_entity_ids"))

    def test_facade_enumeration_is_version_scoped(self) -> None:
        other = ContentDatabase(LOCAL_DATABASE, "4.4.55")
        self.assertEqual(other.list_avatar_ids(), [])
        self.assertEqual(other.list_monster_ids(), [])

    def test_facade_refuses_non_enumerable_tables(self) -> None:
        from hsr_battle_agent.game_data.nanoka_content import ContentDatabaseError

        # P3 widened the allow-list to stages/encounters, but it stays narrow:
        # a table outside it is still refused.
        with self.assertRaises(ContentDatabaseError):
            self.database._entity_ids("waves")
        for expected in ("avatars", "monsters", "stages", "encounters"):
            self.assertIn(expected, self.database.ENUMERABLE_ENTITY_TABLES)
        self.assertEqual(self.database.ENUMERABLE_ENTITY_TABLES, ("avatars", "monsters", "stages", "encounters"))

    def test_service_consumes_the_facade_methods(self) -> None:
        service = ContentProductService(self.database)
        with mock.patch.object(self.database, "list_avatar_ids", return_value=[NATASHA]) as avatars:
            rows = service.list_characters()
        self.assertEqual([row["avatar_id"] for row in rows], [NATASHA])
        avatars.assert_called_once()
        with mock.patch.object(self.database, "list_monster_ids", return_value=[VAGRANT]) as monsters:
            rows = service.list_monsters()
        self.assertEqual([row["monster_id"] for row in rows], [VAGRANT])
        monsters.assert_called_once()


@unittest.skipUnless(LOCAL_DATABASE.is_file(), "local 4.4.54 content database is not present")
class MonsterVariantProvenanceTest(unittest.TestCase):
    """Finding 3 -- variant products retain both provenances separately."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = ContentDatabase(LOCAL_DATABASE, "4.4.54")
        cls.service = ContentProductService(cls.database)

    def test_canonical_monster_has_a_single_self_source(self) -> None:
        provenance = self.service.get_monster(VAGRANT)["provenance"]
        self.assertEqual([source["role"] for source in provenance["sources"]], ["SELF"])
        source = provenance["sources"][0]
        self.assertEqual(source["entity_id"], VAGRANT)
        self.assertTrue(source["entity_sha256"])
        self.assertGreater(source["provenance_count"], 0)
        self.assertFalse(provenance["parent_provenance_available"])
        self.assertFalse(provenance["invented_provenance"])
        self.assertGreater(provenance["entity_provenance_count"], 0)

    def test_variant_retains_requested_and_parent_provenance(self) -> None:
        provenance = self.service.get_monster(VAGRANT_VARIANT)["provenance"]
        self.assertEqual(
            [source["role"] for source in provenance["sources"]],
            ["REQUESTED_ENTITY", "CANONICAL_PARENT"],
        )
        requested, parent = provenance["sources"]
        self.assertEqual(requested["entity_id"], VAGRANT_VARIANT)
        self.assertEqual(parent["entity_id"], VAGRANT)
        self.assertTrue(requested["entity_sha256"])
        self.assertTrue(parent["entity_sha256"])
        self.assertNotEqual(requested["entity_sha256"], parent["entity_sha256"])
        self.assertEqual(
            parent["entity_sha256"],
            self.database.get_monster(VAGRANT)["canonical_sha256"],
        )
        self.assertEqual(
            provenance["entity_provenance_count"],
            requested["provenance_count"] + parent["provenance_count"],
        )
        self.assertTrue(provenance["parent_provenance_available"])
        self.assertFalse(provenance["invented_provenance"])

    def test_parent_and_variant_provenance_entries_are_distinct(self) -> None:
        provenance = self.service.get_monster(VAGRANT_VARIANT)["provenance"]
        requested, parent = provenance["sources"]
        self.assertNotEqual(requested["provenance"], parent["provenance"])
        self.assertTrue(all("raw_relative_path" in entry for entry in parent["provenance"]))

    def test_parent_backed_fields_declare_their_source(self) -> None:
        variant_sources = self.service.get_monster(VAGRANT_VARIANT)["provenance"]["field_sources"]
        self.assertEqual(variant_sources["identity"], "REQUESTED_ENTITY")
        self.assertEqual(variant_sources["static_stats"], "CANONICAL_PARENT")
        self.assertEqual(variant_sources["display.names"], "CANONICAL_PARENT")
        self.assertEqual(variant_sources["display.rank"], "CANONICAL_PARENT")
        self.assertEqual(variant_sources["combat_descriptors.rank"], "CANONICAL_PARENT")
        self.assertEqual(variant_sources["combat_descriptors.monster_camp_id"], "CANONICAL_PARENT")
        self.assertEqual(variant_sources["combat_descriptors.weaknesses"], "VARIANT_STANCE_WEAK_LIST")
        self.assertEqual(variant_sources["combat_descriptors.damage_type_resistance"], "REQUESTED_VARIANT_RECORD")
        self.assertEqual(variant_sources["skills"], "REQUESTED_VARIANT_RECORD")

        canonical_sources = self.service.get_monster(VAGRANT)["provenance"]["field_sources"]
        self.assertEqual(canonical_sources["static_stats"], "SELF")
        self.assertEqual(canonical_sources["display.names"], "SELF")
        self.assertEqual(canonical_sources["combat_descriptors.weaknesses"], "SELF_COLLECTION")
        self.assertEqual(canonical_sources["skills"], "SELF_CHILD_DESCRIPTOR")

    def test_stats_and_display_sources_match_the_declared_map(self) -> None:
        document = self.service.get_monster(VAGRANT_VARIANT)
        sources = document["provenance"]["field_sources"]
        self.assertEqual(document["static_stats_basis"], sources["static_stats"])
        self.assertEqual(document["display"]["names_source"], sources["display.names"])
        self.assertEqual(document["static_stats_source_monster_id"], VAGRANT)

    def test_unproven_parent_is_not_fabricated(self) -> None:
        original = self.database.resolve_monster

        def unproven(monster_id):
            resolution = original(monster_id)
            if resolution is not None and str(monster_id) == VAGRANT_VARIANT:
                resolution = dict(resolution)
                resolution["canonical_monster_id"] = None
            return resolution

        with mock.patch.object(self.database, "resolve_monster", side_effect=unproven):
            document = self.service.get_monster(VAGRANT_VARIANT)
        provenance = document["provenance"]
        self.assertEqual([source["role"] for source in provenance["sources"]], ["REQUESTED_ENTITY"])
        self.assertFalse(provenance["parent_provenance_available"])
        self.assertFalse(provenance["invented_provenance"])
        self.assertIsNone(document["identity"]["canonical_monster_id"])
        self.assertFalse(document["identity"]["parent_resolved"])


if __name__ == "__main__":
    unittest.main()
