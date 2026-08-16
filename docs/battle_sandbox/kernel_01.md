# Battle Sandbox Kernel 01 — DynamicValueEquals Proof

> Final status: **`BATTLE_SANDBOX = KERNEL_01_PROOF`**
> Game semantic version: `4.4.54`
> Evidence source: Battle Semantic Vertical Slice 01
> (`docs/battle_semantics/vertical_slice_01.md`,
> `data/semantics/4.4.54/vertical_slice_01.json`)
> Machine report: `data/sandbox/kernel_01_report.json`

## 1. What this kernel is

Kernel 01 is the smallest correct execution layer that connects one recovered
E4 game semantic to an independent, deterministic sandbox:

```text
Game semantic proof (E4)
  -> Canonical Battle IR
  -> independent sandbox execution
  -> deterministic unit tests
```

The only implemented primitive is:

```text
battle.ir.value.dynamic_value_equals
= RPG.GameCore.DynamicValue.Equals(DynamicValue)
  method_index = 74632
  native_rva   = 0x1CFBE9E0
  evidence     = E4_STATIC_MACHINE_CODE
```

> **Sandbox != Client implementation clone.**
> The sandbox executes Canonical Battle IR.  Client native code is the
> semantic Oracle / evidence source only.  The sandbox does not simulate
> IL2CPP memory layout, and it does not claim to reproduce the client PRNG.

## 2. Module boundaries

```text
src/hsr_battle_agent/
  battle_ir/               Canonical IR (no provenance in runtime logic)
    model.py               PrimitiveSpec / PrimitiveCall / PrimitiveResult
    values.py              DynamicValueType / DynamicValue / ObjectRef
    provenance.py          SourceProvenance (evidence/debug/audit only)
    semantic_artifact.py   narrow vertical_slice_01.json loader/validator
  battle_runtime/          pure semantic implementations
    values.py              dynamic_value_equals(lhs, rhs) -> bool
  battle_sandbox/          kernel
    state.py               BattleState v0 (empty semantic schema + extensions)
    context.py             ExecutionContext(state, rng, trace)
    rng.py                 SandboxRng (deterministic abstraction)
    trace.py               PrimitiveStarted / PrimitiveFinished events
    registry.py            primitive_id -> implementation (explicit failure)
    executor.py            IR -> dispatch -> runtime -> result + trace
    snapshot.py            deterministic snapshot / restore
    sandbox.py             top-level API v0
    hash.py                canonical JSON state hashing
    errors.py              kernel error types
scripts/sandbox/write_kernel_01_report.py
tests/battle_ir/  tests/battle_runtime/  tests/battle_sandbox/
data/sandbox/kernel_01_report.json
```

Dependency direction:

```text
IR primitive -> executor dispatch -> battle_runtime implementation
                                      -> result + trace
```

Planner / Beam / MCTS code depends on `Sandbox` + `PrimitiveCall`; it never
calls a runtime Python function directly.

## 3. DynamicValue representation

`battle_ir.values.DynamicValueType` is the strict recovered enum:

| Tag | Name | Canonical payload |
|---:|---|---|
| 0 | INT | signed 64-bit `int` |
| 1 | FLOAT | IEEE-754 double `float` (NaN, +/-0.0 preserved) |
| 2 | BOOL | raw union payload as signed 64-bit `int` |
| 3 | ARRAY | `ObjectRef` (reference identity) |
| 4 | MAP | `ObjectRef` (reference identity) |
| 5 | STRING | `str \| None` |
| 6 | NULL | `None` |

Rules:

- The enum is never extended without a new semantic recovery slice.
- `DynamicValue` is frozen and clone-friendly; it intentionally has no Python
  `__eq__` and is unhashable, because Python container equality is deep
  equality and would silently contradict E4 ARRAY/MAP/NULL semantics.
- Invalid tags are rejected at the representation boundary.  The runtime still
  implements the E4 `tag > 5 -> false` guard; tag `6` (NULL) is the
  representable case, so `NULL == NULL` is `false`.
- INT/FLOAT/BOOL are scalar cells, not IL2CPP union layout.  Negative INTs are
  supported as signed values.

## 4. Reference identity semantics

`ObjectRef(ref_id, contents=None)`:

- equality and hash use **only** `ref_id`;
- `contents` is optional future-heap metadata and never participates in
  equality/hash;
- same `ref_id` -> `true`; different `ref_id` with byte-identical contents ->
  `false`.

This is the foundation for future Entity / Modifier / Array / Map reference
semantics.  A real heap keyed by `ref_id` is deferred until a recovered
semantic slice reads ARRAY/MAP contents.

## 5. DynamicValueEquals semantics (E4-faithful)

Implemented in `battle_runtime.values.dynamic_value_equals`:

```text
type mismatch            -> false
tag > 5                  -> false        (NULL(6) -> NULL == NULL is false)
INT                      -> integer payload equality
FLOAT                    -> IEEE equality (NaN != NaN; +0.0 == -0.0)
BOOL                     -> (lhs == 1) == (rhs == 1); non-1 payloads normalize
ARRAY                    -> ObjectRef identity only (never deep equality)
MAP                      -> ObjectRef identity only (never deep equality)
STRING                   -> same ref -> true; one null -> false; length differs
                            -> false; otherwise ordinal UTF-16 content equality
```

String notes:

- Python `str` equality is used only after the E4 null/length prechecks; the
  final comparison is implemented as UTF-16 code-unit sequence equality via
  `encode("utf-16-le", errors="surrogatepass")`, so it is ordinal and
  culture-free.
- E4 checks `a == b` before the null guard, so two null string pointers compare
  `true`.  This is a deliberate game-faithful behavior, **not** an accidental
  Python default; it differs from tag-NULL (`NULL == NULL -> false`).

## 6. BattleState v0

```python
BattleState(schema_version=1, extensions={})
```

- No client battle fields exist.  `hp/atk/def/spd/energy/toughness/buffs/...`
  are explicitly absent; they enter only when a semantic slice proves a read
  or write.
- `extensions` is kernel infrastructure used to verify clone isolation and
  migration mechanics.  It must never smuggle game-semantic fields; future
  proven fields become real dataclass fields in a new schema version.
- Versioned `from_dict` rejects unknown schema versions instead of guessing.

## 7. RNG boundary

```text
CLIENT_RNG_ALGORITHM = UNKNOWN
SANDBOX_RNG          = DETERMINISTIC_ABSTRACTION
SANDBOX_RNG_ALGORITHM = PYTHON_RANDOM_MT19937
```

- `SandboxRng` wraps stdlib `random.Random`: same seed + same operation
  sequence -> same sequence under the same Python runtime.
- Supports `seed`, `clone`, `getstate/setstate`, `to_dict/from_dict`,
  `next_u64`, `randint`, `uniform`.
- Sandbox runtime code must never call `random.random()` directly; all game
  randomness must eventually pass through `ExecutionContext.rng`.
- This is a deterministic abstraction, not a claim that the client PRNG has
  been recovered.

## 8. Trace model

`ExecutionTrace` emits machine-readable, deterministic events:

- `PrimitiveStarted(event_id, primitive_id, input_tags,
  semantic_provenance_ref)`
- `PrimitiveFinished(event_id, primitive_event_id, primitive_id, result,
  result_type, semantic_provenance_ref)`

Rules:

- input tags are summaries (`DynamicValue:FLOAT`), never full object dumps;
- results are JSON-safe scalars only for Kernel 01;
- provenance ref is audit metadata (`4.4.54:RPG.GameCore.DynamicValue.Equals:74632`);
- trace is serializable and excluded from logical state hash.

Future event kinds (`ValueResolved`, `PredicateEvaluated`, `TargetSelected`,
`ModifierApplied`, `DamageCalculated`, `EventEmitted`) are deferred.

## 9. Executor, registry, snapshot, hash guarantees

- `PrimitiveRegistry` maps `primitive_id -> RegisteredPrimitive(spec,
  implementation, provenance_ref)`.  Unknown ids raise
  `UnsupportedPrimitiveError`; there is no silent no-op.
- `PrimitiveExecutor.execute(PrimitiveCall, ExecutionContext)` validates input
  names against the registered spec, records started/finished trace events, and
  returns `PrimitiveResult`.
- `ExecutionContext` carries exactly `state`, `rng`, `trace`; no caster/target/
  skill/modifier/event fields are pre-created.
- `context.clone()` deep-copies state and RNG and starts a fresh trace
  (`copy_trace=True` is available for debugging).
- `SandboxSnapshot` captures `BattleState` + RNG state + trace; `to_dict` /
  `from_dict` roundtrip, and `restore_context()` rebuilds an exact branch.
- `state_hash` uses SHA-256 over sorted-key compact JSON of logical state
  (BattleState + RNG state).  Python `id()` never enters hashes; trace is
  excluded.
- Guarantees verified by tests:
  - clone hash initially identical; clone mutation changes hash;
  - original and clone mutations are isolated;
  - snapshot roundtrip restores state, RNG continuation and trace;
  - equal logical state -> equal hash regardless of dict insertion order.

## 10. Top-level API v0

```python
sandbox = Sandbox(registry=..., seed=...)
sandbox.reset(seed=...)
sandbox.clone()
sandbox.execute("battle.ir.value.dynamic_value_equals", lhs=..., rhs=...)
sandbox.snapshot()
sandbox.state_hash()
```

`legal_actions`, `step`, `is_terminal` exist as explicit
`NOT_IMPLEMENTED` stubs; they raise `StubNotImplementedError` and never return
fake empty action sets or `false`.

## 11. Semantic artifact connection

`data/semantics/4.4.54/vertical_slice_01.json` is a real input:

- `battle_ir.semantic_artifact.load_vertical_slice_01()` validates schema,
  `primitive_id`, `semantic_name`, `result`, `determinism`,
  `evidence_level`, the full DynamicValueType enum ordinals and provenance
  note, then produces separated `PrimitiveSpec` + `SourceProvenance`.
- The generated spec is what callers register into `PrimitiveRegistry`; the
  report generator and tests prove this path.
- `method_index` / `native_rva` are provenance only and never participate in
  execution logic.

## 12. Performance discipline

- Registry construction is in-memory and happens once per sandbox setup.
- Execution hot path performs no disk access and no JSON reload.
- No global mutable registry/RNG singleton; `Sandbox` owns its context.
- Optimization is deferred until correctness work reaches a profiler.

## 13. Known unknowns

- FieldDefinition provenance for the `+0x30` ValueType tag byte.
- Generic IL2CPP null-check helper internals (error path only).
- No E5 client-side runtime observation for this slice.
- Real client PRNG algorithm.
- ARRAY/MAP heap contents are optional metadata only until a recovered slice
  reads them.

## 14. Next expansion point

The next semantic slice should target a primitive that **reads or writes
BattleState** (for example a proven value coercion / predicate / modifier
slot read), so that `BattleState` grows by evidence instead of by
Star-Rail-domain assumptions.  Do not start Semantic Recovery 02 from inside
this kernel session.

## 15. Not implemented in Kernel 01 (deliberately)

Damage formula, modifier engine, buff/debuff, DOT, target selector, turn
system, SPD/AV, action queue, energy, toughness, weakness, character skills,
Black Swan semantics, enemy AI, planner.
