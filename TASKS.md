# 总任务表

下面的任务按职责独立拆分。每个任务只要求产出自己的版本化结果，不要求一开始互相调用。详细说明见 `docs/tasks/`。

| 编号 | 独立任务 | 核心结果 | 主要目录 | 前置条件 |
|---:|---|---|---|---|
| T00 | 项目骨架与版本规则 | 可长期复用的目录、Manifest 与命名规范 | `docs/`、`schemas/`、`registry/` | 无 |
| T01 | 原始来源盘点与解包 | Source / Extracted Snapshot | `tools/unpacker/`、`data/sources/`、`data/extracted/` | T00 |
| T02 | 研究前端 | 可查看来源、解包任务、原始文件和版本信息 | `apps/research_ui/` | T01 的最小产物 |
| T03 | 游戏数据标准化与索引 | Normalized Snapshot、角色/技能/Ability 索引 | `src/.../game_data/`、`data/normalized/` | T01、T02 |
| T04 | 版本语义差分 | 新旧版本变化和影响报告 | `src/.../game_data/diff/`、`data/diffs/` | 两个 Normalized Snapshot |
| T05 | 运行时读取可行性 | Runtime Trace、可读取字段清单、置信度 | `tools/trace_capture/`、`src/.../runtime/` | T00；可与 T03 并行研究 |
| T06 | 单技能数值闭环 | 原配置到客户端真值的完整数值链 | `src/.../simulator/`、`data/traces/` | T03、T05 |
| T07 | 最小战斗沙箱 | 单角色/单敌人完整行动与状态变化 | `src/.../simulator/` | T06 |
| T08 | 完整战斗沙箱与发布 | 四人队、多敌人、波次、Buff、行动轴 | `src/.../simulator/`、`data/episodes/` | T07 |
| T09 | 策略规划器 | 合法动作、规则基线、Beam Search/MCTS | `src/.../planning/` | T08 |
| T10 | 模型实验室 | Policy、Value、数据集和模型版本 | `src/.../models/`、`data/datasets/`、`data/model_artifacts/` | T09 |
| T11 | 实时顾问前端 | 当前状态、推荐动作、置信度、重规划状态 | `apps/realtime_advisor/` | 可先用 Mock；正式接入依赖 T05/T09 |
| T12 | 实时集成与状态同步 | Reader → State → Planner/Model → Advisor | `src/.../contracts/`、`src/.../runtime/synchronization/` | T05、T08、T09、T11 |
| T13 | 跨版本更新与回归 | 更新计划、兼容矩阵、沙箱/模型失效判断 | `registry/`、`tests/cross_version/` | T04、T08、T10 |

## 统一完成标准

每项任务关闭前至少满足：

1. 有明确输入、输出和版本信息；
2. 产物写入对应 `data/` 目录并带 Manifest；
3. 不修改旧版本产物；
4. 对失败、未知格式、未支持机制有显式报告；
5. 至少存在一个可重复的验收样例；
6. 结论和限制写入该任务文档；
7. 不为了未来接口提前创建复杂服务或抽象。
