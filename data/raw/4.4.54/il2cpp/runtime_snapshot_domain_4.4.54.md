# RO-RUNTIME Runtime Snapshot — 4.4.54 — STATIC_TARGET_UNRESOLVED

> generated: 2026-08-15 (session RO-RUNTIME)
> game_version: 4.4.54
> target_pid: 36268
> final_status: **STATIC_TARGET_UNRESOLVED**

## 1. 结论

在**不调用 `domain_get()`、不向目标进程写任何内容**的前提下完成了：

```text
api table (0x1A36480, locator E2)
  -> slot 63 wrapper (UnityPlayer+0x453160)
  -> descriptor (UnityPlayer+0x1EE8B68)
  -> descriptor q[5] real-target stub (UnityPlayer+0x48E1C0)
  -> static disassembly
```

但静态反汇编证明该 q[5] stub **不是 `il2cpp_domain_get` 实现**，而是
Unity 原生绑定注册 thunk：

```text
sub rsp,0x28
call UnityPlayer+0xCA3080        ; mov rax,[rip+...]; ret  (global vector)
lea r9, [rip-0x3690]             ; thunk
mov rcx,rax
lea r8, [rip-0x221A]             ; init function
lea rdx, [rip+0x15AFEEF]         ; "::Scripting::UnityEngine::VFX::VFXExpressionNoiseProxy"
jmp UnityPlayer+0xCA4D90         ; append {string, func, func} to global vector
```

因此 **slot 63 = domain_get 的语义绑定不成立**。0x1A36480 的候选空间中，
slot 63 附近全部是 `::Scripting::UnityEngine::...Proxy` 注册项（Physics /
VFX / Animations / TextCore 等），说明此前被定位的是 Unity 代理注册表，
不是标准 IL2CPP introspection API table。

## 2. 静态链（自动解析）

| 项 | 值 |
|---|---|
| api_table_rva | `0x1A36480`（locator best，仅作为本轮比较对象） |
| slot | 63（E2 假设名 `domain_get`） |
| wrapper_rva | `0x453160`（shape A） |
| descriptor_rva | `0x1EE8B68`（mapped .data，磁盘字节加密） |
| descriptor q[5] | `0x48E1C0`（real-target stub） |
| q[5] classification | **proxy-registration** |
| q[5] rdx string | `::Scripting::UnityEngine::VFX::VFXExpressionNoiseProxy` |
| q[5] triple | r9=`0x48AB40`, r8=`0x48BFC0`, rdx=`0x1A3E0D0` |

## 3. 运行中目标只读结果

目标仍为正常初始化的本地 ppSR/Cultivation 客户端（PID 36268）。
只使用 `OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ)` +
`EnumProcessModulesEx` + `ReadProcessMemory`。

| 项 | 值 |
|---|---|
| UnityPlayer.dll base | `0x7FFC4FEF0000` size `0x2756000` |
| GameAssembly.dll base | `0x7FFC2F6E0000` size `0x2080C000` |
| 远程 wrapper bytes | 与磁盘一致，shape A |
| 远程 descriptor q[0] | `0x2`（初始化状态） |
| 远程 descriptor q[1] | `0x11C` |
| 远程 descriptor q[2] | `0x00000700D756E640`（opaque heap object） |
| 远程 descriptor q[5] | `0x48E1C0`（未变化，仍为注册 stub） |
| 远程 descriptor q[7] | `0x1` |
| 远程 descriptor q[10] | `0x0000050007638E58`（opaque heap object） |
| q[2] probe | READABLE，首 qword `0x5000850EF00` 等 opaque 堆指针 |
| q[10] probe | READABLE，含 GameAssembly il2cpp 段共享函数指针（0x1BCF7EF0 等） |

descriptor 在目标中被初始化，但初始化值是不透明的 resolver 对象/句柄；
没有出现可直接验证的 `domain pointer`，也没有静态恢复出
`runtime global -> domain` 的指针链。

## 4. 证据等级

- api table 结构定位：仍为 **E2**（结构一致，语义被本轮证伪）。
- slot 63 语义绑定：**FAIL**。q[5] 代码与字符串是运行时可见事实（E4/E5 级），
  与 E2 假设矛盾。
- 没有形成 E3 runtime type 证据。

## 5. 失败分类

```text
RO-RUNTIME = STATIC_TARGET_UNRESOLVED
```

具体原因不是 ReadProcessMemory 失败，而是静态目标解析失败：

1. 假定 slot 63 → `domain_get` 的索引语义在 4.4.54 不成立；
2. 该表是 Unity 代理注册表；
3. 真正的 IL2CPP API table / domain_get 实现未在当前有限静态链中恢复。

按 Session 规则，本阶段停止，不自动切换到下一候选主线。

## 6. 产物

- `data/raw/4.4.54/il2cpp/runtime_snapshot_static_target_slot63_4.4.54.json`
- `data/raw/4.4.54/il2cpp/runtime_snapshot_domain_4.4.54.json`
- 工具：`tools/reverse/scripts/resolve_runtime_api_target.py`
- 工具：`tools/runtime_snapshot/runtime_snapshot.py`
- 研究文档：`docs/reverse/ro_runtime_snapshot_4.4.54.md`
