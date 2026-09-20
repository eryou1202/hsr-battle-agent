# Terra implementation progress protocol

This protocol is mandatory for every implementation session governed by `terra_implementation_master_v1.json`.

## Authority and status

Authority order is: Astra freeze > frozen Domain 1–9 contracts > exact Terra followups > local audit > historical packets/reports > existing implementation.

For every task, `terra_implementation_master_v1.json` is an implicit control-file exception to the task allowlist, but only for that task's status, notes, changed files, test results, blocker, checkpoint, change-history entry and computed `next_ready_tasks`. It does not authorize DAG, architecture, milestone, semantic-gate or coverage-definition changes.

Allowed statuses are `NOT_STARTED`, `READY`, `IN_PROGRESS`, `BLOCKED`, `IMPLEMENTED_UNVERIFIED`, `DONE`, and `SUPERSEDED`. Never set `DONE` unless every acceptance test and the task's required regression lane passes.

## START

1. Read the master file completely.
2. Locate the exact task by `task_id`; read every field.
3. Run `git status --short`. Preserve unrelated and pre-existing changes.
4. Verify every dependency is `DONE`.
5. Verify every authority path exists and every recorded SHA-256 matches.
6. Confirm the task is `READY`. Set it to `IN_PROGRESS` before editing.
7. Confirm the exact allowed files. Everything else is forbidden.
8. For P0-A2, compare the staged path list to the reviewed authority manifest. Never use `git add .`, `git add -A`, directory staging, or globs.

If a dependency, authority hash or allowed-file condition fails, do not code. Record the blocker and leave semantic behavior unchanged.

## DURING

- Modify only `files_allowed_to_modify`.
- Keep the task's evidence mode and migration constraints explicit.
- Do not solve an UNKNOWN, add content, reverse native behavior, or promote reference code.
- Run the narrow acceptance command after each coherent change.
- Run the fast regression lane when the task touches a shared boundary.
- Record exact commands and exit codes; do not summarize a failure as green.
- Preserve absence/null/false/zero, list nulls, duplicates, source order and numeric lexemes where applicable.
- Before quota/time risk, stop at a coherent boundary and save a checkpoint.

## CHECKPOINT

A checkpoint records:

- task ID and status;
- current HEAD and `git status --short`;
- exact changed files;
- completed requirements and acceptance rows;
- commands, exit codes and relevant output;
- remaining work and next code location;
- unresolved blockers;
- whether state, RNG, allocator, queues or traces may have changed in tests;
- recommended continuation command.

If work is incomplete, status is `IN_PROGRESS`. If code exists but required tests could not run, status is `IMPLEMENTED_UNVERIFIED`. Do not use `DONE`.

## END

1. Run the task's exact acceptance command.
2. Run the minimum lane required by the task and phase.
3. Verify no forbidden file changed.
4. Record changed files, tests/results, coverage-category effects and blockers.
5. Set `DONE` only if all acceptance criteria pass.
6. Recompute readiness: a task becomes `READY` only when all dependencies are `DONE`.
7. Update `next_ready_tasks` without changing the DAG.
8. Append a change-history entry for the implementation checkpoint.
9. Leave unrelated working-tree entries untouched.

## Low quota or time

Stop coding. Persist the exact checkpoint, mark `IN_PROGRESS` or `IMPLEMENTED_UNVERIFIED`, and state the next command. Never compress unfinished work into a false `DONE` claim.

## Environmental and optional failures

An environmental failure must name the exact test, platform symptom, body-pass evidence, reproduction command and re-entry condition. It remains separate from semantic failures. Missing optional dependencies produce `BLOCKED_OPTIONAL`; they do not justify adding runtime dependencies or marking the lane green.

## Change control

Cheap models may update only task-local notes, blockers, file impact, test results and checkpoints. They may not change task dependencies, milestones, architecture decisions, evidence gates or coverage definitions.

A roadmap architecture change requires:

- a unique `change_request_id`;
- reason and evidence;
- affected task IDs;
- semantic and migration impact;
- rollback plan;
- Sol review;
- a new master revision and change-history entry.

Astra is not used for normal roadmap changes. It is used only when concrete, version/hash-qualified evidence answers an existing frozen blocker under the freeze reopen policy.

## Commit safety

Never use destructive reset/checkout commands. Never stage the whole repository. Use explicit pathspecs, inspect `git diff --cached`, and keep the two protected pre-existing modified tracked files unstaged unless a future user explicitly authorizes a separate task.
