# MHY global-metadata.dat 静态格式恢复 — 4.4.54（第一阶段）

> Session 目标：静态恢复当前 `global-metadata.dat` 的 MHY 自定义格式。
> 本阶段最小成功目标：至少恢复一个可验证的 metadata primitive。
> 结论：已恢复 **metadata usage table** 与 **12-byte type-info triple table**
> 两个可靠 primitive，并从 GameAssembly loader 恢复部分 top-level directory。
>
> final_status = **MHY_METADATA = PARTIAL_SCHEMA_RECOVERED**

## 0. 输入资产（全部重新实测）

| 项 | 值 |
|---|---|
| metadata 路径 | `D:\StarRail_4.4.53\StarRail_Data\il2cpp_data\Metadata\global-metadata.dat` |
| size | 100,182,380 (0x5F8A96C) |
| sha256 | `4bfdd6eaed092c1a70431cf32946903e41f716beeb1322291fa1ab1c6dbb33a7` |
| 头部 | `4D 48 59 00 00 00 00 00` = `MHY\0` + u32=0 |
| GameAssembly.dll | 535,482,160 bytes, sha256 `7b44379bf69352022cb3437b03431ddc558ffb34e3d98e7144200f37e8c837cc` |
| 跨版本对照 | 真实存在的 4.4.0 CN 客户端 metadata（94,803,092 B，sha256 `fbb353144351df2217123e53df60c7f38e242789b44240a36b3f2d9a62381dbd`） |

## 1. 文件级结论

### 1.1 文件头大小 = 0x208 [CONFIRMED]

- Loader 代码证据：`GameAssembly.dll` RVA `0x3C7E35E` 引用
  `global-metadata.dat` 字符串，调用文件加载 helper 后，
  RVA `0x3C7E389` 执行 `add rsi, 0x208`，然后把 `rsi` 存入 metadata
  payload 全局（RVA `0x9D387B0`）。
- 二进制证据：4.4.54 与 4.4.0 两个 metadata 文件的
  **longest common prefix == 0x208**；`0x208` 处才出现第一个差异字节。
- 因此：`0x000..0x207` 是 MHY 文件头/常量区，payload 从 `0x208` 开始。
  两个版本的 `0..0x207` 完全一致，说明该区域不含版本相关 count（否则
  4.4.0/4.4.54 不可能逐字节相同）。

### 1.2 文件不是“整体加密”

- whole-file entropy 7.44 bits/byte，但 4 KiB block entropy 从 0 到 7.99。
- 存在大量明文结构化区域，例如：
  - `0x386B8` 起的长 12-byte record 流（部分区间 `(a+=4,b+=1,c=0x47)`）；
  - `0x166CE90` 起单调递增 u32 数组；
  - `0xBE1B8C` 起 16-byte 结构化记录；
  - `0x4C4308C` 起的高位 tag 数组（本次恢复的 usage table）；
  - 尾部约 1.4 MiB 低熵 u32 数组（`0x5E20000..EOF`，371,291 个 u32，
    仅 208 个 distinct values）。
- 另一些区域（`0x208`、`0x15024`、`0x4C164`、`0xC37A88` 等）高熵。
  => 文件是 **mixed plaintext/transformed regions**，不能断言全文件加密。

## 2. GameAssembly 静态证据链

### 2.1 MHY magic xref

- `MHY\0` 在 GameAssembly 中唯一命中：file+`0x47B9158` = RVA `0x47BA958`
  （`.rdata`）。
- 初始化器 RVA `0x3A1D768` 用 `lea rax,[rip+...]` 把该地址写入全局
  `0x9D387A8`；紧邻的下一全局 `0x9D38360` 指向 `0x47BAB60`。
- `0x47BAB60 - 0x47BA958 = 0x208`：GameAssembly 内嵌了一个
  **0x208-byte MHY header-template block**，起始 magic 与文件头相同。
  该 block 是 per-build 的（内容与 metadata 文件头不同），loader 从中
  解码各 table offset/count。

### 2.2 Loader 对 template 字段的变换

Template block（RVA `0x47BA958`）字段以 `raw + const` 或 `raw ^ const`
方式解码。完整已恢复 directory 见 `decode_mhy_directory.py` 输出
`data/raw/4.4.54/il2cpp/mhy_directory_decode_4.4.54.json`。

## 3. 已恢复 primitive A：metadata usage table [CONFIRMED]

| 项 | 值 |
|---|---|
| template field | `+0x160` |
| decode rule | `signed32(u32(template+0x160) + 0xC769CD52)` |
| raw/decoded | raw `0x3D5A6132` → `0x04C42E84` |
| payload-relative offset | `0x4C42E84` |
| **file offset** | **`0x4C4308C`** |
| entry size | **4 bytes** |
| code reader | RVA `0x5720`（以及大量相同模式 accessor） |

Reader 逻辑（RVA `0x571F..0x579A`）：

```text
mov eax, [payload_global]              ; payload base (低 32 位，loader 保证 <4GB)
mov rdx, [template_global]             ; 0x47BA958
mov ebx, 0xC769CD52
add ebx, [rdx+0x160]                   ; 解码 offset
movsxd rbx, ebx
add rbx, rax                           ; table base = payload + offset
mov ecx, [rbx + index*4]               ; entry = u32
mov ebx, ecx
and ebx, 0x1FFFFFFF                    ; low 29 bits = index
and ecx, 0xE0000000                    ; high 3 bits = tag
cmp ecx, 0xC0000000                    ; tag == IL2CPP_TYPE 特殊分支
...
```

独立交叉验证：RVA `0x58DC` 处存在第二个同义 reader，解码规则相同。

对前 1,048,576 个 entry 的 tag 分布（`parse_mhy_metadata_primitives.py`）：

| high bits | count | 标准 IL2CPP 语义 | 证据 |
|---|---|---|---|
| `0x00000000` | 693,052 | invalid/zero | 数据分布 |
| `0x60000000` | 332,610 | StringLiteral | 标准枚举 + 样本连续 |
| `0xC0000000` | 20,105 | Il2CppType | **代码明确分支** |
| `0xE0000000` | 310 | TypeInfo | 标准枚举 [SUPPORTED] |
| `0x80000000` | 962 | FieldInfo | 标准枚举 [SUPPORTED] |
| `0x40000000` | 697 | MethodRef | 标准枚举 [SUPPORTED] |
| `0xA0000000` | 490 | MethodDef | 标准枚举 [SUPPORTED] |
| `0x20000000` | 350 | 其他/待分类 | 数据分布 |

样本（前 4 条）：`0x60000001`、`0x60001243`、`0x60000002`、
`0x60000003`。低 29 位索引范围 `0..0x1FFFFFFF`；`0x60001243` 等重复
索引符合“高频字符串被大量引用”的预期。

结论：这是一个可靠的 metadata table primitive —— 有 raw region、entry
structure、offset interpretation、代码读取逻辑、多 accessor cross-validation
与跨版本一致的 decode 路径（4.4.54 与 4.4.0 文件头共同前缀证据）。

## 4. 已恢复 primitive B：12-byte type-info triple table [CONFIRMED 结构 / SUPPORTED 语义]

| 项 | 值 |
|---|---|
| template field | `+0x38` |
| decode rule | `signed32(u32(template+0x38) + 0xF778F1AB)` |
| raw/decoded | raw `0x0A5B2CC9` → `0x01D41E74` |
| **file offset** | **`0x1D4207C`** |
| entry size | **12 bytes**（3 × u32） |
| code reader | RVA `0x5778` / `0x1EBB9` |

Reader 在 usage 值 tag == `0xC0000000` 时进入：

```text
lea r8, [rbx + rbx*2]                 ; index * 3
mov ecx, [table + r8*4]               ; field[0]
movsxd r8, [table + r8*4 + 4]         ; field[1]（-1 sentinel 分支）
movsxd rdx, [table + r8*4 + 8]        ; field[2]（-1 sentinel 分支）
...
```

文件 `0x1D4207C` 前 128 条样本验证：field1 == -1 的比率为 0.906，
field2 == 0 的比率为 0.258，field0 以小整数/递增索引为主。结构与代码
读取模式完全一致。语义上该表服务于 `0xC0000000` usage tag 的
Il2CppType 解析，具体三字段含义待进一步反编译。

## 5. Top-level directory（部分恢复）[PARTIAL / HYPOTHESIS]

`decode_mhy_directory.py` 从 template 解码出以下 file-offset 候选。
**只有带 reader 证据或明文结构验证的条目才可作为 table start 使用**，
其余仅为 candidate：

| file offset | template field | transform | 结构证据 | 状态 |
|---|---|---|---|---|
| `0x208` | `0x150` | `+0xD882615E` | 40-byte records；reader `0x3C7F193` | SUPPORTED |
| `0x4348` | `0x198` | `+0xB10C86E7` | 高熵 | HYPOTHESIS |
| `0x15024` | `0x118` | `+0xF6D615EF` | 高熵 | HYPOTHESIS |
| `0x386B8` | `0x54` | `+0xD43F4844` | 12-byte record 流（明文） | SUPPORTED |
| `0x4C164` | `0x20` | `+0xB2FCE189` | 高熵 | HYPOTHESIS |
| `0x4D4D4` | `0xD0` | `+0xDFCFC6B0` | 高熵 | HYPOTHESIS |
| `0x37EF94` | `0x78` | `^0x67325228` | 待验证 | HYPOTHESIS |
| `0x3B7444` | `0x158` | `+0xE03EEAC1` | 周期字节结构/高熵混合 | HYPOTHESIS |
| `0xBE1B8C` | `0x9C` | `+0xBC7EC9D7` | 16-byte 明文结构 | SUPPORTED |
| `0xC37A88` | `0xF0` | `+0x9D48920F` | 高熵 | HYPOTHESIS |
| `0xC51CA8` | `0x1D0` | `+0xC9A664A5` | 待验证 | HYPOTHESIS |
| `0x166CE90` | `0x3C` | `+0x978BE7A5` | 单调 u32 明文 | SUPPORTED |
| `0x17DBCDC` | `0x84` | `^0x68531D3F` | 待验证 | HYPOTHESIS |
| `0x1D4207C` | `0x38` | `+0xF778F1AB` | 12-byte triples（本 primitive） | CONFIRMED |
| `0x25E8A8C` | `0x184` | `+0x8709B6A3` | 待验证 | HYPOTHESIS |
| `0x27EF29C` | `0x1B4` | `+0x8D43A4EE` | 待验证 | HYPOTHESIS |
| `0x3725A4C` | `0x18` | `+0xE6CD8E6C` | 8-byte records；reader `0x3BFB762` | SUPPORTED |
| `0x3A1A77C` | `0x14C` | `+0xF3A04294` | 26-byte records；reader `0x3C66F80` | SUPPORTED |
| `0x4C4308C` | `0x160` | `+0xC769CD52` | usage table（本 primitive） | CONFIRMED |
| `0x5D3DA8C` | `0x180` | `+0xE4DBE763` | 近尾部 | HYPOTHESIS |

注意：template 中的 `0x54` 同时被当作 size/4 使用，因此不是所有解码值
都一定是 table start；每个 offset 使用前必须找独立 reader 验证。

## 6. 尚未恢复 / 明确不做

- **payload transform 未识别**：`0x208` 起始的多个区域高熵，但没有
  代码级 evidence 证明是 XOR / stream / compression；本阶段不猜 key。
- 未恢复 string table 语义、typeDefinition/methodDefinition identity。
- 未重新打开 Runtime DLL loader / remote execution 路线。
- 未全量 dump。

## 7. 工具与产物

- `tools/reverse/scripts/analyze_mhy_metadata.py` — 文件画像 JSON
- `tools/reverse/scripts/compare_mhy_metadata.py` — 跨版本结构比较
- `tools/reverse/scripts/analyze_mhy_tail.py` — 尾部 u32 数组画像
- `tools/reverse/scripts/analyze_structured_tables.py` — 明文结构流检测
- `tools/reverse/scripts/scan_metadata_anchors.py` — 二进制锚点扫描
- `tools/reverse/scripts/find_metadata_anchor_xrefs.py` — 静态 xref 扫描
- `tools/reverse/scripts/disasm_capstone.py` — Capstone 反汇编工具
  （需要 `tools/reverse/vendor/capstone`，本 session 本地安装，未入库）
- `tools/reverse/scripts/survey_template_field_uses.py` — template 字段使用扫描
- `tools/reverse/scripts/decode_mhy_header_template.py` — template 字段算术模拟
- `tools/reverse/scripts/decode_mhy_directory.py` — directory 解码
- `tools/reverse/scripts/parse_mhy_metadata_primitives.py` — primitive 验证

数据：

```text
data/raw/4.4.54/il2cpp/metadata_profile_4.4.54.json
data/raw/4.4.54/il2cpp/metadata_compare_4.4.54_vs_4.4.0.json
data/raw/4.4.54/il2cpp/metadata_tail_profile_4.4.54.json
data/raw/4.4.54/il2cpp/metadata_structured_tables_4.4.54.json
data/raw/4.4.54/il2cpp/metadata_anchor_scan_4.4.54.json
data/raw/4.4.54/il2cpp/metadata_anchor_xrefs_4.4.54.json
data/raw/4.4.54/il2cpp/metadata_loader_global_xrefs_4.4.54.json
data/raw/4.4.54/il2cpp/mhy_header_template_decode_4.4.54.json
data/raw/4.4.54/il2cpp/mhy_directory_decode_4.4.54.json
data/raw/4.4.54/il2cpp/mhy_metadata_primitives_4.4.54.json
data/raw/4.4.54/il2cpp/disasm_mhy_init_capstone.txt
data/raw/4.4.54/il2cpp/disasm_mhy_loader_capstone.txt
data/raw/4.4.54/il2cpp/disasm_*.txt                  # 各 reader/table 反汇编
data/raw/4.4.0/il2cpp/metadata_profile_4.4.0.json
data/raw/4.4.0/il2cpp/metadata_tail_profile_4.4.0.json
data/raw/4.4.0/il2cpp/metadata_structured_tables_4.4.0.json
```

## 8. 下一阶段（不在本 Session 自动扩大）

1. 为每个 directory candidate 找独立 reader，确认 entry size 与字段语义；
2. 从 loader 恢复各 table 的 count 字段（template `+0x04` 邻居等），
   建立 offset/count 不变量；
3. 对 `0x208` 起始的高熵 table 寻找 transform 的 code evidence；
4. 只有在 transform 被代码证明后才实现 decoder；
5. 恢复 TypeDefinitions 后停止扩大，输出 10~50 个类型的 Type Registry proof。
