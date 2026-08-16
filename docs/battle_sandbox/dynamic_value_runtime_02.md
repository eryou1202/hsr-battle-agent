# Battle Sandbox DynamicValue Runtime 02

> Final status: **`BATTLE_SANDBOX = DYNAMIC_VALUE_RUNTIME_02_PROOF`**
> Game semantic version: `4.4.54`
> Evidence source: `data/semantics/4.4.54/dynamic_value_batch_02.json`
> Machine report: `data/sandbox/dynamic_value_runtime_02_report.json`

## 1. What changed

Kernel 01 proved one primitive (`DynamicValueEquals`).  Runtime 02 adds the
eleven E4 Batch 02 primitives through the explicit semantic artifact catalog:

```text
catalog.json
  -> artifact validation (schema + sha256 + enabled)
  -> RecoveredPrimitive list (vertical_slice_01 + dynamic_value_batch_02)
  -> explicit implementation bindings
  -> frozen PrimitiveRegistry
```

Filesystem globs are not used as the source of truth.  `create_default()` is
still cached and frozen; execution never reads the catalog or artifact files.

## 2. Implemented primitives

| Primitive ID | Source method | Result |
|---|---|---|
| `battle.ir.value.dynamic_value_to_int` | `get_IntValue` | `int32` |
| `battle.ir.value.dynamic_value_to_uint` | `get_UintValue` | `uint32` |
| `battle.ir.value.dynamic_value_to_long` | `get_LongValue` | `int64` |
| `battle.ir.value.dynamic_value_to_float` | `get_FloatValue` | `float32` |
| `battle.ir.value.dynamic_value_to_double` | `get_DoubleValue` | `float64` |
| `battle.ir.value.dynamic_value_to_bool` | `get_BoolValue` | `boolean` |
| `battle.ir.value.dynamic_value_type` | `get_ValueType` | `DynamicValueType` |
| `battle.ir.value.dynamic_value_string` | `get_StringValue` | `string_or_null` |
| `battle.ir.value.dynamic_value_is_array` | `get_IsArray` | `boolean` |
| `battle.ir.value.dynamic_value_is_map` | `get_IsMap` | `boolean` |
| `battle.ir.value.dynamic_value_is_null` | `get_IsNull` | `boolean` |

`battle.ir.value.dynamic_value_equals` remains unchanged from Kernel 01.

## 3. Runtime semantics notes

- `float32` results are quantized to IEEE-754 binary32.  `cvtsi2ss` on large
  int64 values rounds directly to 24-bit significand (no double-rounding).
- `int32` / `uint32` conversions reproduce the native register widths,
  including the x86 out-of-range/NaN indefinite values.
- `get_FloatValue` / `get_DoubleValue` return `+0.0` for mismatched tags;
  BOOL payloads other than `1` normalize to `+0.0` silently.
- `get_BoolValue` returns false for INT raw payloads other than `0`/`1`
  (native invalid-value log path is diagnostic only and not modeled).
- `get_StringValue` returns `None` on tag mismatch, matching the native null
  return after the log helper.
- Native one-time IL2CPP class-init branches (`get_LongValue`,
  `get_DoubleValue`) are runtime infrastructure and are not part of
  `BattleState`.

## 4. BattleState and trace

- `BattleState` schema is unchanged: these primitives only read their
  `DynamicValue` input.
- Trace model is unchanged: `PrimitiveStarted` + `PrimitiveFinished`; all
  Batch 02 results are JSON-safe scalars (`None`/bool/int/float/str).

## 5. Representation conflicts

- Canonical `DynamicValue` cannot construct ARRAY/MAP cells with null
  payload pointers, while native `get_IsArray` / `get_IsMap` have a
  null-payload false branch.  The runtime keeps that branch defensively; no
  representation change was made.
- `get_ArrayValue` / `get_MapValue` and the raw `longValue` / `doubleValue` /
  `boolValue` union reinterpreters are skipped for the same reason.

## 6. Not implemented

FixPoint conversion, serialization, logging helpers, ToString / GetHashCode /
DebuggerDisplay, op_Implicit allocation wrappers, and all non-value methods.
See the Batch 02 semantic doc for the full candidate table and skip reasons.
