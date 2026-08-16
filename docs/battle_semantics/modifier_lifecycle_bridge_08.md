# Battle Semantic Modifier Lifecycle Bridge 08

> Final status: **`BATTLE_SEMANTIC = MODIFIER_LIFECYCLE_BRIDGE_08_PROOF`**
> Sandbox status: **`BATTLE_SANDBOX = MODIFIER_LIFECYCLE_RUNTIME_08_PROOF`**
> Game version: `4.4.54` (20260731-0529-BetaLive-15953205-OSBETAWin4.4.54-OSCb)
> Evidence level: `E4_STATIC_MACHINE_CODE` (accepted primitives / chain boundaries)
> Artifact schema: `battle_semantics_batch/1`

## 1. Scope

This batch answers one question:

> When a Modifier already exists in an entity's `ModifierList`, what do
> `Add / Remove / Destroy / Activate` really do?

Entry point is the already known
`RPG.GameCore.TurnBasedAbilityComponent.TryAddModifierInstance`
(method index `506463`, RVA `0xE729500`, 3424-byte gap).  No blind modifier
search was performed.

This is **not** the Modifier effect system, not the Event system, not Damage,
not DOT, and not a duration/turn engine.

## 2. First-round report (before PHASE A acceptance)

1. **Commits / tracked state**: `f3476d9`, `33cf283`, `b62910f`, `1ec6983`
   confirmed at session start; pre-existing untracked files
   (`hsr_design_data_hashes.csv`, `hsr_design_data_inventory.csv`,
   `tools/reference/`, `tools/reverse/vendor/`) left untouched.
2. **TryAddModifierInstance method/RVA/body**: M `506463`, RVA `0xE729500`,
   full gap `0xD60` (3424 bytes) to `_AddModifierDelayParam` at `0xE72A260`.
   Switch table at `0xE72A244` (`ordinal = config[+0x18] - 7`).
3. **Existing-instance lookup helper**:
   `TurnBasedAbilityComponent.FindModifierInstance` (`0xE72B410`)
   → `AbilityComponent.FindModifierInstance` (`0xE432540`)
   → `AbilityComponent._IsModifierMatchSearch` (`0xE4326E0`).
4. **Lookup key evidence**: **not** "same name only".  The predicate is
   `(name, State filter, StackingFlag, optional caster RuntimeID, optional
   source-provider object identity)`, see §4.
5. **Destroy/remove path**:
   `TurnBasedModifierInstance.Destroy` (`0xE7384B0`) sets
   `State [+0x80] = 2 (ToBeRemoved)`; the real list mutation is
   `AbilityComponent.RemoveDirtyModifiers` (`0xE430290`): backward scan,
   count--, shift-left, tail clear, version++.
6. **Re-add path**: fresh `TurnBasedModifierInstance..ctor` (`0xE77EB00`)
   → `AbilityComponent.AddModifierInstance` (`0xE431890`) ordered append
   (Batch 07 leaf reused).
7. **Post-apply virtual dispatch**: two calls on the new modifier through the
   lifecycle interface.  Slot `13` = `OnAdded` (unconditional), slot `14` =
   `OnActivate` (conditional on the `AddModifierInstance` bool argument).
8. **ModifierInstance lifecycle fields**: State (`[+0x80]`), StackingFlag
   (`[+0x88]`), destroy guard (`[+0x94]`), ConfigRef (`[+0xa0]`),
   is-max-layer (`[+0x8e]`), Layer (`[+0x288]`), MaxLayer slots
   (`[+0x2e0]`/`[+0x270]`), CurrentLife (`[+0x2c4]`), previous life
   (`[+0x2e4]`), owner component (`[+0x198]`).
9. **Candidates**: 25 plausible candidates, 8 shortlisted (machine-recorded
   in `modifier_lifecycle_discovery_08.json`).
10. **Shortlist**: TryAdd, `AbilityComponent.FindModifierInstance`,
    `_IsModifierMatchSearch`, `Destroy`, `RemoveDirtyModifiers`,
    `_ProcessModifierRedd`, `OnAdded`, `OnActivate`.
11. **PRIMARY chain**: `try_add_modifier_instance_duplicate_chain`, §6.
12. **Dependency boundary**: Event/Damage/DOT/Turn systems were recorded as
    dependencies and not entered.
13. **Duplicate policy closure**: YES — the decision tree is fully bounded;
    refresh internals beyond the recovered deterministic core are deferred.

## 3. Config layout proof: `ModifierConfig.Stacking [+0x18]`

`ModifierConfig.MGMEGEDLMAK` (`0x1D21C7D0`) writes the six config fields in
this exact order (E4 native stores + E3 field order):

| native offset | field |
|---|---|
| `+0x10` | `Priority` |
| `+0x14` | `Count` |
| `+0x18` | `Stacking` (`ModifierStacking` enum) |
| `+0x20` | `DynamicValues` |
| `+0x28` | `DynamicStrings` |
| `+0x30` | `TaskListTemplate` |

Two independent consumers read `[config +0x18]` and switch on the exact enum
ordinals:

- `TryAddModifierInstance` switch: ordinals `7..13`;
- `_ProcessModifierRedd` switch (through `ConfigRef [+0xa0]`): ordinals `2..12`.

`ModifierStacking` E3 members (ordinals 0..13):
`Unknow, Unique, Refresh, Prolong, Multiple, Replace, Merge,
ReplaceByCaster, ReplaceByCasterOrUnStack, EntityUnique,
ReplaceButKeepLifeTime, RetainGlobalLatest, ReplaceByCasterAbility,
RetainGlobalLatestUnique`.

This is not a same-name-stack guess; each enum value has a native branch.

## 4. Duplicate match identity (ABI-independent)

`AbilityComponent._IsModifierMatchSearch` accepts an item when **all** of the
following hold:

| native predicate | recovered meaning | wildcard |
|---|---|---|
| `item.Name [+0x60] == name` (pointer or ordinal content) | config name string | none |
| State filter | `0`: State `0..1`; `1`: State `==1`; other: no filter | other |
| `item.StackingFlag [+0x88] == filter` | StackingFlag from runtime param `[+0x5c]` | `100` |
| caster RuntimeID filter | `resolver([+0x48]).RuntimeID [+0xd0] == filter` | `0` / `-1` |
| source-provider filter | resolver vtable `[+0x130]` object identity == source | `null` |

`TurnBasedAbilityComponent.FindModifierInstance` delegates to the same
container predicate and then type-checks the result against
`TurnBasedModifierInstance`.
`GlobalFindModifierInstance` collects candidate components through the global
modifier manager and calls the **same container predicate** per component.

Therefore:

- `instance_identity` (sandbox) = `ModifierRef(name, owner_entity, instance_ordinal)`;
- `duplicate_match_key` (client) = `(name, StackingFlag, optional
  caster_entity.runtime_id, optional source_provider object identity)`.

They are deliberately recorded as separate artifact sections.  The native
source-provider check is object-pointer equality; the sandbox materializes it
as a caller-supplied deterministic `ObjectRef` and records the native object
id as UNKNOWN.

## 5. TryAddModifierInstance decision tree

```text
TryAddModifierInstance(component, name, config, source_provider, param):
    stacking = config[+0x18]                 # ModifierStacking

    if stacking in {7, 8, 12}:               # ReplaceByCaster family
        lookup = local(component,
                       name,
                       stacking_flag = param[+0x5c],
                       caster = source_provider.entity.RuntimeID,
                       source_provider = source_provider)
    elif stacking in {11, 13}:               # RetainGlobalLatest family
        lookup = global(manager_scope,
                        name,
                        stacking_flag = param[+0x5c])
    else:                                    # 0..6, 9, 10
        lookup = local(component,
                       name,
                       stacking_flag = param[+0x5c])

    existing = lookup.first_match()
    if existing is None:
        return append_new()                  # tail append, Batch 07

    if stacking == Multiple(4):
        return append_new()                  # keep old, append duplicate

    if stacking == RetainGlobalLatest(11):
        existing.Destroy(0)                  # State -> ToBeRemoved(2)
        return append_new()                  # old leaves list on RemoveDirty

    if stacking == RetainGlobalLatestUnique(13):
        if resolver(existing).entity == component.owner_entity:
            return process_existing(existing)
        existing.Destroy(0)
        return append_new()

    return process_existing(existing)

process_existing(existing):
    if existing.State == 0:                  # ToBeAdded
        _AddModifierDelayParam(component, 1, existing, source, param)
        return existing                      # delayed queue; list unchanged
    _ProcessModifierRedd(component, existing, source, param)
    if existing.State == 1:                  # Alive
        _PostProcessAfterModifierAdd(component, existing)
    return existing

append_new():
    new = TurnBasedModifierInstance.ctor(name, config, component,
                                         source_provider, param)
    AddModifierInstance(component, new, activate_flag)
    new.is_max_layer = false                 # native post-append clear
    if new.State == 1:
        _PostProcessAfterModifierAdd(component, new)
    return new
```

Final persistent-list outcomes:

| existing? | Stacking | final `_ModifierList` state |
|---|---|---|
| no | any | ordered tail append |
| yes | `Multiple(4)` | old kept; new duplicate appended |
| yes | `RetainGlobalLatest(11)` | old `State=2`, new appended; old physically removed by `RemoveDirtyModifiers` |
| yes | `RetainGlobalLatestUnique(13)` caster != owner | same as `11` |
| yes | `RetainGlobalLatestUnique(13)` caster == owner | no append; existing processed in place |
| yes | other | no append; existing processed in place or delayed queue |

`_ProcessModifierRedd` recovered deterministic core by its own switch
(`ordinal = config[+0x18] - 2`):

| Stacking | deterministic core |
|---|---|
| `Refresh(2)`, `Replace(5)`, `ReplaceByCaster(7)`, `ReplaceByCasterOrUnStack(8)`, `ReplaceByCasterAbility(12)` | `CurrentLife = new_life`, `previous_life = CurrentLife`, `Count = new_count` |
| `Prolong(3)` | `CurrentLife = current + new` (unless a `-1` sentinel) |
| `Merge(6)` | `CurrentLife = max(current, new)` (unless a `-1` sentinel) |
| `ReplaceButKeepLifeTime(10)` | `Count = new_count`; `CurrentLife` kept |
| `Multiple(4)`, `EntityUnique(9)`, `RetainGlobalLatest(11)`, `RetainGlobalLatestUnique(13)` | config-only branch |

Every path first recomputes `is_max_layer` =
`Layer >= max(1, [+0x2e0] + [+0x270])`.  `OnReplace`,
`_OnModifierValueChanged`, UI refresh and notification tailcalls are deferred
effects.

## 6. Removal / Destroy

`Destroy(int)` (`0xE7384B0`):

```text
if State > 1: return                        # ToBeRemoved/Removed: idempotent
State [+0x80] = 2                           # ToBeRemoved
destroy_reason [+0x98] = arg
cleanup callbacks + recursive child destroy # deferred effects
tailcall BaseModifierInstance.Destroy       # deferred
```

`RemoveDirtyModifiers` (`0xE430290`):

```text
for index in [count-1 .. 0]:
    if item.State == Alive(1): keep
    elif item.destroy_guard [+0x94] > 0: keep
    else:
        dispose(item)                       # deferred virtual
        count--
        shift items[index+1..count] left by one   # memmove
        items[count] = null
        version++
```

Native proof: this is `List<T>.RemoveAt`-equivalent **shift-left**, not
swap-back, not tombstone.  Remaining order is preserved.  Python `list.remove`
is therefore E4-equivalent for this leaf; the sandbox still implements the
explicit filter/shift copy and never relies on unordered collections.

## 7. Lifecycle state and callback mounts

`ModifierState` enum (`BaseModifierInstance.State [+0x80]`, E3 members + E4
consumers):

| ordinal | name | native consumers |
|---|---|---|
| 0 | `ToBeAdded` | `TryAdd` delayed-add branch |
| 1 | `Alive` | Base ctor writes 1; `HasModifier` filter; post-add gate |
| 2 | `ToBeRemoved` | `Destroy` writes 2 |
| 3 | `Removed` | `Destroy` idempotence guard (`> 1`) |

`ModifierStackingFlag` enum (instance `[+0x88]`): `Default(0)`,
`CharacterSkill(1)`, `Equipment(2)`, `Relic(3)`, `Level(4)`, `Rogue(5)`,
`Any(6)`; `100` is the match-predicate wildcard constant.

Post-append virtual mounts in `AddModifierInstance`:

- slot `13` → `TurnBasedModifierInstance.OnAdded` (`0xE781890`),
  unconditional, argument `0`; initializes sequence-state slots
  (`[+0x168]/[+0x16a]/[+0x170]`) — effect internals deferred;
- slot `14` → `TurnBasedModifierInstance.OnActivate` (`0xE781C40`),
  conditional on the bool argument; writes `State=Alive(1)` and
  is-activating `[+0x8d]=1` — lifecycle transition SUPPORTED, effect
  internals deferred.

The slot identities are anchored by concrete consumer call sites:
`AbilityComponent.Tick` dispatches slot `11` with a float argument (Tick),
`ClearAllModifierInstance` dispatches slot `12` with an int argument
(Destroy), and `AddModifierInstance` dispatches slots `13`/`14` with no
argument.

## 8. Stack / duration status

- Stack policy: **CLOSED at the duplicate-decision level** (see §5).  Full
  `OnStack`/`UnStack` effect fan-out stays deferred.
- Duration expiration: still `MODIFIER_EXPIRATION_DEPENDENCY_REQUIRED`.
  This batch recovers only the `CurrentLife`/previous-life refresh arithmetic
  directly touched by `TryAdd`/`_ProcessModifierRedd`; no Turn/Round/Event
  timeline was entered.

## 9. Accepted primitives (8, all E4)

| primitive_id | source method | M | RVA | result |
|---|---|---|---|---|
| `battle.ir.modifier.try_add_modifier_instance` | `TurnBasedAbilityComponent.TryAddModifierInstance` | 506463 | `0xE729500` | `modifier_lifecycle_result` |
| `battle.ir.modifier.container_find_modifier_instance` | `AbilityComponent.FindModifierInstance` | 520243 | `0xE432540` | `modifier_state_or_null` |
| `battle.ir.modifier.match_modifier_search` | `AbilityComponent._IsModifierMatchSearch` | 520252 | `0xE4326E0` | `boolean` |
| `battle.ir.modifier.lifecycle_destroy` | `TurnBasedModifierInstance.Destroy` | 506250 | `0xE7384B0` | `modifier_state` |
| `battle.ir.modifier.container_remove_dirty` | `AbilityComponent.RemoveDirtyModifiers` | 520247 | `0xE430290` | `modifier_container` |
| `battle.ir.modifier.lifecycle_process_redd` | `TurnBasedAbilityComponent._ProcessModifierRedd` | 506464 | `0xE72A3C0` | `modifier_state` |
| `battle.ir.modifier.lifecycle_on_added` | `TurnBasedModifierInstance.OnAdded` | 506175 | `0xE781890` | `modifier_state` |
| `battle.ir.modifier.lifecycle_on_activate` | `TurnBasedModifierInstance.OnActivate` | 506176 | `0xE781C40` | `modifier_state` |

Body windows / branch counts / sha256 / disassembly are machine-recorded in
the JSON artifact.

## 10. PHASE A success conditions

- **A** TryAddModifierInstance duplicate decision tree closed: YES.
- **B** At least one existing-modifier persistent mutation proven: YES
  (`RetainGlobalLatest(11)` Destroy+append, and `RemoveDirtyModifiers`
  shift-left removal).
- **C** Duplicate match identity explicit: YES (`name + StackingFlag +
  optional caster + optional source provider`).
- **D** At least one removal/replace/refresh path E4: YES
  (`Destroy`/`RemoveDirtyModifiers` removal chain and `_ProcessModifierRedd`
  refresh core).
- **E** State / list-ordering read-write set explicit: YES.

## 11. Known unknowns

- runtime param `typeref 608873` canonical type name;
- source-provider resolver vtable `[+0x130]` method identity;
- `TurnBasedAbilityComponent [+0x2b4]` counter / activation-flag semantics;
- global manager search ordering (sandbox uses deterministic runtime-id
  order, recorded as a projection);
- delayed-add queue `[+0x1e0]` processing trigger;
- no E5 client-side runtime observation.

## 12. Explicitly not this round

Modifier effects, DOT, Damage, Event listener runtime, Turn expiration, AV,
Buff/Debuff taxonomy, Black Swan, `legal_actions`, `step`, `is_terminal`,
Planner.

Machine-readable companions:

- `data/semantics/4.4.54/modifier_lifecycle_bridge_08.json`
- `data/raw/4.4.54/modifier_lifecycle_discovery_08.json`
- Sandbox report: `data/sandbox/modifier_lifecycle_runtime_08_report.json`
