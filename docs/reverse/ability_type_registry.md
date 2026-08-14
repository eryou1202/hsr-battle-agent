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

## 7. 4.4.54 目录重建结果（2026-08-04 实测）

> 工具：`tools/unpack/probe_ability_directory_adaptive.py`（自适应反解，
> 不依赖旧偏移）。数据：`data/raw/4.4.54/manifest/`。

### 7.1 新偏移表（取代 4.4.53 全部旧偏移）

| 项 | 4.4.53 | 4.4.54 | 说明 |
|---|---|---|---|
| 归档文件 | `5515caf6...` (125,590,141 B) | `8625dd99...` (125,829,538 B) | 已替换 |
| payload base | `0xB0CC68` | **`0xAF6D1C`** | 自适应反解（15/15 名字投票） |
| 目录块 | `0xB147F8..0xB14A38` | **`0xAFE8AC..0xAFEACC`** | 15 条连续 |
| 记录起点 | base + zigzag(decoded) | 同左（不变） | 格式稳定 |

### 7.2 跨版本格式稳定性（新证据，E2→E3）

- [CONFIRMED]（E2，跨版本）：目录编码、记录前缀、ZigZag 偏移规则在
  4.4.53 → 4.4.54 完全一致（格式 F1-F4 全部复现）。
- [CONFIRMED]（E2）：15 条黑天鹅记录全部重新定位并提取
  （`data/raw/4.4.54/manifest/config_record_probes/black_swan_records/`）。
- [CONFIRMED]（E2）：14/15 条记录长度与 4.4.53 完全一致
  （697/980/531/1918/340/797/460/2275/345/1758/2336/582/5424/754）。
- [CONFIRMED]（E2）：内容对比——**6 条逐字节相同**；
  **8 条仅 1-2 个单字节差异**（如 Skill01_Phase02 在 0x2A、0xEA 各差 1 字节，
  疑似校验/版本字节）；**无任何结构或数值段变化**。
  → 4.4.54 对黑天鹅是纯热修版本，配置语义未变。

### 7.3 对注册表的影响

- type_id 2/8/14/16 的语义结论维持 UNKNOWN（未新增运行时证据）。
- 4.4.54 的 15 条记录已可作为后续 mixin 前缀分析的新输入
  （复用 `inspect_type2_mixin_prefix.py` 的逻辑）。
- 下一步 Task C 的 class 检索仍依赖 metadata 解密（见
  `il2cpp_toolchain_4.4.53.md` 第 6 节）。

## 8. type_id ↔ runtime_class 候选映射初表（2026-08-04）

> 目标 3 产物。所有 runtime_class 均为 **UNKNOWN**；语义列为
> **假设（E0/E1），未经运行时/反编译证实（NOT PROVEN）**。
> 结构事实来自 4.4.53 + 4.4.54 双版本复现（E2）。

### 8.1 类型分布（跨版本稳定，E2）

| type_id | 记录数 | 记录（黑天鹅样本） | 记录类型特征 |
|---|---|---|---|
| 2 | 7 | PassiveSkill01, SkillMazeInLevel, SkillTree02/03, Rank01/02/06 | 被动/星魂/行迹类 |
| 8 | 3 | Skill03_Phase01/02, SkillMazeInLevel_Insert | 终结技阶段/插入技能 |
| 14 | 1 | Skill03_Cutin | 演出/Cutin |
| 16 | 4 | Skill01_Phase01/02, Skill02_Phase01/02 | 普攻/战技阶段 |

4.4.53 与 4.4.54 的 first_mixin_type 分布完全一致（2×7, 16×4, 8×3, 14×1），
同一记录映射同一类型（E2，跨版本稳定）。

### 8.2 候选映射（全部 NOT PROVEN）

| type_id | 结构事实（E2） | 字符串签名（E1） | 语义假设 | confidence |
|---|---|---|---|---|
| 2 | 前缀: flags(2/8) + opcode 0x31 + 0x0A + selector `Caster` + 引用名（见 §7 工具输出） | 引用名全部是 **Modifier 配置名**（`M_BlackSwan_P01_ListenAddPoison`、`MAvatar_BlackSwan_00_DOT`、`M_BlackSwan_00_SkillTree02`…）；出现 `WithBattleEvent`/`RemoveBattleEvent` 后缀 | "按名引用/附加 Modifier 或监听 BattleEvent 的 mixin" | E1，NOT PROVEN |
| 8 | 无 type2 式前缀 | `AllEnemy`、`AllDarkTeam`、`DarkTeamCenter`、`MDF_Count`、`MDF_ResistanceDown`、`MAvatar_BlackSwan_00_DOT_Enhance`、`_can_continue`/`_current_chance`/`_loop_count`、`TeamFormation` | "多目标/群体效果或状态机类 mixin" | E1，NOT PROVEN |
| 14 | 单记录（Cutin） | `CasterWithAllEnemy`、`AllDarkTeam`、`Blend_UltraReady` | "演出/动画控制类 mixin" | E0-E1，NOT PROVEN |
| 16 | 位于技能阶段开头 | `Basic_DamagePercentage`、`ExtraLayer_DamagePercentage`、`Spread_DamagePercentage`、`DefenceIgnore`、`AddDot`、`Rank06_Weighted_Stack_Layer`、`Cast_By_Level` | "伤害/技能主体类 mixin（含 DealDamage 语义候选）" | E1，NOT PROVEN |

### 8.3 DSL 原语名锚点（E1，供未来 class dump xref）

从 4.4.54 记录字符串签名提取的候选原语名（这些名字将来应能在
`ConfigAbility*` 类或配置字段中找到对应）：

```text
# 目标选择器（TargetSelector 候选）
Caster  AbilityTargetEntity  AbilityTargetAdjoinEntity
ModifierOwnerEntity  ModifierOwnerAdjoinEntity  ParamEntity  ParamEntityList
ParamEntityAdjoinEntity  AllEnemy  AllEnemyWithUnSelectable
AllDarkTeam  DarkTeamCenter  AllTeammateWithUnselectable
AllTeamMemberWithUnselectable  CurrentTurnOwnerEntity
SnapshotEntityActualOwner  LevelEntity  AvatarBuffSelf

# 动态值（DynamicValue 候选）
Basic_DamagePercentage  ExtraLayer_DamagePercentage  Spread_DamagePercentage
Cast_By_Level  DefenceIgnore  MDF_PropertyValue  MDF_Count  MDF_MaxLayer
MDF_PropertyRatio  MDF_ResistanceDown  Dot_Layer_Count  Max_DOT_Layer
Rank06_Extra_Layer  Rank06_Chance  Rank06_Weighted_Stack_Layer
_count  _loop_count  _current_chance  _enhance_count  _maxLimit  _drawnCard  _can_continue

# 动作/事件（Action/Event 候选）
DealDamageBlackSwan  AddDot  WithBattleEvent  RemoveBattleEvent
MazeSkill_Triggered  TeamFormation
```

这些名字本身只证明"字符串存在"（E1）；语义归属必须靠运行时类型系统。

### 8.4 下一验证优先级

1. metadata 解密后，用 §8.3 锚点检索 `ConfigAbilityMixin` 继承树
   （首选 `DealDamageBlackSwan`、`AllEnemyWithUnSelectable` 这类独特名字）；
2. 第一个目标建议 **type 16**（普攻/战技阶段，锚点最丰富，
   且 Skill01/02 是后续里程碑 3 的验证对象）。
