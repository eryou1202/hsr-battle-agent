# Semantic Handoff 09

## Capability

Generic Modifier-owned property-contribution lifecycle: a generated StackProperty task selects targets, evaluates its DynamicValue, creates one opaque property contribution per target, records ownership on the persistent Modifier, and later removes that exact contribution by key.

Machine source of truth: `data/semantics/4.4.54/modifier_property_effect_09.json`.

## Proven topology

```text
StackProperty config (+0x18 target, +0x20 property, +0x28 DynamicValue) [SUPPORTED association]
  -> LEIHMEGJNME.OnTaskBegin M506082
  -> TurnBasedModifierInstance.StackProperty M506199
  -> TurnBasedAbilityComponent.StackProperty M506495
  -> Modifier[+0x240] append {property_id, contribution_key, target_component}

TurnBasedModifierInstance._PopStackedProperties M506312
  -> TurnBasedAbilityComponent.UnStackProperty M506496
  -> remove same opaque contribution_key
```

The M506082 config slot layout is native-confirmed. The direct generated factory edge from `RPG.GameCore.StackProperty` to `LEIHMEGJNME` is SUPPORTED by matching serializer/consumer layout, not yet CONFIRMED by a direct allocation edge.

## Proven primitives

- `battle.ir.task.stack_property_executor_init` — `LEIHMEGJNME..ctor`, M506081, `0xB770D00`, `eea586cc6fcbd946b5ca0b8ed710b7d25bb2df2771804e802f0cd8e5258e27ed`.
  Inputs `(task_context, task_config)`; writes executor `+0x18/+0x20`; task context is required. Pseudocode: store both references, mark kind, ensure modifier source.

- `battle.ir.task.stack_property_execute` — `LEIHMEGJNME.OnTaskBegin`, M506082, `0xB770D90`, `ff68b01727e135b2b22effcace3103b0d0e6c18990ded65e643b106fd124ba22`.
  Reads context `+0x68`, config `+0x18/+0x20/+0x28`; selects targets in forward order, evaluates DynamicValue, resolves each component, then calls M506199. Empty target list is a deterministic no-op; used nulls throw.

- `battle.ir.modifier.stack_property_contribution` — `TurnBasedModifierInstance.StackProperty`, M506199, `0xE7851A0`, `d4b7412d7fe22d17ee5e9e90ba468bac66fb978cbc7305405ef4ef62ee1a5c6f`.
  Inputs `(modifier, property_id, value, target_component, context_token, is_refresh)`; reads State `+0x80` and tracking list `+0x240`; State `> Alive` is a no-op. Normal path calls M506495 then appends `{property_id, returned_key, target_component}`. Refresh scans forward for matching `(property_id, target_component)` then routes through M506497. Internal guard policy remains UNKNOWN.

- `battle.ir.property.component_stack_boundary` — `TurnBasedAbilityComponent.StackProperty`, M506495, `0xE72EB90`, `9950bfd264c81de590eefb175f0a8a9dc05a16a015a05f1eeafeb1008419f2d5`.
  Inputs `(component, property_id, value, context)`; writes generic property-domain contribution state and returns an opaque key. It reaches `0xE72EFC0`; final-value materialization is not recovered.

- `battle.ir.modifier.pop_property_contributions` — `TurnBasedModifierInstance._PopStackedProperties`, M506312, `0xE78B740`, `95fc6bd67c4efaa08d073baccf9125940b44b679639b01b2765084c7dc6cc807`.
  Reads ordered records at `Modifier+0x240`; sets/clears pop guard `+0x2d1`; forward-calls M506496 using each `(target_component, property_id, contribution_key)` and consumes the records.

- `battle.ir.property.component_unstack_boundary` — `TurnBasedAbilityComponent.UnStackProperty`, M506496, `0xE731B80`, `ca1fc3692e7db537807189107832b2ff7aa763f5b494e0d64f8e0b01d1a093b7`.
  Inputs `(component, property_id, contribution_key, owner_modifier)`; removes through the same generic property domain. No inverse numeric arithmetic is proven.

All listed hashes use the declared `FIRST_SUCCESSFUL_RET` body projection; exact raw windows are in `data/raw/4.4.54/*property*_09.txt`.

## Persistent State Requirements

- `modifier_property_contributions[ModifierRef]`: ordered `PropertyContribution` records.
- A record contains `target_entity_or_component_ref`, opaque `property_id`, and opaque `contribution_key`.
- `entity_property_contributions[(entity_ref, property_id)]`: ordered keyed contributions. Keep this separate from any final/base property representation.
- Preserve target order on apply and contribution-record order on pop.

## Existing primitives to reuse

- DynamicValue evaluation from Batch 02.
- Target selection from Batch 05.
- Generated task execution context from Batch 06.
- Persistent Modifier identity and Alive/removed state from Batch 08.

## Application/inverse chain

```text
apply StackProperty task
  -> evaluate value once in task context
  -> for each target: add opaque keyed contribution
  -> append owner tracking record

pop owner contributions
  -> for each owner record: remove same key
  -> clear owner tracking records
```

## Mandatory implementation tests

- Two selected targets receive two distinct owner records in selector order.
- A removed/ToBeRemoved Modifier cannot create a new contribution.
- Popping removes only keys recorded for that Modifier; another Modifier's same-property contribution survives.
- Pop is deterministic in record order and leaves no owner records.
- No test or runtime path changes a final stat by direct `+=`/`-=` under this capability.

## UNKNOWN

- `0xE72EFC0` generic per-property materialization and its 83 observed cases.
- Key allocation/collision semantics inside the component property domain.
- Meaning/source of `Silence`, `IsRefresh`, and the M506199 refresh flag in every generated path.
- The universal lifecycle caller that triggers `_PopStackedProperties` for every destruction route.

## MUST NOT IMPLEMENT

- Do not implement `final_property_value += value` or its inverse.
- Do not expose guessed HP/ATK/DEF/SPD formulas.
- Do not map `StackProperty.IsRefresh` to M506199 without further evidence.
- Do not assume Modifier removal already invokes this pop helper on every path.

## Next Native Dependency

`TurnBasedAbilityComponent.StackProperty` enters `0xE72EFC0`, a broad 83-case property-domain dispatcher. It is recorded but deliberately deferred. The next simple-skill-oriented discovery pass should instead index generated task executors that reach a damage-request boundary, then recover the smallest bounded request chain before returning to stat materialization.
