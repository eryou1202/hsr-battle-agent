"""P5A static product transport. Public P2/P3/P4 documents remain authority.

No registry loading, storage queries, policy evaluation or Scenario compilation
is implemented here. Versions and dependencies are always supplied by callers.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from hsr_battle_agent.game_data.content_product import ContentProductService
from hsr_battle_agent.game_data.nanoka_content import ContentDatabase
from hsr_battle_agent.product_support import ScenarioSupportReporter

PRODUCT_CATALOG_SCHEMA = "hsr_battle_agent.fe3_product_catalog/1"
COLLECTION_SCHEMA = "hsr_battle_agent.fe3_product_collection/1"
DETAIL_INDEX_SCHEMA = "hsr_battle_agent.fe3_product_detail_index/1"
DETAIL_CHUNK_SCHEMA = "hsr_battle_agent.fe3_product_detail_chunk/1"
COLLECTIONS = ("characters", "monsters", "stages", "encounters")
PRODUCT_SCHEMAS = {
    "characters": "hsr_battle_agent.character_product/1",
    "monsters": "hsr_battle_agent.monster_product/1",
    "stages": "hsr_battle_agent.stage_product/1",
    "encounters": "hsr_battle_agent.encounter_product/1",
}
SUMMARY_SCHEMAS = {
    name: schema.replace("_product/", "_summary/")
    for name, schema in PRODUCT_SCHEMAS.items()
}
KEY_FIELDS = {"characters": "avatar_id", "monsters": "monster_id",
              "stages": "stage_id", "encounters": "encounter_id"}
REPORT_SCHEMA = "hsr_battle_agent.scenario_support_report/1"


def _version(version: str, source: Any) -> None:
    if version != "4.4.54":
        raise ValueError("EXPLICIT_4_4_54_REQUIRED")
    if source.game_version != version:
        raise ValueError("CONTENT_VERSION_MISMATCH")


def _catalog(version: str, service: ContentProductService, collection: str,
             rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    _version(version, service)
    for row in rows:
        if row["schema"] != SUMMARY_SCHEMAS[collection] or row["game_version"] != version:
            raise ValueError("INVALID_PRODUCT_SUMMARY")
    return deepcopy({"schema": COLLECTION_SCHEMA, "content_version": version,
                     "collection": collection, "row_schema": SUMMARY_SCHEMAS[collection],
                     "count": len(rows), "rows": list(rows)})


def emit_character_catalog(version: str, service: ContentProductService, *,
                           locale: str | None = None) -> dict[str, Any]:
    _version(version, service)
    return _catalog(version, service, "characters", service.list_characters(locale=locale))


def emit_monster_catalog(version: str, service: ContentProductService, *,
                         locale: str | None = None) -> dict[str, Any]:
    _version(version, service)
    return _catalog(version, service, "monsters", service.list_monsters(locale=locale))


def emit_stage_catalog(version: str, service: ContentProductService) -> dict[str, Any]:
    _version(version, service)
    return _catalog(version, service, "stages", service.list_stages(include_package_topology=False))


def emit_encounter_catalog(version: str, service: ContentProductService) -> dict[str, Any]:
    _version(version, service)
    return _catalog(version, service, "encounters", service.list_encounters())


def emit_product_catalog(version: str, service: ContentProductService, *,
                         provenance: Mapping[str, Any],
                         catalogs: Mapping[str, Mapping[str, Any]] | None = None,
                         examples: tuple[Mapping[str, Any], ...] = ()) -> dict[str, Any]:
    """Small root index; never calls a full product/detail method.

    Precomputed catalogs avoid enumerating twice during offline generation.
    Paths are relative to the versioned root, never to an implicit latest.
    """
    _version(version, service)
    if not provenance.get("starting_head") or not provenance.get("authorities"):
        raise ValueError("GENERATION_PROVENANCE_REQUIRED")
    if catalogs is None:
        catalogs = {
            "characters": emit_character_catalog(version, service),
            "monsters": emit_monster_catalog(version, service),
            "stages": emit_stage_catalog(version, service),
            "encounters": emit_encounter_catalog(version, service),
        }
    locations = {}
    for name in COLLECTIONS:
        catalog = catalogs[name]
        if (catalog["schema"] != COLLECTION_SCHEMA or catalog["collection"] != name
                or catalog["content_version"] != version
                or catalog["row_schema"] != SUMMARY_SCHEMAS[name]
                or catalog["count"] != len(catalog["rows"])):
            raise ValueError("INVALID_PRODUCT_COLLECTION")
        locations[name] = {
            "catalog_location": f"{name}/catalog.json",
            "detail_index_location": f"{name}/detail-index.json",
            "key_field": KEY_FIELDS[name], "summary_schema": SUMMARY_SCHEMAS[name],
            "document_schema": PRODUCT_SCHEMAS[name],
        }
    return deepcopy({
        "schema": PRODUCT_CATALOG_SCHEMA, "content_version": version,
        "available_collections": list(COLLECTIONS),
        "counts": {name: catalogs[name]["count"] for name in COLLECTIONS},
        "collections": locations,
        "document_schemas": {**PRODUCT_SCHEMAS, "scenario_support_report": REPORT_SCHEMA},
        "generation_provenance": dict(provenance),
        "version_fallback": "NONE", "dynamic_backend_connected": False,
        "scenario_compilation": "NOT_CONNECTED",
        "detail_transport": "ON_DEMAND_INDEXED_CHUNKS",
        "example_support_reports": list(examples),
    })


def _detail(version: str, service: ContentProductService, collection: str,
            document: dict[str, Any] | None) -> dict[str, Any]:
    _version(version, service)
    if document is None:
        raise LookupError("PRODUCT_NOT_FOUND")
    if document["schema"] != PRODUCT_SCHEMAS[collection] or document["game_version"] != version:
        raise ValueError("INVALID_PRODUCT_DOCUMENT")
    return deepcopy(document)


def emit_character_detail(version: str, service: ContentProductService, avatar_id: str, *,
                          locale: str | None = None) -> dict[str, Any]:
    _version(version, service)
    return _detail(version, service, "characters", service.get_character(avatar_id, locale=locale))


def emit_monster_detail(version: str, service: ContentProductService, monster_id: str, *,
                        locale: str | None = None, level: int | None = None,
                        formation: Mapping[str, Any] | None = None) -> dict[str, Any]:
    _version(version, service)
    return _detail(version, service, "monsters", service.get_monster(
        monster_id, locale=locale, level=level, formation=formation))


def emit_stage_detail(version: str, service: ContentProductService, stage_id: str) -> dict[str, Any]:
    _version(version, service)
    return _detail(version, service, "stages", service.get_stage(stage_id))


def emit_encounter_detail(version: str, service: ContentProductService, encounter_id: str) -> dict[str, Any]:
    _version(version, service)
    return _detail(version, service, "encounters", service.get_encounter(encounter_id))


def emit_scenario_support_report(version: str, database: ContentDatabase,
                                 scenario_package: Mapping[str, Any], *, registry: Any) -> dict[str, Any]:
    """Require an existing valid ScenarioPackage/2 and explicit M14 registry.

    P4 performs input validation and all aggregation; its result is untouched.
    """
    _version(version, database)
    return ScenarioSupportReporter(database, registry=registry).build(scenario_package)
