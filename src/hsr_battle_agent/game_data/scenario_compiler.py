"""Compile version-locked static content into a free ScenarioPackage.

This is the SCENARIO-FREE-001 static assembly layer.  It validates selected
content and preserves all identity/provenance, but deliberately does not
execute behavior IR or construct a mutable BattleState.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .external_reconstruction import ReferenceEvaluator
from .nanoka_content import ContentDatabase, stable_hash


class ScenarioCompileError(ValueError):
    """A scenario cannot be resolved without losing an explicit fact."""


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
        rules = dict(self._mapping(request.get("rules")))
        if "rng_seed" not in rules:
            raise ScenarioCompileError("rules.rng_seed is required for deterministic assembly")
        unsupported_policy = str(rules.get("unsupported_policy", "reject"))
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
        waves_input = self._sequence(request.get("enemy_waves"))
        waves = self._compile_waves(waves_input if waves_input else self._waves_from_template(stage_template))
        buffs = self._compile_buffs(self._sequence(request.get("buff_bindings")), stage_template)
        unresolved_behavior = self._behavior_gaps(players, waves, buffs)
        if unsupported_policy == "reject" and unresolved_behavior:
            # Static assembly is intentionally successful even before behavior
            # compilation.  The unresolved list prevents the package from
            # entering an executable/golden path; it is not a resolution error.
            execution_status = "STATIC_READY_BEHAVIOR_COMPILATION_REQUIRED"
        else:
            execution_status = "DEBUG_OPAQUE_DISABLED_ONLY" if unresolved_behavior else "BEHAVIOR_RESOLVED"

        package = {
            "schema": "hsr_battle_agent.scenario_package/1",
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
        return package

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _sequence(value: Any) -> Sequence[Any]:
        return value if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else ()

    def _compile_players(self, raw_players: Sequence[Any]) -> list[dict[str, Any]]:
        if not raw_players:
            raise ScenarioCompileError("player_team must contain at least one combatant")
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

    def _compile_waves(self, raw_waves: Sequence[Any]) -> list[dict[str, Any]]:
        if not raw_waves:
            raise ScenarioCompileError("at least one enemy wave is required")
        compiled: list[dict[str, Any]] = []
        seen_waves: set[int] = set()
        instances: set[str] = set()
        for position, raw in enumerate(raw_waves):
            wave = self._mapping(raw)
            wave_index = int(wave.get("wave_index", position + 1))
            if wave_index in seen_waves:
                raise ScenarioCompileError(f"duplicate wave_index: {wave_index}")
            seen_waves.add(wave_index)
            enemies: list[dict[str, Any]] = []
            for enemy_position, raw_enemy in enumerate(self._sequence(wave.get("enemies", wave.get("enemy_groups")))):
                enemy = self._mapping(raw_enemy)
                monster_id = enemy.get("monster_id")
                if monster_id is None:
                    raise ScenarioCompileError(f"wave {wave_index} enemy {enemy_position} has no monster_id")
                monster = self.database.get_monster(str(monster_id))
                if monster is None:
                    raise ScenarioCompileError(f"unknown monster: {monster_id}")
                instance_id = str(enemy.get("instance_id", f"wave:{wave_index}:enemy:{enemy_position}"))
                if instance_id in instances:
                    raise ScenarioCompileError(f"duplicate enemy instance_id: {instance_id}")
                instances.add(instance_id)
                enemies.append({"instance_id": instance_id, "monster_id": str(monster_id), "level": int(enemy.get("level", 1)), "monster": monster, "initial_state_overrides": dict(self._mapping(enemy.get("initial_state_overrides"))), "template_position": {"group_index": enemy.get("group_index"), "slot": enemy.get("slot")}})
            if not enemies:
                raise ScenarioCompileError(f"wave {wave_index} has no enemies")
            compiled.append({"wave_index": wave_index, "enemies": enemies})
        return sorted(compiled, key=lambda row: row["wave_index"])

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
    def _waves_from_template(stage_template: Mapping[str, Any] | None) -> Sequence[dict[str, Any]]:
        if not stage_template:
            return ()
        return [{"wave_index": wave["wave_index"], "enemy_groups": wave["enemy_groups"]} for wave in stage_template.get("waves", [])]

    @staticmethod
    def _stage_provenance(stage_template: Mapping[str, Any]) -> dict[str, Any]:
        return {"stage_id": stage_template.get("stage_id"), "stage": stage_template.get("stage"), "source_refs": stage_template.get("source_refs", []), "template_wave_count": len(stage_template.get("waves", [])), "template_buff_count": len(stage_template.get("stage_buffs", []))}

    @staticmethod
    def _behavior_gaps(players: Sequence[Mapping[str, Any]], waves: Sequence[Mapping[str, Any]], buffs: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
        gaps = [{"kind": "AvatarBehavior", "entity_id": player["avatar_id"], "status": "BEHAVIOR_COMPILATION_REQUIRED"} for player in players]
        gaps.extend({"kind": "MonsterBehavior", "entity_id": enemy["monster_id"], "status": "BEHAVIOR_COMPILATION_REQUIRED"} for wave in waves for enemy in wave["enemies"])
        gaps.extend({"kind": "StageBuffBehavior", "entity_id": buff["buff_id"], "status": "BEHAVIOR_COMPILATION_REQUIRED"} for buff in buffs)
        return sorted(gaps, key=lambda item: (item["kind"], item["entity_id"]))
