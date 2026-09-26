# Backend Contract Freeze Audit

Change request: `CR-BACKEND-FREEZE-AUDIT-20260927-001`

Starting HEAD: `8a4dcb00794463e64c257083330e2783167289e8`  |  branch `terra/implementation`

Audit only. No production or contract change.

## Freeze decision

**A. BACKEND_CONTRACT_STACK_FREEZE_READY**

All seven boundaries are explicit and non-overlapping, the import graph is strictly layered with no back-edges, every real-content execution path is denied before any execution artifact can exist, no policy is derived outside its authoritative layer, content versions are explicit with no fallback, and the full backend suite passes. The only open items are forward-looking delta work, not defects in the current stack.

Concrete blocking fixes: none.

## Layer boundaries

| id | boundary | owner | explicit | native claims |
|---|---|---|---|---|
| A | synthetic/local reference action execution | `state_v2` | yes | no |
| B | reference settlement | `OrdinaryReferencePacket` | yes | no |
| C | planner search | `reference_battle_planner` | yes | no |
| D | real-content identity/representation | `json (data)` | yes | no |
| E | content capability querying | `content_support` | yes | no |
| F | real-content planner admission | `content_planner` | yes | no |
| G | native evidence/gate authority | `evidence (EvidenceMode / VersionRelation / ReadinessClass)` | yes | yes |

## Execution safety

| check | result |
|---|---|
| real_content_cannot_create_reference_action_envelope | True |
| real_content_cannot_enter_player_legal_action | True |
| real_content_cannot_expand_planner_successor | True |
| rejected_content_touches_battle_state_rng_allocator_scheduler | False |
| registry_query_artifacts_can_satisfy_gate_certificate | False |
| synthetic_m10_m11_path_explicitly_scoped_and_usable | True |
| implicit_4_5x_fallback_exists | False |
| planner_path_interprets_checked_fields | False |

Re-enacted denial over the canonical registry: **620/620 rejected**, all non-effect counters 0.

## Contract stability

| contract | layer | classification |
|---|---|---|
| TerraBattleState | A | STABLE_WITH_VERSIONED_EXTENSION |
| ReferenceActionEnvelope | A/B | FROZEN_STABLE |
| ReferenceBattleSession | A | FROZEN_STABLE |
| battle planner request/result (ReferenceBattleObjective, ReferenceBattleSearchPolicy, BattlePlan, BattlePlannerResult) | C | FROZEN_STABLE |
| ContentSkillKey | D/E | FROZEN_STABLE |
| SkillCapability | E | FROZEN_STABLE |
| ContentPlannerAdmissionRequest / ContentPlannerAdmissionResult | F | FROZEN_STABLE |
| GateCertificate | G | FROZEN_STABLE |
| EvidenceMode / VersionRelation / Readiness | G | FROZEN_STABLE |
| BindingLevel / SupportStatus / BlockerClass / ReentryHint / UnboundReason | E | FROZEN_STABLE |
| AdmissionReasonCode | F | STABLE_WITH_VERSIONED_EXTENSION |
| NonEffects | F | STABLE_WITH_VERSIONED_EXTENSION |
| M13_VERSION_RELATION_TOKEN map | E | STABLE_WITH_VERSIONED_EXTENSION |
| ContentSupportRegistry internal lookup (_by_key) | E | SHOULD_NOT_BE_EXTERNAL_API |
| content_planner.admission._admit_with_registry | F | SHOULD_NOT_BE_EXTERNAL_API |
| planner_search / planner (M9) | C | LOCAL_ONLY |

## Policy duplication

No policy is derived outside its authoritative layer. Observations are non-blocking:

- **DUP-1** (NON_BLOCKING): M15 reason vocabulary renames M14 reasons
- **DUP-2** (NON_BLOCKING): readiness vocabulary single-sourced

## Version migration readiness

**DELTA_READY_WITH_SMALL_FIXES** — planner/sandbox rewrite required: False

- **DELTA-1** content_support.registry.SUPPORTED_CONTENT_VERSIONS is a single-element allowlist — one deliberate constant edit in the content layer; no planner or sandbox change
- **DELTA-2** the content-production pipeline is hard-pinned to 4.4.54 — data-production side only; parameterising these pins is not an architecture change
- **DELTA-3** M13_VERSION_RELATION_TOKEN maps exactly one close-version relation — additive token registration; fail-closed behaviour is correct in the meantime

## Observations (non-blocking)

- **OBS-1** two distinct GateCertificate classes — document only; this is frozen Terra authority and must not be renamed or merged
- **OBS-2** M11 plan documents carry a content_target label — document only; the evidence block and the M15 denial boundary already forbid that reading
- **OBS-3** ReferenceAdapterGate is a declared, not sealed, gate — document only. The guarantee that real content cannot produce an envelope rests on (a) no content binder existing and (b) the M15 admission boundary, not on a seal; REFERENCE_MODEL can never be promoted to native evidence
- **OBS-4** several independent 4.4.54 version pins in the content pipeline — captured as DELTA-2; not a leak and not a blocker

## Evidence

Full backend suite: **1875 tests, 0 failures, 0 errors** — OK

| milestone | status |
|---|---|
| M10_reference_sandbox | DELIVERED |
| M11_reference_battle_planner | DELIVERED |
| M12_content_binding | BLOCKED_BY_EVIDENCE |
| M13_content_support_registry | DONE |
| M14_capability_query | DONE |
| M15_content_planner_admission | DONE |

## Non-claims

- No contract was redesigned or modified.
- No content was made executable.
- The audit does not claim native evidence for any content.
- M12 remains BLOCKED_BY_EVIDENCE; that is its correct state, not an audit defect.
- No 4.5.54 content was read or interpreted.
