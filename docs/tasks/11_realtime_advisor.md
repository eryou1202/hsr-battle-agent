# T11/T12 实时顾问与集成

## 目标

把真实客户端状态、沙箱、规划器和模型连接成实时建议系统。

## 前端位置

`apps/realtime_advisor/`

## 稳定模块

- Runtime Reader；
- State Builder；
- State Synchronizer；
- Planner/Model Runtime；
- Advisor UI。

## UI 必须显示

- 当前角色、资源和读取置信度；
- 推荐动作、目标、备选方案；
- 预测行动轴和关键理由；
- 规划耗时；
- 缺失字段、同步偏差和重规划状态；
- 暂停与手工纠正入口。

## 验收

在决策窗口内给出建议；实际状态偏离预测后自动重建状态并重新规划；低置信度时不伪装成确定结果。
