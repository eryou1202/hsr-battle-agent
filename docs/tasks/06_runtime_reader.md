# T05 运行时读取可行性

## 目标

尽早确认最终实时策略工具能否稳定获得必要状态。

## 代码位置

- 原型采集：`tools/trace_capture/`
- 稳定实现：`src/hsr_battle_agent/runtime/`

## 首批观察字段

- 决策窗口；
- 当前行动角色；
- 战技点；
- 终结技能量状态；
- 敌人 HP 或韧性；
- 实际技能或目标；
- 时间戳、来源和字段置信度。

## 输出

`data/traces/<game_version>/<reader_version>/<session_id>/`

## 验收

连续战斗中产生可重放的 Runtime Trace，并明确哪些字段可读、推断或缺失。
