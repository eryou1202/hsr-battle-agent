"""Evidence-aware, generic deterministic execution. No strict-admission facade.

This research path executes explicit reference policies. Decision/legality means
caller-bound local actions, never native legality or M15 qualification.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from hsr_battle_agent.battle_ir.behavior import (
    AbilityIR, IRNode, PredicateIR, TargetSelectorIR, canonical_json, stable_hash)
from .behavior_primitives import NumericSemanticGap, fixed_binary, raw_checked
from .behavior_state import BehaviorBattleState, ModifierInstance


class ExecutionStatus(str, Enum):
    COMPLETED = "COMPLETED"
    DECISION_POINT = "DECISION_POINT"
    WAITING_SCHEDULER = "WAITING_SCHEDULER"
    SEMANTIC_GAP = "SEMANTIC_GAP"
    INVALID_ACTION = "INVALID_ACTION"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True)
class SemanticGap:
    node: dict
    task_type: str
    evidence: dict
    required_capability: str
    blocking: bool = True


class GapError(Exception):
    def __init__(self, node: IRNode, capability: str):
        self.gap = SemanticGap(node.to_dict(), node.payload.get("task_type", node.op),
                               node.authority.to_dict(), capability)
        super().__init__(capability)


@dataclass
class GapLedger:
    entries: dict[str, dict] = field(default_factory=dict)

    def record(self, gap: SemanticGap):
        identity = stable_hash({"node": gap.node["node_id"], "evidence": gap.evidence,
                                "capability": gap.required_capability})
        entry = self.entries.setdefault(identity, {
            "primitive": gap.task_type, "node": gap.node["node_id"],
            "content_source": gap.evidence["source_artifact"],
            "frequency": 0, "blocking": gap.blocking,
            "evidence_status": gap.evidence, "required_capability": gap.required_capability,
            "recommended_next_implementation": f"Implement {gap.required_capability} generically with explicit reference policy"})
        entry["frequency"] += 1

    def to_dict(self) -> dict:
        return {"schema": "generic_runtime_semantic_gap_ledger/1",
                "entries": [self.entries[k] for k in sorted(self.entries)]}


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    semantic_authority: str = "REFERENCE_MODEL"
    completed_nodes: int = 0
    gap: SemanticGap | None = None
    trace: tuple[dict, ...] = ()


Handler = Callable[["BehaviorRuntime", IRNode, BehaviorBattleState], object]


class SemanticRegistry:
    def __init__(self):
        self.handlers: dict[str, dict[str, tuple[str, Handler]]] = {
            family: {} for family in ("task", "predicate", "target", "expression", "event")}

    def register(self, family: str, identity: str, handler: Handler, version: str = "reference_v1"):
        if identity in self.handlers[family]:
            raise ValueError(f"duplicate semantic identity {family}:{identity}")
        self.handlers[family][identity] = (version, handler)

    def invoke(self, family: str, engine: BehaviorRuntime, node: IRNode, state: BehaviorBattleState):
        if not isinstance(node, IRNode):
            raise TypeError("semantic operands must be IR nodes")
        entry = self.handlers[family].get(node.op)
        if entry is None:
            raise GapError(node, f"{family}:{node.op}")
        try:
            value = entry[1](engine, node, state)
        except NumericSemanticGap as exc:
            raise GapError(node, str(exc)) from exc
        except KeyError as exc:
            raise GapError(node, f"required semantic input:{exc.args[0]}") from exc
        engine.trace.append({"node": node.node_id, "op": node.op,
            "source_authority": node.authority.to_dict(), "semantic_authority": "REFERENCE_MODEL"})
        if node.op == "RPG.GameCore.TargetAlias":
            engine.trace[-1]["alias_authority"] = "CONFIGURED_REFERENCE_ALIAS"
        return value

    def identity(self) -> str:
        return stable_hash({k: {op: v[0] for op, v in sorted(h.items())}
                            for k, h in self.handlers.items()})


def _expression(engine, node, state):
    p, op = node.payload, node.op
    if op == "literal":
        return raw_checked(p["raw"]) if "raw" in p else p["value"]
    if op == "lookup":
        scope, key = p["scope"], str(p["key"])
        if key not in state.dynamic_values.get(scope, {}):
            raise GapError(node, f"dynamic_provider:{scope}/{key}")
        return raw_checked(state.dynamic_values[scope][key])
    if op == "identity":
        return engine.evaluate(p["arg"], state)
    if op == "conditional":
        branch = "then" if engine.evaluate(p["condition"], state) else "else"
        return engine.evaluate(p[branch], state)
    args = [engine.evaluate(x, state) for x in p["args"]]
    if op in {"add", "sub", "mul", "div"}:
        return fixed_binary(op, *args)
    if op in {"min", "max", "clamp"}:
        for raw in args:
            raw_checked(raw)
        if op == "min":
            return min(args)
        if op == "max":
            return max(args)
        return min(max(args[0], args[1]), args[2])
    operators = {"eq": lambda a,b: a == b, "ne": lambda a,b: a != b,
        "lt": lambda a,b: a < b, "le": lambda a,b: a <= b,
        "gt": lambda a,b: a > b, "ge": lambda a,b: a >= b}
    comparator = operators.get(p.get("comparison"))
    if comparator is None:
        raise GapError(node, "comparison operator binding")
    return comparator(*args)


def _targets(engine, node, state):
    p, op = node.payload, node.op
    if op == "RPG.GameCore.TargetAlias":
        name = p["alias"]
        if name not in engine.aliases:
            raise GapError(node, f"effective_target_alias:{name}")
        return engine.select(engine.aliases[name], state)
    context_ops = {"Caster": "caster", "AbilityTargetEntity": "ability_target",
        "SkillTargetEntityList": "skill_targets", "ParamEntity": "param_entity",
        "ModifierOwnerEntity": "modifier_owner", "RPG.GameCore.TargetFetchCaster": "caster",
        "RPG.GameCore.TargetFetchAbilityTarget": "ability_target",
        "RPG.GameCore.TargetFetchParamEntity": "param_entity"}
    if op in context_ops:
        key = context_ops[op]
        if key not in state.target_context:
            raise GapError(node, f"target_context:{key}")
        value = state.target_context[key]
        ids = value if isinstance(value, list) else [value]
    elif op == "explicit":
        ids = p["entities"]
    elif op == "sequence":
        ids = [eid for child in p["selectors"] for eid in engine.select(child, state)]
    elif op == "compare":
        right = engine.select(p["right"], state)
        ids = [eid for eid in engine.select(p["left"], state)
               if (eid in right) == p["include_matches"]]
    elif op in {"map", "filter"}:
        ids = []
        for eid in engine.select(p["source"], state):
            local = state.clone()
            local.target_context["param_entity"] = eid
            if op == "map":
                ids.extend(engine.select(p["selector"], local))
            elif engine.predicate(p["predicate"], local):
                ids.append(eid)
        # Random nested selectors consume the caller's stream in traversal order.
            state.rng = copy.deepcopy(local.rng)
    elif op == "random":
        ids = engine.select(p["source"], state)
        if not ids:
            raise GapError(node, "nonempty random target candidates")
        ids = [ids[state.rng.index(len(ids))]]
    else:
        raise GapError(node, f"target:{op}")
    if any(not isinstance(eid, str) or eid not in state.entities for eid in ids):
        raise GapError(node, "resolved entity identities for target context")
    return list(ids)


def _predicate(engine, node, state):
    p, op = node.payload, node.op
    if op in {"skill-tree-row-present", "RPG.GameCore.BySkillPointActivated"}:
        key = p.get("key", p.get("fields", {}).get("PointTriggerKey"))
        actor = p.get("actor", state.target_context.get("caster"))
        if key is None or actor not in state.progression:
            raise GapError(node, "explicit actor progression rows")
        rows = state.progression[actor].get("skill_tree_rows")
        if rows is None:
            raise GapError(node, "explicit skill_tree_rows dictionary")
        return str(key) in rows and rows[str(key)] is not None
    if op == "entity-state":
        targets = engine.select(p["target"], state)
        for eid in targets:
            if p["key"] not in state.entities[eid]:
                raise GapError(node, f"entity_state:{p['key']}")
        return all(state.entities[eid][p["key"]] == p["value"] for eid in targets)
    if op == "RPG.GameCore.ByIsTurnActionEntity":
        if "turn_action_entity" not in state.target_context:
            raise GapError(node, "turn action entity context")
        return state.target_context["turn_action_entity"] in engine.select(p["fields"]["TargetType"], state)
    if op == "comparison":
        return bool(engine.evaluate(p["expression"], state))
    if op == "not":
        return not engine.predicate(p["arg"], state)
    if op == "all":
        return all(engine.predicate(child, state) for child in p["args"])
    if op == "any":
        return any(engine.predicate(child, state) for child in p["args"])
    raise GapError(node, f"predicate:{op}")


def _tasks(engine, node, state):
    p, op = node.payload, node.op
    f = p.get("fields", {})
    if op == "RPG.GameCore.PredicateTaskList":
        branch = "SuccessTaskList" if engine.predicate(f["Predicate"], state) else "FailedTaskList"
        value = f.get(branch)
        if value is None:
            return []  # Serialized absent branch, not a missing predicate default.
        if not isinstance(value, IRNode) or value.kind != "TaskSequenceIR":
            raise GapError(node, "decoded conditional task sequence")
        return [value]
    if op == "RPG.GameCore.TriggerAbility":
        engine.select(f["TargetType"], state)
        name = engine.evaluate(f["AbilityName"], state)
        if name not in engine.abilities:
            raise GapError(node, f"decoded_ability_binding:{name}")
        if engine.policies.get("invocation") != "REFERENCE_SEQUENCE":
            raise GapError(node, "ability context/controller inheritance policy")
        return [engine.abilities[name]]
    if op == "RPG.GameCore.SetDynamicValue":
        raise GapError(node, "effective dynamic write provider/key/value binding")
    if op == "RPG.GameCore.HealHP":
        raise GapError(node, "heal pre-hooks/effective operands/settlement/property/post-hooks")
    if op == "dynamic_write":
        value = raw_checked(engine.evaluate(p["value"], state))
        state.dynamic_values.setdefault(p["scope"], {})[str(p["key"])] = value
    elif op in {"property_write", "resource_write"}:
        amount = raw_checked(engine.evaluate(p["value"], state))
        if op == "property_write":
            store = state.properties
        elif p["scope"] == "actor":
            store = state.actor_resources
        elif p["scope"] == "team":
            store = state.team_resources
        else:
            raise GapError(node, "resource scope must be explicitly actor or team")
        owner, key = p["owner"], str(p["key"])
        if op == "property_write" or p["scope"] == "actor":
            if owner not in state.entities:
                raise GapError(node, "resolved mutation owner entity")
        operation = p["operation"]
        if operation == "set":
            store.setdefault(owner, {})[key] = amount
        elif operation == "add":
            if key not in store.get(owner, {}):
                raise GapError(node, f"initial property/resource value:{owner}/{key}")
            store[owner][key] = fixed_binary("add", store[owner][key], amount)
        else:
            raise GapError(node, f"mutation operation:{operation}")
    elif op == "modifier_apply":
        instance = ModifierInstance(**p["instance"])
        if instance.instance_id in state.modifiers:
            raise GapError(node, "modifier stack/renew policy")
        if any(eid not in state.entities for eid in (instance.owner, instance.caster, instance.original_caster)):
            raise GapError(node, "modifier owner/caster identities")
        state.modifiers[instance.instance_id] = instance
    elif op == "modifier_remove":
        if p["instance_id"] not in state.modifiers:
            raise GapError(node, "modifier removal instance binding")
        del state.modifiers[p["instance_id"]]
    elif op == "random_choice":
        choices = p["choices"]
        if not choices:
            raise GapError(node, "nonempty random choices")
        return [choices[state.rng.index(len(choices))]]
    elif op == "barrier":
        if not state.scheduler.barriers.get(p["key"], False):
            return ExecutionStatus.WAITING_SCHEDULER
    elif op == "schedule":
        state.scheduler.schedule(p["tick"], [child.to_dict() for child in p["tasks"]], p.get("release"))
    elif op == "completion":
        state.scheduler.completion_requested = True
    elif op == "event_dispatch":
        event_type = p["event_type"]
        if event_type not in engine.events:
            raise GapError(node, f"event listener/order policy:{event_type}")
        state.pending_events.append({"event_type": event_type, "payload": p.get("payload", {}),
                                     "node": node.to_dict()})
    else:
        raise GapError(node, f"task:{op}")
    return []


def _event(engine, node, state):
    event = state.pending_events[0]
    return engine.events[event["event_type"]]


def default_registry() -> SemanticRegistry:
    registry = SemanticRegistry()
    for op in ("literal", "lookup", "identity", "add", "sub", "mul", "div", "min", "max", "clamp", "compare", "conditional"):
        registry.register("expression", op, _expression)
    for op in ("Caster", "AbilityTargetEntity", "SkillTargetEntityList", "ParamEntity", "ModifierOwnerEntity",
        "RPG.GameCore.TargetAlias", "RPG.GameCore.TargetFetchCaster", "RPG.GameCore.TargetFetchAbilityTarget",
        "RPG.GameCore.TargetFetchParamEntity", "explicit", "sequence", "map", "filter", "compare", "random"):
        registry.register("target", op, _targets)
    for op in ("skill-tree-row-present", "RPG.GameCore.BySkillPointActivated", "entity-state", "comparison",
        "not", "all", "any", "RPG.GameCore.ByIsTurnActionEntity"):
        registry.register("predicate", op, _predicate)
    for op in ("RPG.GameCore.PredicateTaskList", "RPG.GameCore.TriggerAbility", "RPG.GameCore.SetDynamicValue",
        "RPG.GameCore.HealHP", "dynamic_write", "property_write", "resource_write", "modifier_apply",
        "modifier_remove", "random_choice", "barrier", "schedule", "completion", "event_dispatch"):
        registry.register("task", op, _tasks)
    registry.register("event", "event_dispatch", _event)
    from .behavior_expansion import install
    install(registry)
    return registry


class BehaviorRuntime:
    def __init__(self, state: BehaviorBattleState, *, actions: dict[str, AbilityIR] | None = None,
                 abilities: dict[str, AbilityIR] | None = None, aliases: dict[str, TargetSelectorIR] | None = None,
                 events: dict[str, list[IRNode]] | None = None, policies: dict | None = None,
                 registry: SemanticRegistry | None = None, templates: dict[str, IRNode] | None = None):
        self.state = state.clone()
        self.actions = dict(actions or {})
        self.abilities = dict(abilities or {})
        self.templates = dict(templates or {})
        self.aliases = dict(aliases or {})
        self.events = copy.deepcopy(events or {})
        self.policies = copy.deepcopy(policies or {})
        canonical_json(self.policies)
        self.registry = copy.deepcopy(registry) if registry else default_registry()
        self.gaps = GapLedger()
        self.trace: list[dict] = []
        self._selector_stack: list[str] = []

    def evaluate(self, node: IRNode, state=None):
        return self.registry.invoke("expression", self, node, state or self.state)

    def select(self, node: IRNode, state=None):
        state = state or self.state
        identity = node.stable_hash()
        if identity in self._selector_stack or len(self._selector_stack) >= 64:
            raise GapError(node, "target/alias recursive cycle or depth bound")
        self._selector_stack.append(identity)
        candidate = state.clone()
        try:
            result = self.registry.invoke("target", self, node, candidate)
            state.rng = copy.deepcopy(candidate.rng)
            return result
        finally:
            self._selector_stack.pop()

    def predicate(self, node: IRNode, state=None):
        state = state or self.state
        candidate = state.clone()
        result = self.registry.invoke("predicate", self, node, candidate)
        state.rng = copy.deepcopy(candidate.rng)
        return result

    def clone(self) -> BehaviorRuntime:
        result = BehaviorRuntime(self.state, actions=self.actions, abilities=self.abilities,
            aliases=self.aliases, events=self.events, policies=self.policies, registry=self.registry,
            templates=self.templates)
        result.gaps = copy.deepcopy(self.gaps)
        result.trace = copy.deepcopy(self.trace)
        return result

    def snapshot(self) -> dict:
        return {"schema": "evidence_aware_runtime/1", "state": self.state.snapshot(),
            "actions": {k: v.to_dict() for k,v in self.actions.items()},
            "abilities": {k: v.to_dict() for k,v in self.abilities.items()},
            "templates": {k: v.to_dict() for k,v in self.templates.items()},
            "aliases": {k: v.to_dict() for k,v in self.aliases.items()},
            "events": {k: [n.to_dict() for n in v] for k,v in self.events.items()},
            "policies": copy.deepcopy(self.policies), "registry_identity": self.registry.identity()}

    @classmethod
    def from_snapshot(cls, snapshot: dict, registry=None):
        registry = registry or default_registry()
        if snapshot["schema"] != "evidence_aware_runtime/1" or registry.identity() != snapshot["registry_identity"]:
            raise ValueError("snapshot/registry mismatch")
        maps = {key: {k: IRNode.from_dict(v) for k,v in snapshot[key].items()}
                for key in ("actions", "abilities", "aliases")}
        return cls(BehaviorBattleState.from_snapshot(snapshot["state"]), **maps,
            templates={k: IRNode.from_dict(v) for k, v in snapshot.get("templates", {}).items()},
            events={k: [IRNode.from_dict(v) for v in values] for k,values in snapshot["events"].items()},
            policies=snapshot["policies"], registry=registry)

    def stable_hash(self) -> str:
        return stable_hash(self.snapshot())

    def legal_actions(self) -> tuple[str, ...]:
        if self.state.terminal or self.state.scheduler.continuation or self.state.scheduler.callbacks or self.state.pending_events:
            return ()
        return tuple(sorted(self.actions))

    def step(self, action_id: str) -> ExecutionResult:
        if action_id not in self.legal_actions():
            return ExecutionResult(ExecutionStatus.INVALID_ACTION)
        self.trace = []
        self.state.scheduler.completion_requested = False
        self.state.scheduler.continuation.append(self.actions[action_id].to_dict())
        return self.run_until_decision()

    def _callback(self) -> bool:
        scheduler = self.state.scheduler
        if not scheduler.callbacks:
            return False
        callback = scheduler.callbacks.pop(0)
        scheduler.tick = callback["tick"]
        if callback["release"] is not None:
            scheduler.barriers[callback["release"]] = True
        scheduler.continuation[0:0] = callback["nodes"]
        return True

    def run_until_decision(self, max_nodes: int = 10000) -> ExecutionResult:
        completed = 0
        for _ in range(max_nodes):
            state, scheduler = self.state, self.state.scheduler
            if state.terminal:
                return ExecutionResult(ExecutionStatus.TERMINAL, completed_nodes=completed, trace=tuple(self.trace))
            if not scheduler.continuation:
                if state.pending_events:
                    event = state.pending_events[0]
                    node = IRNode.from_dict(event["node"])
                    candidate = state.clone()
                    try:
                        children = self.registry.invoke("event", self, node, candidate)
                    except GapError as exc:
                        self.gaps.record(exc.gap)
                        return ExecutionResult(ExecutionStatus.SEMANTIC_GAP, completed_nodes=completed,
                            gap=exc.gap, trace=tuple(self.trace))
                    self.state = candidate
                    state, scheduler = candidate, candidate.scheduler
                    state.pending_events.pop(0)
                    scheduler.continuation.extend(n.to_dict() for n in children)
                    continue
                if self._callback():
                    continue
                status = ExecutionStatus.COMPLETED if scheduler.completion_requested else ExecutionStatus.DECISION_POINT
                return ExecutionResult(status, completed_nodes=completed, trace=tuple(self.trace))
            node = IRNode.from_dict(scheduler.continuation[0])
            p = node.payload
            if node.kind in {"AbilityIR", "TaskSequenceIR"}:
                if node.kind == "AbilityIR" and node.op == "structure_record":
                    gap = GapError(node, "modifier/event root installation and callback lifecycle policy").gap
                    self.gaps.record(gap)
                    return ExecutionResult(ExecutionStatus.SEMANTIC_GAP, gap=gap,
                        completed_nodes=completed, trace=tuple(self.trace))
                if node.kind == "AbilityIR" and p.get("reference_unbound_sequences"):
                    gap = GapError(node, "ability lifecycle task-list slots require reference continuation policy").gap
                    self.gaps.record(gap)
                    return ExecutionResult(ExecutionStatus.SEMANTIC_GAP, gap=gap,
                        completed_nodes=completed, trace=tuple(self.trace))
                if node.kind == "AbilityIR" and node.op == "decoded_graph":
                    gap = GapError(node, "explicit ability entry binding; decoded graph is a catalog").gap
                    self.gaps.record(gap)
                    return ExecutionResult(ExecutionStatus.SEMANTIC_GAP, gap=gap,
                        completed_nodes=completed, trace=tuple(self.trace))
                elif node.kind == "AbilityIR":
                    children = [p["tasks"]]
                else:
                    children = p["tasks"]
                scheduler.continuation[0:1] = [child.to_dict() for child in children]
                continue
            candidate = state.clone()
            try:
                if node.kind == "UnsupportedSemanticIR":
                    raise GapError(node, p["required_capability"])
                children = self.registry.invoke("task", self, node, candidate)
                if children == ExecutionStatus.WAITING_SCHEDULER:
                    if self._callback():
                        continue
                    return ExecutionResult(ExecutionStatus.WAITING_SCHEDULER,
                        completed_nodes=completed, trace=tuple(self.trace))
            except GapError as exc:
                self.gaps.record(exc.gap)
                return ExecutionResult(ExecutionStatus.SEMANTIC_GAP, completed_nodes=completed,
                                       gap=exc.gap, trace=tuple(self.trace))
            # Each leaf is atomic: a gap never leaks RNG, property or event mutations.
            candidate.scheduler.continuation[0:1] = [child.to_dict() for child in children]
            self.state = candidate
            completed += 1
        return ExecutionResult(ExecutionStatus.WAITING_SCHEDULER,
            completed_nodes=completed, trace=tuple(self.trace))

    def replay(self, action_ids: list[str]) -> tuple[BehaviorRuntime, tuple[ExecutionResult, ...]]:
        runtime = self.clone()
        results = []
        for action in action_ids:
            result = runtime.step(action)
            results.append(result)
            if result.status in {ExecutionStatus.SEMANTIC_GAP, ExecutionStatus.INVALID_ACTION, ExecutionStatus.WAITING_SCHEDULER}:
                break
        return runtime, tuple(results)
