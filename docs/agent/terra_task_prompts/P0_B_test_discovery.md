# P0-B — Repair root unittest discovery

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

Task ID: **P0-B**

Dependencies: `P0-A2`.

Read the task object in the master. Run `git status --short`, verify every dependency is `DONE`, verify authority paths/hashes, and confirm this task is `READY`. If any check fails, do not edit; report the exact blocker.

## Allowed files

- `tests/__init__.py`
- `docs/agent/project_index.md`
- `data/semantics/4.4.54/full_reconstruction/terra_implementation_master_v1.json`

## Forbidden files

- Every Astra freeze, reverse-master, frozen Domain 1–9, targeted-evidence and exact-followup artifact.
- `data/semantics/4.4.54/catalog.json` and all SHA-256-pinned catalog artifacts.
- The two protected pre-existing modified files: `data/raw/4.4.54/damage_request_dispatch_resolution_18.json` and `docs/agent/handoffs/damage_request_dispatch_resolution_18.md`.
- Every file not listed under “Allowed files”.

## Implementation requirements

- Add only the missing root test package marker.
- Keep stdlib unittest; add no test framework or dependency.
- Verify the documented root command enters discovery instead of raising `Start directory is not importable`.
- Document known downstream failures separately; do not fix them here.



## Non-goals

- Do not edit test bodies or semantic expectations.
- Do not classify downstream failures as discovery failures.
- No native semantic inference, reverse engineering, content fetch, broad refactor, or reference-to-native promotion.
- Do not fix any unrelated failing test.

## Tests

- `python -m unittest discover -s tests -t . -p "test_*.py" -v; expected: discovery runs, with only separately recorded known baseline failures/errors`
- `python -m unittest discover -s tests/battle_sandbox -t . -p "test_*.py"; expected: green`

A test is successful only when its expected outcome matches the task. Record command, exit code and unexpected output. Do not mark `DONE` if an acceptance test is unavailable or unexpectedly fails.

## Git safety

Preserve all unrelated changes. Never run destructive reset/checkout. Never use `git add .`, `git add -A`, a directory pathspec, or a glob. Do not commit unless this prompt explicitly requires the reviewed preservation commit.

## Master update procedure

Cheap models may update only this task's status, notes, changed-file list, test results, blocker and checkpoint, plus the computed `next_ready_tasks` list. Do not rewrite dependencies, milestones, decisions, evidence gates, coverage definitions or the DAG. Set `DONE` only after all acceptance tests pass.

## Checkpoint procedure

Before quota/time risk, stop coding and record: task/status, HEAD, `git status --short`, exact changed files, completed requirements, commands/results, remaining work, blockers and next command. Use `IN_PROGRESS` or `IMPLEMENTED_UNVERIFIED`; never claim `DONE`.

## Final response format

```text
TASK: P0-B
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

