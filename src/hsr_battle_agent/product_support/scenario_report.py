# -*- coding: utf-8 -*-
"""Deterministic Scenario Support Report over an existing ``scenario_package/2``.

CR-P4-SCENARIO-SUPPORT-REPORT-20260929-001.

What this is
------------

One descriptive, product-facing report that truthfully explains, for one already
assembled Scenario Package:

* what static content resolved;
* which Avatar skills M14 can describe (and which it cannot);
* what M15 real-content admission decides for each of those skills;
* which Monster and Stage facts exist only statically;
* which content/runtime gaps remain, keeping each category distinct.

What this is NOT
----------------

It executes no battle, creates no ``ReferenceActionEnvelope`` and no
``PlayerLegalAction``, invokes no planner (neither M10 nor M11), constructs no
battle state, draws no RNG and promotes no evidence.  It is not a second
Scenario Package and it defines no "executable scenario" type.

Authorities consumed (never re-implemented)
-------------------------------------------

* Scenario identity/assembly: the input ``scenario_package/2`` itself.
* Static product projections: :class:`~hsr_battle_agent.game_data.content_product.ContentProductService`
  (P2) for characters/monsters and (P3) for stages/encounters.
* M14 content capability + execution eligibility: the public ``content_support`` API.
* M15 real-content admission: the public ``content_planner.admit_content_for_planner``.
* Family-level runtime facts: current pinned machine artifacts, copied with their
  artifact identity and hash.

Version coherence is enforced across the Scenario Package, the ContentDatabase,
the ContentProductService and the supplied M14 registry.  There is no "latest"
resolution and no cross-version substitution.

Authority chain (single, non-injectable)
----------------------------------------

``registry`` is a **required** constructor argument: the report always performs
M15 admission, which needs an authoritative M14 registry, so there is no
registry-free report mode (``M14_REGISTRY_NOT_SUPPLIED`` is a P2 character
browsing state, never a valid P4 report state).  The product service is always
built internally from the same database and the same registry, so character/M14
facts and M15 admission facts can never come from different authorities::

    scenario_package/2
      -> ContentDatabase(database)
      -> ContentProductService(database, registry=registry)
      -> M14 registry (character capability + eligibility)
      -> M15 admission against the same registry and content version

Input validity is checked in two independent ways: ``package_sha256`` proves the
content is unchanged, and a structural shape check proves the fields this report
reads are actually the right kinds of things.  Neither substitutes for the other.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..content_planner import (
    ADMISSION_OUTCOMES,
    NON_EFFECT_FIELDS,
    ContentPlannerAdmissionRequest,
    admit_content_for_planner,
)
from ..content_support import ContentSupportRegistry
from ..game_data.content_product import ContentProductService
from ..game_data.nanoka_content import ContentDatabase, stable_hash

#: The product document this module emits.
SCENARIO_SUPPORT_REPORT_SCHEMA = "hsr_battle_agent.scenario_support_report/1"

#: The only Scenario Package schema this reporter accepts.  ``/1`` is refused by
#: name rather than silently accepted.
SCENARIO_PACKAGE_SCHEMA = "hsr_battle_agent.scenario_package/2"
REJECTED_SCENARIO_PACKAGE_SCHEMA = "hsr_battle_agent.scenario_package/1"

#: This layer never reaches the planner facade.
PLANNER_FACADE_REFERENCED = False

#: The exact M15 admission outcome this report is allowed to consume.  A future
#: build may add tokens to ``ADMISSION_OUTCOMES``; that must NOT widen P4's
#: accepted result set, so the gate compares against this literal only.
ACCEPTED_M15_OUTCOME = "REJECTED"
FUTURE_OUTCOME_AUTO_EXTENSION = False

#: Family-level runtime scopes.  Both are family-level because no authoritative
#: per-entity join exists.
FAMILY_LEVEL_ONLY = "FAMILY_LEVEL_ONLY"

#: Runtime mechanisms that this repository does not implement, expressed in the
#: repositories' own reporting vocabulary (never a new readiness hierarchy).
MONSTER_RUNTIME_MECHANISMS_NOT_IMPLEMENTED = (
    "monster_ai",
    "monster_skill_execution",
    "phase_or_body_part_runtime",
    "formation_arbitration",
)
STAGE_RUNTIME_MECHANISMS_NOT_IMPLEMENTED = (
    "wave_spawn",
    "wave_progression_or_clear",
    "stage_buff_activation",
    "mode_rules",
    "score_rules",
    "special_terminal_rules",
    "boss_phase_or_body_part_handling",
)

#: Pinned family-level machine artifacts, relative to the repository root.
FAMILY_COVERAGE_ARTIFACT = (
    "data/semantics/4.4.54/full_reconstruction/full_content_compiler_census_001.json"
)
BEHAVIOR_COVERAGE_ARTIFACT = (
    "data/semantics/4.4.54/full_reconstruction/behavior_coverage_census_002.json"
)
GOLDEN_LEDGER_ARTIFACT = (
    "data/semantics/4.4.54/full_reconstruction/terra_golden_ledger_v1.json"
)
COVERAGE_LEDGER_ARTIFACT = (
    "data/semantics/4.4.54/full_reconstruction/coverage_ledger_v1.json"
)
MONSTER_AI_LEDGER_ARTIFACT = (
    "data/semantics/4.4.54/full_reconstruction/monster_ai_binding_ledger_001.json"
)

#: The distinct unresolved-content source categories.  They are reported
#: separately and are never flattened into one generic error list.
UNRESOLVED_CONTENT_CATEGORIES = (
    "scenario_unresolved_behavior",
    "stage_unknown_references",
    "character_static_skill_without_m14_row",
    "m14_blocker_classes_and_reentry_hints",
    "m15_rejection_reasons",
    "loadout_unapplied_contextual_effects",
    "monster_static_missing_fields",
)


class ScenarioSupportReportError(ValueError):
    """The report cannot be produced without inventing or discarding a fact."""


class MissingM14RegistryError(ScenarioSupportReportError):
    """No explicit M14 registry was supplied.

    Every Scenario Support Report performs M15 admission, and admission needs an
    authoritative M14 registry, so this reporter has no registry-free mode.  The
    ``M14_REGISTRY_NOT_SUPPLIED`` state is meaningful for P2 character browsing
    and is deliberately not a valid P4 report state.
    """


class UnsupportedScenarioSchemaError(ScenarioSupportReportError):
    """The input is not a ``scenario_package/2``."""


class ContentVersionMismatchError(ScenarioSupportReportError):
    """A supplied authority disagrees on the content version."""


class MalformedScenarioPackageError(ScenarioSupportReportError):
    """The package is missing structure the report requires."""


class UnsupportedFutureAdmissionOutcomeError(ScenarioSupportReportError):
    """Admission produced an outcome this report has no right to consume.

    The report is not the positive execution path.  If a future build ever
    admits content, that is a different change request with its own authority;
    here it fails closed instead of entering a planner.
    """


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _id_sort_key(value: Any) -> tuple:
    text = str(value)
    return (0, int(text), "") if text.isdigit() else (1, 0, text)


def _counts(values: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _require_sequence(value: Any, path: str) -> Sequence[Any]:
    """Structural check: ``value`` must be a real sequence, not a str or mapping."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise MalformedScenarioPackageError(
            f"{path} must be a sequence; received {type(value).__name__}"
        )
    return value


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MalformedScenarioPackageError(
            f"{path} must be a mapping; received {type(value).__name__}"
        )
    return value


class ScenarioSupportReporter:
    """Build one deterministic Scenario Support Report.

    ``database`` fixes the content version and ``registry`` is the **required**
    M14 authority.  Both are validated for coherence at construction:

    * ``registry.content_version`` must equal ``database.game_version``;
    * a missing/``None`` registry raises :class:`MissingM14RegistryError`.

    There is exactly one authority chain and no injection seam for it::

        scenario_package/2
          -> ContentDatabase(database)
          -> ContentProductService(database, registry=registry)
          -> M14 registry (character capability + eligibility)
          -> M15 admission against the same registry and content version

    No registry is loaded implicitly and there is no "latest" resolution.
    """

    def __init__(
        self,
        database: ContentDatabase,
        *,
        registry: ContentSupportRegistry,
        repository_root: Path | str | None = None,
    ) -> None:
        if registry is None:
            raise MissingM14RegistryError(
                "an explicit M14 ContentSupportRegistry is required: every Scenario Support "
                "Report performs M15 admission, so there is no registry-free report mode "
                "(M14_REGISTRY_NOT_SUPPLIED is a P2 character-browsing state only)"
            )
        if registry.content_version != database.game_version:
            raise ContentVersionMismatchError(
                f"M14 registry content_version {registry.content_version!r} does not match "
                f"database game_version {database.game_version!r}"
            )
        self.database = database
        self.registry = registry
        # One authority chain: the product service is always built here from the
        # SAME database and the SAME registry, so character/M14 facts and M15
        # admission facts can never come from different authorities.
        self.products = ContentProductService(database, registry=registry)
        self.repository_root = Path(repository_root) if repository_root is not None else _default_root()

    # -- public entrypoint -------------------------------------------------- #
    def build(self, scenario_package: Mapping[str, Any]) -> dict[str, Any]:
        """Validate one Scenario Package and return its support report."""
        package = self._validate(scenario_package)

        players = self._static_resolution_players(package)
        waves = self._static_resolution_waves(package)

        character_blocks, admission_blocks, loadout_blocks = self._avatar_sections(players)
        admission_summary = _admission_summary(admission_blocks)
        stage_block = self._stage_static_support(package)
        monster_blocks = self._monster_static_support(waves)
        unresolved = self._unresolved_content(
            package, character_blocks, admission_blocks, loadout_blocks, stage_block, monster_blocks,
        )

        summary = {
            "player_count": len(players),
            "wave_count": len(waves),
            "enemy_instance_count": sum(len(wave["enemies"]) for wave in waves),
            "static_avatar_skill_count": sum(
                block["static_skill_count"] for block in character_blocks
            ),
            "m14_row_count": sum(block["capability"]["skills_with_m14_row"] or 0 for block in character_blocks),
            "missing_m14_row_count": sum(
                block["capability"]["skills_without_m14_row"] or 0 for block in character_blocks
            ),
            "m15_admission_result_count": len(admission_blocks),
            "m15_admission_outcome_counts": admission_summary["outcome_counts"],
            "m15_reason_code_counts": admission_summary["reason_code_counts"],
            "stage_unknown_reference_count": stage_block["unknown_reference_count"],
            "scenario_unresolved_behavior_count": len(_sequence(package.get("unresolved_behavior"))),
            "unapplied_loadout_effect_count": sum(
                block["unapplied_contextual_count"] for block in loadout_blocks
            ),
            "variant_enemy_occurrence_count": sum(
                1 for wave in waves for enemy in wave["enemies"]
                if enemy["resolution"]["resolved_kind"] == "MONSTER_VARIANT"
            ),
        }

        document = {
            "schema": SCENARIO_SUPPORT_REPORT_SCHEMA,
            "identity": {
                "content_version": package["game_version"],
                "scenario_id": package.get("scenario_id"),
                "scenario_mode": package.get("mode"),
                "scenario_package_schema": package.get("schema"),
                "scenario_package_sha256": package.get("package_sha256"),
                "scenario_package_hash_verified": True,
                "source_stage_id": _mapping(package.get("source_stage")).get("stage_id"),
                "source_stage_present": bool(package.get("source_stage")),
                "rng_seed": _mapping(package.get("rules")).get("rng_seed"),
                "rng_seed_role": "static Scenario metadata only; no RNG is drawn by this report",
                "report_schema": SCENARIO_SUPPORT_REPORT_SCHEMA,
            },
            "summary": summary,
            "static_resolution": {
                "authority": "the input hsr_battle_agent.scenario_package/2 (ScenarioCompiler output)",
                "players": [
                    {key: value for key, value in player.items() if key != "static_loadout"}
                    for player in players
                ],
                "waves": waves,
                "buff_bindings": [dict(_mapping(entry)) for entry in _sequence(package.get("buff_bindings"))],
                "buff_binding_count": len(_sequence(package.get("buff_bindings"))),
                "rules": dict(_mapping(package.get("rules"))),
                "unsupported_policy": package.get("unsupported_policy"),
                "execution_status": package.get("execution_status"),
                "reconstruction_status": package.get("reconstruction_status"),
                "golden_eligible": package.get("golden_eligible"),
                "provenance_policy": package.get("provenance_policy"),
                "rule_records_reinterpreted": False,
                "unresolved_behavior_distinct_from_missing_static_entities": True,
            },
            "avatar_content_support": {
                "authority": "ContentProductService / CharacterProduct (P2) over M14",
                "registry_loaded": self.products.m14_registry_supplied,
                "registry_content_version": None if self.registry is None else self.registry.content_version,
                "characters": character_blocks,
            },
            "real_content_execution_admission": {
                "authority": "content_planner.admit_content_for_planner (public M15 API)",
                "api_used": "admit_content_for_planner",
                "private_helpers_used": [],
                "planner_facade_referenced": PLANNER_FACADE_REFERENCED,
                "admission_outcome_vocabulary": list(ADMISSION_OUTCOMES),
                "accepted_outcomes": [ACCEPTED_M15_OUTCOME],
                "future_outcome_auto_extension": FUTURE_OUTCOME_AUTO_EXTENSION,
                "outcome_vocabulary_is_authority_metadata_only": True,
                "expected_outcome": ACCEPTED_M15_OUTCOME,
                "unexpected_outcome_handling": "fail closed with UnsupportedFutureAdmissionOutcomeError; never enter a planner",
                "results": admission_blocks,
                "outcome_counts": admission_summary["outcome_counts"],
                "reason_code_counts": admission_summary["reason_code_counts"],
                "non_effects": admission_summary["non_effects"],
                "non_effects_source": "content_planner.NonEffects (public M15 representation), summed across results",
                "permission_fields": admission_summary["permission_fields"],
            },
            "loadout_static_support": {
                "authority": "the Scenario Package's embedded hsr_battle_agent.static_loadout/1 documents",
                "re_evaluated_here": False,
                "contextual_effects_applied_here": False,
                "retained_status_vocabulary": ["UNAPPLIED_CONTEXTUAL"],
                "players": loadout_blocks,
            },
            "monster_static_support": {
                "authority": "ContentProductService / MonsterProduct (P2) plus the Scenario resolution records",
                "occurrences": monster_blocks,
                "occurrence_identity_kept_separate_from_monster_identity": True,
                "monster_ai_claimed": False,
                "monster_skill_execution_claimed": False,
            },
            "monster_runtime_support": self._monster_runtime_support(),
            "stage_static_support": stage_block,
            "stage_runtime_support": self._stage_runtime_support(),
            "unresolved_content": unresolved,
            "unsupported_runtime_mechanisms": self._unsupported_runtime_mechanisms(admission_blocks, stage_block),
            "non_claims": self._non_claims(admission_summary),
            "runtime_semantics_added": False,
        }
        document["report_sha256"] = stable_hash(document)
        # Copy isolation: the returned report shares no mutable container with the
        # caller's package or with any cached artifact payload.
        return deepcopy(document)

    def _validate_shape(self, package: Mapping[str, Any]) -> None:
        """Structural validation of exactly the fields this report consumes.

        ``package_sha256`` proves content integrity, not schema validity, so this
        runs independently of the hash check.  It deliberately re-creates no
        ScenarioCompiler business rule -- only the shapes the report actually
        reads, so an incorrectly typed field can never be silently treated as
        empty by ``_sequence()``.
        """
        players = _require_sequence(package["players"], "players")
        if not players:
            raise MalformedScenarioPackageError("players must contain at least one entry")
        for index, player in enumerate(players):
            _require_mapping(player, f"players[{index}]")

        waves = _require_sequence(package["waves"], "waves")
        for index, wave in enumerate(waves):
            wave_row = _require_mapping(wave, f"waves[{index}]")
            if "enemies" not in wave_row:
                raise MalformedScenarioPackageError(f"waves[{index}] is missing enemies")
            enemies = _require_sequence(wave_row["enemies"], f"waves[{index}].enemies")
            for position, enemy in enumerate(enemies):
                _require_mapping(enemy, f"waves[{index}].enemies[{position}]")

        bindings = _require_sequence(package["buff_bindings"], "buff_bindings")
        for index, binding in enumerate(bindings):
            _require_mapping(binding, f"buff_bindings[{index}]")

        rules = _require_mapping(package["rules"], "rules")
        if "rng_seed" not in rules:
            raise MalformedScenarioPackageError("rules must contain rng_seed")

        unresolved = _require_sequence(package["unresolved_behavior"], "unresolved_behavior")
        for index, entry in enumerate(unresolved):
            _require_mapping(entry, f"unresolved_behavior[{index}]")

        source_stage = package.get("source_stage")
        if source_stage is not None:
            _require_mapping(source_stage, "source_stage")

    # -- input validation --------------------------------------------------- #
    def _validate(self, scenario_package: Any) -> dict[str, Any]:
        if not isinstance(scenario_package, Mapping):
            raise MalformedScenarioPackageError("scenario_package must be a mapping")
        package = dict(scenario_package)

        schema = package.get("schema")
        if schema == REJECTED_SCENARIO_PACKAGE_SCHEMA:
            raise UnsupportedScenarioSchemaError(
                f"{REJECTED_SCENARIO_PACKAGE_SCHEMA} is superseded and is not accepted; "
                f"this reporter consumes {SCENARIO_PACKAGE_SCHEMA} only"
            )
        if schema != SCENARIO_PACKAGE_SCHEMA:
            raise UnsupportedScenarioSchemaError(
                f"expected {SCENARIO_PACKAGE_SCHEMA}, received {schema!r}"
            )

        game_version = _text(package.get("game_version"))
        if game_version is None:
            raise MalformedScenarioPackageError("scenario_package has no explicit game_version")
        if game_version != self.database.game_version:
            raise ContentVersionMismatchError(
                f"scenario_package game_version {game_version!r} does not match "
                f"database game_version {self.database.game_version!r}"
            )
        if self.registry is not None and game_version != self.registry.content_version:
            raise ContentVersionMismatchError(
                f"scenario_package game_version {game_version!r} does not match "
                f"M14 registry content_version {self.registry.content_version!r}"
            )

        for field in ("players", "waves", "buff_bindings", "rules", "unresolved_behavior"):
            if field not in package:
                raise MalformedScenarioPackageError(f"scenario_package is missing {field!r}")
        self._validate_shape(package)

        # Stable-hash verification: the repository hash convention hashes the
        # package without its own hash field, which is reproducible here without
        # duplicating any ScenarioCompiler internals.
        recorded = package.get("package_sha256")
        if not isinstance(recorded, str) or not recorded:
            raise MalformedScenarioPackageError("scenario_package has no package_sha256")
        recomputed = stable_hash({k: v for k, v in package.items() if k != "package_sha256"})
        if recomputed != recorded:
            raise MalformedScenarioPackageError(
                "scenario_package package_sha256 does not match its content; refusing to consume it"
            )
        return package

    # -- static resolution -------------------------------------------------- #
    def _static_resolution_players(self, package: Mapping[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for player in _sequence(package.get("players")):
            entry = _mapping(player)
            loadout = _mapping(entry.get("loadout"))
            rows.append({
                "instance_id": entry.get("instance_id"),
                "slot": entry.get("slot"),
                "avatar_id": None if entry.get("avatar_id") is None else str(entry["avatar_id"]),
                "static_loadout_schema": loadout.get("schema"),
                "static_loadout_present": bool(loadout),
                "skill_levels": dict(_mapping(entry.get("skill_levels"))),
                "trace_state": dict(_mapping(entry.get("trace_state"))),
                "initial_state": dict(_mapping(entry.get("initial_state"))),
                # The embedded static loadout is retained for the loadout section;
                # it is never re-evaluated here.
                "static_loadout": dict(loadout),
            })
        return rows

    def _static_resolution_waves(self, package: Mapping[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for wave in _sequence(package.get("waves")):
            wave_row = _mapping(wave)
            enemies = []
            for enemy in _sequence(wave_row.get("enemies")):
                item = _mapping(enemy)
                resolution = _mapping(item.get("resolution"))
                enemies.append({
                    "instance_id": item.get("instance_id"),
                    "requested_monster_id": None if item.get("monster_id") is None else str(item["monster_id"]),
                    "level": item.get("level"),
                    "origin": item.get("origin"),
                    "template_position": dict(_mapping(item.get("template_position"))),
                    "resolution": {
                        "requested_id": resolution.get("requested_id"),
                        "resolved_kind": resolution.get("resolved_kind"),
                        "canonical_monster_id": resolution.get("canonical_monster_id"),
                        "variant_id": resolution.get("variant_id"),
                    },
                })
            rows.append({
                "wave_index": wave_row.get("wave_index"),
                "wave_id": wave_row.get("wave_id"),
                "origin": wave_row.get("origin"),
                "override_applied": wave_row.get("override_applied"),
                "enemies": enemies,
            })
        return rows

    # -- avatar / M14 / M15 ------------------------------------------------- #
    def _avatar_sections(
        self, players: Sequence[Mapping[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        character_blocks: list[dict[str, Any]] = []
        admission_blocks: list[dict[str, Any]] = []
        loadout_blocks: list[dict[str, Any]] = []
        for player in players:
            avatar_id = player["avatar_id"]
            document = None if avatar_id is None else self.products.get_character(avatar_id)
            skills = [] if document is None else [
                {
                    "skill_id": skill["skill_id"],
                    "m14_status": skill["m14_status"],
                    "m14_capability": skill["m14_capability"],
                    "m14_execution_eligibility": skill["m14_execution_eligibility"],
                }
                for skill in document["skills"]
            ]
            character_blocks.append({
                "avatar_id": avatar_id,
                "instance_id": player["instance_id"],
                "slot": player["slot"],
                "character_product_available": document is not None,
                "character_product_sha256": None if document is None else document["product_sha256"],
                "static_skill_count": len(skills),
                "capability": {
                    "registry_loaded": False if document is None else document["capability"]["registry_loaded"],
                    "status": None if document is None else document["capability"]["status"],
                    "skills_with_m14_row": None if document is None else document["capability"]["skills_with_m14_row"],
                    "skills_without_m14_row": None if document is None else document["capability"]["skills_without_m14_row"],
                    "skills_without_m14_row_ids": [] if document is None else document["capability"]["skills_without_m14_row_ids"],
                    "policy_authority": None if document is None else document["capability"]["policy_authority"],
                },
                "skills": skills,
                "capability_recomputed_here": False,
                "m13_raw_json_read": False,
            })
            loadout_blocks.append(self._loadout_block(player))
            for skill in skills:
                admission_blocks.append(self._admit(avatar_id, skill))
        return character_blocks, admission_blocks, loadout_blocks

    def _loadout_block(self, player: Mapping[str, Any]) -> dict[str, Any]:
        """The Scenario Package's embedded static loadout, never re-evaluated."""
        loadout = _mapping(player.get("static_loadout"))
        unapplied = [dict(_mapping(entry)) for entry in _sequence(loadout.get("unapplied_contextual_effects"))]
        return {
            "instance_id": player.get("instance_id"),
            "slot": player.get("slot"),
            "avatar_id": player.get("avatar_id"),
            "static_loadout_schema": loadout.get("schema"),
            "static_loadout_present": bool(loadout),
            "avatar_level": loadout.get("avatar_level"),
            "avatar_promotion": loadout.get("avatar_promotion"),
            "eidolon_rank": loadout.get("eidolon_rank"),
            "lightcone_id": loadout.get("lightcone_id"),
            "final_properties": None if not loadout else dict(_mapping(loadout.get("final_properties"))),
            "unapplied_contextual_effects": unapplied,
            "unapplied_contextual_count": len(unapplied),
            "all_unapplied_statuses_canonical": all(
                entry.get("status") == "UNAPPLIED_CONTEXTUAL" for entry in unapplied
            ),
            "contextual_effects_applied_here": False,
        }

    def _admit(self, avatar_id: Any, skill: Mapping[str, Any]) -> dict[str, Any]:
        request = ContentPlannerAdmissionRequest(
            content_version=self.database.game_version,
            avatar_id=str(avatar_id),
            skill_id=str(skill["skill_id"]),
        )
        result = admit_content_for_planner(request, registry=self.registry)

        # Strict gate: P4 consumes EXACTLY the reviewed outcome.  A future build
        # widening ADMISSION_OUTCOMES must not silently widen what this report
        # accepts, so the comparison is against the literal, not the vocabulary.
        outcome = _value(result.outcome)
        if outcome != ACCEPTED_M15_OUTCOME or not result.rejected:
            raise UnsupportedFutureAdmissionOutcomeError(
                f"admission for {request.skill_key} produced outcome {outcome!r} "
                f"(rejected={result.rejected!r}); this report accepts exactly "
                f"{ACCEPTED_M15_OUTCOME!r} and will not enter a planner "
                f"(future_outcome_auto_extension={FUTURE_OUTCOME_AUTO_EXTENSION})"
            )
        if any(getattr(result, name) for name in (
            "may_create_reference_action_envelope",
            "may_enter_player_legal_actions",
            "may_expand_planner_successor",
            "may_mutate_state",
        )):
            raise UnsupportedFutureAdmissionOutcomeError(
                f"admission for {request.skill_key} reported a non-false permission conclusion"
            )
        if not result.non_effects.is_neutral():
            raise UnsupportedFutureAdmissionOutcomeError(
                f"admission for {request.skill_key} reported a non-neutral NonEffects record"
            )

        payload = result.to_dict()
        payload["m14_status"] = skill["m14_status"]
        payload["m14_row_present"] = skill["m14_capability"] is not None
        payload["m14_execution_eligibility_present"] = skill["m14_execution_eligibility"] is not None
        payload["consumed_from_public_api"] = "admit_content_for_planner"
        payload["private_helpers_used"] = []
        return payload

    # -- monster ------------------------------------------------------------ #
    def _monster_static_support(self, waves: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for wave in waves:
            for enemy in wave["enemies"]:
                monster_id = enemy["requested_monster_id"]
                document = None if monster_id is None else self.products.get_monster(monster_id)
                missing = [] if document is None else list(document["unknown"]["missing_static_stats"])
                rows.append({
                    "wave_index": wave["wave_index"],
                    "wave_id": wave["wave_id"],
                    "instance_id": enemy["instance_id"],
                    "requested_monster_id": monster_id,
                    "level": enemy["level"],
                    "level_supplied": enemy["level"] is not None,
                    "formation": dict(enemy.get("template_position") or {}) or None,
                    "formation_source": "Scenario Package template_position (group_index / slot)",
                    "resolved_kind": enemy["resolution"]["resolved_kind"],
                    "canonical_monster_id": enemy["resolution"]["canonical_monster_id"],
                    "variant_id": enemy["resolution"]["variant_id"],
                    "monster_product_available": document is not None,
                    "monster_product_sha256": None if document is None else document["product_sha256"],
                    "static_stats_available": None if document is None else not missing,
                    "missing_static_stats": missing,
                    "runtime_support": None if document is None else document["runtime_support"],
                    "variant_identity_is_static_identity": True,
                    "runtime_support_success_implied": False,
                })
        return rows

    # -- stage -------------------------------------------------------------- #
    def _stage_static_support(self, package: Mapping[str, Any]) -> dict[str, Any]:
        source_stage = _mapping(package.get("source_stage"))
        stage_id = source_stage.get("stage_id")
        if stage_id is None:
            return {
                "authority": "ContentProductService / StageProduct (P3)",
                "source_stage_present": False,
                "stage_id": None,
                "stage_product_sha256": None,
                "stage_absent_is_not_an_error": True,
                "note": "this is a free Scenario with no source Stage template; no Stage gap is reported",
                "unknown_reference_count": 0,
                "stage_package_topology_present": False,
                "encounter_source_modes": [],
                "stage_buff_references": [],
                "rule_metadata_present": False,
                "f9_retained_static_metadata_present": False,
                "canonical_mode": None,
                "canonical_mode_established": False,
            }
        document = self.products.get_stage(str(stage_id))
        if document is None:
            raise ScenarioSupportReportError(
                f"source_stage_id {stage_id!r} is referenced by the Scenario Package but no "
                "Stage product can be built for it"
            )
        return {
            "authority": "ContentProductService / StageProduct (P3)",
            "source_stage_present": True,
            "stage_id": document["identity"]["stage_id"],
            "stage_product_sha256": document["product_sha256"],
            "stage_absent_is_not_an_error": False,
            "stage_package_topology_present": bool(document["topology"].get("waves")),
            "stage_package_sha256": document["topology"].get("package_sha256"),
            "wave_count": document["topology"]["wave_count"],
            "enemy_placement_count": document["topology"]["enemy_placement_count"],
            "encounter_source_modes": list(document["mode"]["encounter_source_modes"]),
            "raw_stage_type": document["mode"]["raw_stage_type"],
            "canonical_mode": document["mode"]["canonical_mode"],
            "canonical_mode_established": document["mode"]["canonical_mode_established"],
            "stage_buff_references": [
                {"buff_id": entry.get("buff_id"), "resolution_status": entry.get("resolution_status")}
                for entry in _sequence(document["topology"].get("stage_buffs"))
            ],
            "rule_metadata_present": bool(document["rules"].get("rule_metadata")),
            "rule_metadata_interpreted": False,
            "win_condition_count": document["rules"]["win_condition_count"],
            "lose_condition_count": document["rules"]["lose_condition_count"],
            "unknown_references": [
                dict(_mapping(entry)) for entry in _sequence(document["topology"].get("unknown_references"))
            ],
            "unknown_reference_count": document["topology"]["unknown_reference_count"],
            "f9_retained_static_metadata_present": bool(
                document["static_source_metadata"]["fields_present"]
            ),
            "f9_fields_present": list(document["static_source_metadata"]["fields_present"]),
            "f9_fields_absent": list(document["static_source_metadata"]["fields_absent"]),
            "template_provenance": dict(source_stage),
        }

    # -- family-level runtime ----------------------------------------------- #
    def _artifact(self, relative: str) -> dict[str, Any]:
        path = self.repository_root / relative
        if not path.is_file():
            return {"available": False, "artifact": relative, "reason": "ARTIFACT_NOT_PRESENT"}
        raw = path.read_bytes()
        return {
            "available": True,
            "artifact": relative,
            "artifact_sha256": hashlib.sha256(raw).hexdigest(),
            "artifact_bytes": len(raw),
            "payload": json.loads(raw.decode("utf-8")),
        }

    def _monster_runtime_support(self) -> dict[str, Any]:
        census = self._artifact(FAMILY_COVERAGE_ARTIFACT)
        behavior = self._artifact(BEHAVIOR_COVERAGE_ARTIFACT)
        monster_ai = self._artifact(MONSTER_AI_LEDGER_ARTIFACT)
        facts: list[dict[str, Any]] = []
        if census["available"]:
            families = {
                str(entry.get("family")): entry for entry in _sequence(census["payload"].get("static_family_coverage"))
            }
            for family in ("Monster", "MonsterSkill"):
                entry = families.get(family)
                if entry is None:
                    continue
                facts.append({
                    "family": family,
                    "artifact": census["artifact"],
                    "artifact_sha256": census["artifact_sha256"],
                    "report_id": census["payload"].get("report_id"),
                    "status": census["payload"].get("status"),
                    "static_total": entry.get("static_total"),
                    "behavior_mapped": entry.get("behavior_mapped"),
                    "executable": entry.get("executable"),
                    "golden": entry.get("golden"),
                    "unmapped": entry.get("unmapped"),
                })
        if behavior["available"]:
            entry = _mapping(_mapping(behavior["payload"].get("families")).get("Monster"))
            facts.append({
                "family": "Monster",
                "artifact": behavior["artifact"],
                "artifact_sha256": behavior["artifact_sha256"],
                "report_id": behavior["payload"].get("report_id"),
                "status": behavior["payload"].get("status"),
                "behavior_bearing_denominator": entry.get("behavior_bearing_denominator"),
                "canonicalized": entry.get("canonicalized"),
                "executable_reference": entry.get("executable_reference"),
                "golden_tested": entry.get("golden_tested"),
            })
        exact_links = None
        for fact in facts:
            if fact["family"] == "Monster" and "behavior_mapped" in fact:
                exact_links = fact["behavior_mapped"]
        join_block: dict[str, Any] = {"available": monster_ai["available"]}
        if monster_ai["available"]:
            join_block.update({
                "artifact": monster_ai["artifact"],
                "artifact_sha256": monster_ai["artifact_sha256"],
                "schema": monster_ai["payload"].get("schema"),
                "join_summary": dict(_mapping(monster_ai["payload"].get("join_summary"))),
                "non_inferences": list(_sequence(monster_ai["payload"].get("non_inferences"))),
                "scope_note": "this is a targeted 14-row Monster AI binding ledger, not a per-entity census over all 628 static Monsters",
            })
        return {
            "scope": FAMILY_LEVEL_ONLY,
            "per_entity_runtime_claim_available": False,
            "per_entity_claim_emitted": False,
            "reason": (
                "the pinned family census records behaviour_mapped = 0 for the Monster family, so no "
                "authoritative per-static-Monster behaviour join exists to make a per-entity statement from"
            ),
            "exact_static_entity_link_count": exact_links,
            "per_static_monster_behavior_join_available": False,
            "family_facts": facts,
            "per_static_monster_ai_ledger": join_block,
            "runtime_mechanisms_not_implemented": list(MONSTER_RUNTIME_MECHANISMS_NOT_IMPLEMENTED),
            "non_claims": [
                "No per-Monster runtime-ready or executable-reference result is emitted.",
                "A MONSTER_VARIANT resolved to a canonical parent is a static identity success, not a runtime-support success.",
            ],
        }

    def _stage_runtime_support(self) -> dict[str, Any]:
        census = self._artifact(FAMILY_COVERAGE_ARTIFACT)
        behavior = self._artifact(BEHAVIOR_COVERAGE_ARTIFACT)
        golden = self._artifact(GOLDEN_LEDGER_ARTIFACT)
        ledger = self._artifact(COVERAGE_LEDGER_ARTIFACT)
        facts: list[dict[str, Any]] = []
        if census["available"]:
            families = {
                str(item.get("family")): item for item in _sequence(census["payload"].get("static_family_coverage"))
            }
            stage_buff = families.get("StageBuff")
            if stage_buff is not None:
                facts.append({
                    "family": "StageBuff",
                    "artifact": census["artifact"],
                    "artifact_sha256": census["artifact_sha256"],
                    "report_id": census["payload"].get("report_id"),
                    "status": census["payload"].get("status"),
                    "static_total": stage_buff.get("static_total"),
                    "canonicalized": stage_buff.get("canonicalized"),
                    "behavior_mapped": stage_buff.get("behavior_mapped"),
                    "executable": stage_buff.get("executable"),
                    "golden": stage_buff.get("golden"),
                    "unmapped": stage_buff.get("unmapped"),
                })
        if behavior["available"]:
            stage_buff = _mapping(_mapping(behavior["payload"].get("families")).get("StageBuff"))
            facts.append({
                "family": "StageBuff",
                "artifact": behavior["artifact"],
                "artifact_sha256": behavior["artifact_sha256"],
                "report_id": behavior["payload"].get("report_id"),
                "status": behavior["payload"].get("status"),
                "behavior_bearing_denominator": stage_buff.get("behavior_bearing_denominator"),
                "canonicalized": stage_buff.get("canonicalized"),
                "captured_records": stage_buff.get("captured_records"),
                "executable_reference": stage_buff.get("executable_reference"),
                "golden_tested": stage_buff.get("golden_tested"),
                "static_definition_only": stage_buff.get("static_definition_only"),
            })
        golden_block: dict[str, Any] = {"available": golden["available"]}
        if golden["available"]:
            native_trace = _sequence(golden["payload"].get("native_trace"))
            golden_block.update({
                "artifact": golden["artifact"],
                "artifact_sha256": golden["artifact_sha256"],
                # The ledger's own field names are recorded, but the entries are
                # reported as a count/claim rather than under a key that could be
                # mistaken for an execution artifact held by this report.
                "source_field_names": ["golden", "native_trace"],
                "golden": golden["payload"].get("golden"),
                "native_trace_entry_count": len(native_trace),
                "native_trace_claim": "PRESENT" if native_trace else "NONE",
                "qualifying_independent_oracles": len(
                    _sequence(golden["payload"].get("qualifying_independent_native_oracles"))
                ),
            })
        ledger_block: dict[str, Any] = {"available": ledger["available"]}
        if ledger["available"]:
            ledger_block.update({
                "artifact": ledger["artifact"],
                "artifact_sha256": ledger["artifact_sha256"],
                "ledger_id": ledger["payload"].get("ledger_id"),
                "status": ledger["payload"].get("status"),
                "counting_rule": ledger["payload"].get("counting_rule"),
            })
        return {
            "scope": FAMILY_LEVEL_ONLY,
            "per_entity_runtime_claim_available": False,
            "per_entity_claim_emitted": False,
            "stage_runtime_implemented": False,
            "family_facts": facts,
            "golden_block": golden_block,
            "coverage_ledger": ledger_block,
            "runtime_mechanisms_not_implemented": list(STAGE_RUNTIME_MECHANISMS_NOT_IMPLEMENTED),
            "not_inferred_from": [
                "StagePackage presence",
                "StageAbility path presence",
                "Stage Buff static binding presence",
            ],
            "non_claims": [
                "No per-Stage execution-readiness field is emitted.",
                "Static Stage/StageBuff presence never implies runtime support.",
            ],
        }

    # -- unresolved content / mechanisms / non-claims ----------------------- #
    def _unresolved_content(
        self,
        package: Mapping[str, Any],
        characters: Sequence[Mapping[str, Any]],
        admissions: Sequence[Mapping[str, Any]],
        loadouts: Sequence[Mapping[str, Any]],
        stage_block: Mapping[str, Any],
        monsters: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        missing_m14 = [
            {"avatar_id": block["avatar_id"], "skill_id": skill["skill_id"]}
            for block in characters for skill in block["skills"]
            if skill["m14_status"] == "NO_M14_ROW"
        ]
        blockers = sorted({
            str(blocker)
            for admission in admissions
            for blocker in _sequence(_mapping(admission).get("blocker_classes"))
        })
        reentry = sorted({
            str(hint)
            for admission in admissions
            for hint in _sequence(_mapping(admission).get("reentry_hints"))
        })
        return {
            "categories": list(UNRESOLVED_CONTENT_CATEGORIES),
            "categories_kept_distinct": True,
            "scenario_unresolved_behavior": {
                "source": "Scenario Package unresolved_behavior",
                "meaning": "behavior compilation is required for these entities; this is NOT a missing static entity",
                "entries": [dict(_mapping(entry)) for entry in _sequence(package.get("unresolved_behavior"))],
                "count": len(_sequence(package.get("unresolved_behavior"))),
                "is_missing_static_entity": False,
            },
            "stage_unknown_references": {
                "source": "StageProduct / StagePackage unknown_references",
                "entries": [dict(_mapping(entry)) for entry in _sequence(stage_block.get("unknown_references"))],
                "count": int(stage_block.get("unknown_reference_count") or 0),
                "stage_present": bool(stage_block.get("source_stage_present")),
            },
            "character_static_skill_without_m14_row": {
                "source": "CharacterProduct capability (M14 linkage)",
                "entries": missing_m14,
                "count": len(missing_m14),
            },
            "m14_blocker_classes_and_reentry_hints": {
                "source": "M14 blocker classes / reentry hints copied through M15",
                "blocker_classes": blockers,
                "blocker_class_count": len(blockers),
                "reentry_hints": reentry,
                "reentry_hint_count": len(reentry),
                "count": len(blockers) + len(reentry),
            },
            "m15_rejection_reasons": {
                "source": "M15 admission results",
                "reason_code_counts": _counts([str(_mapping(entry).get("reason_code")) for entry in admissions]),
                "count": len(admissions),
            },
            "loadout_unapplied_contextual_effects": {
                "source": "static_loadout/1 unapplied_contextual_effects",
                "entries": [
                    {"avatar_id": block["avatar_id"], "effects": list(block["unapplied_contextual_effects"])}
                    for block in loadouts if block["unapplied_contextual_count"]
                ],
                "count": sum(block["unapplied_contextual_count"] for block in loadouts),
            },
            "monster_static_missing_fields": {
                "source": "MonsterProduct unknown.missing_static_stats",
                "entries": [
                    {"instance_id": row["instance_id"], "monster_id": row["requested_monster_id"],
                     "missing_static_stats": list(row["missing_static_stats"])}
                    for row in monsters if row["missing_static_stats"]
                ],
                "count": sum(len(row["missing_static_stats"]) for row in monsters),
            },
        }

    def _unsupported_runtime_mechanisms(
        self,
        admissions: Sequence[Mapping[str, Any]],
        stage_block: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "built_from_existing_authorities_only": True,
            "new_readiness_hierarchy_introduced": False,
            "m14_blocker_classes": sorted({
                str(blocker)
                for admission in admissions
                for blocker in _sequence(_mapping(admission).get("blocker_classes"))
            }),
            "m15_reason_codes": sorted({
                str(_mapping(admission).get("reason_code")) for admission in admissions
            }),
            "m15_non_effect_fields": list(NON_EFFECT_FIELDS),
            "character_product_limitations": [
                "Skill execution is not supplied by this product.",
                "No behavior IR is attached and no battle state is constructed.",
            ],
            "monster_product_limitations": list(MONSTER_RUNTIME_MECHANISMS_NOT_IMPLEMENTED),
            "stage_product_limitations": list(STAGE_RUNTIME_MECHANISMS_NOT_IMPLEMENTED),
            "monster_family_scope": FAMILY_LEVEL_ONLY,
            "stage_family_scope": FAMILY_LEVEL_ONLY,
            "stage_canonical_mode_established": bool(stage_block.get("canonical_mode_established")),
        }

    def _non_claims(self, admission_summary: Mapping[str, Any]) -> dict[str, Any]:
        non_effects = _mapping(admission_summary.get("non_effects"))
        return {
            "real_content_execution_performed": False,
            "reference_action_envelopes_created": non_effects.get("reference_action_envelopes", 0),
            "player_legal_actions_created": non_effects.get("player_legal_actions", 0),
            "planner_invoked": False,
            "battle_state_created": False,
            "native_evidence_promoted": False,
            "golden_claimed": False,
            "scenario_is_executable": False,
            "scenario_is_planner_ready": False,
            "approximates_game_behavior": False,
            "m15_rejection_proves_game_behavior": False,
            "family_level_runtime_evidence_applies_to_an_individual_monster_or_stage": False,
            "non_effects_are_all_zero": all(int(non_effects.get(name, 0)) == 0 for name in NON_EFFECT_FIELDS),
        }


# --------------------------------------------------------------------------- #
# module-level helpers
# --------------------------------------------------------------------------- #
def _default_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _admission_summary(admissions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate the M15 NonEffects/public fields without inventing counters."""
    non_effects = {name: 0 for name in NON_EFFECT_FIELDS}
    permission_fields = {
        "may_create_reference_action_envelope": False,
        "may_enter_player_legal_actions": False,
        "may_expand_planner_successor": False,
        "may_mutate_state": False,
    }
    for admission in admissions:
        for name in NON_EFFECT_FIELDS:
            non_effects[name] += int(_mapping(admission.get("non_effects")).get(name, 0))
        for name in permission_fields:
            permission_fields[name] = permission_fields[name] or bool(admission.get(name))
    return {
        "outcome_counts": _counts([str(_mapping(entry).get("outcome")) for entry in admissions]),
        "reason_code_counts": _counts([str(_mapping(entry).get("reason_code")) for entry in admissions]),
        "non_effects": non_effects,
        "permission_fields": permission_fields,
    }


def build_scenario_support_report(
    scenario_package: Mapping[str, Any],
    database: ContentDatabase,
    *,
    registry: ContentSupportRegistry,
) -> dict[str, Any]:
    """Convenience wrapper around :class:`ScenarioSupportReporter`.

    ``registry`` is required for the same reason as in the constructor: every
    report performs M15 admission, so there is no registry-free report mode.
    """
    return ScenarioSupportReporter(database, registry=registry).build(scenario_package)


__all__ = [
    "SCENARIO_SUPPORT_REPORT_SCHEMA",
    "SCENARIO_PACKAGE_SCHEMA",
    "REJECTED_SCENARIO_PACKAGE_SCHEMA",
    "FAMILY_LEVEL_ONLY",
    "ACCEPTED_M15_OUTCOME",
    "FUTURE_OUTCOME_AUTO_EXTENSION",
    "UNRESOLVED_CONTENT_CATEGORIES",
    "MONSTER_RUNTIME_MECHANISMS_NOT_IMPLEMENTED",
    "STAGE_RUNTIME_MECHANISMS_NOT_IMPLEMENTED",
    "PLANNER_FACADE_REFERENCED",
    "ScenarioSupportReporter",
    "build_scenario_support_report",
    "ScenarioSupportReportError",
    "MissingM14RegistryError",
    "UnsupportedScenarioSchemaError",
    "ContentVersionMismatchError",
    "MalformedScenarioPackageError",
    "UnsupportedFutureAdmissionOutcomeError",
]
