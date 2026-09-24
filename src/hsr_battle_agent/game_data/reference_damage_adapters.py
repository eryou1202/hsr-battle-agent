"""Exact-shape, whole-step REFERENCE_MODEL damage adapters (REF02-001)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from enum import Enum
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.game_data.reference_operation_adapters import ReferenceAdapterGate


class ReferenceDamageError(ValueError):
    pass


def _d(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ReferenceDamageError("boolean is not numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ReferenceDamageError(f"non-numeric value {value!r}") from error
    if not result.is_finite():
        raise ReferenceDamageError("non-finite damage input")
    return result


class PacketKind(Enum):
    ORDINARY_DAMAGE = "ORDINARY_DAMAGE"
    EXPLICIT_HEAL = "EXPLICIT_HEAL"
    TASK_MARKER = "TASK_MARKER"


@dataclass(frozen=True)
class ReferenceEntityState:
    entity_id: str
    hp: Decimal
    max_hp: Decimal
    shield: Decimal
    toughness: Decimal

    def __post_init__(self) -> None:
        if not self.entity_id or self.max_hp <= 0 or min(self.hp, self.shield, self.toughness) < 0:
            raise ReferenceDamageError("invalid explicit entity state")
        if self.hp > self.max_hp:
            raise ReferenceDamageError("hp exceeds max_hp")


@dataclass(frozen=True)
class ReferenceCombatState:
    entities: tuple[ReferenceEntityState, ...]
    resource_owner: str
    resource_current: Decimal
    timeline_token: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", tuple(self.entities))
        ids = tuple(entity.entity_id for entity in self.entities)
        if not ids or len(set(ids)) != len(ids) or self.resource_current < 0:
            raise ReferenceDamageError("invalid combat state")

    def entity(self, entity_id: str) -> ReferenceEntityState:
        matches = [entity for entity in self.entities if entity.entity_id == entity_id]
        if len(matches) != 1:
            raise ReferenceDamageError("target is absent or ambiguous")
        return matches[0]


_EXACT_PACKET_KEYS = frozenset({
    "packet_schema", "kind", "source_id", "targets", "base_value", "factors",
    "resource_cost", "resource_owner", "toughness_delta", "survival_closed",
    "events_closed", "task_id", "task_owner",
})
_SPECIAL_KEYS = frozenset({
    "SPHitRatio", "HitSplitRatio", "DamageValue", "DamageBehavior", "Nonlethal",
    "RandomCrit", "SpecialFormula", "UnknownTargetCardinality", "UnknownEventCallback",
})


@dataclass(frozen=True)
class OrdinaryReferencePacket:
    packet_schema: str
    kind: PacketKind
    source_id: str
    targets: tuple[str, ...]
    base_value: Decimal
    factors: tuple[tuple[str, Decimal], ...]
    resource_cost: Decimal
    resource_owner: str
    toughness_delta: Decimal
    survival_closed: bool
    events_closed: bool
    task_id: str | None
    task_owner: str | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OrdinaryReferencePacket":
        if not isinstance(data, Mapping):
            raise ReferenceDamageError("packet must be a mapping")
        present = set(data)
        special = sorted(present & _SPECIAL_KEYS)
        if special:
            raise ReferenceDamageError(f"unsupported special field(s): {special}")
        if present != _EXACT_PACKET_KEYS:
            raise ReferenceDamageError(
                f"packet shape mismatch: missing={sorted(_EXACT_PACKET_KEYS-present)}, "
                f"extra={sorted(present-_EXACT_PACKET_KEYS)}"
            )
        if data["packet_schema"] != "ordinary_reference_packet/1":
            raise ReferenceDamageError("unsupported packet schema")
        try:
            kind = PacketKind(data["kind"])
        except (TypeError, ValueError) as error:
            raise ReferenceDamageError("unsupported packet kind") from error
        targets_raw = data["targets"]
        factors_raw = data["factors"]
        if not isinstance(targets_raw, list) or not all(isinstance(x, str) and x for x in targets_raw):
            raise ReferenceDamageError("targets must be an explicit list of ids")
        if not isinstance(factors_raw, list):
            raise ReferenceDamageError("factors must be an ordered explicit list")
        factors: list[tuple[str, Decimal]] = []
        for item in factors_raw:
            if not isinstance(item, Mapping) or set(item) != {"name", "value"}:
                raise ReferenceDamageError("factor shape is not exact")
            if not isinstance(item["name"], str) or not item["name"]:
                raise ReferenceDamageError("factor name required")
            factors.append((item["name"], _d(item["value"])))
        packet = cls(
            str(data["packet_schema"]), kind, str(data["source_id"]), tuple(targets_raw),
            _d(data["base_value"]), tuple(factors), _d(data["resource_cost"]),
            str(data["resource_owner"]), _d(data["toughness_delta"]),
            data["survival_closed"], data["events_closed"], data["task_id"], data["task_owner"],
        )
        packet._validate()
        return packet

    def _validate(self) -> None:
        if not self.source_id or self.resource_cost < 0 or self.toughness_delta < 0:
            raise ReferenceDamageError("invalid source, resource cost, or toughness delta")
        if not isinstance(self.survival_closed, bool) or not isinstance(self.events_closed, bool):
            raise ReferenceDamageError("closure flags must be explicit booleans")
        if self.kind is PacketKind.TASK_MARKER:
            if not self.task_id or not self.task_owner or self.targets:
                raise ReferenceDamageError("task marker requires owner/id and no damage target")
            if self.base_value != 0 or self.factors or self.resource_cost != 0 or self.toughness_delta != 0:
                raise ReferenceDamageError("task marker cannot carry combat effects")
        else:
            if len(self.targets) != 1:
                raise ReferenceDamageError("supported ordinary packet requires exactly one target")
            if self.task_id is not None or self.task_owner is not None:
                raise ReferenceDamageError("combat packet cannot smuggle a task marker")
            if not self.survival_closed or not self.events_closed:
                raise ReferenceDamageError("survival and event dependencies must be closed")
            if self.kind is PacketKind.EXPLICIT_HEAL and self.toughness_delta != 0:
                raise ReferenceDamageError("heal cannot carry toughness damage")


@dataclass(frozen=True)
class ReferenceDamageResult:
    before: ReferenceCombatState
    after: ReferenceCombatState
    amount: Decimal
    hp_delta: Decimal
    shield_delta: Decimal
    toughness_delta: Decimal
    task_marker: tuple[str, str] | None
    evidence_mode: EvidenceMode = EvidenceMode.REFERENCE_MODEL


def apply_reference_packet(
    gate: ReferenceAdapterGate,
    state: ReferenceCombatState,
    packet_data: Mapping[str, Any],
    *,
    version: str,
    sha256: str,
    scope: str,
) -> ReferenceDamageResult:
    """Validate the complete packet, then return a new reference state."""
    packet = OrdinaryReferencePacket.from_dict(packet_data)  # all late blockers first
    gate.require(version=version, sha256=sha256, scope=scope, owner=packet.source_id)
    if packet.resource_owner != state.resource_owner:
        raise ReferenceDamageError("resource owner mismatch")
    if packet.resource_cost > state.resource_current:
        raise ReferenceDamageError("insufficient explicit resource")
    if packet.kind is PacketKind.TASK_MARKER:
        if packet.task_owner != packet.source_id:
            raise ReferenceDamageError("marker owner mismatch")
        return ReferenceDamageResult(state, state, Decimal("0"), Decimal("0"),
                                     Decimal("0"), Decimal("0"),
                                     (packet.task_id or "", packet.task_owner or ""))

    with localcontext() as context:
        context.prec = 38
        amount = packet.base_value
        for _name, factor in packet.factors:
            amount *= factor
    if amount < 0:
        raise ReferenceDamageError("negative damage/heal amount is unsupported")

    target = state.entity(packet.targets[0])
    hp_delta = shield_delta = applied_toughness = Decimal("0")
    if packet.kind is PacketKind.ORDINARY_DAMAGE:
        shield_loss = min(target.shield, amount)
        hp_loss = min(target.hp, amount - shield_loss)
        applied_toughness = min(target.toughness, packet.toughness_delta)
        changed = ReferenceEntityState(target.entity_id, target.hp-hp_loss, target.max_hp,
                                       target.shield-shield_loss, target.toughness-applied_toughness)
        hp_delta, shield_delta = -hp_loss, -shield_loss
    else:
        heal = min(target.max_hp-target.hp, amount)
        changed = ReferenceEntityState(target.entity_id, target.hp+heal, target.max_hp,
                                       target.shield, target.toughness)
        hp_delta = heal
    entities = tuple(changed if item.entity_id == changed.entity_id else item for item in state.entities)
    after = ReferenceCombatState(entities, state.resource_owner,
                                 state.resource_current-packet.resource_cost, state.timeline_token)
    return ReferenceDamageResult(state, after, amount, hp_delta, shield_delta,
                                 -applied_toughness, None)


__all__ = [
    "OrdinaryReferencePacket", "PacketKind", "ReferenceCombatState",
    "ReferenceDamageError", "ReferenceDamageResult", "ReferenceEntityState",
    "apply_reference_packet",
]
