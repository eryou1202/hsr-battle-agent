# Authority Integrity Reconciliation

Date: 2026-09-20
Incident: `AUTHORITY_INTEGRITY_RECONCILIATION_001`
Branch: `terra/implementation`
Investigation-start HEAD: `a505a25cf96bb718784faa85f4d962262d251ca5`

## Outcome

The authority control plane is reconciled without changing the Astra freeze, reverse master, freeze handoff, or any Domain artifact.

The three Domain files on disk do not have the SHA-256 values recorded by the frozen authority:

| Domain file | Frozen expected SHA-256 | Preserved current SHA-256 | Repair class |
|---|---|---|---|
| `astra_formation_boss_v1.json` | `50d7e45a8838542882d2bcc114486638e96433234db2799c0254a22b8e91fe13` | `e4820e01060d208c4e6bbcce11bcb580d8d0bcd855960c6edf15c49574262b29` | `CURRENT_BYTES_SEMANTICALLY_EQUIVALENT_RECONCILE_HASH` |
| `astra_monster_ai_v1.json` | `6e742e8cf8e6ebb391f4debe324cc6645971d0bbc503d5b2dabf18216b483198` | `c00830c9af0a433dd330948f373690294bdb817b2ff3600d4be090fdfbe7dda1` | `CURRENT_BYTES_SEMANTICALLY_EQUIVALENT_RECONCILE_HASH` |
| `astra_triggerability_v1.json` | `a582917cd595b9eab8f3800b705a301e6a868a9f91571b3f9ba9242cd2b824f4` | `f74d3bf9256c4440a8f8c851b61a80b873ca9889d2eac2a8c4fb8cad3ede4246` | `CURRENT_BYTES_SEMANTICALLY_EQUIVALENT_RECONCILE_HASH` |

The old expected hashes remain part of the historical freeze record. The current hashes are accepted only through the versioned reconciliation record at `data/semantics/4.4.54/full_reconstruction/authority_reconciliation_001.json`. This is a control-plane overlay, not a semantic reopen.

## What happened

The preservation manifest copied three SHA-256 values from the freeze input list, while preservation commit `3243c5eb947f3583e5918ef45cacb7ce6fcfd862` captured different bytes for those files. A later P0 reconciliation correctly detected the mismatch and stopped.

Independent recomputation found:

- 26 of the 30 preservation-manifest entries matched exactly.
- Three immutable Domain entries had the incident mismatches.
- The mutable Terra implementation master differed from its preservation-time manifest hash because later bookkeeping changed it. That is a snapshot identity issue, not a fourth semantic-authority mismatch.
- The three relevant targeted-evidence files were also checked; two recorded pins matched and the Formation/Boss targeted-evidence file had no independent frozen pin.

## Recovery search

No byte-identical copy of any expected Domain blob was recovered.

The search covered 1,815 local Git blobs, including reachable and dangling objects, reachable commits and branches, the index, reflogs, repository copies under `D:\HSR_Battle_Agent`, and conversation-produced local files under `C:\Users\而忧\.codex`. A separate SHA-256 scan covered 1,518 plausible local files. All three expected-hash searches returned zero candidates.

The current Domain files first entered Git history in preservation commit `3243c5e`. Because no candidate matched an expected SHA-256, no Domain restoration was authorized or performed.

## Semantic-equivalence audit

This audit compared frozen contract surfaces; it did not redo semantic reverse engineering.

### Formation/Boss

The current file retains the freeze's partial native architecture status, evidence-blocked Terra readiness, blockers `FB-Q1` through `FB-Q4`, and all 14 strict rejection boundaries. Its counts remain 1,505 targeted nodes, 1,050 records, 1,087 monster operations, and 804 monster records. It does not claim compiler or executable coverage. Topology remains separate from targeting, scheduling, modifier lifecycle, and phase semantics.

Classification: `BOOKKEEPING_ONLY`. The expected bytes are unavailable, so this does not assert a direct byte-diff characterization; it records that no semantic contract divergence was found and the repair is confined to hash bookkeeping.

### Monster AI

The current file retains frozen status, scoped declarative architecture closure, partial Terra readiness, blockers `MA-Q01` through `MA-Q05`, and all 23 strict rejection boundaries. The final counts and duplicate-preservation rules agree with the freeze and exact followups.

Older same-file text saying one sequence mapping request remained is superseded by the later `sequence_id_binding` and `end_of_domain_gate` sections and by final freeze conflict `SC-03`. This does not alter an implementation gate or authorize native AI selection.

Classification: `SEMANTIC_BUT_SUPERSEDED_AND_FREEZE_CONSISTENT`.

### TriggerAbility

The current historical status `PASS_4_COMPLETE_BLOCKED_BY_EVIDENCE` is compatible with final frozen status. Execution readiness remains `NO`; blockers `TA-P4-Q1` through `TA-P4-Q3` and all 12 strict rejection boundaries agree. The measured counts remain 4,125 calls, 2,665 unique calls, 1,460 missing calls, 164 local OnStart candidates, and zero invocation-eligibility records.

Classification: `BOOKKEEPING_ONLY`. The expected bytes are unavailable, so this does not assert a direct byte-diff characterization; it records that no semantic contract divergence was found and the repair is confined to hash bookkeeping.

No difference affecting implementation gates, strict rejection boundaries, blocker identity, architecture, or native/reference classification was found. Semantic truth is therefore not at risk under the reconciliation overlay. Astra is not required.

## Control-file repairs

The implementation master contained one duplicate JSON member:

- Location: `$.progress_update_protocol`
- Key: `master_control_file_exception`
- Both values: identical
- Ordinary parser behavior: the earlier member is silently discarded

The second adjacent copy was removed surgically. The master was not fully reserialized. `tools/control/validate_json_no_duplicate_keys.mjs` now rejects duplicate object keys in control JSON.

Mutable control state follows this identity rule:

- Immutable semantic authority may remain SHA-256 pinned.
- The mutable implementation master is identified by schema/version plus Git commit/blob identity or an external manifest.
- The master must not attempt to validate an internally self-referential SHA-256.
- The preservation manifest's old master hash remains a historical snapshot, not a perpetual invariant.

## Git integrity

`show-ref`, the branch log, reflogs, `ls-remote origin`, and `git fsck --full` agree on the active named refs. Local and origin refs matched at investigation start. The fsck report contained 38 dangling blobs and 73 dangling trees, but no dangling commits and no missing or corrupt objects.

Current repository integrity is healthy. The reported earlier SIGTERM/ref-loss incident cannot be attributed further from current evidence, and no current ref repair was necessary.

Agents must never directly create, edit, or delete `.git` metadata. If a normal Git ref mutation fails, stop Git mutation, preserve object IDs and reflog evidence, and request review.

## P0 status and re-entry

`P0-A1` and `P0-A2` are closed under `AUTHORITY_RECONCILIATION_001`. Their original blocker records remain in the master as history and are explicitly marked resolved.

The following tasks become READY:

- `P0-B` — repair root unittest discovery
- `P0-C` — replace stale catalog constants with derived assertions
- `P0-E` — install reference-quarantine guard rails
- `P0-F` — ratify migration, RNG, and quarantine ADRs

The recommended next cheap-model task is `P0-B`. Cheap-model long runs may resume after the narrow reconciliation commit is validated and pushed. This session does not start any of those tasks.

The two protected pre-existing modified tracked files remain untouched and unstaged:

- `data/raw/4.4.54/damage_request_dispatch_resolution_18.json`
- `docs/agent/handoffs/damage_request_dispatch_resolution_18.md`

No production file, test, frozen semantic artifact, or Domain artifact was modified.
