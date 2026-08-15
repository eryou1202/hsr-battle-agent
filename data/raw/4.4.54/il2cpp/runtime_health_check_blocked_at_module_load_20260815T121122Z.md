# HD-2 Runtime Health Check — BLOCKED_AT_MODULE_LOAD

> generated_utc: 2026-08-15T12:11:22Z
> generated_local: 2026-08-15 20:11:22
> game_version: 4.4.54
> final_status: **BLOCKED_AT_MODULE_LOAD**

## 1. 结论

标准、显式、可见的 `LoadLibraryW` 研究加载路径在进入目标进程前被
`OpenProcess` 拒绝：

- 请求权限：
  `PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ`
- `GetLastError = 5`（`ERROR_ACCESS_DENIED`）
- 没有加载 DLL、没有 CreateRemoteThread、没有写内存、没有 hook / patch。

因此：

```text
HD-2 = BLOCKED_AT_MODULE_LOAD
```

## 2. 已确认环境事实

| 项 | 值 |
|---|---|
| StarRail.exe | PID 36268，`D:\StarRail_4.4.53\StarRail.exe` |
| probe integrity | High，elevated=false |
| target integrity | High，elevated=true |
| `PROCESS_QUERY_INFORMATION \| PROCESS_VM_READ` | OK |
| Toolhelp module snapshot | `ERROR_ACCESS_DENIED (5)` |
| PSAPI `EnumProcessModulesEx(LIST_MODULES_ALL)` | OK，`lpcbNeeded=1184`，148 modules |
| UnityPlayer.dll | `base=0x7FFC4FEF0000 size=0x2756000` |
| GameAssembly.dll | `base=0x7FFC2F6E0000 size=0x2080C000` |
| remote read-only locator | `0x1A36480`，score 98.64，confidence high |
| locator details | 27/27 known，240 wrapper，237 descriptor，3/3 twin |
| comparison-only | expected `0x1A36480` → MATCH |

## 3. Loader 原始输出

```text
target: pid=36268 name=StarRail.exe
preflight: UnityPlayer.dll and GameAssembly.dll are loaded.
loading (visible LoadLibraryW): D:\HSR_Battle_Agent\hsr-battle-agent\tools\runtime_probe\build\hsr_runtime_health_probe.dll
BLOCKED: OpenProcess failed (error 5: 拒绝访问。).
Do not attempt to bypass this restriction; report BLOCKED.
exit=3
```

## 4. 为什么不是 PRECHECK 失败

PRECHECK 全部通过，因为它只申请只读权限。真正 loader 需要的
`PROCESS_CREATE_THREAD / PROCESS_VM_OPERATION / PROCESS_VM_WRITE` 被同一进程
的访问策略拒绝。因此阻塞点明确为 **module load 阶段的 OpenProcess**，
不是 API table、不是 Runtime 初始化。

## 5. 停止记录

未尝试：

- SeDebugPrivilege
- AdjustTokenPrivileges
- PEB 手工遍历
- NtQueryInformationProcess
- VirtualQueryEx 扫描
- 驱动
- hook / patch
- manual map / hidden injection / module hiding / anti-detection
- 任何保护绕过

## 6. 下一步（仅建议，不自动执行）

可能的合规路径需要人工决策：

1. 在允许授予 `PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION | PROCESS_VM_WRITE`
   的隔离研究环境重启客户端；
2. 或使用其他已被项目安全边界允许的显式研究加载路径（需重新评估）；
3. 或保持 BLOCKED。
