# Runtime Health Check Probe（HD-2 前置）

本目录是 **最小、只读** 的 IL2CPP Runtime Health Check Probe。它只验证：

```text
domain → assemblies → image → class count → ~10 classes → class name/namespace
```

不 dump 全量 methods/fields，不进入 BattleInstance / Ability Execute / Modifier
Runtime / Battle Sandbox。Phase A 只构建和离线测试；Phase B 必须等用户明确
确认客户端已正常启动后才能执行。

## 安全边界（必须遵守）

- 仅用于本地研究客户端 / 隔离环境；禁止正式服。
- Probe 只调用 IL2CPP 内省 API 并读取内存；不写游戏内存、不 hook、不 patch、
  不隐藏模块、不做反检测、不绕过任何保护。
- 加载方式是**显式可见**的 `LoadLibraryW`（`loader/load_probe.exe` 通过标准
  `CreateRemoteThread` 调用）。模块名 `hsr_runtime_health_probe.dll` 始终出现在
  目标进程模块列表中。
- 如果客户端/保护拒绝标准加载路径：**停止并报告 BLOCKED**，不要升级为任何
  规避手段。
- `probe_config.ini` 中的 `expected_table_rva=0x1A36480` 是 **comparison-only**
  验证值，只用于 locator 运行后的日志核对；locator 源码、生成先验和评分过程
  都不读取该值。

## 目录

```text
tools/runtime_probe/
├── build.ps1                          # MSVC 构建 + 离线测试（自动发现 vswhere）
├── probe_config.ini                   # 运行配置（含 comparison-only 验证值）
├── README.md
├── EXPERIMENT.md                      # Phase B 实验 runbook
├── gen/locator_prior.h                # 由 Python locator 常量生成的先验头
├── probe/                             # 注入 DLL 源码
│   ├── dll_main.cpp                   # DllMain → worker thread（AllocConsole）
│   ├── health_check.cpp/h             # 9 步 fail-stop pipeline
│   ├── api_locator.cpp/h              # 结构评分 locator 的 C++ 移植
│   ├── pointer_validation.cpp/h       # 指针/字符串安全读取
│   ├── pe_model.cpp/h                 # 内存 PE section 模型
│   ├── json.cpp/h                     # 无依赖 JSON 输出
│   └── log_sink.cpp/h                 # 控制台 + UTF-8 日志
├── loader/load_probe.cpp              # 显式研究 loader（Phase B 才运行）
├── scripts/gen_locator_prior.py       # 从 Python locator 生成 C++ 先验
├── schema/health_check_result.schema.json
└── tests/
    ├── probe_self_tests.cpp           # 离线 C++ 自测（合成 locator + mock runtime）
    └── read_cstring_mini.cpp          # read_cstring 边界回归测试
```

Python 静态测试：`tests/cross_version/test_runtime_probe.py`。

## 构建与离线测试

工具链：本机 MSVC（通过 `vswhere` 自动发现 `vcvars64.bat`）。不使用 Rust/cmake。

```powershell
# 仓库根目录
powershell -NoProfile -ExecutionPolicy Bypass -File tools\runtime_probe\build.ps1 -RunTests
```

`-RunTests` 依次运行：

1. `read_cstring_mini.exe` — `read_cstring` 的 NUL 终止 / max_len 边界回归；
2. `probe_self_tests.exe` — JSON、pointer validation、合成 locator（27/27
   shape、3/3 twin、240 wrapper）、failure-stop（null domain 立即停止）、
   完整 mock runtime 链。

真实 UnityPlayer 的 locator 一致性检查（只做只读结构扫描，不调用 il2cpp
API，不启动游戏）：

```powershell
.\tools\runtime_probe\build\probe_self_tests.exe `
    --unity-path D:\StarRail_4.4.53\UnityPlayer.dll `
    --expect-rva 0x1A36480
```

预期输出：`candidates=958 best=0x1A36480 score=98.64 confidence=high
wrapper=240 desc=237`，与 Python locator 结果一致。

Python 测试：

```powershell
python -m unittest discover -s tests\cross_version -p "test_*.py" -v
```

## 输出

运行一次后，在配置的 `output_dir`（默认
`data/raw/4.4.54/il2cpp/`）生成同名的 `.json` + `.log`。

- JSON schema：`tools/runtime_probe/schema/health_check_result.schema.json`；
- JSON 顶层稳定字段：`schema_version / tool / game_version / version_source /
  generated_utc / pid / process_name / process_path / steps / failure_step /
  error / hd2`；
- `steps` 是严格顺序数组，第一个 `success=false` 即终止点；
- `hd2=true` 仅当全部 9 步成功。

游戏版本只从
`StarRail_Data\StreamingAssets\BinaryVersion.bytes`（fallback：StarRail.exe
version resource）读取，绝不从安装目录名推断。

## 步骤与失败语义

```text
module_discovery          → UnityPlayer.dll / GameAssembly.dll 已加载 + PE 可解析
api_table_locator         → C++ 结构评分 locator，high confidence，comparison-only 核对
domain_get                → 非空、可读 domain
domain_get_assemblies     → 1..65536 个 assembly，数组与每个指针可读
assembly_get_image        → 第一个 assembly 的 image 有效
image_name                → 可读、可打印、非空字符串
image_get_class_count     → 1..1000000（可配置）
image_get_classes         → 顺序读取前 10 个 class（可配置），每个指针有效
class_names               → 每个 class 的 name（非空）/ namespace 可读可打印
```

任一步失败：记录 JSON + 日志后立即停止，不执行后续步骤。所有 game 返回的
指针先经 `PointerValidator`（canonical / committed / readable / module /
section）验证；API 调用由 SEH guard 包裹，fault 会转为失败而不是继续。

## 加载 / 卸载（Phase B 才使用）

加载：客户端已正常初始化后（UnityPlayer.dll 与 GameAssembly.dll 均已加载），
由人工明确确认后执行：

```powershell
.\tools\runtime_probe\build\load_probe.exe
# 或显式指定：
.\tools\runtime_probe\build\load_probe.exe --process StarRail.exe `
    --dll .\tools\runtime_probe\build\hsr_runtime_health_probe.dll --check-only
```

卸载：Probe 不安装 hook，也不常驻后台线程；工作线程完成后退出。模块会一直
留在进程模块列表直到游戏退出（这是显式加载的预期行为）。**清理 = 正常退出
游戏客户端**；之后可删除 `build/`、输出 JSON/日志。若需要再次运行，重启游戏
后再加载（loader 会检测已加载并拒绝重复注入）。

## Phase A 状态

- 源码、构建脚本、schema、静态/单元测试、清理说明已完成；
- 未启动 StarRail.exe / Cultivation.exe / ppsr.exe；
- 未运行 loader；
- 等待用户手动启动客户端并确认后再进入 Phase B。
