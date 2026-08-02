# T13 跨版本更新与回归

## 目标

让游戏更新只增加快照、适配和迁移，不推翻项目骨架。

## 子任务

- 新版本 Source/Extracted/Normalized Snapshot；
- 语义差分和影响分类；
- Runtime Reader 回归；
- 沙箱 Ruleset 兼容测试；
- 新原语和新 Opcode 处理；
- 跨版本黄金测试；
- 数据集失效标记；
- 旧模型评估与 fresh/stale/incompatible 状态；
- 更新 Compatibility Registry 和 aliases。

## 验收

能够同时复现旧版本和新版本的完整依赖链，并明确当前推荐 Reader、Simulator 和 Model。
