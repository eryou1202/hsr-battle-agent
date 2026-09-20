# P0-A1 — Build exact authority preservation manifest

You are executing one bounded task in `D:\\HSR_Battle_Agent\\hsr-battle-agent`.

## Authority files

Read these before editing:

- `data/semantics/4.4.54/full_reconstruction/astra_semantic_freeze_v1.json`
- `docs/agent/astra_semantic_freeze_handoff_2026-09-20.md`
- `data/semantics/4.4.54/full_reconstruction/astra_reverse_master_v1.json`
- `data/semantics/4.4.54/full_reconstruction/terra_local_repository_audit_001.json`
- `docs/agent/terra_local_repository_audit_2026-09-20.md`
- `data/semantics/4.4.54/full_reconstruction/terra_implementation_master_v1.json`

Authority precedence is freeze > frozen Domain 1–9 > exact Terra followups > local audit > historical reports > implementation. Existing code is not semantic truth when it conflicts with the freeze.

## Dependencies and start gate

Task ID: **P0-A1**

Dependencies: none.

Read the task object in the master. Run `git status --short`, verify every dependency is `DONE`, verify authority paths/hashes, and confirm this task is `READY`. If any check fails, do not edit; report the exact blocker.

## Allowed files

- `docs/agent/authority_commit_manifest_2026-09-20.json`
- `data/semantics/4.4.54/full_reconstruction/terra_implementation_master_v1.json`

## Forbidden files

- Every Astra freeze, reverse-master, frozen Domain 1–9, targeted-evidence and exact-followup artifact.
- `data/semantics/4.4.54/catalog.json` and all SHA-256-pinned catalog artifacts.
- The two protected pre-existing modified files: `data/raw/4.4.54/damage_request_dispatch_resolution_18.json` and `docs/agent/handoffs/damage_request_dispatch_resolution_18.md`.
- Every file not listed under “Allowed files”.

## Implementation requirements

- Enumerate only the freeze authority inputs whose role is FROZEN_DOMAIN or TERRA_FOLLOWUP, plus the freeze/master/handoff, Terra audit/handoff and implementation-plan artifacts.
- For directly referenced untracked evidence needed to keep a frozen contract auditable, add each path only after manual path/hash/role review; do not sweep a directory.
- Record path, role, tracked/untracked state, SHA-256, governing hash source and whether it is stage-approved.
- Record both protected modified tracked files as explicit exclusions.
- Do not stage or commit.

## Special safety rule

This task is inventory-only. If the manifest cannot distinguish authoritative evidence from an unrelated dump, stop and request Sol review; do not guess.

## Non-goals

- Do not edit any authority artifact.
- Do not include unrelated raw dumps, reverse tools, inventories or convenience globs.
- No native semantic inference, reverse engineering, content fetch, broad refactor, or reference-to-native promotion.
- Do not fix any unrelated failing test.

## Tests

- `python -m json.tool docs/agent/authority_commit_manifest_2026-09-20.json`
- `For every manifest entry: Test-Path and Get-FileHash -Algorithm SHA256`
- `git diff --cached --name-only must be empty`

A test is successful only when its expected outcome matches the task. Record command, exit code and unexpected output. Do not mark `DONE` if an acceptance test is unavailable or unexpectedly fails.

## Git safety

Preserve all unrelated changes. Never run destructive reset/checkout. Never use `git add .`, `git add -A`, a directory pathspec, or a glob. Do not commit unless this prompt explicitly requires the reviewed preservation commit.

## Master update procedure

Cheap models may update only this task's status, notes, changed-file list, test results, blocker and checkpoint, plus the computed `next_ready_tasks` list. Do not rewrite dependencies, milestones, decisions, evidence gates, coverage definitions or the DAG. Set `DONE` only after all acceptance tests pass.

## Checkpoint procedure

Before quota/time risk, stop coding and record: task/status, HEAD, `git status --short`, exact changed files, completed requirements, commands/results, remaining work, blockers and next command. Use `IN_PROGRESS` or `IMPLEMENTED_UNVERIFIED`; never claim `DONE`.

## Final response format

```text
TASK: P0-A1
STATUS: <DONE|IN_PROGRESS|IMPLEMENTED_UNVERIFIED|BLOCKED>
CHANGED FILES:
- ...
TESTS:
- <command> => <exit/result>
COVERAGE EFFECT: <exact category; no combined percentage>
BLOCKERS: <none or exact blocker>
NEXT READY TASKS:
- ...
CHECKPOINT: <none or exact continuation>
```

## Stop condition

Stop immediately after the allowed-file diff is complete, required tests are recorded, the task-local master checkpoint is updated, and no forbidden file changed.

