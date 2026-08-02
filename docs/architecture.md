# 架构说明

## 职责分层

```text
外部来源
  └─ tools/unpacker、tools/trace_capture
        ↓
版本化数据产物
  └─ data/sources、extracted、normalized、traces
        ↓
正式业务模块
  ├─ game_data
  ├─ runtime
  ├─ simulator
  ├─ planning
  └─ models
        ↓
前端
  ├─ research_ui
  └─ realtime_advisor
```

## 当前不建立的内容

- 不提前拆微服务；
- 不提前搭后端 API；
- 不提前固定 BattleState 全字段；
- 不让沙箱直接依赖某一种解包器；
- 不让模型直接依赖沙箱内部对象；
- 不在目录名中表示任务顺序。

## 后续联动原则

只有当两个模块都已产生稳定样本时，才在 `src/hsr_battle_agent/contracts/` 接受公共数据结构。接受前先放在对应任务文档或 `schemas/` 草案中验证。
