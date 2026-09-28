"""Deterministic read-only Character / Monster product projections.

CR-P2-CONTENT-PRODUCT-PROJECTION-20260928-001.

This module turns the existing 4.4.54 static Avatar and Monster records into
stable, product-facing read-only documents for a later Character Library,
Monster Library, Team Builder and Scenario Builder.  It is *product packaging*,
never runtime reconstruction:

* it executes no behavior IR;
* it implements no Monster AI, and makes no per-monster readiness claim;
* it re-derives **nothing** about M14 policy (binding level, support status,
  readiness, blocker classes, reentry hints, execution eligibility are copied
  verbatim from ``content_support`` when a registry is supplied);
* it reads no M13 registry JSON -- M14 is the only content-interpretation
  authority it consults.

Representation policy (stated explicitly so nothing is implied)
--------------------------------------------------------------

Documents are **plain dict documents** carrying a stable ``schema`` string and
a stable ``product_sha256``, and they are **copy-isolated** before being
returned.  Immutable product typing is deliberately *not* claimed and is
deferred, matching the game_data product layer convention (``stage_package/1``,
``scenario_package/2``).  See the P2 control artifact for the full rationale.

M14 dependency
--------------

The service never loads a registry implicitly and never resolves a "latest"
version.  Exactly one explicit ``content_support`` registry may be supplied, and
its ``content_version`` must equal the database version or construction fails
closed; every capability is re-checked against the service version at call time.
With no registry, the character document says so explicitly
(``capability.registry_loaded = false``) and both the capability and the
execution-eligibility fields stay ``null`` rather than being invented.  The M14
import is resolved lazily at call time so the static module-level import graph
keeps ``game_data`` independent of the content-support layer.

M14 is the sole authority for ``binding_level`` / ``support_status`` /
``readiness`` / ``blocker classes`` / ``reentry hints`` / execution eligibility.
Every one of those values is copied verbatim from the public M14 API; none is
recomputed or inferred here.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .nanoka_content import ContentDatabase, stable_hash


class ContentProductError(ValueError):
    """A product projection could not be produced without inventing a fact."""


class UnknownLocaleError(ContentProductError):
    """The caller asked for a locale outside the observed data vocabulary."""


#: Product document schemas.
CHARACTER_PRODUCT_SCHEMA = "hsr_battle_agent.character_product/1"
MONSTER_PRODUCT_SCHEMA = "hsr_battle_agent.monster_product/1"

#: The exact locale vocabulary observed in the 4.4.54 canonical records
#: (the ``collection`` block of both avatars and monsters carries these keys).
LOCALE_VOCABULARY = ("en", "ja", "ko", "zh")

#: There is deliberately no backend default locale: ``None`` means "return every
#: available locale".  A caller-supplied locale is never silently substituted.
DEFAULT_LOCALE = None

#: Monster runtime support is family-level only.  This product supplies static
#: packaging, and says so explicitly rather than implying execution.
MONSTER_RUNTIME_SUPPORT = {
    "evidence_scope": "FAMILY_LEVEL_ONLY",
    "per_entity_readiness_claim": "NONE",
    "monster_ai": "NOT_SUPPLIED_BY_THIS_PRODUCT",
    "monster_skill_execution": "NOT_SUPPLIED_BY_THIS_PRODUCT",
    "phase_or_body_part_runtime": "NOT_SUPPLIED_BY_THIS_PRODUCT",
    "battle_state_construction": "NOT_SUPPLIED_BY_THIS_PRODUCT",
    "statement": (
        "This document is a static read-only projection. It is not a BattleActor, "
        "not a ReferenceActionEnvelope and not a PlayerLegalAction, and it asserts "
        "no AI behavior, no skill executability and no native evidence for any "
        "individual monster."
    ),
}

#: Static stat fields read from the canonical Monster record (never invented).
MONSTER_STATIC_STAT_FIELDS = (
    "hp_base",
    "attack_base",
    "defence_base",
    "speed_base",
    "critical_damage_base",
    "stance_base",
    "stance_count",
    "status_resistance_base",
    "initial_delay_ratio",
    "minimum_fatigue_ratio",
)

#: Product-layer limitations repeated in every document's ``unknown`` block.
CHARACTER_LIMITATIONS = (
    "Skill execution is not supplied by this product.",
    "No behavior IR is attached and no battle state is constructed.",
    "M14 capability rows are descriptive only and are never an execution permission.",
)
MONSTER_LIMITATIONS = (
    "Monster AI is not supplied by this product.",
    "Monster skill execution is not supplied by this product.",
    "Phase and body-part runtime are not supplied by this product.",
    "Runtime evidence for monsters is family-level only; no per-monster claim is made.",
)

#: Product schemas for the Stage / Encounter projections (CR-P3).
STAGE_PRODUCT_SCHEMA = "hsr_battle_agent.stage_product/1"
STAGE_SUMMARY_SCHEMA = "hsr_battle_agent.stage_summary/1"
ENCOUNTER_PRODUCT_SCHEMA = "hsr_battle_agent.encounter_product/1"
ENCOUNTER_SUMMARY_SCHEMA = "hsr_battle_agent.encounter_summary/1"

#: The existing topology authority this projection consumes.  It is NOT replaced.
STAGE_PACKAGE_SCHEMA = "hsr_battle_agent.stage_package/1"

#: Raw Stage fields audit F9 recorded as dropped from ``stage_package/1``.  They
#: are retained here as STATIC SOURCE METADATA and are never interpreted as
#: runtime behavior.  A field absent from the record is reported as ``null``.
STAGE_RAW_METADATA_FIELDS = (
    "stage_name",
    "stage_type",
    "stage_ability_config",
    "monster_list",
    "sub_level_graphs",
    "trial_avatar_list",
    "forbid_exit_battle",
    "hard_level_group",
    "monster_warning_ratio",
    "level_graph_path",
    "elite_group",
    "battle_scoring_group",
    "level",
    "release",
    "stage_config_data",
)

#: Fields of :data:`STAGE_RAW_METADATA_FIELDS` that must never be read as runtime
#: behavior.  They are carried verbatim and labelled as source metadata only.
STAGE_NON_INTERPRETED_FIELDS = (
    "stage_ability_config",
    "level_graph_path",
    "sub_level_graphs",
)

#: F10 policy: ``stage_type`` is uniformly "Challenge" for every packaged Stage,
#: so no canonical gameplay mode is established by this product.
CANONICAL_STAGE_MODE_ESTABLISHED = False

STAGE_LIMITATIONS = (
    "Wave spawning and wave progression/clear are not supplied by this product.",
    "Stage Buff activation is not supplied by this product.",
    "Mode rules, score rules and special terminal rules are not supplied by this product.",
    "Boss phase / body-part runtime is not supplied by this product.",
    "Monster AI and formation arbitration are not supplied by this product.",
    "No per-stage execution readiness is claimed; P4 will own runtime support reporting.",
)

ENCOUNTER_LIMITATIONS = (
    "Encounter runtime is not supplied by this product.",
    "Encounter difficulty and reward resolution are not supplied by this product.",
    "Story or maze progression semantics are not supplied by this product.",
)

#: Stage and Encounter records carry no en/ja/ko/zh locale bundle, so the locale
#: policy is "no locale structure" rather than a silent default.
STAGE_LOCALE_STATUS = "NO_LOCALE_STRUCTURE"

#: Fields every Encounter payload carries, whatever its source mode.
ENCOUNTER_COMMON_FIELDS = ("event_index", "lane", "source_mode", "stage_id")

#: The mode-specific context fields observed in the 4.4.54 Encounter records.
#: Anything outside these two sets is surfaced as an unrecognised field rather
#: than being quietly dropped.
ENCOUNTER_SOURCE_MODE_FIELDS = {
    "boss": ("boss_id", "difficulty_id", "difficulty_name"),
    "maze": ("maze_id", "maze_record_id", "maze_record_index", "maze_context"),
    "story": (
        "story_id", "story_level_id", "story_level_index", "story_name",
        "story_level_context", "story_metadata",
    ),
}


# --------------------------------------------------------------------------- #
# stage / encounter helpers
# --------------------------------------------------------------------------- #
def _composite_id_sort_key(value: Any) -> tuple:
    """Stable numeric-aware ordering for colon-composite IDs like encounter IDs."""
    return tuple(
        (0, int(part), "") if part.isdigit() else (1, 0, part)
        for part in str(value).split(":")
    )


def _count_wave_fields(package: Mapping[str, Any]) -> tuple[int, int]:
    waves = list(_sequence(package.get("waves")))
    placements = sum(len(_sequence(_mapping(wave).get("enemy_groups"))) for wave in waves)
    return len(waves), placements


def _stage_topology(package: Mapping[str, Any]) -> dict[str, Any]:
    """The authoritative stage_package/1 topology, preserved verbatim."""
    waves = [dict(_mapping(wave)) for wave in _sequence(package.get("waves"))]
    wave_count, placement_count = _count_wave_fields(package)
    return {
        "authority": "hsr_battle_agent.stage_package/1 (ContentDatabase.get_stage_package)",
        "package_schema": package.get("schema"),
        "package_sha256": package.get("package_sha256"),
        "wave_count": wave_count,
        "enemy_placement_count": placement_count,
        "waves": waves,
        "stage_buff_count": len(_sequence(package.get("stage_buffs"))),
        "stage_buffs": [dict(_mapping(entry)) for entry in _sequence(package.get("stage_buffs"))],
        "encounter_contexts": [dict(_mapping(entry)) for entry in _sequence(package.get("encounter_contexts"))],
        "unknown_reference_count": len(_sequence(package.get("unknown_references"))),
        "unknown_references": [dict(_mapping(entry)) for entry in _sequence(package.get("unknown_references"))],
    }


def _stage_rules(package: Mapping[str, Any]) -> dict[str, Any]:
    """Rule metadata carried verbatim; never interpreted or re-mapped."""
    metadata = dict(_mapping(package.get("rule_metadata")))
    return {
        "authority": "stage_package/1 rule_metadata (verbatim)",
        "rule_metadata": metadata,
        "win_condition_count": len(_sequence(metadata.get("win_conditions"))),
        "lose_condition_count": len(_sequence(metadata.get("lose_conditions"))),
        "win_conditions_interpreted": False,
        "mapped_to_scenario_rule_ids": False,
        "execution_semantics": "NOT_SUPPLIED",
        "note": (
            "win/lose conditions are opaque stage-authored tokens; this product neither "
            "interprets them nor converts them into ScenarioCompiler rule identifiers"
        ),
    }


def _stage_source_metadata(raw_data: Mapping[str, Any]) -> dict[str, Any]:
    """Audit F9 -- raw Stage fields retained as static source metadata only."""
    present = [
        name for name in STAGE_RAW_METADATA_FIELDS
        if name in raw_data and raw_data.get(name) not in (None, "", [], {})
    ]
    absent = [name for name in STAGE_RAW_METADATA_FIELDS if name not in present]
    stage_name = raw_data.get("stage_name")
    if isinstance(stage_name, int):
        name_kind = "STATIC_NUMERIC_ID"
    elif stage_name in (None, ""):
        name_kind = "ABSENT"
    else:
        name_kind = "PRESENT"
    return {
        "classification": "STATIC_SOURCE_METADATA_ONLY",
        "note": (
            "raw canonical Stage fields that stage_package/1 does not retain; the fields "
            "listed in non_interpreted_fields are carried verbatim and are NOT interpreted "
            "as runtime behavior"
        ),
        "non_interpreted_fields": list(STAGE_NON_INTERPRETED_FIELDS),
        "fields_present": present,
        "fields_absent": absent,
        "stage_name": stage_name,
        "stage_name_kind": name_kind,
        "stage_type": raw_data.get("stage_type"),
        "field_values": {name: raw_data.get(name) for name in STAGE_RAW_METADATA_FIELDS},
    }


def _stage_mode_block(package: Mapping[str, Any], raw_data: Mapping[str, Any]) -> dict[str, Any]:
    """Audit F10 -- raw classification plus encounter modes; no invented mode."""
    source_modes = sorted({
        str(_mapping(context).get("source_mode"))
        for context in _sequence(package.get("encounter_contexts"))
        if _mapping(context).get("source_mode")
    })
    return {
        "raw_stage_type": raw_data.get("stage_type") or package.get("mode"),
        "encounter_source_modes": source_modes,
        "canonical_mode": None,
        "canonical_mode_established": CANONICAL_STAGE_MODE_ESTABLISHED,
        "inference_performed": False,
        "note": (
            "every packaged 4.4.54 Stage reports stage_type 'Challenge', and game-mode "
            "context is only available at Encounter level via source_mode; no canonical "
            "gameplay mode (for example Memory of Chaos, Pure Fiction, Apocalyptic Shadow) "
            "is inferred or claimed. stage_type 'Challenge' must never be read as an "
            "established game mode."
        ),
    }


def _monster_placements(
    package: Mapping[str, Any],
    resolver,
) -> list[dict[str, Any]]:
    """Flatten the package's placements and attach stable Monster references.

    Nothing is re-derived from raw tables: waves, group_index, slot, monster_id and
    level come straight from the authoritative package.  The only addition is the
    P0 static identity of each Monster, plus a stable product reference instead of
    an embedded MonsterProduct.
    """
    rows = []
    for wave in _sequence(package.get("waves")):
        wave_row = _mapping(wave)
        for group in _sequence(wave_row.get("enemy_groups")):
            placement = _mapping(group)
            monster_id = placement.get("monster_id")
            resolution = None if monster_id is None else resolver(str(monster_id))
            rows.append({
                "wave_id": wave_row.get("wave_id"),
                "wave_index": wave_row.get("wave_index"),
                "group_index": placement.get("group_index"),
                "slot": placement.get("slot"),
                "monster_id": None if monster_id is None else str(monster_id),
                "level": placement.get("level"),
                "resolution_status": placement.get("resolution_status"),
                "resolved_kind": None if resolution is None else resolution["resolved_kind"],
                "canonical_monster_id": None if resolution is None else resolution["canonical_monster_id"],
                "monster_product_ref": {
                    "service": "ContentProductService.get_monster",
                    "monster_id": None if monster_id is None else str(monster_id),
                },
            })
    return rows


def _encounter_static_display(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Exact static text supplied by the Encounter record; no localization."""
    maze_context = _mapping(payload.get("maze_context"))
    text = {
        "difficulty_name": _text(payload.get("difficulty_name")),
        "story_name": _text(payload.get("story_name")),
        "maze_context_desc": _text(maze_context.get("desc")),
    }
    return {
        "localized": False,
        "locale_vocabulary": [],
        "locale_status": STAGE_LOCALE_STATUS,
        "static_display_text": text,
        "static_text_fields_present": sorted(name for name, value in text.items() if value),
        "note": (
            "Encounter records carry no en/ja/ko/zh locale bundle; the exact static text "
            "supplied is reported verbatim and no localization is fabricated"
        ),
    }


def _encounter_context_block(payload: Mapping[str, Any]) -> dict[str, Any]:
    """The mode-specific Encounter context, preserved verbatim and classified."""
    source_mode = _text(payload.get("source_mode"))
    expected = ENCOUNTER_SOURCE_MODE_FIELDS.get(source_mode, ())
    present = sorted(str(key) for key in payload)
    common = [name for name in ENCOUNTER_COMMON_FIELDS if name in payload]
    return {
        "source_mode": source_mode,
        "common_fields_present": sorted(common),
        "mode_context_fields_present": sorted(name for name in expected if name in payload),
        "unrecognised_fields": sorted(
            name for name in present
            if name not in ENCOUNTER_COMMON_FIELDS and name not in expected
        ),
        "context_fields_present": present,
        "static_context": dict(payload),
        "context_merged_across_encounters": False,
    }


# --------------------------------------------------------------------------- #
# small deterministic helpers
# --------------------------------------------------------------------------- #
def _value(value: Any) -> Any:
    """Unwrap an enum-like value to its canonical machine string."""
    return getattr(value, "value", value)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _id_sort_key(value: Any) -> tuple:
    """Stable numeric-aware ordering for game IDs held as strings."""
    text = str(value)
    return (0, int(text), "") if text.isdigit() else (1, 0, text)


def _promotion_sort_key(value: Any) -> tuple:
    text = str(value)
    return (0, int(text), "") if text.isdigit() else (1, 0, text)


def _resolve_locale(locale: Any) -> str | None:
    """Validate an explicitly requested locale.  No hidden fallback."""
    if locale is None:
        return None
    if not isinstance(locale, str) or not locale:
        raise UnknownLocaleError("locale must be a non-empty string or None")
    if locale not in LOCALE_VOCABULARY:
        raise UnknownLocaleError(
            f"unsupported locale {locale!r}; observed 4.4.54 vocabulary is {list(LOCALE_VOCABULARY)}"
        )
    return locale


def _names(collection: Mapping[str, Any]) -> dict[str, str]:
    """Every available localized name, keyed by locale.  Nothing is filled in."""
    return {
        locale: collection[locale]
        for locale in LOCALE_VOCABULARY
        if _text(collection.get(locale))
    }


def _display_block(collection: Mapping[str, Any], locale: str | None) -> dict[str, Any]:
    """The display section: all available locales plus an explicit locale view."""
    names = _names(collection)
    available = sorted(names)
    missing = [entry for entry in LOCALE_VOCABULARY if entry not in names]
    if locale is None:
        status = "MULTI"
        localized_name = None
    elif locale in names:
        status = "PRESENT"
        localized_name = names[locale]
    else:
        status = "ABSENT"
        localized_name = None
    return {
        "names": names,
        "localized_name": localized_name,
        "locale": locale,
        "locale_status": status,
        "locale_vocabulary": list(LOCALE_VOCABULARY),
        "available_locales": available,
        "missing_locales": missing,
        "locale_fallback_used": False,
    }


def _provenance_block(provenance: Any) -> dict[str, Any]:
    """Reuse the existing entity provenance verbatim; invent nothing."""
    entries = [dict(_mapping(entry)) for entry in _sequence(provenance)]
    return {
        "entity_provenance": entries,
        "entity_provenance_count": len(entries),
        "source": "canonical SQLite content facade (ContentDatabase)",
        "invented_provenance": False,
    }


def _entity_source(role: str, entity: Mapping[str, Any]) -> dict[str, Any]:
    """One provenance source: an existing ContentDatabase envelope, verbatim."""
    provenance = [dict(_mapping(entry)) for entry in _sequence(entity.get("provenance"))]
    return {
        "role": role,
        "entity_id": entity.get("entity_id"),
        "original_game_id": entity.get("original_game_id"),
        "game_id_status": entity.get("game_id_status"),
        "confidence": entity.get("confidence"),
        "reconstruction_status": entity.get("reconstruction_status"),
        "entity_sha256": entity.get("canonical_sha256"),
        "provenance": provenance,
        "provenance_count": len(provenance),
    }


def _monster_provenance_block(
    requested_entity: Mapping[str, Any],
    parent_entity: Mapping[str, Any] | None,
    field_sources: Mapping[str, str],
    requested_role: str = "REQUESTED_ENTITY",
) -> dict[str, Any]:
    """Retain the requested entity and its proven canonical parent separately.

    A variant's display/stats/rank are read from the canonical parent, so the
    parent's provenance and entity identity must be retained alongside the
    variant's own.  An unproven parent contributes nothing: nothing is fabricated.
    A canonical Monster has a single ``SELF`` source.
    """
    sources = [_entity_source(requested_role, requested_entity)]
    if parent_entity is not None:
        sources.append(_entity_source("CANONICAL_PARENT", parent_entity))
    return {
        "sources": sources,
        "field_sources": dict(sorted(field_sources.items())),
        "entity_provenance_count": sum(entry["provenance_count"] for entry in sources),
        "source": "canonical SQLite content facade (ContentDatabase)",
        "invented_provenance": False,
        "parent_provenance_available": parent_entity is not None,
    }


def _is_pronounced_parent_absent(resolution: Mapping[str, Any]) -> bool:
    return (
        resolution.get("resolved_kind") == "MONSTER_VARIANT"
        and resolution.get("canonical_monster_id") is None
    )


# --------------------------------------------------------------------------- #
# service
# --------------------------------------------------------------------------- #
class ContentProductService:
    """Read-only product projections over one explicitly versioned content DB.

    ``database`` fixes the content version at construction; there is no version
    parameter and therefore no "latest" resolution anywhere in this module.

    M14 is supplied as one explicit, version-coherent dependency.  A registry
    whose ``content_version`` disagrees with the database version is refused at
    construction, and every capability is re-checked against the service version
    at call time, so a mixed-version projection can never be emitted.
    """

    def __init__(
        self,
        database: ContentDatabase,
        *,
        registry: Any | None = None,
    ) -> None:
        if registry is not None:
            registry_version = getattr(registry, "content_version", None)
            if registry_version != database.game_version:
                raise ContentProductError(
                    "M14 registry content_version "
                    f"{registry_version!r} does not match database game_version "
                    f"{database.game_version!r}; refusing a mixed-version projection"
                )
        self.database = database
        self._registry = registry

    # -- introspection ------------------------------------------------------ #
    @property
    def game_version(self) -> str:
        return self.database.game_version

    @property
    def m14_registry_supplied(self) -> bool:
        return self._registry is not None

    def _avatar_capabilities(self, avatar_id: str) -> tuple[Any, ...] | None:
        """Return M14 capabilities, or ``None`` when no M14 authority is supplied."""
        if self._registry is None:
            return None
        # Lazy, explicit import: keeps the static module-level import graph free
        # of a game_data -> content_support edge, and is only reached when the
        # caller explicitly supplied a registry.
        from hsr_battle_agent.content_support import get_avatar_skills

        capabilities = tuple(get_avatar_skills(self._registry, str(avatar_id)))
        # Fail closed on a capability that reports a different content version,
        # rather than dropping it or rewriting it.
        for capability in capabilities:
            capability_version = capability.key.content_version
            if capability_version != self.game_version:
                raise ContentProductError(
                    f"M14 capability {capability.key.canonical} reports content_version "
                    f"{capability_version!r} but the service projects {self.game_version!r}"
                )
        return capabilities

    def _avatar_execution_eligibility(self, avatar_id: str, skill_id: str) -> dict[str, Any] | None:
        """The authoritative M14 execution-eligibility denial for one skill.

        Never inferred from readiness/status/binding/settlement: it is the
        verbatim result of the public M14 function.
        """
        if self._registry is None:
            return None
        from hsr_battle_agent.content_support import real_content_execution_eligibility

        return _eligibility_payload(
            real_content_execution_eligibility(self._registry, str(avatar_id), str(skill_id))
        )

    # -- ID lists ---------------------------------------------------------- #
    def _character_ids(self) -> Sequence[str]:
        # The facade owns enumeration authority; the product re-sorts so its own
        # ordering guarantee never depends on the facade's iteration order.
        return sorted(self.database.list_avatar_ids(), key=_id_sort_key)

    def _monster_ids(self) -> Sequence[str]:
        return sorted(self.database.list_monster_ids(), key=_id_sort_key)

    def _stage_ids(self) -> Sequence[str]:
        return sorted(self.database.list_stage_ids(), key=_id_sort_key)

    def _encounter_ids(self) -> Sequence[str]:
        return sorted(self.database.list_encounter_ids(), key=_composite_id_sort_key)

    # -- character enumeration --------------------------------------------- #
    def list_characters(self, *, locale: str | None = None) -> tuple[dict[str, Any], ...]:
        """Lightweight deterministic character browse rows for one content version."""
        wanted = _resolve_locale(locale)
        rows = []
        for avatar_id in self._character_ids():
            entity = self.database.get_avatar(avatar_id)
            if entity is None:  # pragma: no cover - ids come from the same table
                continue
            data = _mapping(entity.get("data"))
            collection = _mapping(data.get("collection"))
            detail = _mapping(data.get("detail"))
            display = _display_block(collection, wanted)
            rows.append(deepcopy({
                "schema": "hsr_battle_agent.character_summary/1",
                "game_version": self.game_version,
                "avatar_id": str(avatar_id),
                "names": display["names"],
                "localized_name": display["localized_name"],
                "locale": display["locale"],
                "locale_status": display["locale_status"],
                "rarity": _rarity_value(detail, collection),
                "rarity_code": _text(detail.get("rarity")) or _text(collection.get("rank")),
                "path": _text(detail.get("base_type")) or _text(collection.get("baseType")),
                "element": _text(detail.get("damage_type")) or _text(collection.get("damageType")),
            }))
        return tuple(rows)

    def list_monsters(self, *, locale: str | None = None) -> tuple[dict[str, Any], ...]:
        """Lightweight deterministic monster browse rows for one content version."""
        wanted = _resolve_locale(locale)
        rows = []
        for monster_id in self._monster_ids():
            entity = self.database.get_monster(monster_id)
            if entity is None:  # pragma: no cover - ids come from the same table
                continue
            data = _mapping(entity.get("data"))
            collection = _mapping(data.get("collection"))
            detail = _mapping(data.get("detail"))
            child_ids = _self_and_child_ids(collection, str(monster_id))
            display = _display_block(collection, wanted)
            rows.append(deepcopy({
                "schema": "hsr_battle_agent.monster_summary/1",
                "game_version": self.game_version,
                "monster_id": str(monster_id),
                "names": display["names"],
                "localized_name": display["localized_name"],
                "locale": display["locale"],
                "locale_status": display["locale_status"],
                "rank": _text(detail.get("rank")) or _text(collection.get("rank")),
                "monster_camp_id": detail.get("monster_camp_id"),
                "weaknesses": list(_sequence(collection.get("weak"))) or None,
                "variant_count": len([entry for entry in child_ids if entry != str(monster_id)]),
                "declared_child_count": len(child_ids),
            }))
        return tuple(rows)

    # -- character product -------------------------------------------------- #
    def get_character(self, avatar_id: Any, *, locale: str | None = None) -> dict[str, Any] | None:
        """Project one Avatar into a deterministic Character product document."""
        wanted = _resolve_locale(locale)
        entity = self.database.get_avatar(str(avatar_id))
        if entity is None:
            return None
        data = _mapping(entity.get("data"))
        collection = _mapping(data.get("collection"))
        detail = _mapping(data.get("detail"))

        skills = self._character_skills(str(avatar_id), detail)
        capability = _capability_summary(skills, self.m14_registry_supplied, self._registry)
        traces = _character_traces(str(avatar_id), detail)
        eidolons = _character_eidolons(detail)
        lightcones = sorted(
            {str(entry) for entry in _sequence(detail.get("lightcones"))},
            key=_id_sort_key,
        )
        memosprite = _memosprite_block(detail)

        display = _display_block(collection, wanted)
        display["descriptions"] = {
            "collection": _text(collection.get("desc")),
            "detail": _text(detail.get("desc")),
            "note": "reported verbatim from the shipped records; no locale is asserted for either blurb",
        }
        display["rarity"] = _rarity_value(detail, collection)
        display["rarity_code"] = _text(detail.get("rarity")) or _text(collection.get("rank"))
        display["path"] = _text(detail.get("base_type")) or _text(collection.get("baseType"))
        display["element"] = _text(detail.get("damage_type")) or _text(collection.get("damageType"))
        display["icon"] = _text(collection.get("icon")) or _text(detail.get("image_path"))
        display["description"] = _text(detail.get("desc"))

        unknown = {
            "limitations": list(CHARACTER_LIMITATIONS),
            "unavailable_sections": _unavailable_character_sections(detail, capability),
            "missing_locales": display["missing_locales"],
            "static_skills_without_m14_row": (
                capability["skills_without_m14_row_ids"] if capability["counts_available"] else None
            ),
            "m14_registry_supplied": self.m14_registry_supplied,
            # Eligibility is never fabricated: every skill without an M14 row
            # (or every skill, when no registry was supplied) is listed here.
            "execution_eligibility_available": capability["execution_eligibility_available"],
            "skills_without_execution_eligibility": [
                entry["skill_id"] for entry in skills
                if entry["m14_execution_eligibility"] is None
            ],
            "unresolved_static_references": [],
        }

        document = {
            "schema": CHARACTER_PRODUCT_SCHEMA,
            "game_version": self.game_version,
            "identity": {
                "avatar_id": str(avatar_id),
                "original_game_id": entity.get("original_game_id"),
                "game_id_status": entity.get("game_id_status"),
                "confidence": entity.get("confidence"),
                "reconstruction_status": entity.get("reconstruction_status"),
                "entity_sha256": entity.get("canonical_sha256"),
            },
            "display": display,
            "progression": _progression_block(detail),
            "skills": skills,
            "traces": traces,
            "eidolons": eidolons,
            "equipment": {
                "compatible_lightcone_ids": lightcones,
                "compatible_lightcone_count": len(lightcones),
                "relic_reference": dict(_mapping(detail.get("relics"))) or None,
            },
            "memosprite": memosprite,
            "capability": capability,
            "provenance": _provenance_block(entity.get("provenance")),
            "unknown": unknown,
            "runtime_semantics_added": False,
        }
        document["product_sha256"] = stable_hash(document)
        return deepcopy(document)

    def _character_skills(self, avatar_id: str, detail: Mapping[str, Any]) -> list[dict[str, Any]]:
        capabilities = self._avatar_capabilities(avatar_id)
        by_skill: dict[str, Any] = {}
        if capabilities:
            by_skill = {str(capability.key.skill_id): capability for capability in capabilities}
        entries = []
        for skill_id in sorted(_mapping(detail.get("skills")), key=_id_sort_key):
            payload = _mapping(_mapping(detail.get("skills")).get(skill_id))
            capability = by_skill.get(str(skill_id))
            # Eligibility is the verbatim public M14 result, never inferred from
            # execution_readiness / support_status / binding_level / settlement.
            eligibility = (
                None if capability is None
                else self._avatar_execution_eligibility(avatar_id, str(skill_id))
            )
            entries.append({
                "skill_id": str(skill_id),
                "skill_numeric_id": int(skill_id) if str(skill_id).isdigit() else None,
                "name": _text(payload.get("name")),
                "desc": _text(payload.get("desc")),
                "simple_desc": _text(payload.get("simple_desc")),
                "tag": _text(payload.get("tag")),
                "sp_base": payload.get("sp_base"),
                "bp_add": payload.get("bp_add"),
                "bp_need": payload.get("bp_need"),
                "show_stance_list": list(_sequence(payload.get("show_stance_list"))) or None,
                "skill_combo_value_delta": payload.get("skill_combo_value_delta"),
                "max_level": _max_skill_level(payload),
                "levels": _skill_levels(payload),
                "m14_status": "LINKED" if capability is not None else (
                    "NO_M14_ROW" if capabilities is not None else "M14_REGISTRY_NOT_SUPPLIED"
                ),
                "m14_capability": None if capability is None else _capability_payload(capability),
                "m14_execution_eligibility": eligibility,
            })
        return entries

    # -- monster product ---------------------------------------------------- #
    def get_monster(
        self,
        monster_id: Any,
        *,
        locale: str | None = None,
        level: int | None = None,
        formation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Project one Monster or MonsterVariant into a Monster product document.

        ``level`` is a caller/placement input and is never read from the base
        Monster record.  ``formation`` (``group_index`` / ``slot``) is recorded
        only when the caller supplies it.
        """
        wanted = _resolve_locale(locale)
        requested_id = str(monster_id)
        resolution = self.database.resolve_monster(requested_id)
        if resolution is None:
            return None

        kind = resolution["resolved_kind"]
        canonical_id = resolution.get("canonical_monster_id")
        variant_id = resolution.get("variant_id")

        entity = resolution["entity"]
        variant_data: Mapping[str, Any] = {}
        parent_entity: Mapping[str, Any] | None = None
        if kind == "MONSTER":
            base_data = _mapping(entity.get("data"))
        else:
            variant_data = _mapping(entity.get("data"))
            parent_entity = None if canonical_id is None else self.database.get_monster(canonical_id)
            base_data = (
                _mapping(parent_entity.get("data")) if parent_entity is not None else {}
            )

        base_detail = _mapping(_mapping(base_data).get("detail"))
        base_collection = _mapping(_mapping(base_data).get("collection"))
        descriptor = (
            _self_child_descriptor(base_detail, requested_id)
            if kind == "MONSTER"
            else variant_data
        )

        if kind == "MONSTER":
            names_source = "SELF"
            stats_source = base_detail
            stats_basis = "SELF"
            weaknesses = list(_sequence(base_collection.get("weak"))) or None
            weaknesses_source = "SELF_COLLECTION"
            record_source = "SELF_CHILD_DESCRIPTOR"
            rank = _text(base_detail.get("rank")) or _text(base_collection.get("rank"))
            camp = base_detail.get("monster_camp_id")
        else:
            names_source = "CANONICAL_PARENT"
            stats_source = base_detail
            stats_basis = "CANONICAL_PARENT"
            weaknesses = list(_sequence(descriptor.get("stance_weak_list"))) or None
            weaknesses_source = "VARIANT_STANCE_WEAK_LIST"
            record_source = "REQUESTED_VARIANT_RECORD"
            rank = _text(base_detail.get("rank")) or _text(base_collection.get("rank"))
            camp = base_detail.get("monster_camp_id")

        display = _display_block(base_collection, wanted)
        display["names_source"] = names_source
        display["descriptions"] = {
            "collection": _text(base_collection.get("desc")),
            "detail": _text(base_detail.get("desc")),
            "note": "reported verbatim; a variant record carries no display data, so the canonical parent is used",
        }
        display["icon"] = _text(base_collection.get("icon")) or _text(base_detail.get("image_path"))
        display["rank"] = rank
        display["rank_source"] = names_source

        stats = {field: stats_source.get(field) for field in MONSTER_STATIC_STAT_FIELDS}
        missing_stats = [field for field, value in stats.items() if value is None]

        skills = [
            {
                "skill_id": str(_mapping(entry).get("id")),
                "skill_name": _text(_mapping(entry).get("skill_name")),
                "skill_desc": _text(_mapping(entry).get("skill_desc")),
                "damage_type": _text(_mapping(entry).get("damage_type")),
                "sp_hit_base": _mapping(entry).get("sp_hit_base"),
                "source": record_source,
            }
            for entry in _sequence(descriptor.get("skill_list"))
        ]

        variants = _variant_descriptors(base_detail, requested_id)

        # Mechanically state which source supplied each parent-backed field.
        field_sources = {
            "identity": "REQUESTED_ENTITY",
            "display.names": names_source,
            "display.descriptions": names_source,
            "display.icon": names_source,
            "display.rank": names_source,
            "static_stats": stats_basis,
            "combat_descriptors.rank": names_source,
            "combat_descriptors.monster_camp_id": names_source,
            "combat_descriptors.phase_list": names_source,
            "combat_descriptors.max_monster_phase": names_source,
            "combat_descriptors.weaknesses": weaknesses_source,
            "combat_descriptors.damage_type_resistance": record_source,
            "combat_descriptors.elite_group": record_source,
            "combat_descriptors.hard_level_group": record_source,
            "skills": record_source,
            "variant_descriptors": record_source if kind == "MONSTER" else names_source,
        }

        document = {
            "schema": MONSTER_PRODUCT_SCHEMA,
            "game_version": self.game_version,
            "identity": {
                "requested_id": requested_id,
                "resolved_kind": kind,
                "canonical_monster_id": canonical_id,
                "variant_id": variant_id,
                "original_game_id": entity.get("original_game_id"),
                "game_id_status": entity.get("game_id_status"),
                "confidence": entity.get("confidence"),
                "reconstruction_status": entity.get("reconstruction_status"),
                "entity_sha256": entity.get("canonical_sha256"),
                "parent_resolved": not _is_pronounced_parent_absent(resolution),
            },
            "display": display,
            "static_stats": stats,
            "static_stats_basis": stats_basis,
            "static_stats_source_monster_id": canonical_id if kind == "MONSTER_VARIANT" else requested_id,
            "combat_descriptors": {
                "weaknesses": weaknesses,
                "weaknesses_source": weaknesses_source,
                "damage_type_resistance": (
                    [dict(_mapping(entry)) for entry in _sequence(descriptor.get("damage_type_resistance"))] or None
                ),
                "rank": rank,
                "elite_group": descriptor.get("elite_group"),
                "hard_level_group": descriptor.get("hard_level_group"),
                "monster_camp_id": camp,
                "phase_list": list(_sequence(base_detail.get("phase_list"))) or None,
                "max_monster_phase": base_detail.get("max_monster_phase"),
            },
            "skills": skills,
            "variant_descriptors": variants,
            "context": {
                "level": None if level is None else int(level),
                "level_source": "NOT_SUPPLIED" if level is None else "CALLER",
                "formation": None if formation is None else {
                    "group_index": _mapping(formation).get("group_index"),
                    "slot": _mapping(formation).get("slot"),
                },
                "note": "level is a caller/placement input; it is never stored on the base Monster record",
            },
            "runtime_support": dict(MONSTER_RUNTIME_SUPPORT),
            "provenance": _monster_provenance_block(
                entity,
                parent_entity,
                field_sources,
                requested_role="SELF" if kind == "MONSTER" else "REQUESTED_ENTITY",
            ),
            "unknown": {
                "limitations": list(MONSTER_LIMITATIONS),
                "missing_locales": display["missing_locales"],
                "missing_static_stats": missing_stats,
                "damage_type_resistance_supplied": descriptor.get("damage_type_resistance") is not None,
                "unresolved_static_references": [],
            },
            "runtime_semantics_added": False,
        }
        document["product_sha256"] = stable_hash(document)
        return deepcopy(document)

    # -- stage product ------------------------------------------------------ #
    def list_stages(self, *, include_package_topology: bool = False) -> tuple[dict[str, Any], ...]:
        """Lightweight deterministic Stage browse rows.

        ``include_package_topology`` is off by default: the four package-derived
        counts require ``get_stage_package``, which costs roughly 23 ms per Stage
        (about 34 s across all 1,459).  With the flag off those counts are
        explicitly ``null`` rather than guessed or re-derived from raw tables.
        """
        modes_by_stage = self._encounter_source_modes_by_stage()
        rows = []
        for stage_id in self._stage_ids():
            raw = self.database.get_stage(stage_id)
            if raw is None:  # pragma: no cover - ids come from the same table
                continue
            raw_data = _mapping(raw.get("data"))
            counts = {
                "wave_count": None,
                "enemy_placement_count": None,
                "stage_buff_count": None,
                "unknown_reference_count": None,
            }
            if include_package_topology:
                package = self.database.get_stage_package(stage_id)
                if package is not None:
                    wave_count, placement_count = _count_wave_fields(package)
                    counts = {
                        "wave_count": wave_count,
                        "enemy_placement_count": placement_count,
                        "stage_buff_count": len(_sequence(package.get("stage_buffs"))),
                        "unknown_reference_count": len(_sequence(package.get("unknown_references"))),
                    }
            rows.append(deepcopy({
                "schema": STAGE_SUMMARY_SCHEMA,
                "game_version": self.game_version,
                "stage_id": str(stage_id),
                "stage_name": raw_data.get("stage_name"),
                "stage_name_kind": _stage_source_metadata(raw_data)["stage_name_kind"],
                "raw_stage_type": raw_data.get("stage_type"),
                "encounter_source_modes": modes_by_stage.get(str(stage_id), []),
                "topology_counts_included": include_package_topology,
                **counts,
            }))
        return tuple(rows)

    def get_stage(self, stage_id: Any) -> dict[str, Any] | None:
        """Project one Stage into a Stage product document.

        The topology, rule metadata, Stage Buffs, encounter contexts and unknown
        references are preserved from ``stage_package/1`` unchanged; this method
        never rebuilds them.  (``ContentProductService.get_stage`` returns a Stage
        product document, whereas ``ContentDatabase.get_stage`` returns the raw
        canonical entity envelope.)
        """
        key = str(stage_id)
        package = _mapping(self.database.get_stage_package(key))
        raw = self.database.get_stage(key)
        if not package and raw is None:
            return None
        raw_data = _mapping(_mapping(raw).get("data"))
        raw_provenance = [dict(entry) for entry in _sequence(_mapping(raw).get("provenance"))]

        topology = _stage_topology(package) if package else {
            "authority": "hsr_battle_agent.stage_package/1 (ContentDatabase.get_stage_package)",
            "package_schema": None,
            "package_sha256": None,
            "wave_count": None,
            "enemy_placement_count": None,
            "waves": None,
            "stage_buff_count": None,
            "stage_buffs": None,
            "encounter_contexts": None,
            "unknown_reference_count": None,
            "unknown_references": None,
        }
        placements = _monster_placements(package, self.database.resolve_monster) if package else []
        source_refs = [dict(entry) for entry in _sequence(package.get("source_refs"))]
        source_metadata = _stage_source_metadata(raw_data)

        document = {
            "schema": STAGE_PRODUCT_SCHEMA,
            "game_version": self.game_version,
            "identity": {
                "stage_id": key,
                "stage_package_id": package.get("stage_id"),
                "original_game_id": _mapping(raw).get("original_game_id"),
                "game_id_status": _mapping(raw).get("game_id_status"),
                "confidence": _mapping(raw).get("confidence"),
                "reconstruction_status": _mapping(raw).get("reconstruction_status"),
                "entity_sha256": _mapping(raw).get("canonical_sha256"),
            },
            "display": {
                "localized": False,
                "locale_vocabulary": [],
                "locale_status": STAGE_LOCALE_STATUS,
                "stage_name": raw_data.get("stage_name"),
                "stage_name_kind": source_metadata["stage_name_kind"],
                "raw_stage_type": raw_data.get("stage_type"),
                "note": (
                    "Stage records carry no en/ja/ko/zh locale bundle; the exact static values "
                    "supplied are reported verbatim and no localization is fabricated"
                ),
            },
            "mode": _stage_mode_block(package, raw_data),
            "topology": topology,
            "monster_placements": placements,
            "rules": _stage_rules(package),
            "static_source_metadata": source_metadata,
            "provenance": {
                "package_source_refs": source_refs,
                "package_source_ref_count": len(source_refs),
                "raw_stage_entity_provenance": raw_provenance,
                "raw_stage_entity_provenance_count": len(raw_provenance),
                "source": "canonical SQLite content facade (ContentDatabase)",
                "invented_source_relationships": False,
            },
            "unknown": {
                "limitations": list(STAGE_LIMITATIONS),
                "stage_package_unknown_references": [dict(entry) for entry in _sequence(package.get("unknown_references"))],
                "stage_package_unknown_reference_count": len(_sequence(package.get("unknown_references"))),
                "stage_package_available": bool(package),
                "raw_stage_available": raw is not None,
                "unresolved_static_references": [],
            },
            "runtime_semantics_added": False,
        }
        document["product_sha256"] = stable_hash(document)
        return deepcopy(document)

    # -- encounter product -------------------------------------------------- #
    def _encounter_source_modes_by_stage(self) -> dict[str, list[str]]:
        """Stage ID -> sorted source modes, read from the Encounter records."""
        mapping: dict[str, set[str]] = {}
        for encounter_id in self._encounter_ids():
            entity = self.database.get_encounter(encounter_id)
            if entity is None:  # pragma: no cover - ids come from the same table
                continue
            payload = _mapping(entity.get("data"))
            stage_id = payload.get("stage_id")
            mode = _text(payload.get("source_mode"))
            if stage_id is None or mode is None:
                continue
            mapping.setdefault(str(stage_id), set()).add(mode)
        return {key: sorted(value) for key, value in mapping.items()}

    def list_encounters(self) -> tuple[dict[str, Any], ...]:
        """Lightweight deterministic Encounter browse rows."""
        rows = []
        for encounter_id in self._encounter_ids():
            entity = self.database.get_encounter(encounter_id)
            if entity is None:  # pragma: no cover - ids come from the same table
                continue
            payload = _mapping(entity.get("data"))
            related = [str(payload["stage_id"])] if payload.get("stage_id") is not None else []
            rows.append(deepcopy({
                "schema": ENCOUNTER_SUMMARY_SCHEMA,
                "game_version": self.game_version,
                "encounter_id": str(encounter_id),
                "source_mode": _text(payload.get("source_mode")),
                "related_stage_count": len(related),
                "related_stage_ids": related,
                "static_display_text": _encounter_static_display(payload)["static_display_text"],
            }))
        return tuple(rows)

    def get_encounter(self, encounter_id: Any) -> dict[str, Any] | None:
        """Project one Encounter into an Encounter product document.

        (``ContentProductService.get_encounter`` returns an Encounter product
        document, whereas ``ContentDatabase.get_encounter`` returns the raw
        canonical entity envelope.)
        """
        key = str(encounter_id)
        entity = self.database.get_encounter(key)
        if entity is None:
            return None
        payload = _mapping(entity.get("data"))
        stage_id = payload.get("stage_id")
        related_stage_ids = [] if stage_id is None else [str(stage_id)]
        related = [
            {
                "stage_id": candidate,
                "order_supplied": False,
                "stage_exists_in_content": self.database.get_stage(candidate) is not None,
                "stage_product_ref": {"service": "ContentProductService.get_stage", "stage_id": candidate},
            }
            for candidate in related_stage_ids
        ]

        document = {
            "schema": ENCOUNTER_PRODUCT_SCHEMA,
            "game_version": self.game_version,
            "identity": {
                "encounter_id": key,
                "source_mode": _text(payload.get("source_mode")),
                "original_game_id": entity.get("original_game_id"),
                "game_id_status": entity.get("game_id_status"),
                "confidence": entity.get("confidence"),
                "reconstruction_status": entity.get("reconstruction_status"),
                "entity_sha256": entity.get("canonical_sha256"),
            },
            "display": _encounter_static_display(payload),
            "static_context": _encounter_context_block(payload),
            "related_stages": related,
            "related_stage_ids": related_stage_ids,
            "provenance": _provenance_block(entity.get("provenance")),
            "unknown": {
                "limitations": list(ENCOUNTER_LIMITATIONS),
                "stage_reference_supplied": stage_id is not None,
                "multiple_stage_identities_supplied": len(related_stage_ids) > 1,
                "context_merged_across_encounters": False,
                "unresolved_static_references": [],
            },
            "runtime_semantics_added": False,
        }
        document["product_sha256"] = stable_hash(document)
        return deepcopy(document)


# --------------------------------------------------------------------------- #
# section builders
# --------------------------------------------------------------------------- #
def _rarity_value(detail: Mapping[str, Any], collection: Mapping[str, Any]) -> int | None:
    code = _text(detail.get("rarity")) or _text(collection.get("rank"))
    if code and code[-1].isdigit():
        return int(code[-1])
    return None


def _max_skill_level(payload: Mapping[str, Any]) -> int | None:
    levels = _mapping(payload.get("level"))
    numeric = [int(key) for key in levels if str(key).isdigit()]
    return max(numeric) if numeric else None


def _skill_levels(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    levels = _mapping(payload.get("level"))
    entries = []
    for key in sorted(levels, key=_promotion_sort_key):
        row = _mapping(levels.get(key))
        entries.append({
            "level": int(row.get("level", key)) if str(key).isdigit() else row.get("level"),
            "param_list": list(_sequence(row.get("param_list"))),
        })
    return entries


def _progression_block(detail: Mapping[str, Any]) -> dict[str, Any]:
    stats = _mapping(detail.get("stats"))
    keys = sorted(stats, key=_promotion_sort_key)
    return {
        "promotion_keys": keys,
        "promotion_count": len(keys),
        "promotion_stat_tables": {key: dict(_mapping(stats[key])) for key in keys},
        "level_domain": {
            "explicit_level_cap": None,
            "max_promotion_key": keys[-1] if keys else None,
            "note": (
                "the static Avatar record supplies per-promotion stat tables and per-trace "
                "avatar_level_limit / avatar_promotion_limit values; it does not declare a "
                "single level cap, so none is reported"
            ),
        },
    }


def _character_traces(avatar_id: str, detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten the avatar's own skill-tree into one row per trace point level."""
    trees = _mapping(detail.get("skill_trees"))
    rows = []
    for point in sorted(trees):
        levels = _mapping(trees.get(point))
        for level in sorted(levels, key=_promotion_sort_key):
            record = _mapping(levels.get(level))
            rows.append({
                "trace_id": f"{avatar_id}:{point}:{level}",
                "point": point,
                "level": int(level) if str(level).isdigit() else level,
                "point_id": record.get("point_id"),
                "point_type": record.get("point_type"),
                "point_trigger_key": record.get("point_trigger_key"),
                "anchor": record.get("anchor"),
                "max_level": record.get("max_level"),
                "pre_point": list(_sequence(record.get("pre_point"))),
                "status_add_list": list(_sequence(record.get("status_add_list"))),
                "level_up_skill_id": [str(v) for v in _sequence(record.get("level_up_skill_id"))],
                "avatar_level_limit": record.get("avatar_level_limit"),
                "avatar_promotion_limit": record.get("avatar_promotion_limit"),
                "default_unlock": record.get("default_unlock"),
                "icon": record.get("icon"),
            })
    return rows


def _character_eidolons(detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    ranks = _mapping(detail.get("ranks"))
    rows = []
    for rank in sorted(ranks, key=_promotion_sort_key):
        record = _mapping(ranks.get(rank))
        rows.append({
            "rank": int(rank) if str(rank).isdigit() else rank,
            "eidolon_id": str(record.get("id")) if record.get("id") is not None else None,
            "name": _text(record.get("name")),
            "desc": _text(record.get("desc")),
            "param_list": list(_sequence(record.get("param_list"))),
            "icon": record.get("icon"),
        })
    return rows


def _memosprite_block(detail: Mapping[str, Any]) -> dict[str, Any]:
    sprite = _mapping(detail.get("memosprite"))
    if not sprite:
        return {"present": False}
    skills = _mapping(sprite.get("skills"))
    return {
        "present": True,
        "name": _text(sprite.get("name")),
        "static_skill_ids": sorted((str(key) for key in skills), key=_id_sort_key),
        "hp_skill": sprite.get("hp_skill"),
        "icon": _text(sprite.get("icon")),
        "m14_coverage": "NOT_COVERED_BY_AVATAR_SKILL_M14_LINKAGE",
    }


def _capability_payload(capability: Any) -> dict[str, Any]:
    """Copy one M14 SkillCapability verbatim.  Nothing is recomputed."""
    key = capability.key
    return {
        "authority": "content_support.SkillCapability (M14)",
        "recomputed_by_product_layer": False,
        "avatar_id": key.avatar_id,
        "skill_id": key.skill_id,
        "content_version": key.content_version,
        "binding_level": _value(capability.binding_level),
        "support_status": _value(capability.support_status),
        "representation_readiness": _value(capability.representation_readiness),
        "execution_readiness": _value(capability.execution_readiness),
        "settlement_present": bool(capability.settlement_present),
        "settlement_kinds": [_value(entry) for entry in capability.settlement_kinds],
        "blocker_classes": [_value(entry) for entry in capability.blocker_classes],
        "primary_blocker": _value(capability.primary_blocker),
        "reentry_hints": [_value(entry) for entry in capability.reentry_hints],
        "entry_ability": capability.entry_ability,
        "prepare_ability": capability.prepare_ability,
        "version_relation": _value(capability.version_relation),
    }


def _eligibility_payload(eligibility: Any) -> dict[str, Any]:
    """Copy one M14 ExecutionEligibility denial verbatim.  Nothing is inferred."""
    key = eligibility.key
    return {
        "authority": "content_support.real_content_execution_eligibility (M14)",
        "recomputed_by_product_layer": False,
        "avatar_id": key.avatar_id,
        "skill_id": key.skill_id,
        "content_version": key.content_version,
        "outcome": _value(eligibility.outcome),
        "reason_code": eligibility.reason_code,
        "reason_detail": eligibility.reason_detail,
        "execution_evidence_mode": _value(eligibility.execution_evidence_mode),
        "representation_evidence_mode": _value(eligibility.representation_evidence_mode),
        "satisfies_gate_certificate": eligibility.satisfies_gate_certificate,
        "satisfies_native_evidenced": eligibility.satisfies_native_evidenced,
    }


def _capability_summary(
    skills: Sequence[Mapping[str, Any]],
    registry_supplied: bool,
    registry: Any,
) -> dict[str, Any]:
    linked = [entry["skill_id"] for entry in skills if entry["m14_status"] == "LINKED"]
    missing = [entry["skill_id"] for entry in skills if entry["m14_status"] == "NO_M14_ROW"]
    with_eligibility = [
        entry["skill_id"] for entry in skills if entry.get("m14_execution_eligibility") is not None
    ]
    outcomes = sorted({
        entry["m14_execution_eligibility"]["outcome"]
        for entry in skills if entry.get("m14_execution_eligibility") is not None
    })
    if not registry_supplied:
        status = "M14_REGISTRY_NOT_SUPPLIED"
    elif not skills:
        status = "NO_STATIC_SKILLS"
    elif not linked:
        status = "NONE"
    elif missing:
        status = "PARTIAL"
    else:
        status = "COMPLETE"
    return {
        "registry_loaded": registry_supplied,
        "registry_content_version": getattr(registry, "content_version", None) if registry is not None else None,
        "source": "content_support.get_avatar_skills",
        "status": status,
        # link counts are only meaningful when an M14 authority was supplied;
        # otherwise they are explicitly unknown rather than reported as zero.
        "counts_available": registry_supplied,
        "static_skill_count": len(skills),
        "skills_with_m14_row": len(linked) if registry_supplied else None,
        "skills_without_m14_row": len(missing) if registry_supplied else None,
        "skills_with_m14_row_ids": linked if registry_supplied else [],
        "skills_without_m14_row_ids": missing if registry_supplied else [],
        "execution_eligibility_source": "content_support.real_content_execution_eligibility",
        "execution_eligibility_available": registry_supplied,
        "skills_with_execution_eligibility": len(with_eligibility) if registry_supplied else None,
        "execution_eligibility_outcomes": outcomes if registry_supplied else [],
        "policy_authority": "M14 (binding_level / support_status / readiness / blocker classes / reentry hints / execution eligibility are copied verbatim, never recomputed)",
        "execution_claimed": False,
    }


def _unavailable_character_sections(
    detail: Mapping[str, Any], capability: Mapping[str, Any]
) -> list[str]:
    unavailable = []
    if not capability["registry_loaded"]:
        unavailable.append("m14_capability")
    if not _mapping(detail.get("relics")):
        unavailable.append("relic_reference")
    if not _sequence(detail.get("lightcones")):
        unavailable.append("compatible_lightcone_ids")
    if not _mapping(detail.get("skill_trees")):
        unavailable.append("traces")
    if not _mapping(detail.get("ranks")):
        unavailable.append("eidolons")
    return unavailable


def _self_and_child_ids(collection: Mapping[str, Any], self_id: str) -> list[str]:
    child = [str(entry) for entry in _sequence(collection.get("child"))]
    if self_id not in child:
        child = [self_id] + child
    return sorted(set(child), key=_id_sort_key)


def _self_child_descriptor(detail: Mapping[str, Any], monster_id: str) -> Mapping[str, Any]:
    """The base variant descriptor embedded in a canonical Monster record."""
    for entry in _sequence(detail.get("child")):
        candidate = _mapping(entry)
        if str(candidate.get("id")) == str(monster_id):
            return candidate
    return {}


def _variant_descriptors(detail: Mapping[str, Any], monster_id: str) -> list[dict[str, Any]]:
    rows = []
    for entry in _sequence(detail.get("child")):
        record = _mapping(entry)
        variant_id = str(record.get("id")) if record.get("id") is not None else None
        rows.append({
            "variant_id": variant_id,
            "is_self_variant": variant_id == str(monster_id),
            "elite_group": record.get("elite_group"),
            "hard_level_group": record.get("hard_level_group"),
            "stance_weak_list": list(_sequence(record.get("stance_weak_list"))),
            "damage_type_resistance": [dict(_mapping(item)) for item in _sequence(record.get("damage_type_resistance"))],
            "skill_ids": [str(_mapping(item).get("id")) for item in _sequence(record.get("skill_list"))],
            "hp_modify_ratio": record.get("hp_modify_ratio"),
            "attack_modify_ratio": record.get("attack_modify_ratio"),
            "defence_modify_ratio": record.get("defence_modify_ratio"),
            "speed_modify_ratio": record.get("speed_modify_ratio"),
            "speed_modify_value": record.get("speed_modify_value"),
            "stance_modify_ratio": record.get("stance_modify_ratio"),
            "stance_modify_value": record.get("stance_modify_value"),
        })
    return sorted(rows, key=lambda row: _id_sort_key(row["variant_id"]))


__all__ = [
    "CHARACTER_PRODUCT_SCHEMA",
    "MONSTER_PRODUCT_SCHEMA",
    "STAGE_PRODUCT_SCHEMA",
    "STAGE_SUMMARY_SCHEMA",
    "ENCOUNTER_PRODUCT_SCHEMA",
    "ENCOUNTER_SUMMARY_SCHEMA",
    "STAGE_PACKAGE_SCHEMA",
    "LOCALE_VOCABULARY",
    "DEFAULT_LOCALE",
    "MONSTER_RUNTIME_SUPPORT",
    "MONSTER_STATIC_STAT_FIELDS",
    "STAGE_RAW_METADATA_FIELDS",
    "STAGE_NON_INTERPRETED_FIELDS",
    "CANONICAL_STAGE_MODE_ESTABLISHED",
    "STAGE_LOCALE_STATUS",
    "ENCOUNTER_COMMON_FIELDS",
    "ENCOUNTER_SOURCE_MODE_FIELDS",
    "ContentProductService",
    "ContentProductError",
    "UnknownLocaleError",
]
