# Semantic Handoff 13 - Damage Value to HP Bridge

`CAPABILITY_STATUS = COMPLETED_SCOPED_DAMAGE_VALUE_TO_HP_BRIDGE`

This handoff closes the smallest native bridge from the generated
DamageByAttackProperty executor family into the already-sealed
DirectDamageHP transition:

```text
M507308 NNGMOCFGPBN (PGOOHIHKHNJ, 0xC3123B0)
  -> M504579 TargetDamageHP (RPG.GameCore.AbilityStatic, 0xE46D760)
  -> M506499 DirectDamageHP (0xE732180, mode=0)
```

It is a call/argument/control-flow contract, not a damage formula. ATK/DEF/
RES/Crit/Bonus/Break/Toughness are not recovered.

## Primitive identities

| Primitive | Method / RVA | Body hash | Evidence |
| --- | --- | --- | --- |
| M507308 `NNGMOCFGPBN` | 507308, `0xC3123B0`, type 55138 | `8476ff815aa429870f3c6869dbe5d4e0a2c48322b307a93b5849577e8bf31945` | CONFIRMED |
| M504579 `TargetDamageHP` | 504579, `0xE46D760`, type 54573 | `0b786840c0676358981c18a5c23b5a6f93830897a5928bb18f1be492e101ce27` | CONFIRMED |
| M506499 `DirectDamageHP` | sealed by Handoff 12 | `7f712493e35452e66166f1bcca4c51f2b8b3eecf5f65df54c1a85c00526e887a` | CONFIRMED |
| Damage post-process wrapper | M504559 `DamagePostProcess`, `0xE4655B0` | body `0xB0`, wrapper | CONFIRMED |
| Damage post-process inner | M504598 `_MortallyWondedProcess`, `0xE465660` | `6fac82d4e55bcdad1366184fdd1a133fce5b7f511e012d75c3226be2943efe0a` (len `0x7EC`) | CONFIRMED identity; internals UNKNOWN |
| HP-delta value evaluator | M530155 `GOCKCOMLFEO`, `0x1954B9420`, type 57813 | small bounded helper | CONFIRMED identity; exact selection internals UNKNOWN |
| Shield recompute | M504557 `RecomputeShieldCost`, `0xE464D20` | boundary | CONFIRMED identity; semantics not recovered |
| Stance helper | M504390 `GetStanceDamage`, `0xE442F00` | boundary | CONFIRMED identity; not entered |

## M507308 semantic role

`DAMAGE_REQUEST_BUILD_AND_DISPATCH` (evidence-supported, not name-derived):

- It is a generated-executor helper shared by `DamageByAttackProperty` and
  `ProcessStoredDamage` executor types.
- CONFIRMED native args (from prologue and caller M507304 `0xC30F610`):
  - `rcx`: a `PGOOHIHKHNJ` instance; stored in `[rsp+0x98]` and later passed
    as M504579 arg5.
  - `rdx`: outer-executor record `[r15+0x20]`; stored `[rsp+0x88]`.
  - `r8`: damage-result/request object; fields `+0xE8`, `+0x2D8` are read.
  - `r9`: stored `[rsp+0xA8]`; passed into `GetStanceDamage` as arg1.
  - stack arg5..10: two entity objects (`[task+0x18]`, `[task+0x10]`), two
    resolved component/ability objects, a byte flag, and one extra pointer.
- CONFIRMED important callees:
  - M504390 `GetStanceDamage` (stance boundary, not entered).
  - M504422 `ResolveDamageDisplayResult` (presentation boundary).
  - M504559 -> M504598 `DamagePostProcess` / `_MortallyWondedProcess`
    (writes the FixPoint value forwarded to M504579).
  - M504579 `TargetDamageHP`.
- CONFIRMED damage value origin slot:
  - `[rsp+0xA0] = damage_request[+0x2D8]` (initial).
  - `DamagePostProcess(&request_ref, &[rsp+0xA0], entity_a, entity_b)` may
    rewrite `[rsp+0xA0]`; M504598 writes its output through the second
    pointer at `0xE465931`, `0xE465A3F`, `0xE465C61`.
  - The value loaded from `[rsp+0xA0]` is the exact FixPoint passed as
    M504579 arg3. Its internal post-process formula is UNKNOWN.
- CONFIRMED normal iteration/order: M507308 has no target loop around
  TargetDamageHP; it builds one context struct and makes one TargetDamageHP
  call at `0xC313187`. Target iteration happens inside M504579.

## Exact M507308 -> M504579 arguments

Call site `0xC313187`, target `0xE46D760`:

| M504579 slot | Value produced by M507308 | Evidence |
| --- | --- | --- |
| rcx | `r14`, the `[task+0x10]` entity object | CONFIRMED register flow |
| rdx | `&local_context` at `[rsp+0x460]`, assembled from `rdi+0x20` (0xB2-byte copy), `rdi[+0xD2/+0xD3/+0xD7]`, local flag bytes, `[rsp+0xC8]`, `[rsp+0xD0]`, and `r15` | CONFIRMED offsets |
| r8 | `[rsp+0xA0]` FixPoint after `DamagePostProcess` | CONFIRMED |
| r9 | `&out_struct` at `[rsp+0xD8]` | CONFIRMED |
| stack arg5 | `rdi`, the `PGOOHIHKHNJ` instance | CONFIRMED |

No target list is passed explicitly. M504579 derives its target list from
arg1 (`[arg1+0x80] -> [+0xA0] -> [+0x88][arg1[+0xFC]]`) and iterates it
internally.

## M504579 semantic role

`TARGET_DAMAGE_HP_BRIDGE`:

- It is a static multi-target bridge, not a damage formula.
- CONFIRMED entry contract:
  - arg1 = entity whose component table and target list drive resolution.
  - arg2 = context struct (0x108 bytes copied per target).
  - arg3 = FixPoint damage value `V` from M507308; shield recompute may
    overwrite `V` before use.
  - arg4 = output pointer; arg5 = executor/request record.
- CONFIRMED damage-kind selector:
  `r13d = 10` when `arg5[+0x2F9] == 0`, else `r13d = 0`.
- CONFIRMED evaluator read:
  `Q = GOCKCOMLFEO(evaluator)` where
  `evaluator = [[[arg1+0x80]+0xA0]+0x88][arg1[+0xFC]] ... [+0x48][+0x10]`.
  `Q` is a FixPoint; the evaluator's internal selection/clamp is UNKNOWN.
- CONFIRMED normal per-target path (the path reached when target resolution
  succeeds):
  - `cur = GetProperty(target_component, 10)` (CurrentHP).
  - `mx  = GetProperty(target_component, 1)` (MaxHP).
  - `S0 = fp_mul(mx, Q)`.
  - if `S0 > 0`: `S = S0`; else if evaluator-context flag
    `[[...]+0x48][+0x31] != 0`: `S = S0`; else `S = global 0x95C1CC0`
    (identity UNKNOWN).
  - `delta = fp_sub(S, cur)`; normal finite delta passed is
    `fp_sub(cur, S)` negative when `S < cur` (the native code negates
    `fp_sub(cur, S)`).
  - input record value = `-V` for normal finite `V`; flag byte = 1.
- CONFIRMED normal edge into the sealed HP endpoint:

```text
DirectDamageHP(
    target_component,                 # rcx = [rbp+0x698]
    delta = S - CurrentHP,            # rdx = r12 (negative for damage)
    damage_kind = 11,                 # r8d = 0xB
    context = copy_of_arg2,           # r9
    out_applied_ptr,                  # stack arg5
    input_record = {-V, flag=1},      # stack arg6
    mode = 0                          # stack arg7
)
```

- CONFIRMED call site: `0xE46E5D1`.
- Fallback branch when target/config resolution fails (`0xE46E805`):
  applies `-V` directly to the source-resolved component with
  `damage_kind = r13d` (10 or 0), `mode = 0` (`0xE46E8D2`), or a third
  branch (`0xE46EA17`) that passes `mode = arg5[+0x19C]`; that dynamic mode
  is recorded but NOT recovered.

## Actual DirectDamageHP shape reached

For the recommended normal combat path:

```text
damage_kind = 11
mode = 0
```

This is NOT the sealed `damage_kind=100` SetHP shape, and it is NOT
mode 4/5/6. Handoff 12's mode-0 transition semantics apply; the new
`damage_kind=11` value is recorded for the caller shape.

## Damage-value origin summary

- `V` from M507308 = post-processed `damage_request[+0x2D8]` FixPoint
  (M504559/M504598 output; post-process internals UNKNOWN).
- The normal HP delta does NOT use `V` directly. It uses the M504579-evaluated
  ability value `Q` and the target's MaxHP:
  `delta = fp_mul(MaxHP, Q) - CurrentHP`.
- `V` still reaches DirectDamageHP as the input-record value `-V`, and it is
  the direct delta source on the fallback branch (`delta = -V`).

## Pseudocode (normal path)

```text
# M507308 (generated executor helper)
V0 = damage_request[+0x2D8]
V = damage_post_process(&request_ref, &V0, entity_a, entity_b)  # may rewrite V0
context = build_context(executor_record, flags, entity refs)
target_damage_hp(entity, context, V, &out, executor_record)

# M504579
r13_kind = 10 if executor_record[+0x2F9] == 0 else 0
evaluator = resolve_evaluator(entity)
Q = GOCKCOMLFEO(evaluator)              # exact internals UNKNOWN
for target in resolve_targets(entity):  # internal list, forward order
    component = resolve_component(target)
    cur = get_property(component, 10)   # CurrentHP
    mx  = get_property(component, 1)    # MaxHP
    S0 = fp_mul(mx, Q)
    S = S0 if (S0 > 0 or evaluator_flag) else GLOBAL_0x95C1CC0
    delta = fp_sub(S, cur)              # <= 0 for damage
    record = {-V, 1}
    direct_damage_hp(component, delta, 11, context, &applied, &record, 0)

# M506499
# sealed Handoff 12 semantics; damage_kind=11 and mode=0 are the native args.
```

## UNKNOWN / next frontier

- M504598 `_MortallyWondedProcess` internal post-process writes
  (`0xE465931`, `0xE465A3F`, `0xE465C61`).
- M530155 `GOCKCOMLFEO` exact value selection/clamp and the meaning of global
  `0x95B1E18`.
- Fallback global `0x95C1CC0`.
- M504557 `RecomputeShieldCost` semantics (it can overwrite `V`).
- M504579 fallback mode `arg5[+0x19C]`; do not reverse DirectDamageHP modes
  4/5/6 in this task.
- `DamageByAttackProperty` config field-name mapping for `arg2` is SUPPORTED
  by the topology probe; native offsets above are the contract.

## Exact next native entry points

1. `0x1954B9420` M530155 GOCKCOMLFEO (bounded evaluator).
2. `0xE465660` M504598 `_MortallyWondedProcess` (bounded post-process).
3. Only after those: M504579 fallback mode branch `0xE46EA17`.
