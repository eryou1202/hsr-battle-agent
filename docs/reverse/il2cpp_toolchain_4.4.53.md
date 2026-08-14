# IL2CPP 逆向工具链评估与计划（4.4.54 资产）

> 计划文档（Task B），不是工具实测报告。
> 本文件描述：当前资产的定制特征、各工具预期兼容性、执行计划、产出物。
> game_version: 4.4.54（BetaLive 20260731-0529，见 `client_version_state.md`）
> 状态: [CONFIRMED] 资产特征；[HYPOTHESIS]/[UNKNOWN] 工具兼容性（待实测）

## 1. 当前资产特征（已实测确认）

### 1.1 global-metadata.dat（100,182,380 B）

- 文件头：`4D 48 59 00`（`MHY\0`）——**非标准 IL2CPP metadata 头**。
  标准头应为 `AF1BB1FA` + 版本号（当前主流 v24.5 / v27 / v29+ / v31+）。
- 全文件扫描：**不存在** `AF1BB1FA` / `FA B1 1B AF`（0 处命中）。
- 头部 64 字节除 `MHY\0` 与 4 字节 0 外全部呈随机分布 → 内容经过加密/混淆。
- 头部 0x08 处字节 `F1` 疑似密钥种子（[HYPOTHESIS]，需对照社区解密器验证）。

结论：这是米哈游定制 metadata 格式（与 Genshin 同族）。任何要求标准
`AF1BB1FA` 头的通用工具**直接失败**。

### 1.2 GameAssembly.dll（535,482,160 B）

- PE 有效：`MZ` / `PE\0\0`，x86-64（machine 0x8664），11 个节。
- 节表（关键节）：

| 节名 | RVA | VSize | RawSize | 说明 |
|---|---|---|---|---|
| .text | 0x1000 | 0x04027306 | 0x04027400 | 代码 64 MB |
| .rdata | 0x4029000 | 0x05390504 | 0x05390600 | 只读数据 87 MB |
| .data | 0x93BA000 | 0x00A929A0 | 0x00138000 | 可写数据 |
| .pdata | 0x9E4D000 | 0x0128ED4C | 0x0128EE00 | 异常表 |
| **il2cpp** | 0xB0E3000 | **0x13E9DCA0** | 0x13E9DE00 | IL2CPP 代码段 **333 MB** |
| **.upx0** | 0x1EF81000 | 0x014C1230 | 0x014C1400 | 疑似 UPX 风格压缩段 21.5 MB |
| .reloc | 0x20443000 | 0x003C8128 | 0x003C8200 | 重定位表 |

- 导出表：仅 1 个命名导出 `il2cpp_get_api_table`（2 个函数槽）。
  不存在 `il2cpp_init` / `il2cpp_class_from_name` 等标准导出
  （全文件字符串扫描 0 命中）。
  → 符号恢复需要解析 api table 结构（函数指针表），而非标准导出。
- `.upx0` 节：名称疑似 UPX，但文件中未找到 `UPX!`/`UPX0`/`NRV2` 标记
  （[HYPOTHESIS] 自定义壳或改名 UPX，需实测解压）。唯一命中 `LZMA`
  位于 .rdata（0x5B4F5FF），可能是第三方库字符串，证据弱。

### 1.3 其他相关组件

- `startup-metadata.dat`（3,898,140 B）：同族定制格式（待验证头部）。
- `xlua.dll` / `xluau.dll`：xLua / xLuaU 运行时（战斗可能涉及 Lua 逻辑）。
- `Persistent\IFix\Windows`：**当前为空**（iFix 热更未落地或已清理）。
- `mhypbase.dll` / `hkrpg.dll`：原生 SDK/运行时；`HoYoKProtect.sys`：
  内核反作弊驱动 —— **只读分析，禁止触碰/加载**（安全边界）。

## 2. 工具链评估（静态结论，待实测）

| 工具 | 对本资产预期 | 理由 | 优先级 |
|---|---|---|---|---|
| [honkai-dumper](https://github.com/lanylow/honkai-dumper)（lanylow） | **主候选，预期可用** | 专为 HSR 定制：处理 `MHY` 定制 metadata 与 api-table 导出；持续维护（2026 仍有提交） | P0 |
| Il2CppDumper（Perfare） | 预期失败 | 依赖标准 metadata（`AF1BB1FA`+版本）；对最新 metadata 版本支持滞后（issues #892/#894 显示连 v39/Unity 6000 都未跟进） | 不采用 |
| Cpp2IL（SamboyCoding） | 条件可用 | 本体支持较新 metadata，但同样无法直接读 `MHY` 头；需先把 metadata 解密/转换为标准格式，或走 no-metadata 模式 | P1 备用 |
| Il2CppInspector（djkaty） | 条件可用 | 静态分析+IDA/Ghidra 插件能力强，但同样依赖标准 metadata | P2 备用 |
| Ghidra / IDA | 必用 | E4 级证据（execute 逻辑反编译）的最终手段；需先获得符号 dump + 解壳 | P0（与 dump 并行） |

关键结论：**通用工具全部卡在"非标准 metadata"这一步**。
路径分叉：

```text
A. honkai-dumper 直接成功 → 最快路径
B. 失败 → 先解密 metadata 到标准格式 → Cpp2IL/Il2CppInspector
C. 无论如何 → Ghidra 验证关键方法（E4 证据）
```

## 3. 执行计划（下一步具体动作）

### 步骤 1：honkai-dumper 实测（预期 1 次会话）

```powershell
# 建议工作目录
cd "D:\HSR_Battle_Agent\hsr-battle-agent\tools\reverse"
git clone https://github.com/lanylow/honkai-dumper.git
# 按 README 构建（.NET）后运行：
#   输入 GameAssembly.dll + global-metadata.dat（当前 4.4.54 资产）
# 产出：类/字段/方法 dump（JSON/CSV 均可）
```

成功标准（验收）：

- 能枚举 `ConfigAbility*` 类族（如 `ConfigAbilityMixin` 子类、`ConfigAbilityAction`）；
- 能给出方法 RVA 与字段偏移；
- 上述结果输出到 `data/raw/4.4.54/il2cpp/`（版本化存放）。

若失败，记录失败模式（解不开 metadata / 版本不识别 / api table 解析失败），
转入步骤 2。

### 步骤 2：metadata 解密/标准化（备用路径）

- 参照社区方案逆向 `MHY\0` 头解密：
  - lanylow/honkai-dumper 源码中的 metadata 读取逻辑（最权威参考）；
  - 社区解密脚本（如 [astra1dev gist](https://gist.githubusercontent.com/astra1dev/ce969ef413a4a89f9625f969cb2c32e8/raw)、
    [metadata v39 修复讨论](https://forum.sbenny.com/thread/updated-il2cppdumper-with-metadata-version-39-support-download.194934/) 同族经验）；
- 目标：把解密后的数据还原为标准 IL2CPP metadata 布局（magic/version 可被
  Cpp2IL 接受），然后跑 Cpp2IL 交叉验证 honkai-dumper 结果。
- 本步骤同时回答："metadata 版本号是多少、用什么 key、什么算法"。

### 步骤 3：Ghidra 深度验证（E4 证据）

- 对 GameAssembly.dll 做预处理：.upx0 节解压（先试标准 `upx -d`；
  失败则手工识别壳）；
- 导入符号 dump 后定位：
  - `ConfigAbilityMixin` 的 vtable / 构造 / 反序列化 / Execute 类方法；
  - `il2cpp_get_api_table` 导出的 api table 解析；
- 产出方法级反编译证据，用于 Type Registry 的 E4 条目。

### 步骤 4：产出物（全部版本化到 data/raw/4.4.54/）

```text
data/raw/4.4.54/il2cpp/
├─ class_dump.json / class_dump.csv      # 类、继承、字段
├─ method_rva.csv                        # 方法名 → RVA
├─ api_table.json                        # il2cpp api table 结构
├─ metadata_format_notes.md              # MHY 头解密结论
└─ toolchain_run_log.md                  # 各工具成败记录
```

## 4. 第一批检索锚点（与 Task C 共用）

dump 完成后，优先在类清单中搜索：

```text
ConfigAbility            ConfigAbilityMixin       ConfigAbilityAction
ConfigAbilityPredicate   ModifierInstance         TargetSelector
DynamicValue             BattleEvent              BattleAction
DealDamage               AddModifier              RemoveModifier
ChangeModifierLayer      AddEnergy                ChangeSkillPoint
AdvanceAction            TriggerBattleEvent
```

以及 DesignData 暴露的字符串锚点（见 `ability_type_registry.md`）。

## 5. 风险与未知项

| 项 | 状态 | 说明 |
|---|---|---|
| metadata 解密算法 | [UNKNOWN] | 头 `MHY\0` + 0x08 处 `F1` 疑似密钥，未验证 |
| .upx0 壳类型 | [UNKNOWN] | 无 UPX 标记，可能是自定义壳 |
| api table 布局 | [UNKNOWN] | 导出仅 1 个函数，符号恢复依赖它 |
| honkai-dumper 对 4.4.54 的兼容性 | [HYPOTHESIS] | 需要实测；若滞后可能需 fork 修 metadata 版本 |
| Lua/xLua 在战斗中的参与度 | [UNKNOWN] | xluau.dll 存在，需确认战斗 DSL 是否含 Lua 路径 |

## 6. 实测结果（2026-08-04，4.4.54 资产）

本节是上表评估的**实测更新**，结论取代对应旧行。

### 6.1 honkai-dumper 实测

- 已克隆并审阅源码（vendored 于 `tools/reverse/honkai-dumper`，
  commit `bff8cd3`，2025-11-05，**"Updated for Honkai: Star Rail 3.7.0"**）。
- **它是进程内注入型工具，不是静态 dump 工具**：以 cdylib 注入运行中的
  游戏进程，通过 api table 运行时遍历 Il2Cpp 对象图。
- 其 api table 位置为硬编码 `UnityPlayer.dll + 0x1EED6A8`，**仅对 3.7.0 有效**；
  实测 4.4.54 的 UnityPlayer.dll 该位置内容为无效值（400 项全部 OUTSIDE）。
- 结论：作为静态路径不可用；作为运行时探针需配套注入器（lanylow 的
  genshin-utility）且目标为运行中的全球服客户端 —— 与项目"本地/隔离"
  边界冲突，**降级为 P2 运行时备选**，不进入本轮主路径。

### 6.2 其他候选工具结论

- **Pom-Pom（gmh5225）**：实测是外挂（含反作弊绕过、速度/隐身等），
  **违反项目安全边界，已删除克隆并禁止参考**。
- Il2CppDumper / Cpp2IL / Il2CppInspector：均需标准 metadata；
  在 metadata 解密完成前不可用（维持原评估）。

### 6.3 global-metadata.dat 保护机制（新确认）

| 项 | 实测结果 | 证据 |
|---|---|---|
| 头部 | `4D 48 59 00`（`MHY\0`）+ 4 字节 0（疑似 version=0）+ 加密主体 | 头部字节 |
| 加密主体 | 100MB 高熵（4MB 熵 7.94 bit/byte），全文无 `AF1BB1FA`、无任何真实字符串（最长"字符串"是随机命中的乱码） | 全文扫描 |
| 尾部 | **约 2KB 明文表**：重复 u32（0x6EC09×155、0x67C2C×130、0x91FE8×66、0x91FE6×78…） | 尾部 hex |
| startup-metadata.dat | 3.9MB **全加密**，无 MHY 头、无明文尾 | 头部/尾部 hex |

已尝试并排除：单字节 XOR（256 全扫）、4 字节候选密钥、自 XOR 链、
Kasiski 周期分析（无显著周期）、zlib/gzip/zstd/lz4 魔数。
→ 加密算法/密钥**未破解**，需社区方案或运行时探针。

### 6.4 GameAssembly.dll 保护机制（新确认）

- 导出 `il2cpp_get_api_table`（RVA `0x3BE4230`）**代码被混淆**，
  反汇编含 `movzx/mov r12w/xor` 垃圾指令序列，且 **call 目标落入
  `.upx0` 段**（约 RVA `0x1EFE49xx`）→ 真实逻辑在加壳段内。
- `.upx0`（21.5MB）：无 `UPX!`/`UPX0` 标记，非标准 UPX；文件 overlay
  （3.98MB，RVA 表样式数据）也无壳标识 → **自定义加壳/加密代码段**。
- **方法指针巨阵已定位**：.rdata 文件偏移 `0x44EBB88..0x47B9158`，
  RVA `0x44ED388`，**367,290 个连续指针**全部指向 `il2cpp` 段
  （这是 il2cpp 的 methodPointers 数组；后续 metadata 解密后可用于
  method index → RVA 映射）。数据见 `data/raw/4.4.54/il2cpp/`。
- api table 在 4.4.54 中未能在 UnityPlayer 定位（getter 混淆 + 表位置
  随版本移动）；用已知索引指纹扫描被 .rdata 指针饱和淹没，**未定位**。

### 6.5 静态路径状态与下一步

```text
静态类 dump 的硬阻塞 = metadata 解密（算法未知）
下一候选动作（按优先级）：
  1. 检索社区 HSR metadata 解密器（数据挖掘社区每个版本都在做）
  2. Cpp2IL no-metadata 模式 + 二进制启发式（无类名，仅结构）
  3. 运行时探针路径（honkai-dumper 类工具，需先解决注入与边界问题）
```

新增工具（本会话产出，均为纯静态离线分析）：

- `tools/unpack/probe_ability_directory_adaptive.py` — 4.4.54 能力目录
  自适应重建（已产出 `data/raw/4.4.54/manifest/`）。
- `tools/reverse/scripts/parse_api_table.py` — PE/api-table 解析器（4.4.54
  中 getter 混淆导致直接解析失败，保留用于后续版本验证）。
- `tools/reverse/scripts/scan_api_table.py` — api table 指纹扫描器
  （结论：4.4.54 指针饱和，需要更强判别特征）。

> 安全边界提醒：所有分析仅限本地文件（静态）与隔离环境（动态）；
> 不加载、不修改 `HoYoKProtect.sys`，不研究反作弊绕过。
