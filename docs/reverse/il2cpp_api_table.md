# IL2CPP API Table 研究（4.4.54）

> Task 1 产物。研究目标：`GameAssembly.dll` 导出 `il2cpp_get_api_table` 的
> 结构与 4.4.54 的 IL2CPP function table 定位。
> game_version: 4.4.54（BetaLive 20260731-0529）
> 研究日期: 2026-08-04（第二轮）
> 状态: [SUPPORTED] table 结构定位；[CONFIRMED] export 反 harness 守卫

## 1. 导出函数 il2cpp_get_api_table

| 项 | 值 | 证据 |
|---|---|---|
| 导出名 | `il2cpp_get_api_table` | PE 导出表（唯一命名导出） |
| RVA | `0x3BE4230`（.text） | PE 解析 + 运行时 GetProcAddress 一致 |
| 函数体 | 混淆（垃圾指令序列 + 栈游戏），call 目标落入 `.upx0` 段（约 RVA `0x1EFE49xx`） | 手工解码 + 运行时验证 |
| 输入参数 | 无（标准 il2cpp getter 无参） | — |
| 返回 | function table 指针（预期）；**裸 harness 中调用崩溃** | 见下 |

### 1.1 反 harness 守卫（[CONFIRMED]，运行时证据）

在隔离进程（LoadLibrary + GetProcAddress + 直接调用）中调用 export：

- 第一次访问违例：`RVA 0x1F1434A3`（.upx0 内），**写 0x0**，
  寄存器状态为解密中间值（rax=0x5C6E9CFA46F14FD4，rsp 已切换到
  自定义栈 0x40010DExx）→ 解码链状态损坏。
- 对崩溃点做"写指令 NOP 化 + 继续执行"（VEH，最多 80 处补丁）：
  解码器推进 3 段后返回垃圾值（0x4C3），随后再次崩溃。
- 结论：getter 的解码链依赖**游戏启动期初始化**（.upx0 内 18 个
  DIR64 指针槽在裸进程中只有加载器填的 delta 值，真实值由保护代码
  在游戏启动时写入）。**export 不能直接在 harness 中取得 table。**

### 1.2 返回结构（[SUPPORTED]）

getter 返回的 table = 函数指针数组（标准 il2cpp api table），
4.4.54 中位于 **UnityPlayer.dll .rdata RVA `0x1A36480`**：

- 数组元素 = 8 字节指针，指向 UnityPlayer .text 的 **wrapper stub**；
- wrapper 布局为 32 字节间隔的多个函数簇
  （0x452C40-0x453620 / 0x4538A0-0x453E60 / 0x453F40-0x454EA0 /
  0x455180-0x4556C0 …）；
- wrapper 形状（class_* 族）：
  `45 33 c0 | 48 8d 0d <desc> | 33 d2 | e9 <dispatcher>` —
  即 `lea rcx, descriptor; jmp dispatcher(0x4B1F53A)`；
- descriptor 表在 UnityPlayer .rdata `0x1EE8xxx`，
  `descriptor[5]` = 真实函数桩指针（0x48Exxx 区，本身也是桩，
  内部 call/jmp 目标为运行时解码地址）。

### 1.3 slot 顺序与 honkai-dumper 索引的兼容性（[SUPPORTED]）

在 RVA `0x1A36480` 对齐下，全部 27 个 honkai-dumper 已知索引
（functions.rs）命中正确的相对位置：

```text
 22 assembly_get_image        0x4532E0
 31 class_get_fields          0x452F60   33 class_get_interfaces  0x453020
 35 class_get_methods         0x453040   37 class_get_name        0x4530A0
 39 class_get_namespace       0x452EE0   40 class_get_parent      0x4537A0
 43 class_is_valuetype        0x452EA0   45 class_get_flags       0x452EC0
 49 class_from_type           0x452F40   53 class_is_enum        0x452D60
 63 domain_get                0x453160   65 domain_get_assemblies 0x453180
 72 field_get_flags           0x453DA0   73 field_get_name        0x453220
 75 field_get_offset          0x453200   76 field_get_type        0x453DE0
116 method_get_return_type    0x45342E0  117 method_get_name       0x4534B60
123 method_get_param_count    0x45348A0  124 method_get_param      0x4534100
161 type_get_name             0x4535240  162 type_is_byref         0x4534E80
163 type_get_attrs            0x4535140
168 image_get_name            0x4535120  169 image_get_class_count 0x4535680
170 image_get_class           0x45356C0
```

对齐锚点（双子对）：

- slot 10/12 = 0x453AA0/0x453AE0（双子函数，相距 0x40）
- slot 63/65 = 0x453160/0x453180（双子，相距 0x20）
- 两对相距恰好 **53 slot × 8 = 424 字节**（与索引差 63-10=53 一致）

完整 240 slot 转储：`data/raw/4.4.54/il2cpp/api_table_4.4.54.json`。

## 2. 结论（Task 1 问题回答）

1. **返回什么结构**：函数指针数组（il2cpp api table），条目为
   UnityPlayer .text 的 wrapper stub（descriptor + dispatcher 模式）。
   [SUPPORTED]
2. **是否可得与 honkai-dumper 兼容的 function table**：结构上兼容
   （索引布局一致）；但运行时调用被守卫拦截，裸 harness 无法直接
   枚举。需要游戏启动态或进一步绕过守卫（不在本轮范围）。
   [SUPPORTED / 部分 LIKELY]
3. **slot 顺序是否与旧版本一致**：与 honkai-dumper 3.7.0 索引表
   完全一致（27/27 命中）。[SUPPORTED]
4. **自动识别方式**：`tools/reverse/scripts/find_il2cpp_api_table.py`
   初版（基于双子对 + 组内相邻 + 全索引代码指针检查）；
   4.4.54 上命中 828 个候选（宽松），锚定双子对后可收敛到
   0x1A36480。[HYPOTHESIS，待细化]

## 3. 层叠保护结构（4.4.54）

```text
il2cpp_get_api_table (GameAssembly .text 0x3BE4230, 混淆)
  └─ call → .upx0 解码链 (0x1EFE49xx, 依赖启动期初始化, 18 个 DIR64 指针槽)
       └─ 返回 → api table (UnityPlayer .rdata 0x1A36480)
            ├─ wrapper stub (UnityPlayer .text 0x452C40-0x4556C0, 32B 间隔)
            │    └─ lea rcx, descriptor; jmp dispatcher (0x4B1F53A)
            ├─ descriptor 表 (UnityPlayer .rdata 0x1EE8xxx)
            │    └─ [5] = 真实函数桩 (0x48Exxx)
            │         └─ 内部 call/jmp 目标 = 运行时解码地址
            └─ 行为: 裸 harness 调用 wrapper → 返回垃圾（门控未开）
```

## 4. 证据等级汇总

| 结论 | 等级 | 依据 |
|---|---|---|
| export RVA 0x3BE4230 | CONFIRMED | PE 解析 + GetProcAddress |
| export 混淆 + call 进 .upx0 | CONFIRMED | 反汇编 + VEH 运行时 |
| export 反 harness 守卫 | CONFIRMED | 裸调用崩溃（写 0x0）+ NOP 推进后返回垃圾 |
| table @ UnityPlayer .rdata 0x1A36480 | SUPPORTED | 27/27 索引对齐 + 双子对锚点 + 三层结构一致 |
| slot 顺序与 honkai-dumper 一致 | SUPPORTED | 索引映射逐项命中 |
| wrapper/descriptor/真实桩三层 | SUPPORTED | 结构反汇编 |
| 运行时枚举可行性（裸 harness） | CONFIRMED 不可行 | 行为测试（domain_get 返回垃圾） |
