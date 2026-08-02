# 项目结构

```text
hsr-battle-agent/
├── apps/
│   ├── research_ui/
│   └── realtime_advisor/
├── src/hsr_battle_agent/
│   ├── game_data/
│   ├── runtime/
│   ├── simulator/
│   ├── planning/
│   ├── models/
│   └── contracts/
├── tools/
│   ├── unpacker/
│   ├── trace_capture/
│   ├── data_inspector/
│   └── migration/
├── data/
│   ├── sources/
│   ├── extracted/
│   ├── normalized/
│   ├── diffs/
│   ├── traces/
│   ├── scenarios/
│   ├── episodes/
│   ├── datasets/
│   └── model_artifacts/
├── schemas/
├── registry/
├── configs/
├── scripts/
├── docs/
│   └── tasks/
└── tests/
```

## 结构含义

- 代码按职责组织，不按任务执行顺序编号；
- 任务顺序写在 `docs/roadmap.md`；
- 解包代码固定放在 `tools/unpacker/`；
- 解包结果、标准化结果和版本差分分层保存；
- 研究前端与最终实时顾问前端分开；
- 正式接口只有在真实数据和联动需求稳定后才进入 `contracts/`；
- 游戏更新通过新快照、差分、迁移和兼容记录处理，不覆盖旧产物。
