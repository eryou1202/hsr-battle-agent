# Real IL2CPP API Root — 4.4.54（il2cpp_get_api_table export re-verification）

> 2026-08-15 session. Scope: resolve the REAL return source of the
> `GameAssembly.dll` export `il2cpp_get_api_table`, using only PE-export
> re-verification and bounded static analysis. No remote code, no injection,
> no patch, no runtime ReadProcessMemory unless a static candidate global or
> pointer chain exists.
>
> Stop condition reached:
>
> ```text
> REAL_API_ROOT = DYNAMIC_DISPATCH_UNRESOLVED
> ```

## 1. 本 Session 为什么开

Previous sessions proved that `UnityPlayer .rdata RVA 0x1A36480` is a Unity
native proxy registration table, NOT a standard IL2CPP introspection API
table (see `docs/reverse/ro_runtime_snapshot_4.4.54.md`). This session starts
from the actual GameAssembly export and does not inherit any old slot
semantics or table RVA.

## 2. 输入工件

| 项 | 值 |
|---|---|
| 文件 | `D:\StarRail_4.4.53\GameAssembly.dll` |
| game_version | 4.4.54 |
| size | 535,482,160 bytes |
| sha256 | `7b44379bf69352022cb3437b03431ddc558ffb34e3d98e7144200f37e8c837cc` |
| PE | PE32+, image base `0x180000000`, 11 sections |

## 3. PE export directory re-verification（CONFIRMED）

从当前文件的 PE export directory 自动重新解析（非历史记录）：

| 项 | 值 |
|---|---|
| export_exists | True |
| export_name（精确匹配） | `il2cpp_get_api_table` |
| ordinal | 1 |
| export_rva | `0x3BE4230` |
| section | `.text` |
| section executable | True |
| forwarder | False |
| entry_bytes(64) | `41 54 49 bc 1b c6 92 8c 37 3e 3b 14 4d 0f b6 e4 66 41 bc 0d cd 9c 41 81 f4 bf 6b 08 1f e8 37 07 40 1b fc f4 55 41 2e aa 71 37 1c 43 33 79 05 56 4b ac 0a 1d 9d 7a 45 ae e9 25 a7 63 cd b9 f4 50` |

This independently confirms the old RVA `0x3BE4230` record, but now from the
current binary's export directory with an automatic tool.

## 4. Entry minimal CFG（automatic）

工具：`tools/reverse/scripts/resolve_il2cpp_get_api_table.py`（无硬编码
4.4.54 RVA；纯 Python 最小 x86-64 解码器 + bounded linear sweep）。

入口 `0x3BE4230` 的前置路径：

```text
3BE4230  push r12
3BE4232  mov  r12, 0x143B3E378C92C61B
3BE423C  movzx r12, r12b
3BE4240  mov  r12d, 0x419CCD0D
3BE4247  xor  rsp, 0x1F086BBF        ; stack pivot / stack-machine setup
3BE424D  call 0x1EFE4989              ; -> .upx0, executable section
```

第一个直接调用目标 `0x1EFE4989`（`.upx0`）的 pre-call CFG：

```text
1EFE4989  mov  r12, [rsp+r12-...]     ; stack-machine operand
1EFE4991  mov  [rsp+0x10], imm32
1EFE499A  push [rsp+8]
1EFE499E  popfq                        ; uses pushed bytes as flags
1EFE499F  lea  rsp, [rsp+0x10]
1EFE49A4  call 0x1F1A2DB4              ; still inside .upx0
```

入口线性扫描在 call 之后立即落入不可靠字节区（`fc f4 55 ...`），随后出现
`hlt` 与不可解码序列；这是混淆函数体的预期行为，不是真实 fallthrough CFG。

### 4.1 A–F 直接回答

| 问题 | 回答 | 证据 |
|---|---|---|
| A. `mov rax,[rip+global]; ret` | **否** | entry 无 RIP-relative read；自动扫描 reads=[] |
| B. `lea rax,[...]; ret` | **否** | entry 无 RIP-relative lea |
| C. initializer/helper 后返回 global | **未观察到** | entry 只有一个 direct call，且 call 后无静态可还原的 global load |
| D. wrapper / dispatcher | **是** | stack pivot（`xor rsp`）后 call 入 `.upx0`；target 本身是 stack-machine prologue |
| E. TLS / singleton / state object 读取 | **未观察到** | 无 RIP-relative 内存操作，无 TLS 指令形态 |
| F. 需要调用参数 | **无法静态确认，但入口未读取 RCX/RDX/R8/R9** | 前 6 条指令只写 r12/rsp |

## 5. Candidate globals / pointer chain

- `candidate_global_rvas`: **[]**
- `rip_relative_reads`: []（entry）
- `rip_relative_writes`: []（entry）
- `rip_relative_leas`: []（entry）
- `pointer_chain`: []（静态无链）

因此按 protocol 不执行外部 ReadProcessMemory 验证：没有可验证的静态候选
global 或 pointer chain。

## 6. 分类与证据等级

| 结论 | 等级 | 依据 |
|---|---|---|
| export 存在且 name-exact | CONFIRMED | 当前 PE export directory 自动解析 |
| ordinal=1、RVA=`0x3BE4230`、`.text`、可执行、非 forwarder | CONFIRMED | 同上 |
| entry 为 stack-machine dispatcher（xor rsp + call `.upx0`） | SUPPORTED | 自动最小 CFG；与旧手工解码记录一致 |
| 第一个 call target 无静态 RIP-relative return source | SUPPORTED | bounded target CFG（pre-call 6 条） |
| export 依赖运行时/保护态 transform，静态不可还原 | LIKELY | 旧 session 运行时 CONFIRMED：裸 harness 调用崩溃/返回垃圾，解码链依赖启动期初始化（不重新执行） |
| `REAL_API_ROOT = DYNAMIC_DISPATCH_UNRESOLVED` | CONFIRMED（protocol 分类） | 上述证据 |

Final classification: **DYNAMIC_DISPATCH**，confidence **medium**（静态路径）。
`candidate_return_source = None`。

## 7. 不做什么

- 不调用该 export；不注入；不 hook；不 patch；不绕过保护。
- 不把 `0x1A36480` 继续命名为 `il2cpp_api_table`。
  `find_il2cpp_api_table.py` 输出已增加
  `semantic_status = disproven_as_il2cpp_api_table` 与
  `structural_artifact_type = unity_native_proxy_registration_table`。
- 本 Session 最终状态为 `DYNAMIC_DISPATCH_UNRESOLVED`，不是裸 `UNRESOLVED`，
  因此不自动切换到 MHY metadata static recovery。

## 8. 产物

- 工具：`tools/reverse/scripts/resolve_il2cpp_get_api_table.py`
- 机器可读结果：
  `data/raw/4.4.54/il2cpp/real_il2cpp_api_root_4.4.54.json`
- 环境事实：`docs/agent/dsh_windows_environment.md` 已更新
  （where.exe UNUSABLE + 0x1A36480 语义纠正 + 本结果）。
