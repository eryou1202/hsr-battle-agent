# Terra baseline test matrix and environmental policy

Status: **M0.5 test-baseline codification (P0-D)**. Owner: Terra implementation plan.
Authority order is unchanged: Astra freeze > frozen Domain 1–9 > exact Terra followups >
local audit > historical reports > existing implementation.

This document defines the lanes, the deterministic fast command, the environmental
quarantine rules and the optional-dependency blocked states. It records measurements;
it does not redefine any semantic gate or coverage definition. Golden stays **0**.

## 1. Lane definitions

Lanes are evidence classes, not directories. A suite belongs to the narrowest lane whose
claim it actually supports, and coverage is never combined across lanes.

| Lane | Meaning | Current content |
| --- | --- | --- |
| `FAST_UNIT` | Narrow task tests; deterministic, DB-free, no network | `tests/battle_ir`, `tests/battle_sandbox`, `tests/battle_runtime` |
| `STRUCTURAL` | Schemas, hashes, presence, identity, descriptors, gates | catalog/semantic-artifact validation in `tests/battle_ir`; the P0-E reference-quarantine guard rails |
| `REFERENCE_MODEL` | Explicit reference adapters; labels can never count as native | reference-execution and per-domain reference tests under `tests/game_data` (DB-backed) |
| `SOURCE_BACKED` | Real payload/operation fixtures with exact provenance | `tests/reverse`, content-ingestion fixtures under `tests/game_data` |
| `NATIVE_TRACE` | Matched version/hash observed native transitions | **empty — none promoted**; nothing here may be counted from reference output |
| `GOLDEN` | Independent full-fixture oracle | **count 0** |

`NATIVE_TRACE` and `GOLDEN` are deliberately empty. Nothing in this repository currently
qualifies, and no lane may be promoted into them without new version/hash-qualified
evidence.

## 2. FAST_UNIT — the deterministic fast command

```powershell
& "<resolved python>" -m unittest discover -s tests/battle_ir -t . -p "test_*.py"
& "<resolved python>" -m unittest discover -s tests/battle_sandbox -t . -p "test_*.py"
& "<resolved python>" -m unittest discover -s tests/battle_runtime -t . -p "test_*.py"
```

One-line form, used as the per-task regression requirement:

```
python -m unittest discover -s tests/battle_ir -t . -p "test_*.py" && python -m unittest discover -s tests/battle_sandbox -t . -p "test_*.py" && python -m unittest discover -s tests/battle_runtime -t . -p "test_*.py"
```

Use the repository-resolved interpreter documented in
`docs/agent/dsh_windows_environment.md`; do not use bare `python` or `py`.

### Measured baseline (2026-09-20, after P0-B and P0-C)

| Suite | Tests | Result | ~Time |
| --- | --- | --- | --- |
| `tests/battle_ir` | 131 | OK | 8.3 s |
| `tests/battle_sandbox` | 208 | OK | 0.25 s |
| `tests/battle_runtime` | 185 | OK | 0.19 s |
| **FAST_UNIT total** | **524** | **OK, 0 failures, 0 errors** | ~9 s |

Determinism check required by P0-D: the three commands were run twice back to back and
produced **identical counts and identical results** (131 / 208 / 185, all `OK`). The same
figures were reproduced under both the repository-resolved Python 3.11.9 and a managed
Python 3.13.12.

### Wider deterministic run

```
python -m unittest discover -s tests -t . -p "test_*.py"
```

Measured: **532 tests, OK**. That is FAST_UNIT (524) plus `tests/reverse` (8). See the
discovery gap in section 5 — this root command does **not** cover the whole `tests/` tree.

### Known-baseline note

Before P0-C the root run reported `Ran 493 tests, FAILED (failures=3)`, the three stale
catalog cardinality assertions in `tests/battle_ir/test_semantic_batch_catalog.py`. P0-C
derived those expectations from the catalog under test, so the fast lane is now fully
green with no weakened expectation. Do not treat the historical 3-failure figure as the
current baseline.

## 3. Environmental policy

Windows tempfile cleanup errors are **not** ignored globally and are never called green.
A cleanup failure is quarantined only when the test body demonstrably passed, and it must
carry an exact reproduction command and a re-entry condition.

### Quarantined environmental failures

| Test | Symptom | Body-pass evidence | Lane |
| --- | --- | --- | --- |
| `tests/game_data/test_external_reconstruction.py::ExternalReconstructionTest::test_external_records_stage_detail_and_static_loadout_round_trip` | `PermissionError: [WinError 32] 另一个程序正在使用此文件，进程无法访问。` while unlinking `content.sqlite` inside `tempfile.TemporaryDirectory.__exit__` → `shutil.rmtree` | All assertions (lines 106–125) are inside the `with` block; the traceback's outer frame is `tempfile.py __exit__`, not an assertion line | `REFERENCE_MODEL` (DB-backed, out of lane) |
| `tests/game_data/test_external_reconstruction.py::ExternalReconstructionTest::test_rebuild_is_deterministic_and_refuses_other_versions` | same `[WinError 32]` while unlinking `first.sqlite` | Assertions at lines 136–138 are the last statements inside the `with` block; failure occurs only in cleanup | `REFERENCE_MODEL` (DB-backed, out of lane) |

Reproduction:

```
set PYTHONPATH=src
python -m unittest discover -s tests/game_data -p "test_*.py"
```

Measured: **Ran 153 tests in ~89 s, FAILED (errors=2)** — exactly the two cleanup errors
above, plus zero failures. The two errors are recorded as `ENVIRONMENTAL`, not green: the
suite exits non-zero.

Environmental classification is void if the failure traceback ever points at an assertion
or at test-body code instead of `tempfile`/`shutil` cleanup. Re-entry: classify as a real
failure the moment a body-level traceback appears, and re-measure rather than assume.

### Why this suite is out of lane

`tests/game_data` builds real SQLite content databases (~89 s). It is DB-backed, so it is
never part of the fast per-task lane; it belongs to the `REFERENCE_MODEL` /
`SOURCE_BACKED` milestone-closing lanes.

## 4. Optional-dependency suites (`BLOCKED_OPTIONAL`)

These suites fail at **import time**, before any test body runs. They are blocked, not
green, and no runtime dependency may be added to make them green.

| Suite | Exact error | Missing extra |
| --- | --- | --- |
| `tests/unpacker/test_pipeline_units.py` | `ModuleNotFoundError: No module named 'numpy'` raised from `tools/unpack_pipeline/mhy_core.py` line 23 | `numpy` |
| `tests/cross_version/test_find_il2cpp_api_table.py` | `ModuleNotFoundError: No module named 'numpy'` | `numpy` |
| `tests/cross_version/test_runtime_probe.py` | `ModuleNotFoundError: No module named 'jsonschema'` | `jsonschema` |

Note the loader reports these as `unittest.loader._FailedTest`; the bodies never run, so
there is no body-pass evidence and no environmental quarantine is available.

Reproduction:

```
python -m unittest discover -s tests/unpacker -p "test_*.py"
python -m unittest discover -s tests/cross_version -p "test_*.py"
```

Measured: `tests/unpacker` Ran 1 test → 1 collection error; `tests/cross_version` Ran 2
tests → 2 collection errors.

Re-entry condition: install the optional extras declared in `pyproject.toml`
(`test-optional`), re-run both commands, and record the real pass/fail/error counts. Until
then these suites are `BLOCKED_OPTIONAL` and are excluded from fast regression.

`numpy` and `jsonschema` are **test-only extras**. `[project].dependencies` stays empty so
that the production package and the fast lane never require them.

## 5. Discovery gap (recorded, not fixed here)

`python -m unittest discover -s tests -t .` walks only **importable packages**. Directories
under `tests/` without an `__init__.py` are silently skipped:

| Directory | Package? | In the root run? |
| --- | --- | --- |
| `tests/battle_ir` | yes | yes (131) |
| `tests/battle_sandbox` | yes | yes (208) |
| `tests/battle_runtime` | yes | yes (185) |
| `tests/reverse` | yes | yes (8) |
| `tests/game_data` | no | **no** — 153 tests invisible to the root command |
| `tests/cross_version` | no | **no** |
| `tests/unpacker` | no | **no** |
| `tests/models`, `tests/planning`, `tests/runtime`, `tests/semantics`, `tests/simulator` | no | no test modules present (contain only `.gitkeep`) |

Consequences and rules:

- The root command's green `OK` must never be reported as "the whole test tree is green".
- The affected directories also cannot be discovered with an explicit `-t .` top level;
  they raise `ImportError: Start directory is not importable` until they gain a package
  marker. They can still be exercised today with `-s tests/<dir>` plus `PYTHONPATH=src`.
- Follow-up owner: a future P0 task may add `tests/<dir>/__init__.py` markers. That was
  outside P0-D's allowlist and was deliberately not done, and no test file was modified.

Expected effect once markers are added: the root run should rise by the `tests/game_data`
count (153) and by whatever the optional suites contribute once their extras are present.
Until a suite is dependency-complete and body-green, it is not counted.

## 6. Lane assignment for closing a phase or milestone

- **Task closing:** the task's own exact tests, plus FAST_UNIT when the task touches a
  shared boundary.
- **Phase closing:** every task test in the phase, plus FAST_UNIT and STRUCTURAL.
- **Milestone closing:** phase-closing plus the relevant `REFERENCE_MODEL`,
  `SOURCE_BACKED` and replay lanes. Heavy DB/SQLite suites (`tests/game_data`) and the
  optional-dependency suites run only when the milestone scope requires them, and must be
  reported together with their environmental/optional status.

## 7. Invariants

- Golden = **0**. No lane may be relabelled to change that.
- `NATIVE_TRACE` stays empty until independently promoted version/hash-qualified evidence
  exists. Reference output cannot fill it.
- Environmental exclusions are per-test and evidence-backed; there is no global ignore.
- `BLOCKED_OPTIONAL` is never reported as green, and no runtime dependency is added to
  clear it.
- No semantic expectation may be weakened to make a lane green.
