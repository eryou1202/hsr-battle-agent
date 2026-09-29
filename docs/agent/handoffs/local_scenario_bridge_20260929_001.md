# P5B local Scenario bridge

CR-P5B-LOCAL-SCENARIO-BRIDGE-20260929-001. Starting HEAD:
`e17666c7a56e652271058fa5fcd671bf73ef0e42`, branch `terra/implementation`.
P5A is committed at that HEAD. All implementation files in this CR are additive.

The bridge provides two independent operations: compile a ScenarioCompiler
request into `hsr_battle_agent.scenario_package/2`, then request P4 support analysis
of that package into `hsr_battle_agent.scenario_support_report/1`. Frontend code
can inspect the compiled document before the second call. No visual builder or
UI wiring is included. Static browsing continues to use the existing P5A assets
and clients; their original static connectivity metadata is unchanged.

## Two-process development

Terminal A, from the repository, with Python 3.11+ and `src` importable:

```powershell
Set-Location D:\HSR_Battle_Agent\hsr-battle-agent
$env:PYTHONPATH = "$PWD\src"
python -m hsr_battle_agent.frontend_bridge --content-version 4.4.54 --port 8765
```

This workspace's available, verified interpreter is embedded Python 3.13.14,
which ignores PYTHONPATH. Its equivalent entry point is:

```powershell
Set-Location D:\HSR_Battle_Agent\hsr-battle-agent
& 'D:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable\python_embeded\python.exe' -c "import sys,runpy; sys.path.insert(0,'src'); runpy.run_module('hsr_battle_agent.frontend_bridge',run_name='__main__')" --content-version 4.4.54 --port 8765
```

Terminal B:

```powershell
Set-Location D:\HSR_Battle_Agent\hsr-battle-agent\frontend
$env:VITE_HSR_BRIDGE_URL = 'http://127.0.0.1:8765'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

The new `createConfiguredScenarioBridgeClient('4.4.54')` helper reads that explicit
URL when invoked by a future consumer. Construction performs no I/O. Its status
starts as `NOT_CONNECTED`; the first call verifies BridgeInfo and the selected
content version. Missing configuration or a network failure produces an explicit
`ScenarioBridgeConnectionError` with status `NOT_CONNECTED`, with no fallback.
Vite never starts Python. Stop Terminal A with Ctrl+C. Test services were closed
after verification; no background bridge is left running by this CR.

Future consumers call `compile(draft)` and `support(compiled)` separately through
`ScenarioCompileSource` and `ScenarioSupportSource`. Neither operation invokes
the other. They use native fetch, omit credentials, refuse redirects, and accept
only an explicitly configured localhost/127.0.0.1 HTTP base origin. No Vite config,
HTTP client dependency, package configuration or existing FE3 file was changed.

## Authority and transport

| Route | Input | Output |
| --- | --- | --- |
| GET `/api/v1/info` | none | `hsr_battle_agent.frontend_bridge_info/1` |
| POST `/api/v1/scenario/compile` | unchanged ScenarioCompiler request | `hsr_battle_agent.scenario_package/2` |
| POST `/api/v1/scenario/support` | unchanged ScenarioPackage/2 | `hsr_battle_agent.scenario_support_report/1` |

Startup requires literal `4.4.54`, with no latest lookup or fallback. Exactly one
ContentDatabase, one public ContentSupportRegistry, one ScenarioCompiler and one
ScenarioSupportReporter are constructed. Compiler and reporter share the same
database; reporter receives that exact registry. Identity/version disagreement,
missing database or unavailable authority prevents startup. Neither HTTP body
nor CLI exposes registry paths, database paths, arbitrary imports or Python RPC.

Responses serialize the authority documents with backend `stable_bytes`, without
wrapping, decorating or recomputing fields. The reporter retains responsibility
for package hash, version and shape checks and for all descriptive aggregation.
The request DTO in TypeScript supplies structure only: no identifier resolution,
loadout computation, wave overlay, rule interpretation, hashes or admission rules.

The package import guard checks schema/version and required structural records,
preserving P0 Monster resolution and P1 origins/provenance/rule records. Nullable
fields remain null and missing required fields fail closed. Only the reviewed
inspection statuses `STATIC_READY_BEHAVIOR_COMPILATION_REQUIRED` and
`DEBUG_OPAQUE_DISABLED_ONLY` with `golden_eligible=false` are imported. Positive
future states fail closed. These fields confer no execution permission.

The browser retains the original compile-response JSON in a private WeakMap,
outside the backend document. This is necessary because JavaScript serialization
changes Python integral float tokens such as `98.0` to `98`, breaking P4's hash
validation. Support sends the original JSON text unchanged. A structural snapshot
detects edits and requires recompilation; it calculates no hash. For an existing
compiled file, use `importScenarioPackage(fileText, '4.4.54')`. A plain parsed
object without its original source is rejected before support transport.

The support response uses the unchanged P5A P4 decoder. M15 remains REJECTED;
Monster and Stage runtime scope remains FAMILY_LEVEL_ONLY. The full distinct P4
sections and non-claims survive import without scores or a combined support flag.

## Local HTTP boundary

The implementation uses only Python's standard library HTTPServer. Existing
runtime dependencies are empty. ContentDatabase opens short-lived SQLite
connections; shared concurrent access has no explicit authority guarantee, so
the service handles one request at a time. There is no connection pool and no
startup enumeration of Stage details or product browse collections.

The bind address is fixed at `127.0.0.1`; there is no host override. Host headers
must match localhost or 127.0.0.1 and the actual listening port. Default exact
Origin allowlist:

- `http://localhost:5173`
- `http://127.0.0.1:5173`
- `http://localhost:4173`
- `http://127.0.0.1:4173`

Repeated `--allow-origin` replaces this list with explicit local origins. Remote,
wildcard, null, credentialed and path-containing origins are refused. Origin-less
CLI/test requests are permitted. OPTIONS accepts only a known route, its method,
an allowed origin and Content-Type headers. CORS echoes the allowed origin and
never uses `*` or credentials. POST requires application/json and an exact buffered
Content-Length, with a 2 MiB cap checked before reading/JSON parsing. Duplicate
JSON keys, nonstandard constants, transfer encoding and malformed JSON fail
closed. Connections have a ten-second socket timeout and close after a response.

Errors use `hsr_battle_agent.frontend_bridge_error/1` and stable transport codes:
INVALID_JSON, REQUEST_TOO_LARGE, UNSUPPORTED_CONTENT_VERSION,
SCENARIO_COMPILE_REJECTED, SUPPORT_REPORT_REJECTED, METHOD_NOT_ALLOWED, NOT_FOUND,
UNSUPPORTED_MEDIA_TYPE, ORIGIN_NOT_ALLOWED, INTERNAL_ERROR. Fixed safe messages
contain no exception text, tracebacks, environment values, stack frames or local
paths. Responses are no-store and nosniff; request/exception logs are suppressed.

No cookie/session authentication is needed for this loopback-only, stateless,
read/compute service protected by exact local origins and JSON POSTs. Requests
perform static database reads, existing M14 reads and public compilation/P4
aggregation. They expose no file mutation, battle session, action envelope, legal
actions, RNG draws, planner, allocation tickets or battle execution. M10–M15 and
all existing frontend visual files remain unchanged.

## Validation

- 264 backend tests passed in 133.126 seconds: new bridge (21), ScenarioCompiler,
  P1 conformance, P0 resolution parity, P4 reporter, both P5A/frozen adapter suites,
  and P2/P3 product suites. No skips. The P3 census was test-only.
- 193 frontend tests passed across 13 files, including 61 new bridge tests and
  the unchanged P5A static tests. Typecheck, lint and production build passed.
- A live native-fetch integration loaded the real frontend client through Vite,
  contacted a real loopback Python service, compiled and then separately obtained
  P4 support. The 65,611-byte package retained its verified hash; M15 was REJECTED,
  planner_invoked was false. Calls took 57 ms locally; server exited successfully.
- Real fixtures cover free, Stage-backed 420101 and variant/rule overlay packages.
  Their JSON sizes are recorded in the control artifact. Only tests import them.
- All 674 inventoried pre-existing files retained their starting SHA-256 values;
  every starting git-status entry was preserved. HEAD and branch are unchanged.
  No git add/commit or other git write was performed. No reverse regeneration ran.

Control artifact: `data/control/local_scenario_bridge_20260929_001.json`.
Handoff: `CR-P5B-LOCAL-SCENARIO-BRIDGE-20260929-001_changed_files.zip`, containing
only CR-owned additive files and a manifest with sizes/hashes. The archive is
reopened and checked against that manifest before delivery.
