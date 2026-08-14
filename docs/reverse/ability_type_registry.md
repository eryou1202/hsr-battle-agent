# Ability / Mixin Type Registry（初版）

> P0 产物：Battle DSL 类型注册表（起点）。
> registry_version: 0.1
> game_version: 4.4.53（既有探测产物）/ 4.4.54（当前磁盘资产，偏移待重建）
> 状态：0 个类型达到 supported（全部 UNKNOWN / E1-E2 级证据）

## 1. 注册表条目格式

每个类型按以下结构记录（未发现证据的字段留空或 null）：

```json
{
  "category": "AbilityMixin",
  "type_id": 2,
  "runtime_class": "UNKNOWN",
  "serialized_name": null,
  "base_class": null,
  "field_layout": [],
  "field_meanings": {},
  "execute_rva": null,
  "related_methods": [],
  "evidence": [],
  "confidence": "unknown",
  "game_version": "4.4.53"
}
```

证据等级：E0 猜测 / E1 字符串推测 / E2 多样本结构一致 /
E3 runtime class / metadata 支持 / E4 反编译逻辑 / E5 运行时验证。

## 2. 已确认的二进制格式事实（与类型语义无关，但先固化）

### F1: Ability 名称编码
- [CONFIRMED]（E2，15/15 样本）：Ability 名称为
  **ULEB128 长度前缀 + UTF-8 字节**。
- 复现：`python tools/unpack/inspect_ability_headers.py`
  （对 4.4.53 的 `5515caf6...` 输出 15/15 正确）。
- 版本：4.4.53（当前磁盘为 4.4.54 新归档，需重跑）。

### F2: Ability payload 目录编码（ZigZag）
- [CONFIRMED]（E2）：目录位于 payload 区（4.4.53 样本 `0xB147F8`），
  目录值采用 ZigZag 编码；正偶数样本 `decoded_offset = encoded_value / 2`；
  记录起点 `record_start = 0xB0CC68 + decoded_offset`。
- 复现：`tools/unpack/probe_ability_directory.py`。
- 版本：4.4.53。

### F3: 目录是"入口表"而非"独占边界表"
- [CONFIRMED]（E2）：`Skill03_Cutin` 记录中的字符串 `CasterWithAllEnemy`
  跨越"下一记录起点"边界 → 目录 entry 是对象起点索引，
  **不能**把相邻 entry 差值当作对象结束边界。
- 解析时必须自带 lookahead / 直接读原始字节。

### F4: 记录前缀结构
- [CONFIRMED]（E2）：稳定解析出的前缀字段顺序：
  `outer tag / wrapper` → `ability bit field` → `ability name`
  → `mixin count` → `first mixin type` → `mixin body offset`。
- 数据：`data/raw/4.4.53/manifest/black_swan_ability_headers.csv/json`。

## 3. Mixin Type ID 现状（严禁猜测语义）

| type_id | 观测位置 | 证据 | runtime_class | 语义 | confidence |
|---|---|---|---|---|---|
| 2 | 黑天鹅 ability 样本 | E2（结构一致，见 `black_swan_type2_mixin_prefixes.csv/json`） | UNKNOWN | UNKNOWN | unknown |
| 8 | 黑天鹅 ability 样本 | E2 | UNKNOWN | UNKNOWN | unknown |
| 14 | 黑天鹅 ability 样本 | E2 | UNKNOWN | UNKNOWN | unknown |
| 16 | 黑天鹅 ability 样本 | E2 | UNKNOWN | UNKNOWN | unknown |

**禁止**仅凭"旁边出现 Modifier 字符串"就给 Type 2 起名 `AddModifier`。
至少需要 E3（runtime class / metadata）或 E4（反编译）证据。

## 4. 字符串锚点（E1 级，xref 用）

来自 4.4.53 DesignData 黑天鹅样本（`black_swan_named_strings.csv` /
`persistent_design_*_keywords.csv`），作为后续 IL2CPP dump 的检索起点：

```text
MAvatar_BlackSwan_00_DOT            MAvatar_BlackSwan_00_DOT_Enhance
MAvatar_BlackSwan_00_DefenceDown    DealDamageBlackSwan
AbilityTargetEntity                 ModifierOwnerEntity
ParamEntity                         Caster
MDF_PropertyValue                   MDF_Count
MDF_ResistanceDown                  Basic_DamagePercentage
ExtraLayer_DamagePercentage         Spread_DamagePercentage
DefenceIgnore                       Dot_Layer_Count
```

这些名字本身只证明"字符串存在"（E1）；语义归属必须靠运行时类型系统。

## 5. Coverage 统计（初始）

| 类别 | supported | 已知 id | 说明 |
|---|---|---|---|
| AbilityMixin | 0 | 2, 8, 14, 16（UNKNOWN） | 仅头部结构 |
| AbilityAction | 0 | — | 未开始 |
| Predicate | 0 | — | 未开始 |
| TargetSelector | 0 | — | 未开始 |
| Modifier | 0 | — | 未开始 |
| DynamicValue | 0 | — | 未开始 |

supported 定义：parser + IR + runtime + 测试全部通过（仅能解析名字不算）。

## 6. 下一步（Task C 前置）

1. 在 4.4.54 新归档 `8625dd99...` 上重跑目录探测，
   重建偏移表（复用 `tools/unpack/` 现有脚本，仅更换输入文件）。
2. 完成 Task B（IL2CPP dump）后，用类型清单检索
   `ConfigAbilityMixin` 继承树，建立 type_id ↔ runtime_class 候选表。
3. 第一个验证目标建议选证据最多的 type（当前候选 2），
   达到 E4 后写完整证据链（binary id → class → fields → execute → called systems）。
