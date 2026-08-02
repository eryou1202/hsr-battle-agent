# T10 模型实验室

## 目标

让模型加速搜索和估值，而不是绕过沙箱直接控制游戏。

## 代码位置

`src/hsr_battle_agent/models/`

## 子任务

- 数据集 Manifest；
- BattleState/Action 编码；
- Policy 行为克隆；
- Value 估值；
- Action Mask；
- Policy/Value 引导搜索；
- 模型评估、别名和兼容状态；
- 沙箱修复或 Schema 变化后的失效判断。

## 验收

每个模型可追溯到数据集、沙箱 Release、特征 Schema、训练代码 Commit、随机种子和评估报告。
