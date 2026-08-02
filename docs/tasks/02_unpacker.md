# T01 原始来源盘点与解包

## 目标

把客户端、私服资源或公开转储转换为可追溯、不可变的版本化快照。

## 代码位置

`tools/unpacker/`

## 数据位置

- 输入：`data/sources/<game_version>/<snapshot_hash>/`
- 输出：`data/extracted/<game_version>/<snapshot_hash>/unpacker-<version>/`

## 子任务

- 文件盘点、Hash 和版本识别；
- Source Snapshot Manifest；
- Extractor Registry；
- 完整来源和增量来源处理；
- 未知格式、失败文件和完整性报告；
- 解包器升级后重新提取，但不覆盖旧结果。

## 验收

同一 Source Snapshot 和同一解包器版本可重复得到相同内容 Hash；失败项可定位。
