# honkai-dumper 可移植性拆解

> Task 2 产物。目标：区分 honkai-dumper 源码中"版本强绑定"与"版本无关"部分，
> 明确除 `UnityPlayer + 0x1eed6a8` 之外还有哪些 3.7.0 绑定点。
> 分析对象：commit `bff8cd3`（2025-11-05，"Updated for Honkai: Star Rail 3.7.0"）
> 已 vendored 于 `tools/reverse/honkai-dumper/`。

## 1. 四层拆解

| 层 | 文件 | 内容 | 版本耦合度 |
|---|---|---|---|
| A. table 定位 | `src/il2cpp/functions.rs` `Il2CppFunctions::new` | **`UnityPlayer base + 0x1EED6A8`** 作为函数指针数组起点 | **强绑定**（唯一硬编码位置） |
| B. table slot 定义 | 同上（`index!(funcs, N)` 常量） | 27 个索引：22/31/33/35/37/39/40/43/45/49/53/63/65/72/73/75/76/116/117/123/124/161/162/163/168/169/170 | 弱绑定（il2cpp api 顺序，跨版本稳定；4.4.54 已验证一致） |
| C. 遍历逻辑 | `api.rs` + `outputs/*.rs` | domain→assemblies→image→classes→fields/methods 的标准 il2cpp API 调用 | 版本无关 |
| D. 输出逻辑 | `outputs/csdumper.rs`、`outputs/methoddumper.rs` | C#/JSON 格式化 | 版本无关 |

## 2. 除 0x1EED6A8 之外的版本绑定点

| 点 | 位置 | 说明 | 4.4.54 状态 |
|---|---|---|---|
| `MethodInfo` 结构体布局 | `src/il2cpp/types.rs` | `{klass@0x0, method_pointer@0x8, pad[0x20], flags}` — `methoddumper` 直接读 `(*method).method_pointer` | UNKNOWN（需运行时验证；2019 系 il2cpp 标准布局，LIKELY 不变） |
| VA 基址 `0x180000000` | `csdumper.rs` 输出 RVA→VA | 与当前 ImageBase 一致 | 4.4.54 ImageBase=0x180000000 ✓ |
| valuetype 字段偏移 `-0x10` 修正 | `csdumper.rs` write_fields | il2cpp 布局知识 | UNKNOWN |
| slot 索引（弱绑定） | `functions.rs` | il2cpp api 标准顺序 | 4.4.54 结构验证一致（见 il2cpp_api_table.md） |

## 3. 重要结论

1. **"只支持 3.7.0" 不成立**：honkai-dumper 的核心逻辑（B/C/D）是
   版本无关的；真正失效的只有 **A（table 位置 0x1EED6A8）**。
   4.4.54 的 table 已定位（UnityPlayer .rdata `0x1A36480`），
   把 A 替换为自动定位器后，B/C/D 应可直接复用。
2. **4.4.54 的新增障碍**（honkai-dumper 源码未覆盖）：
   - table 条目从"直接函数指针"变为"wrapper stub + descriptor +
     真实函数桩"三层结构 → 直接 `call table[63]` 会进入受守卫的
     wrapper（裸进程返回垃圾，游戏内可能正常）；
   - export/getter 有反 harness 守卫（见 il2cpp_api_table.md §1.1）。
3. **可移植改造方向**：
   - `Il2CppFunctions::new` 的 table 起点改用自动 locator
     （`find_il2cpp_api_table`；Task A 已完成：4.4.54 上唯一高置信收敛到
     UnityPlayer RVA `0x1A36480`，见 il2cpp_api_table.md §5）；
   - 若 wrapper 层在游戏内可正常调用（需要运行时验证），
     B/C/D 无需改动；
   - 若 wrapper 层需要额外初始化，则需在注入后等待游戏
     初始化完成再 dump（当前 base.rs 已 sleep 10s，也许足够）。

## 4. 对后续路径的影响

- 运行时路径（honkai-dumper 注入）的可行性取决于：
  游戏内 wrapper 是否可被直接调用（游戏启动后守卫已开，LIKELY 可）；
  以及注入本身的环境边界（需要用户决策）。
- 静态路径：table 结构已恢复（SUPPORTED），但 wrapper 内部
  逻辑仍被混淆，静态无法直接获得真实函数 RVA。
