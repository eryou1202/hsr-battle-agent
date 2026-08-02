# T03 游戏数据标准化与索引

## 目标

将不同来源的解包结果转换成沙箱和研究工具可稳定读取的数据快照。

## 代码位置

`src/hsr_battle_agent/game_data/`

## 输出位置

`data/normalized/<game_version>/<snapshot_hash>/schema-<version>/`

## 子任务

- 原始格式 Loader；
- 角色、技能、Ability、Modifier、怪物、AI Normalizer；
- 引用图和断链报告；
- 按 ID/名称查询索引；
- Schema 版本和迁移策略；
- 标准化统计和未知节点清单。

## 验收

输入一个首批角色 ID，可追踪到技能参数、Ability 和关联 Modifier，并保留原始来源定位。
