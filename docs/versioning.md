# 版本与命名规则

## 需要同时管理的版本

1. `game_version_raw`：游戏原始版本字符串，例如 `OSBETAWin4.4.52`；
2. `source_snapshot_id`：某次原始来源内容快照；
3. `extractor_version`：解包器代码版本；
4. `normalized_schema_version`：标准化数据结构版本；
5. `simulator_engine_version`：沙箱引擎版本；
6. `ruleset_snapshot_id`：沙箱实际加载的规则数据；
7. `battle_state_schema_version`：策略输入状态结构版本；
8. `dataset_id`：训练数据集版本；
9. `model_version`：模型递增版本；
10. `runtime_reader_version`：客户端读取实现版本。

## 目录命名

避免把所有信息塞进一个超长目录名，使用层级表达：

```text
data/sources/<game_version_raw>/<snapshot_hash>/
data/extracted/<game_version_raw>/<snapshot_hash>/unpacker-<version>/
data/normalized/<game_version_raw>/<snapshot_hash>/schema-<version>/
data/model_artifacts/<model_name>/v0001/
```

完整父子关系、Git Commit、Hash 和兼容信息写入 `manifest.json`。

## 不可变原则

- 已完成的快照目录不可原地修改；
- 修复解包器后生成新的 Extracted Snapshot；
- Schema 变化后生成新的 Normalized Snapshot；
- 旧沙箱 Release、数据集和模型都保留；
- `registry/aliases.yaml` 只保存当前别名，不替代具体版本。

## 增量更新

可保存 delta 输入，但所有下游模块只读取物化后的完整快照。沙箱、前端和模型不直接解析补丁链。

## 推荐 Manifest 最小字段

```json
{
  "artifact_type": "normalized_snapshot",
  "artifact_id": "...",
  "created_at": "...",
  "status": "complete",
  "game_version_raw": "OSBETAWin4.4.52",
  "parents": [],
  "producer": "hsr-unpacker",
  "producer_version": "0.1.0",
  "producer_git_commit": "...",
  "schema_name": "normalized_game_data",
  "schema_version": "0.1.0",
  "content_hash": "sha256:...",
  "statistics": {},
  "warnings": []
}
```
