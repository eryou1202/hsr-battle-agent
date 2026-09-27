"""Compile version-locked static content into a free ScenarioPackage.

This is the SCENARIO-FREE-001 static assembly layer.  It validates selected
content and preserves all identity/provenance, but deliberately does not
execute behavior IR or construct a mutable BattleState.

Monster references are resolved through the single static identity authority
``ContentDatabase.resolve_monster`` so that a Scenario Package and a real Stage
Package can never disagree about whether a placement is known.  The resolution
record is static identity data only; it is never an AI, skill, phase or
execution claim.

CR-P1-SCENARIO-CONTRACT-CONFORMANCE-20260927-001 closed three audited contract
gaps without adding runtime semantics:

* F2 -- ``player_team`` is bounded to ``1..4`` combatants.
* F3 -- every ``victory_rule_id`` / ``defeat_rule_id`` reference is emitted as
  an explicit resolution record, so a consumer can never mistake "a string was
  supplied" for "the rule is known and executable".  The static content layer
  holds no victory/defeat rule catalogue, so no supplied ID is promoted to
  ``RESOLVED`` and a supplied ID is reported as ``UNKNOWN``.
* F4 -- caller waves are overlaid on the resolved Stage template instead of
  replacing it; the template ``wave_id`` and both provenances are retained.

Audit F5 (loadout completeness) is explicitly NOT addressed by this change:
no relic-slot, set_id, initial_state, skill_level or rank validation was added.

The package is still a deterministic static document.  It is returned as a
copy-isolated plain object; freezing the returned type (audit F6) is deferred
and recorded in the P1 control artifact.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .external_reconstruction import ReferenceEvaluator
from .nanoka_content import (
    MONSTER_RESOLUTION_IDENTITY_FIELDS, ContentDatabase, stable_hash,
)


class ScenarioCompileError(ValueError):
    """A scenario cannot be resolved without losing an explicit fact."""


#: Product schema emitted by this compiler.
#:
#: ``hsr_battle_agent.scenario_package/1`` is the pre-P1 static shape, whose
#: ``rules`` block echoed bare ``victory_rule_id`` / ``defeat_rule_id`` strings.
#: ``.../2`` is the current shape: the P0 static monster-resolution metadata
#: plus P1 explicit rule records plus the wave identity/origin/provenance
#: contract.  Replacing the bare rule strings with structured records is not a
#: purely additive change, so the version was bumped rather than silently
#: re-interpreted.  No exact-shape production consumer exists, so this is the
#: low-cost migration window.
PACKAGE_SCHEMA = "hsr_battle_agent.scenario_package/2"
#: The superseded pre-P1 static shape.
LEGACY_PACKAGE_SCHEMA = "hsr_battle_agent.scenario_package/1"

#: Contract-bounded player team size (FREE-SCENARIO-ASSEMBLY-4.4.54-V1).
MIN_PLAYER_TEAM = 1
MAX_PLAYER_TEAM = 4

#: Wave provenance origins used by the deterministic Stage-template overlay.
WAVE_ORIGINS = ("TEMPLATE", "TEMPLATE_WITH_CALLER_OVERRIDE", "CALLER")

#: Rule-reference resolution vocabulary.
#:
#: ``RESOLVED`` requires a rule catalogue, which this layer does not have, so it
#: is unreachable.  ``CALLER_DECLARED_LOCAL`` requires the caller to declare a
#: rule as locally owned, and no such typed input exists, so it is unreachable
#: too.  A bare supplied string carries no such information, so the honest
#: current mapping is ``UNKNOWN``; ``UNSPECIFIED`` means the caller supplied no
#: rule at all.
RULE_RESOLUTION_STATES = (
    "RESOLVED", "UNKNOWN", "CALLER_DECLARED_LOCAL", "UNSPECIFIED",
)
#: The subset of :data:`RULE_RESOLUTION_STATES` currently reachable.  A bare
#: caller string can never be classified as caller-owned, so
#: ``CALLER_DECLARED_LOCAL`` is deliberately excluded.
REACHABLE_RULE_RESOLUTION_STATES = ("UNKNOWN", "UNSPECIFIED")
#: No rule reference in this layer carries runtime semantics.
RULE_EXECUTION_SEMANTICS = "NONE"


class ScenarioCompiler:
    """Pure free-scenario assembler over local canonical/SQLite content only."""

    def __init__(self, database: ContentDatabase) -> None:
        self.database = database
        self.evaluator = ReferenceEvaluator(database)

    def compile(self, request: Mapping[str, Any]) -> dict[str, Any]:
        version = str(request.get("game_version", self.database.game_version))
        if version != self.database.game_version:
            raise ScenarioCompileError(f"scenario version {version} cannot use {self.database.game_version} content")
        scenario_id = request.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ScenarioCompileError("scenario_id is required")
        rules_input = dict(self._mapping(request.get("rules")))
        if "rng_seed" not in rules_input:
            raise ScenarioCompileError("rules.rng_seed is required for deterministic assembly")
        unsupported_policy = str(rules_input.get("unsupported_policy", "reject"))
        if unsupported_policy not in {"reject", "opaque-disabled"}:
            raise ScenarioCompileError("unsupported_policy must be reject or opaque-disabled")

        source_stage_id = request.get("source_stage_id")
        stage_template = None
        if source_stage_id is not None:
            stage_template = self.database.get_stage_package(str(source_stage_id))
            if stage_template is None:
                raise ScenarioCompileError(f"unknown source_stage_id: {source_stage_id}")
            if stage_template.get("unknown_references"):
                raise ScenarioCompileError("source Stage Package has unresolved references")

        players = self._compile_players(self._sequence(request.get("player_team")))
        effective_waves = self._effective_waves(stage_template, self._sequence(request.get("enemy_waves")))
        waves = self._compile_waves(effective_waves)
        buffs = self._compile_buffs(self._sequence(request.get("buff_bindings")), stage_template)
        unresolved_behavior = self._behavior_gaps(players, waves, buffs)
        if unsupported_policy == "reject" and unresolved_behavior:
            # Static assembly is intentionally successful even before behavior
            # compilation.  The unresolved list prevents the package from
            # entering an executable/golden path; it is not a resolution error.
            execution_status = "STATIC_READY_BEHAVIOR_COMPILATION_REQUIRED"
        else:
            execution_status = "DEBUG_OPAQUE_DISABLED_ONLY" if unresolved_behavior else "BEHAVIOR_RESOLVED"

        rules = {
            "rng_seed": rules_input["rng_seed"],
            "unsupported_policy": unsupported_policy,
            "victory_rule": self._resolve_rule(rules_input.get("victory_rule_id")),
            "defeat_rule": self._resolve_rule(rules_input.get("defeat_rule_id")),
        }

        package = {
            "schema": PACKAGE_SCHEMA,
            "game_version": version,
            "scenario_id": scenario_id,
            "mode": str(request.get("mode", "standard/free")),
            "source_stage": self._stage_provenance(stage_template) if stage_template else None,
            "players": players,
            "waves": waves,
            "buff_bindings": buffs,
            "rules": rules,
            "unresolved_behavior": unresolved_behavior,
            "unsupported_policy": unsupported_policy,
            "execution_status": execution_status,
            "reconstruction_status": "STATIC_RECONSTRUCTION_READY",
            "golden_eligible": not unresolved_behavior and unsupported_policy != "opaque-disabled",
            "provenance_policy": "canonical SQLite/static references only; external raw JSON and network are never runtime inputs",
        }
        package["package_sha256"] = stable_hash(package)
        # Copy isolation: the returned package shares no mutable container with
        # the caller's request or the database facade.  See audit F6 / the P1
        # control artifact -- the returned value is deliberately a plain dict.
        return deepcopy(package)

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _sequence(value: Any) -> Sequence[Any]:
        return value if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else ()

    @staticmethod
    def _unspecified_rule() -> dict[str, Any]:
        return {
            "requested_id": None,
            "resolution_status": "UNSPECIFIED",
            "resolved_rule": None,
            "authority": None,
            "execution_semantics": RULE_EXECUTION_SEMANTICS,
        }

    def _resolve_rule(self, requested: Any) -> dict[str, Any]:
        """Represent one victory/defeat rule reference with explicit state.

        The static content layer holds no victory/defeat rule catalogue, so a
        supplied identifier can never be promoted to ``RESOLVED``.  A bare
        string also carries no information about whether it denotes a real game
        rule, an unknown identifier or a caller-owned local rule, so it is
        recorded as ``UNKNOWN`` rather than being classified as caller-owned.
        The reference keeps its identity, carries no execution semantics, and
        makes "a string was supplied" impossible to mistake for "the rule is
        known and executable".
        """
        if requested is None or requested == "":
            return self._unspecified_rule()
        if not isinstance(requested, str):
            raise ScenarioCompileError("rules.victory_rule_id / rules.defeat_rule_id must be strings")
        return {
            "requested_id": requested,
            "resolution_status": "UNKNOWN",
            "resolved_rule": None,
            "authority": None,
            "execution_semantics": RULE_EXECUTION_SEMANTICS,
        }

    def _compile_players(self, raw_players: Sequence[Any]) -> list[dict[str, Any]]:
        if len(raw_players) < MIN_PLAYER_TEAM:
            raise ScenarioCompileError("player_team must contain at least one combatant")
        if len(raw_players) > MAX_PLAYER_TEAM:
            raise ScenarioCompileError(
                f"player_team may contain at most {MAX_PLAYER_TEAM} combatants; received {len(raw_players)}"
            )
        compiled: list[dict[str, Any]] = []
        seen_slots: set[str] = set()
        for index, raw in enumerate(raw_players):
            player = self._mapping(raw)
            slot = str(player.get("slot", index))
            if slot in seen_slots:
                raise ScenarioCompileError(f"duplicate player slot: {slot}")
            seen_slots.add(slot)
            avatar_input = self._mapping(player.get("avatar"))
            avatar_id = avatar_input.get("avatar_id")
            if avatar_id is None:
                raise ScenarioCompileError(f"player {slot} has no avatar.avatar_id")
            avatar = self.database.get_avatar(str(avatar_id))
            if avatar is None:
                raise ScenarioCompileError(f"unknown avatar: {avatar_id}")
            lightcone_input = self._mapping(player.get("lightcone"))
            relics = []
            for relic in self._sequence(player.get("relics")):
                item = dict(self._mapping(relic))
                if "template_or_piece_id" in item and "template_id" not in item:
                    item["template_id"] = item.pop("template_or_piece_id")
                relics.append(item)
            trace_state = self._mapping(avatar_input.get("trace_state"))
            loadout = {
                "avatar_id": avatar_id,
                "level": avatar_input.get("level", 80),
                "promotion": avatar_input.get("promotion", 6),
                "eidolon_rank": avatar_input.get("eidolon", 0),
                "trace_ids": list(self._sequence(trace_state.get("unlocked_trace_ids"))),
                "relics": relics,
            }
            if lightcone_input:
                loadout.update({
                    "lightcone_id": lightcone_input.get("lightcone_id"),
                    "lightcone_level": lightcone_input.get("level", loadout["level"]),
                    "lightcone_promotion": lightcone_input.get("promotion", loadout["promotion"]),
                    "lightcone_superimposition": lightcone_input.get("superimposition", 1),
                })
            try:
                materialized = self.evaluator.materialize_loadout(loadout)
            except (KeyError, ValueError) as error:
                raise ScenarioCompileError(f"invalid player loadout in slot {slot}: {error}") from error
            compiled.append({
                "instance_id": str(player.get("instance_id", f"player:{slot}")),
                "slot": slot,
                "avatar_id": str(avatar_id),
                "avatar": avatar,
                "loadout": materialized,
                "skill_levels": dict(self._mapping(avatar_input.get("skill_levels"))),
                "trace_state": dict(trace_state),
                "initial_state": dict(self._mapping(player.get("initial_state"))),
            })
        return compiled

    def _effective_waves(
        self,
        stage_template: Mapping[str, Any] | None,
        caller_waves: Sequence[Any],
    ) -> list[dict[str, Any]]:
        """Overlay caller waves onto the resolved Stage template base set.

        Deterministic overlay rule (contract requirement "resolve a Stage
        template before caller overrides, then retain both template provenance
        and override provenance"):

        * the Stage template establishes the base ordered wave set;
        * a caller wave whose ``wave_index`` matches a template wave REPLACES
          that wave's enemies and keeps the template wave identity;
        * a caller wave with a previously unseen ``wave_index`` is ADDED;
        * template waves the caller does not mention are RETAINED.

        No wave-removal mechanism exists in this contract, so none is invented:
        an omitted template wave is always retained.
        """
        source_stage_id = str(stage_template.get("stage_id")) if stage_template else None
        entries: list[dict[str, Any]] = []
        by_index: dict[int, dict[str, Any]] = {}
        if stage_template:
            for template_wave in stage_template.get("waves", []):
                wave_index = int(template_wave["wave_index"])
                if wave_index in by_index:
                    raise ScenarioCompileError(f"duplicate template wave_index: {wave_index}")
                entry = {
                    "wave_index": wave_index,
                    "wave_id": template_wave.get("wave_id"),
                    "origin": "TEMPLATE",
                    "override_applied": False,
                    "template_wave_id": template_wave.get("wave_id"),
                    "template_wave_index": wave_index,
                    "caller_wave_id": None,
                    "enemy_source": template_wave.get("enemy_groups", []),
                }
                entries.append(entry)
                by_index[wave_index] = entry
        seen_caller: set[int] = set()
        for position, raw in enumerate(caller_waves):
            wave = self._mapping(raw)
            wave_index = int(wave.get("wave_index", position + 1))
            if wave_index in seen_caller:
                raise ScenarioCompileError(f"duplicate wave_index: {wave_index}")
            seen_caller.add(wave_index)
            caller_enemies = self._sequence(wave.get("enemies", wave.get("enemy_groups")))
            template_entry = by_index.get(wave_index)
            if template_entry is not None:
                template_entry["origin"] = "TEMPLATE_WITH_CALLER_OVERRIDE"
                template_entry["override_applied"] = True
                template_entry["caller_wave_id"] = wave.get("wave_id")
                template_entry["enemy_source"] = caller_enemies
                continue
            entry = {
                "wave_index": wave_index,
                "wave_id": wave.get("wave_id"),
                "origin": "CALLER",
                "override_applied": False,
                "template_wave_id": None,
                "template_wave_index": None,
                "caller_wave_id": wave.get("wave_id"),
                "enemy_source": caller_enemies,
            }
            entries.append(entry)
            by_index[wave_index] = entry
        for entry in entries:
            entry["source_stage_id"] = source_stage_id
        return sorted(entries, key=lambda entry: entry["wave_index"])

    def _compile_waves(self, effective_waves: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        if not effective_waves:
            raise ScenarioCompileError("at least one enemy wave is required")
        compiled: list[dict[str, Any]] = []
        instances: set[str] = set()
        for wave in effective_waves:
            wave_index = int(wave["wave_index"])
            origin = wave["origin"]
            enemies: list[dict[str, Any]] = []
            for enemy_position, raw_enemy in enumerate(self._sequence(wave["enemy_source"])):
                enemy = self._mapping(raw_enemy)
                monster_id = enemy.get("monster_id")
                if monster_id is None:
                    raise ScenarioCompileError(f"wave {wave_index} enemy {enemy_position} has no monster_id")
                resolution = self.database.resolve_monster(str(monster_id))
                if resolution is None:
                    raise ScenarioCompileError(f"unknown monster: {monster_id}")
                instance_id = str(enemy.get("instance_id", f"wave:{wave_index}:enemy:{enemy_position}"))
                if instance_id in instances:
                    raise ScenarioCompileError(f"duplicate enemy instance_id: {instance_id}")
                instances.add(instance_id)
                # ``monster_id`` keeps the caller's requested ID verbatim; the
                # resolution record states which static identity kind answered
                # it and the proven canonical parent, when there is one.
                enemies.append({
                    "instance_id": instance_id,
                    "monster_id": str(monster_id),
                    "level": int(enemy.get("level", 1)),
                    "monster": resolution["entity"],
                    "resolution": {name: resolution[name] for name in MONSTER_RESOLUTION_IDENTITY_FIELDS},
                    "initial_state_overrides": dict(self._mapping(enemy.get("initial_state_overrides"))),
                    "template_position": {"group_index": enemy.get("group_index"), "slot": enemy.get("slot")},
                    "origin": origin,
                })
            if not enemies:
                raise ScenarioCompileError(f"wave {wave_index} has no enemies")
            compiled.append({
                "wave_index": wave_index,
                "wave_id": wave["wave_id"],
                "origin": origin,
                "override_applied": bool(wave["override_applied"]),
                "provenance": {
                    "source_stage_id": wave["source_stage_id"],
                    "template_wave_id": wave["template_wave_id"],
                    "template_wave_index": wave["template_wave_index"],
                    "caller_wave_index": None if origin == "TEMPLATE" else wave_index,
                    "caller_wave_id": wave["caller_wave_id"],
                },
                "enemies": enemies,
            })
        return compiled

    def _compile_buffs(self, raw_buffs: Sequence[Any], stage_template: Mapping[str, Any] | None) -> list[dict[str, Any]]:
        bindings: list[dict[str, Any]] = []
        if stage_template:
            for index, buff in enumerate(stage_template.get("stage_buffs", [])):
                bindings.append({"binding_id": f"template:{stage_template['stage_id']}:buff:{index}", "buff_id": str(buff["buff_id"]), "scope": "battle", "owner_or_target": "battle", "activation": "battle_start", "parameter_overrides": {}, "template_resolution": buff.get("resolution_status")})
        for raw in raw_buffs:
            binding = self._mapping(raw)
            buff_id = binding.get("buff_id")
            if buff_id is None:
                raise ScenarioCompileError("Buff binding has no buff_id")
            bindings.append({"binding_id": str(binding.get("binding_id", f"buff:{len(bindings)}")), "buff_id": str(buff_id), "scope": str(binding.get("scope", "battle")), "owner_or_target": binding.get("owner_or_target", "battle"), "activation": str(binding.get("activation", "battle_start")), "parameter_overrides": dict(self._mapping(binding.get("parameter_overrides"))), "template_resolution": None})
        seen: set[str] = set()
        for binding in bindings:
            if binding["binding_id"] in seen:
                raise ScenarioCompileError(f"duplicate buff binding_id: {binding['binding_id']}")
            seen.add(binding["binding_id"])
            resolved = self.database.get_stage_buff(binding["buff_id"]) or self.database.get_external_stage_buff(binding["buff_id"])
            if resolved is None:
                raise ScenarioCompileError(f"unknown buff: {binding['buff_id']}")
            binding["buff"] = resolved
        return bindings

    @staticmethod
    def _stage_provenance(stage_template: Mapping[str, Any]) -> dict[str, Any]:
        return {"stage_id": stage_template.get("stage_id"), "stage": stage_template.get("stage"), "source_refs": stage_template.get("source_refs", []), "template_wave_count": len(stage_template.get("waves", [])), "template_buff_count": len(stage_template.get("stage_buffs", []))}

    @staticmethod
    def _behavior_gaps(players: Sequence[Mapping[str, Any]], waves: Sequence[Mapping[str, Any]], buffs: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
        gaps = [{"kind": "AvatarBehavior", "entity_id": player["avatar_id"], "status": "BEHAVIOR_COMPILATION_REQUIRED"} for player in players]
        gaps.extend({"kind": "MonsterBehavior", "entity_id": enemy["monster_id"], "status": "BEHAVIOR_COMPILATION_REQUIRED"} for wave in waves for enemy in wave["enemies"])
        gaps.extend({"kind": "StageBuffBehavior", "entity_id": buff["buff_id"], "status": "BEHAVIOR_COMPILATION_REQUIRED"} for buff in buffs)
        return sorted(gaps, key=lambda item: (item["kind"], item["entity_id"]))
