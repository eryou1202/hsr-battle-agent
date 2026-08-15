# runtime_snapshot — External Read-Only Runtime Snapshot

External, read-only runtime structure reader for the local ppSR / Cultivation
research client. First PoC of the RO-RUNTIME line.

Boundary:

- `OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ)` only;
- PSAPI `EnumProcessModulesEx` module discovery;
- `ReadProcessMemory` only for known module ranges and static-derived pointer
  chains, with null / canonical / module-range checks and fail-stop;
- no DLL, no loader, no remote code, no writes, no full address-space scan.

## Usage

Static target resolution first:

```powershell
$env:PYTHONPATH = "$PWD\.venv\site-packages"   # if capstone is installed there
& "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" `
    tools\reverse\scripts\resolve_runtime_api_target.py `
    --unity D:\StarRail_4.4.53\UnityPlayer.dll `
    --game  D:\StarRail_4.4.53\GameAssembly.dll `
    --slot 63 --table-rva 0x1A36480 `
    --json data\raw\4.4.54\il2cpp\runtime_snapshot_static_target_slot63_4.4.54.json
```

External read (client must be running and initialized):

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" `
    tools\runtime_snapshot\runtime_snapshot.py `
    --pid 36268 `
    --unity-file D:\StarRail_4.4.53\UnityPlayer.dll `
    --game-file  D:\StarRail_4.4.53\GameAssembly.dll `
    --table-rva 0x1A36480 --slot 63 `
    --game-version 4.4.54 --probe-heap-fields `
    --json data\raw\4.4.54\il2cpp\runtime_snapshot_domain_4.4.54.json
```

`--table-rva` must come from a static locator run / checked-in locator JSON.
Never hardcode ASLR runtime base addresses.

## Current status (4.4.54)

`final_status = STATIC_TARGET_UNRESOLVED`.

The slot 63 chain resolves to a Unity proxy-registration stub
(`::Scripting::UnityEngine::VFX::VFXExpressionNoiseProxy`), not to
`il2cpp_domain_get`. See:

- `docs/reverse/ro_runtime_snapshot_4.4.54.md`
- `data/raw/4.4.54/il2cpp/runtime_snapshot_domain_4.4.54.md`
