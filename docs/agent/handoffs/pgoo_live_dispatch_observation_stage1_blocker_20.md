# PGOOHIHKHNJ Live Dispatch Observation — Stage 1 Blocker 20

`STATUS = BLOCKED`

`BLOCKER = RUNTIME_INSTANCE_OBSERVATION_REQUIRED`

Artifact: `data/raw/4.4.54/pgoo_live_dispatch_observation_stage1_blocker_20.json`

## Baseline

All mandatory commits, including `f8757cd`, are ancestors of `HEAD`. The
dispatch remains the exact unresolved site already bounded by Handoffs 17–19:

```text
M507304 0xC30F0BC
instance = PGOOHIHKHNJ executor
C = [instance + 0x0]
F = [C + 0x120]
B = call F(...)
M507308 reads B[+0x2D8]
```

The previously proposed M507307, M507309, and M507328 remain rejected by the
published ABI/table evidence. No callee was entered.

## Permitted-tooling result

The available external runtime readers use only `PROCESS_QUERY_INFORMATION |
PROCESS_VM_READ`, PSAPI module enumeration, and `ReadProcessMemory` over
known module ranges or code-proven static chains. They do not locate managed
task/executor instances, inspect execution registers, or enumerate heaps.

The only existing tool that reaches in-process runtime state uses `LoadLibraryW`
through `CreateRemoteThread` to load a DLL. That is forbidden by the present
Stage 1 contract (and the historical HD-2 run is blocked at module load).

No `StarRail`, `Cultivation`, or `ppSR` process was active during this audit.
This alone is not the decisive blocker: even with an approved process running,
the allowed readers provide no code-guided path to a live `PGOOHIHKHNJ`
instance. Getting the required `r15`/instance at M507304 instead needs either
forbidden runtime instrumentation/debugger capture or an impermissible blind
heap sweep.

## Exact next frontier

An approved read-only, code-guided mechanism must first yield the live
`PGOOHIHKHNJ` instance address at (or immediately around) M507304. Once it
exists, perform the narrowly scoped reads:

1. `C = qword[instance + 0x0]`.
2. Confirm `byte[C + 0xCA] & 4` is set.
3. `F = qword[C + 0x120]`.
4. Normalize `F` using the *actual* loaded GameAssembly base, resolve its RVA
   and registry method index, then ABI-check against `0xC30F0BC`.

Until that observation exists, Stage 2+ cannot proceed without guessing.
