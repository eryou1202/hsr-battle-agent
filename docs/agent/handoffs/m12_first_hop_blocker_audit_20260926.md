# M12 first-hop expansion + blocker policy audit — CR-M12-FIRST-HOP-BLOCKER-AUDIT-20260926-001

Mechanical evidence only. The **only** previous-census restriction removed is the
single-named-target requirement. TriggerAbility was not executed or traversed
beyond one named edge, no compiler policy was changed, no runtime code was
written, no semantics were inferred, no existing M12 record was modified, no Git
write was issued.

- **Starting HEAD:** `52a1a0760af894d3c80958f4c63e5fd39d382284`
- **Machine-readable output:** `data/content_binding/4.4.54/content_first_hop_blocker_audit_001.json`
- **Decision:** `B. MORE_SETTLEMENT_CANDIDATES_FOUND_BUT_ALL_BLOCKED` **+**
  `D. COMPILER_POLICY_REVIEW_REQUIRED`
- **Next executor:** SOL

## 1. Exhaustive first-hop enumeration

The join is unchanged: 528 behaviour-root-bound skills, 519 EntryAbility roots
present in the 342 MB full compiler report (14,042 records streamed).

| Named targets in the root | Roots |
| --- | --- |
| 0 | 195 |
| 1 | **20** (this was the whole previous census) |
| 2 | **290** |
| 3 or more | 14 |

- **642 first-hop edges** (occurrence identity preserved, duplicates kept)
- **634 distinct target abilities**; 8 names occur more than once
- **0 targets missing** from the compiler report
- **0 targets missing** a raw `ConfigAbility` ability definition (668 container files, 6,870 defined names)
- Maximum depth is exactly one named edge; no target was followed further

## 2. Classification of all 634 target bodies

| Class | Count |
| --- | --- |
| TARGET_A_CLEAN | **0** |
| TARGET_B_RUNTIME_INPUT_ONLY | **0** |
| TARGET_C_STRUCTURALLY_BLOCKED | **241** |
| TARGET_D_NO_SETTLEMENT | **393** |

- **241 roots** reach at least one settlement target (previous census: 7 → **×34.4**)
- 0 roots have more than one distinct settlement target
- 235 roots have **mixed** settlement and non-settlement targets
- Settlement kinds: **226 `DAMAGE_REQUEST`, 24 `HEAL_REQUEST`** (previous census saw 1 heal body)
- 0 toughness-related settlement targets
- **All 241 are `compile_status: REJECTED`; all 241 carry a `WaitAnimState` blocker; 0 have zero blockers**

Structural blocker count per body ranges from **2** (20 bodies) to **29**.

| Structural blocker | Bodies |
| --- | --- |
| `BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` | **241 (all)** |
| `EXECUTABLE_REFERENCE_DAMAGE_MIXED_STATE_FIELDS` | 185 |
| `EXECUTABLE_REFERENCE_ADD_MODIFIER_ARGUMENTS_UNSUPPORTED` | 83 |
| `EXECUTABLE_REFERENCE_MODIFIER_DEFINITION_UNRESOLVED` | 54 |
| `EXECUTABLE_REFERENCE_RETARGET_TARGET_UNSUPPORTED` | 39 |
| `EXECUTABLE_REFERENCE_DAMAGE_ATTACK_TYPE_UNSUPPORTED` | 37 |
| `EXECUTABLE_REFERENCE_PROPERTY_VALUE_TYPE_UNSUPPORTED` | 21 |
| `EXECUTABLE_REFERENCE_UNSUPPORTED_HEAL_FORMULA` | 7 |

## 3. Blocker policy audit — existing authority only

Authority chain: `effect_ir_contract_v1.json` (assigns `kind`, `semantic_status`,
`gating_risk`) → `behavior_compiler.py::_compile_operations` (the only omission
rule) → `_reference_payload_problem` (per-operation payload gate) →
`tests/game_data/test_behavior_compiler.py`.

**The compiler has exactly one omission rule:**

```
semantic_status == "PRESENTATION" and gating_risk == "NONE"
    -> disposition = HEADLESS_PRESENTATION_OMITTED
```

Everything else that is behaviour-affecting becomes a `REJECT_NOT_NOOP`
diagnostic with reason `BEHAVIOR_AFFECTING_NODE_NOT_COMPILED`, which makes the
whole record `REJECTED`.

| Operation | Verdict |
| --- | --- |
| `RPG.GameCore.WaitAnimState` | **`EXPLICITLY_REJECTED`** |
| `RPG.GameCore.TriggerEffect` (sibling presentation) | `EXISTING_PRESENTATION_OMISSION_AUTHORIZED` |
| `RPG.GameCore.AddModifier` | **`EXPLICITLY_REJECTED`** (outside its allowlist) |
| `RPG.GameCore.Retarget` with `ByRandom=true` | **`EXPLICITLY_REJECTED`** |
| `RPG.GameCore.PredicateTaskList` | `NO_POLICY_FOUND` (bound and executable-reference; not an exclusion question) |
| `RPG.GameCore.DispelStatus` | `NO_POLICY_FOUND` (already bound `STRUCTURAL_PACKET_ONLY`) |

No new rule was created and no policy was changed.

## 4. WaitAnimState — why it differs from its presentation siblings

- **9,520** WaitAnimState occurrences appear as blockers corpus-wide; **0** appear as compiled operations.
- Every one carries `gating_risk: POSSIBLE_STATE_COMMIT`. **No WaitAnimState is ever compiled without `REJECT_NOT_NOOP`.**
- No code path treats it as presentation-only, and there is no special-case rule naming it.
- The contract assigns `TriggerEffect`, `TriggerAnimState`, `VCameraConfigChange` and `LookAt` `gating_risk: NONE` with *"none for headless simulation"* — those four **are** omitted. It assigns `WaitAnimState` `POSSIBLE_STATE_COMMIT` with *"explicit compiler gate"*.
- Therefore WaitAnimState fails the second half of the single omission rule, falls through to the generic `else`, and becomes a diagnostic.
- The contract's `headless_rule` permits omission "only after the compiler establishes they do not gate an effect, action completion, legal action, target, resource, or scheduler transition". **No such gate exists.**
- **241 of 241 settlement bodies contain a WaitAnimState blocker.** This is the universal, unavoidable blocker.

## 5. AddModifier

Blockers are **not** all the same — **6 distinct reasons**, dominated by
`EXECUTABLE_REFERENCE_MODIFIER_DEFINITION_UNRESOLVED` (6,676 corpus-wide) and
`EXECUTABLE_REFERENCE_ADD_MODIFIER_ARGUMENTS_UNSUPPORTED` (1,504). The existing
supported shapes are an explicit allowlist: `{ModifierName}`,
`{ModifierName, DynamicValues}`, `{ModifierName, LifeTime}` (fixed non-negative
integral, target `ModifierOwnerEntity`),
`{Chance, DynamicValues, InheritCaster, LifeTime, ModifierName}` (Chance==1,
InheritCaster==CasterSelf, fixed positive LifeTime, target `ParamEntity`), and
`{ModifierName, AliveOnly}` only when `AliveOnly` is exactly `False`. No
generalisation across shapes was performed.

## 6. Random Retarget

The only supported Retarget shape is `source_type RPG.GameCore.Retarget`, target
exactly `{Alias: ModifierOwnerAdjoinEntity}`, arguments exactly
`{MaxNumber, TaskList}`, `MaxNumber` a fixed positive integer — **no randomness**.
The code comment states the model is "deliberately limited … no random draw …
random selection remain separate contracts". Of **638** `ByRandom=true`
occurrences corpus-wide (aliases `AllDarkTeam`, `AllTeamMember`, `AllTeammate`,
`AllLightTeam`, `AllEnemy`, …), **0 match the supported form**. The test
`test_retarget_accepts_only_fixed_nonrandom_owner_adjoin_task_list` explicitly
asserts `ByRandom=True` is rejected. **No bounded random-target contract exists.**

## 7. Why the candidate count changed from 7 to 241

The previous census inspected a body only when the root had **exactly one**
top-level TriggerAbility target (20 roots) plus 3 roots whose own body carried a
settlement operation. **290 roots name two targets and 14 name three or more**,
and a root body usually has no settlement operation of its own. Removing that one
restriction exposes 642 edges → 634 distinct bodies → 241 settlement-bearing.
**No policy changed.** The gain is ×34.4 and the clean-candidate count is
unchanged: **0 before, 0 after.**

## 8. Top 10 candidates (existing-authorized cleanliness order)

| # | Body | Avatar/Skill | Structural blockers | Ops | Siblings |
| --- | --- | --- | --- | --- | --- |
| 1 | `Avatar_Klara_00_Skill01_Phase02` | 1107/110701 | 2 | 3 | 0 |
| 2 | `Avatar_Lynx_00_Skill01_Phase02` | 1110/111001 | 2 | 3 | 0 |
| 3 | `Avatar_FuXuan_00_Skill01_Phase02` | 1208/120801 | 2 | 3 | 0 |
| 4 | `Avatar_RuanMei_Skill01_Phase02` | 1303/130301 | 2 | 4 | 0 |
| 5 | `Avatar_Sam_00_Skill01_Phase02` | 1310/131001 | 2 | 3 | 0 |
| 6 | `Avatar_Misha_00_Skill01_Phase02` | 1312/131201 | 2 | 4 | 0 |
| 7 | `Avatar_Jade_00_Skill01_Phase02` | 1314/131401 | 2 | 4 | 0 |
| 8 | `Avatar_Constance_00_Skill01_Phase02` | 1321/132101 | 2 | 3 | 0 |
| 9 | `Avatar_Mydeimos_00_Skill01_Phase02` | 1404/140401 | 2 | 3 | 0 |
| 10 | `Avatar_Ashveil_00_Skill01_Phase02` | 1504/150401 | 2 | 3 | 0 |

For 19 of the top 20 the two blockers are exactly
`BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` (WaitAnimState class) +
`EXECUTABLE_REFERENCE_DAMAGE_MIXED_STATE_FIELDS`; the 20th adds
`RETARGET_TARGET_UNSUPPORTED`. **None is clean and none is called executable.**
The full 241-row ranking is in the JSON artifact.

## 9. Decision

**B. MORE_SETTLEMENT_CANDIDATES_FOUND_BUT_ALL_BLOCKED**, accompanied by
**D. COMPILER_POLICY_REVIEW_REQUIRED**.

- `EXISTING_POLICY_ALREADY_UNLOCKS_CANDIDATE`: **NO** — no authority authorizes omitting WaitAnimState, and no candidate reaches zero blockers.
- The dominant blocker (WaitAnimState `REJECT_NOT_NOOP`) has **no existing exclusion rule** and is `EXPLICITLY_REJECTED` by the contract, which names it as requiring "explicit compiler gate".
- Next executor: **SOL** (per the brief, SOL is appropriate for A or D).

## 10. Non-claims

TriggerAbility was not executed. WaitAnimState is **not** asserted safe to omit.
AddModifier is **not** asserted ignorable. Random Retarget is **not** asserted
safe. No content action is called executable. M12 is **not** declared unblocked.

## 11. Validation

JSON parses; duplicate-key validation PASS. The 528-skill population reproduces.
All 642 first-hop occurrences reproduce. All 634 targets exist in both the
compiler report and the raw ability containers. Compiler statuses, dispositions
and blocker reasons reproduce. Settlement counts reproduce. Every policy verdict
cites an exact existing source, symbol or test. No production code, no existing
M12 record and no frozen authority was modified; read-only Git only.
