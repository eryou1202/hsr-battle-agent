# Phase B 实验 Runbook：Runtime Health Check

> 状态：Phase A 已完成（Probe 构建 + 离线测试全部通过）。
> 本文件只在用户明确确认“客户端已正常启动”后执行。
> 不启动 ppSR / Cultivation；不自动操作 GUI；不启动战斗。

## 前置条件（由用户完成）

1. 用户手动启动本地研究客户端 `D:\StarRail_4.4.53\StarRail.exe`。
2. 等待正常初始化完成：UnityPlayer.dll 与 GameAssembly.dll 均已加载
   （建议到达可操作主界面后通知）。
3. 用户明确回复“客户端已启动”或等价确认。

版本真值：不信任目录名。Probe 会自行读取
`StarRail_Data\StreamingAssets\BinaryVersion.bytes`，Phase B 记录中应出现
`4.4.54` 与 build `20260731-0529`。

## 执行顺序（严格）

```powershell
# 0. preflight：确认目标进程与模块已就绪，不注入
.\tools\runtime_probe\build\load_probe.exe --check-only

# 1-9. 注入显式、可见的 probe（只读 introspection）
.\tools\runtime_probe\build\load_probe.exe
```

Probe 内部严格依次执行并 fail-stop：

```text
module_discovery
→ api_table_locator（自动定位 + comparison-only 核对 0x1A36480）
→ domain_get
→ domain_get_assemblies
→ assembly_get_image
→ image_name
→ image_get_class_count
→ image_get_classes（前 10 个，顺序）
→ class_names
```

## 产物

默认输出到 `data/raw/4.4.54/il2cpp/`：

```text
runtime_health_check_<utc>_pid<pid>.json
runtime_health_check_<utc>_pid<pid>.log
```

同时 probe 会 `AllocConsole` 显示可见控制台日志。

## 判定

- 全部 9 步成功且结果合理 → 顶层 JSON `hd2=true`，判定 **HD-2 = PASS**。
- 任一步失败 → JSON `steps` 最后一条 `success=false`，`failure_step` /
  `error` 标明失败步骤；判定 **HD-2 = FAIL / BLOCKED**。
- 若 loader 的 preflight/OpenProcess/VirtualAllocEx/CreateRemoteThread 被客户端
  或保护拒绝 → 立即停止并报告 **BLOCKED**，不尝试任何绕过。

## 成功后

仅允许继续一个小成果：第一份 Runtime Type Skeleton（namespace / class_name /
base_class / field_count / method_count / method_rvas），锚点先查
`Ability / Mixin / Modifier / Predicate / Target / DynamicValue / BattleEvent`。
不立即做大范围 xref、Execute 反编译、Battle Runtime 实现。

## 清理

- Probe 无 hook、无驻留线程；退出游戏客户端即完全卸载。
- 如需重跑：重启客户端后再次 loader（loader 会拒绝重复加载）。
- 可删除 `tools/runtime_probe/build/` 与 `data/raw/4.4.54/il2cpp/runtime_health_check_*`。
