# T07/T08 战斗沙箱

## 目标

先完成最小行动循环，再扩展成可供搜索和训练使用的完整沙箱。

## 代码位置

`src/hsr_battle_agent/simulator/`

## 最小阶段

- Entity、资源和属性；
- Formula VM；
- 单体目标；
- 伤害、能量、SP、削韧；
- 速度和行动值；
- 固定种子；
- Trace 输出。

## 完整阶段

- 四人队与多敌人；
- Buff/Modifier 生命周期；
- 治疗、护盾、击破；
- 多段、弹射、追加攻击；
- 终结技插队、额外回合；
- 波次和胜负；
- 客户端差分验证；
- Simulator Release Manifest。

## 验收

固定输入可重复；黄金样例通过；沙箱引擎版本与 Ruleset Snapshot 分离。
