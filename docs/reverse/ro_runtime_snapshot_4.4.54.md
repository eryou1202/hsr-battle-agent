# RO-RUNTIME 4.4.54 — External Read-Only Runtime Snapshot（第一阶段）

> 路线：Static Runtime Function Analysis → runtime global / pointer chain →
> external ReadProcessMemory → domain/assemblies/images/classes。
> 本阶段最小目标：不调用 `domain_get()`，从静态恢复的链读出合理 domain 值。
> 结果：**STATIC_TARGET_UNRESOLVED**。

## 1. 目标与方法

- 仅允许：静态分析 + PSAPI + `PROCESS_VM_READ` + `ReadProcessMemory`。
- 不允许：远程 LoadLibrary / CreateRemoteThread / VirtualAllocEx /
  WriteProcessMemory / 全地址空间扫描 / PEB / NtQueryInformationProcess。
- 起点：已有 API Table locator（E2）与 honkai-dumper 索引假设
  （slot 63 = domain_get）。
- 静态阶段在本进程 `LoadLibrary(UnityPlayer.dll/GameAssembly.dll)` 后
  只读检查映射内存（磁盘 `.data` 是加密字节，映射后可读）；
  运行阶段只对正常初始化的本地 ppSR 客户端使用只读句柄。

## 2. 已确认链

```text
table entry @ UnityPlayer .rdata 0x1A36480 (locator best)
  -> slot 63 wrapper @ UnityPlayer .text 0x453160
      45 33 C0 | 48 8D 0D <desc> | 33 D2 | E9 <0xC3F540>
  -> descriptor @ UnityPlayer .data 0x1EE8B68 (0x58-byte record)
  -> descriptor q[5] @ UnityPlayer .text 0x48E1C0
```

## 3. q[5] “real target” 的静态事实

`0x48E1C0` 不是 `il2cpp_domain_get`，而是标准 proxy 注册 thunk：

```asm
48 83 EC 28          sub rsp, 0x28
E8 B7 4E 81 00       call 0xCA3080     ; mov rax,[rip+...]; ret（全局 vector 指针）
4C 8D 0D 70 C9 FF FF lea r9, [0x48AB40] ; 指向 descriptor 的二次 thunk
48 8B C8             mov rcx, rax
4C 8D 05 E6 DD FF FF lea r8, [0x48BFC0] ; 初始化函数
48 8D 15 EF FE 5A 01 lea rdx, [0x1A3E0D0]
                     ; "::Scripting::UnityEngine::VFX::VFXExpressionNoiseProxy"
E9 A6 6B 81 00       jmp 0xCA4D90      ; 向 vector append {rdx,r8,r9} 24B tuple
```

r8 初始化函数进一步调用 `0xC431F0`，后者 call 目标落入加密 `.upx0` 段
（动态 dispatch / resolver）。因此即使忽略语义问题，该链也会进入
“初始化后的秘密状态 + 复杂动态计算”区域。

## 4. 关键反证：slot 索引语义不成立

对全部 A-shape 已知槽位自动提取 q[5] rdx 字符串，结果全部是 Unity
C# 代理类注册名，例如：

| 槽 | E2 假设名 | q[5] rdx 字符串 |
|---|---|---|
| 31 | class_get_fields | `::Scripting::UnityEngine::MeshColliderExProxy` |
| 33 | class_get_interfaces | `::Scripting::UnityEngine::PhysicsProxy` |
| 63 | domain_get | `::Scripting::UnityEngine::VFX::VFXExpressionNoiseProxy` |
| 65 | domain_get_assemblies | `::Scripting::UnityEngine::VFX::VFXExpressionValuesProxy` |
| 116 | method_get_return_type | `::Scripting::UnityEngine::Animations::RotationConstraintProxy` |
| 168 | image_get_name | `::Scripting::UnityEngineInternal::WebRequestUtilsProxy` |

结论：`0x1A36480` 及其 locator 候选邻域是 **Unity 引擎原生绑定代理注册表**，
不是标准 IL2CPP introspection API table。此前“slot 顺序与 honkai-dumper
27/27 一致”是结构形状相似（E2），语义命名是错误的。

## 5. 运行中目标只读观察（PID 36268）

- 模块：UnityPlayer `0x7FFC4FEF0000/0x2756000`，
  GameAssembly `0x7FFC2F6E0000/0x2080C000`。
- 远程 wrapper / q[5] 字节与磁盘一致。
- 初始化后 descriptor：
  `q[0]=2, q[1]=0x11C, q[2]=0x700D756E640, q[5]=0x48E1C0,
   q[7]=1, q[10]=0x50007638E58, q[11]=2`。
- q[2]/q[10] 指向可读的 opaque 堆对象；未形成可验证的 domain 对象，
  也没有静态恢复出的 `runtime_global_rva`。

## 6. 失败分类

```text
RO-RUNTIME = STATIC_TARGET_UNRESOLVED
```

- `STATIC_TARGET_UNRESOLVED`：真实 `domain_get` 实现与 runtime global
  未能从给定 API table 链恢复；E2 索引语义被 q[5] 静态代码证伪。
- 未进入 `REMOTE_READ_FAILED` / `POINTER_VALIDATION_FAILED`：
  只读通道本身全部 PASS。
- 不自动切换下一候选主线。

## 7. 工具与产物

- `tools/reverse/scripts/resolve_runtime_api_target.py`
  （slot → table/wrapper/descriptor/q5 → stub 分类 → JSON）
- `tools/runtime_snapshot/runtime_snapshot.py`
  （StarRail.exe → PSAPI → remote PE → 链读取/验证 → JSON）
- `tools/runtime_snapshot/README.md`
- `data/raw/4.4.54/il2cpp/runtime_snapshot_static_target_slot63_4.4.54.json`
- `data/raw/4.4.54/il2cpp/runtime_snapshot_domain_4.4.54.json`
- `data/raw/4.4.54/il2cpp/runtime_snapshot_domain_4.4.54.md`

## 8. 对后续的直接影响（仅记录，不在本 Session 执行）

1. `docs/reverse/il2cpp_api_table.md` 与 locator prior 中
   “slot 索引 = il2cpp API”结论需要降级为 E2 且注明已被语义反证。
2. 真实 IL2CPP API table 的定位需要新的、更强语义锚点
   （如真正可静态识别的 `domain_get` 代码形状），
   不能复用当前 proxy-registration prior。
3. 只读基础设施（PSAPI + RPM + 远程 PE + pointer validation）已被验证
   可完全复用于下一候选。
