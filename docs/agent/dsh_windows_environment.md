# DSH Windows Environment Handoff

> Long-lived CONFIRMED facts and recovery rules for this repository on the
> current Windows workstation. New sessions should read this file first.

## Platform

- Host = Windows.
- Prefer `pwsh` (Windows PowerShell) for Windows-native tasks: processes,
  registry, PATH, Windows APIs, PowerShell scripts, Windows paths.
- `bash` remains available for text/Git/cross-platform work. Choose the tool
  for the task; if a bash call fails in this Windows DSH environment, record
  why and switch to `pwsh`. Do not mechanically repeat the same failing call.

## File editing

- If `edit` returns `FS_NOT_OBSERVED`, recover with: `read` the file, then
  `edit` again. The error itself does not mean the file is corrupted.

## Python

CONFIRMED in the current DSH environment:

| Item | Status |
|---|---|
| bare `python` (resolves to Python 3.14.3 first) | fails with `0xc0000142`; project does NOT use it |
| `C:\WINDOWS\py.exe` / `py -3.11` | fails with `0xc0000142`; project does NOT use it |
| `<LOCALAPPDATA>\Programs\Python\Python311\python.exe` (3.11.9) | VERIFIED working |

Policy:

- Use `scripts/python/resolve_python.ps1` for project Python calls.
- Never depend on PATH order or auto-probe unknown interpreters.
- Resolver order: explicit `-PythonExe` → `HSR_PYTHON_EXE` → verified local
  Python 3.11 fallback → explicit FAIL.
- Do not re-test the known-failing launchers in every new session.
- Do not modify system/user PATH and do not reinstall Python.

## MSVC

- `D:\VSCcommunity` exists on this workstation and has successfully built the
  project.
- `vswhere.exe` has also shown `0xc0000142` in the DSH environment. Do not
  auto-install/upgrade/reinstall Visual Studio because of that.
- Do not treat `D:\VSCcommunity` as the only valid path on all machines.

## Build environment

- `tools/runtime_probe/build.ps1` only modifies child-process `PATH` /
  `INCLUDE` / `LIB`; it has no `setx` and no registry writes.
- DSH pwsh tool calls run in independent PowerShell processes; child process
  environment changes do not leak back to the parent.
- Never pollute user/system environment with `setx` or registry writes.

## Development discipline

- Small change → minimal build → minimal test → PASS → next step.
- Do not repeat the same failing operation unchanged.

## Runtime reverse status

CONFIRMED:

- PRECHECK = PASS.
- Toolhelp module snapshot: `ERROR_ACCESS_DENIED(5)`.
- PSAPI `EnumProcessModulesEx`: PASS.
- `PROCESS_QUERY_INFORMATION | PROCESS_VM_READ`: PASS.
- Runtime-memory API table locator: best RVA `0x1A36480`, score 98.64,
  confidence high, known 27/27, wrapper 240, descriptor 237, twin 3/3.
- HD-2 = BLOCKED_AT_MODULE_LOAD.

Archived (do not re-open): remote `LoadLibrary` / `CreateRemoteThread` /
`VirtualAllocEx` / `WriteProcessMemory` / manual map / `SeDebugPrivilege` /
driver / hook / patch / protection bypass.

Currently allowed for the local ppSR / Cultivation research client:

- static analysis;
- PSAPI module discovery;
- `PROCESS_VM_READ` + `ReadProcessMemory`.
