"""Search state for the evidence-aware runtime, outside frozen Terra ownership.

Explicit IDs and JSON values only. Scheduler continuations and callback nodes are
serialized IR, so a snapshot is sufficient to resume on a clone.
"""
from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field

from hsr_battle_agent.battle_ir.behavior import canonical_json, stable_hash


def validate_json(value):
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise TypeError("state maps require string keys")
        for child in value.values():
            validate_json(child)
    elif isinstance(value, list):
        for child in value:
            validate_json(child)
    elif value is not None and not isinstance(value, (str, bool, int, float)):
        raise TypeError("state values must use JSON primitives")


@dataclass
class DeterministicRNG:
    """Versioned SplitMix64 reference stream; not the native client's RNG."""
    state: int = 0
    draws: int = 0
    algorithm: str = "splitmix64_reference_v1"

    def __post_init__(self):
        if (isinstance(self.state, bool) or not isinstance(self.state, int) or
            isinstance(self.draws, bool) or not isinstance(self.draws, int) or
            not 0 <= self.state < 2**64 or self.draws < 0 or self.algorithm != "splitmix64_reference_v1"):
            raise ValueError("invalid reference RNG state")

    def next_u64(self) -> int:
        mask = 2**64 - 1
        self.state = (self.state + 0x9E3779B97F4A7C15) & mask
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
        self.draws += 1
        return value ^ (value >> 31)

    def index(self, size: int) -> int:
        if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= 2**64:
            raise ValueError("random selection requires nonempty candidates")
        # Rejection avoids modulo bias and documents variable draw consumption.
        bound = 2**64 - (2**64 % size)
        while True:
            value = self.next_u64()
            if value < bound:
                return value % size


@dataclass
class ModifierInstance:
    instance_id: str
    config_identity: str
    owner: str
    caster: str
    original_caster: str
    stack: int
    count: int
    duration: dict
    dynamic_values: dict = field(default_factory=dict)
    snapshot_data: dict = field(default_factory=dict)
    event_registrations: list[dict] = field(default_factory=list)
    authority: dict = field(default_factory=dict)


@dataclass
class SchedulerState:
    tick: int = 0
    next_sequence: int = 0
    continuation: list[dict] = field(default_factory=list)
    callbacks: list[dict] = field(default_factory=list)
    barriers: dict[str, bool] = field(default_factory=dict)
    completion_requested: bool = False

    def schedule(self, tick: int, nodes: list[dict], release: str | None = None):
        if isinstance(tick, bool) or not isinstance(tick, int) or tick < self.tick:
            raise ValueError("cannot schedule callbacks in the past")
        self.callbacks.append({"tick": tick, "sequence": self.next_sequence,
                               "nodes": copy.deepcopy(nodes), "release": release})
        self.next_sequence += 1
        self.callbacks.sort(key=lambda item: (item["tick"], item["sequence"]))


@dataclass
class BehaviorBattleState:
    schema: str = "evidence_aware_behavior_state/1"
    entities: dict[str, dict] = field(default_factory=dict)
    properties: dict[str, dict[str, int]] = field(default_factory=dict)
    actor_resources: dict[str, dict[str, int]] = field(default_factory=dict)
    team_resources: dict[str, dict[str, int]] = field(default_factory=dict)
    progression: dict[str, dict] = field(default_factory=dict)
    modifiers: dict[str, ModifierInstance] = field(default_factory=dict)
    dynamic_values: dict[str, dict[str, int]] = field(default_factory=dict)
    target_context: dict[str, object] = field(default_factory=dict)
    scheduler: SchedulerState = field(default_factory=SchedulerState)
    pending_events: list[dict] = field(default_factory=list)
    rng: DeterministicRNG = field(default_factory=DeterministicRNG)
    mechanics: dict = field(default_factory=dict)
    presentation: dict = field(default_factory=dict)
    terminal: bool = False

    def __post_init__(self):
        if self.schema != "evidence_aware_behavior_state/1":
            raise ValueError("unsupported behavior state schema")
        # Validate/copy through the same boundary used for snapshots.
        raw_document = asdict(self)
        validate_json(raw_document)
        document = json.loads(canonical_json(raw_document))
        for key in ("entities", "properties", "actor_resources", "team_resources",
                    "progression", "dynamic_values", "target_context", "pending_events",
                    "mechanics", "presentation"):
            setattr(self, key, document[key])
        self.modifiers = {k: ModifierInstance(**v) for k, v in document["modifiers"].items()}
        self.scheduler = SchedulerState(**document["scheduler"])
        self.rng = DeterministicRNG(**document["rng"])

    def snapshot(self) -> dict:
        return json.loads(canonical_json(asdict(self)))

    @classmethod
    def from_snapshot(cls, value: dict) -> BehaviorBattleState:
        document = copy.deepcopy(value)
        document["scheduler"] = SchedulerState(**document["scheduler"])
        document["rng"] = DeterministicRNG(**document["rng"])
        document["modifiers"] = {k: ModifierInstance(**v) for k, v in document["modifiers"].items()}
        return cls(**document)

    def clone(self) -> BehaviorBattleState:
        return self.from_snapshot(self.snapshot())

    def stable_hash(self) -> str:
        return stable_hash(self.snapshot())
