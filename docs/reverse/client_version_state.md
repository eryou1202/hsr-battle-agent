# 客户端版本状态调查（2026-08-03 快照）

> game_version: 目录标签 `4.4.53`，实际二进制 **4.4.54（BetaLive）**
> 调查日期: 2026-08-03（本次会话）
> 状态: [CONFIRMED]

## 结论摘要

`D:\StarRail_4.4.53` 目录中的客户端**已经不是纯净的 4.4.53**：
4.4.53 → 4.4.54 的升级流程已经在 2026-08-03 夜间执行过，
**二进制与设计数据都已替换为 4.4.54 版本**，目录名 `4.4.53` 只是遗留标签。

## 证据链

### E5：客户端自报版本

`StarRail_Data\StreamingAssets\BinaryVersion.bytes`（245 B）明文包含版本串：

```
20260731-0529-BetaLive-15953205-OSBETAWin4.4.54-OSCb
```

即：构建日期 2026-07-31、分支 BetaLive、补丁号 15953205、
渠道 OSBETAWin、**版本 4.4.54**。

（`ClientConfig.bytes` 佐证这是 OverSea CBT 构建：`com.HoYoverse.hkrpgoverseacbtest`。）

### E5：hdiffmap 目标哈希 = 磁盘哈希/大小

`D:\StarRail_4.4.53\hdiffmap.json` 是 4.4.53→4.4.54 的差分清单，
其 `target_file_size` 与磁盘当前文件完全一致：

| 文件 | hdiffmap target size | 磁盘实际 size | 一致 |
|---|---|---|---|
| GameAssembly.dll | 535,482,160 | 535,482,160 | ✓ |
| global-metadata.dat | 100,182,380 | 100,182,380 | ✓ |
| data.unity3d | 23,195,060 | 23,195,060 | ✓ |
| UnityPlayer.dll | 38,753,584 | 38,753,584 | ✓ |

（旧 `data/raw/4.4.53/manifest/core_files.csv` 记录的 4.4.53 快照：
GameAssembly.dll = 536,318,768、global-metadata.dat = 100,357,100，
与 hdiffmap 的 `source_file_size` 完全一致。）

### E5：升级流程残留物

- `StarRail_4.4.53_4.4.54_hdiff.7z`（2.0 GB，2026-08-03 22:57 下载）
- `hdiffmap.json`、`deletefiles.txt`（2026-08-03 10:37）
- 二进制文件时间戳集中在 2026-08-03 23:09–23:11（补丁应用时刻）

### E5：4.4.53 关键配置归档已被替换

| 项 | 旧（4.4.53） | 新（当前磁盘） |
|---|---|---|
| 文件 | `5515caf6ca5446d524d17c5c9da6c3c2.bytes` | `8625dd99e13b0dfe6b45f47f9bfe3e36.bytes` |
| 大小 | 125,590,141 | 125,829,538 |
| 位置 | Persistent\DesignData\Windows | 同左 |
| 状态 | **已不存在**（全盘搜索无结果） | 存在 |

新归档 `8625dd99...` 中仍能找到黑天鹅配置：
`MAvatar_BlackSwan_00` ×57、`DealDamageBlackSwan` ×50、`AbilityTargetEntity` ×50
（另 7 处在 `c2774a75...`），
见 `data/raw/4.4.53/manifest/persistent_design_blackswan_scan_20260803.csv`。
即：**配置数据内容类别未变，只是归档文件与内部偏移全部更新**。

## 对项目的影响

1. **旧偏移全部失效**：`0xB0CC68`（payload 起点）、`0xB147F8`（目录）等
   是 4.4.53 专有偏移，不能用于当前 `8625dd99...` 文件。
   需要在新文件上重新执行目录探测（复用 `tools/unpack/probe_ability_directory.py`
   与 `inspect_ability_headers.py` 的解析逻辑，输入文件换掉即可）。
2. **既有研究产物仍然有效，但属于 4.4.53 版本**：
   - `data/raw/4.4.53/manifest/config_record_probes/`（黑天鹅 15 条记录 .bin）
   - `black_swan_ability_headers.csv/json`、`black_swan_type2_mixin_prefixes.*`、
     `black_swan_named_strings.csv` 等
   这些是格式研究的有效素材；数值/偏移必须标注 `game_version=4.4.53`。
3. **RVA 与 metadata 快照已变**：4.4.54 的 GameAssembly.dll /
   global-metadata.dat 需要重新 dump，旧 RVA 全部作废。
4. **仓库旧快照过时**：`data/raw/4.4.53/manifest/` 下 07-28 之前生成的
   `design_data_hashes.csv`、`core_files.csv` 等对应升级前文件集合。

## 建议下一步

1. 将当前客户端正式登记为新版本快照（建议目录 `data/raw/4.4.54/`，
   或 `data/raw/4.4.53+4.4.54-patch/` 并在命名上明确区分），
   避免"4.4.53"名义下新旧数据混用。
2. 决定是否保留一份纯净 4.4.53 副本用于版本 diff：
   注意 `StarRail_4.4.53_4.4.54_hdiff.7z` 内是 **hdiff 补丁**而非完整旧版本，
   无法直接作为 4.4.53 原始数据使用；如需旧版本，要从备份或重新下载获取。
3. 新 DesignData 上重跑黑天鹅目录探测，重建 4.4.54 偏移表（Task A 后续）。
4. 对新 GameAssembly.dll / global-metadata.dat 执行 IL2CPP dump（Task B）。
