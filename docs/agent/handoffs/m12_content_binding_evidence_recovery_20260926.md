# M12 content-binding evidence recovery — CR-M12-EVIDENCE-RECOVERY-20260926-001

Mechanical discovery and reconciliation only. No runtime code, no semantic
inference, no M10/M11 change, no existing M12 record change, no Git write.

- **Starting HEAD:** `47c8b495a26adc4336a4e085ce0422ce983a4a7d`
- **Branch:** `terra/implementation`
- **Machine-readable output:** `data/content_binding/4.4.54/content_binding_evidence_recovery_001.json`
- **Reentry recommendation:** `MULTIPLE_NEW_EVIDENCE_ITEMS_REQUIRE_SOL_REVIEW`

This change request does **not** assert that M12 is unblocked. Only Sol may make
that determination.

## 1. Primary question A — exact SkillID → behavior relation

**Answer: NONE FOUND.**

| Test | Scale | Result |
| --- | --- | --- |
| JSON objects containing **both** a skill-id key and an ability-name key | 2,405 files / 1,897,439 objects | **0** |
| JSON objects containing a skill-id key and a `Name: "Skill<label>"` | same | **0** |
| Nanoka 4.4.54 `skills.payload_json` ability/behavior fields | 664 rows | **none** (keys are `id, name, desc, simple_desc, type, type_name, tag, sp_base, bp_need, bp_add, show_stance_list, level, extra, skill_combo_value_delta, owner_avatar_id`) |
| Authoritative mapping artifact | `full_content_behavior_mapping_001.json` family `Skill` | `static_entities_unmapped: 664 / 664`, `behavior_records_direct_id_link: 0`, `behavior_records_exact_config_id_link: 0` |

The mapping artifact's own counting rule already refuses this class:
*"SOURCE_PATH_ONLY and parent-only names do not count as static links."*

### What exact relations *do* exist (all same-object, all literal)

| # | Left | Right | Objects | Binds behavior? |
| --- | --- | --- | --- | --- |
| R1 | `AvatarSkillConfig.SkillID` | `AvatarSkillConfig.SkillTriggerKey` (`Skill<label>`) | 9,551 (6,702 Avatar / 2,839 MonsterSkill / 9 D5) | no |
| R2 | `AvatarConfig.AvatarID` | `AvatarConfig.JsonPath` (CharacterConfig path) | 91 | no |
| R3 | `AvatarConfig.AvatarID` | `AvatarConfig.SkillList[]` (numeric SkillIDs) | 91 | no |
| R4 | `CharacterConfig.SkillList[].Name` (`Skill<label>`) | `.EntryAbility` / `.PrepareAbility` | 848 in 142 files | yes (no numeric id) |
| R5 | `CharacterConfig.SkillAbilityList[].Skill` | `.AbilityList[]` | present, mirrored with provenance in `astra_equipment_trace_eidolon_targeted_evidence_v1.json` | yes (no numeric id) |

### The single missing edge

`AvatarSkillConfig.SkillTriggerKey  ==  Avatar CharacterConfig.SkillList[].Name`

- For **monsters** this equality is *declared*: `monster_ai_sequence_id_binding_001.json :: binding_rule` — *"serialized SkillTriggerKey exactly equals CharacterConfig.SkillList.Name."*
- For **avatars** it is declared **nowhere**. Supplying it is an authorisation decision, not a mechanical discovery, so every candidate remains **NON_EXACT**.

The avatar `CharacterConfig` files contain **no numeric SkillID** and **no `SkillTriggerKey` field** (verified by literal search for 110501/110502/110503 and 130701/130702 — all absent).

## 2. Primary question B — Natasha provenance/hash mismatch

**Classification: `DIFFERENT_SERIALIZATION` (CRLF vs LF). Mechanically proven.**

| Fact | Value |
| --- | --- |
| Declaring artifact | `data/semantics/4.4.54/real_skill_heal_boundary_30.json` → `content.artifact_sha256` |
| Declared hash | `c135173b1d6b1365aa515f48749192ff5f7798f09a81c804ed6e9c4a79a92b10` |
| Named file | `data/raw/4.4.54/natasha_skill02_healhp_content_30.json` |
| Current raw SHA-256 | `4dcca0baa2474373b20f785d47b853087971d99ae52617e030fe0931d81f5596` |
| Current bytes / CRLF / bare LF | 9,156 / 270 / 0 |
| SHA-256 after CRLF→LF normalisation | `c135173b…` — **equals the declaration exactly** |
| Declared hash matches any repo file | **NO** (6,693 files hashed) |
| Git blob sha1 @ `4d27854` vs @ HEAD | `b237ac44…` == `b237ac44…` |
| `git status` for the path | clean |
| `core.autocrlf` / `.gitattributes` | `true` / present |

The JSON content has **never changed** since it was committed in `4d27854`
(2026-08-24 14:29:59). The declaration was added 12 minutes later in `dd1a62c`.
The two digests are the same document in two newline encodings.

**Why the ledger flagged a mismatch:** the M12 ledger hashed the CRLF
working-tree bytes for this file, while its recorded hashes for the sibling
artifacts match those files' *raw* bytes — e.g. `ability_file_container_natasha_30.json`
(raw `6d173573…` recorded; its LF-normalised form would be `96ba13df…`). The
ledger therefore mixed normalisation conventions between files, which produced a
false `PROVENANCE_DIGEST_MISMATCH`.

**No repair was attempted.** The declaration was not rewritten and no file was
modified. Note this removes the digest blocker *only*; `SOURCE_VERSION_UNVERIFIED`
remains, because the source archive path still carries a 4.4.53 label.

## 3. Primary question C — exact occurrences

SkillID exact-token hit counts: `110501` 43 files, `110502` 41, `110503` 38,
`130701` 22, `130702` 21. Files that contain **both** a target SkillID and its
audited behavior string:

| Pair | Files | Which |
| --- | --- | --- |
| 110502 ↔ `Avatar_Natasha_00_Skill02_Phase02` | 5 | the M12 ledger itself + 4 `dynamic_core` / `dynamic_mvp` packets |
| 110501 ↔ `…Skill01_Phase02` | 1 | the M12 ledger only |
| 110503 ↔ `…Skill03_EnterReady` | 1 | the M12 ledger only |
| 130701 / 130702 ↔ `…BlackSwan…` | 2 each | the M12 ledger + `astra_equipment_trace_eidolon_targeted_evidence_v1.json` |

In every non-ledger case the co-occurrence is **not a structured join**:

- `dynamic_core/packets_v1.json` packet `DYN-HEAL-STATE-01` — the SkillID appears only inside a prose string: *"Nanoka 4.4.54 Skill 110502 level parameters are a static amount reference only"*; the behavior name appears in the `scope` prose.
- `dynamic_mvp_v1/blocker_closure_packets_v1.json` packet `DYN-MVP-HEAL-001` — behavior name in prose; no SkillID in the enclosing object.
- `astra_equipment_trace_eidolon_targeted_evidence_v1.json` — the enclosing object is `{"Skill": "Skill01", "AbilityList": [...]}`: a **label**, not a SkillID; the numeric id lives elsewhere in the same 15 MB file.

## 4. Primary question D — REF02 field matrix

Applied rule: `SAFE_TO_USE = YES` only when an exact artifact supplies the field
under the same candidate binding. Every field except `source_id` needs
`BEHAVIOR_BOUND`, which is established for no candidate.

| Field | Exact content value? | Source | Value (candidate 1 — 110502) | Safe to use |
| --- | --- | --- | --- | --- |
| `kind` | PARTIAL | Nanoka row / AvatarSkillConfig | `type=BPSkill, tag=Restore, SkillEffect=Restore` | **NO** — no artifact maps these onto REF02 `kind` |
| `source_id` | YES | `skills.entity_id` | `110502` | **YES** — exact static identity under `STATIC_ID_BOUND` |
| `targets` | NO under binding | `CharacterConfig.SkillList[1].TargetInfo.TargetType` | `FriendSelect` — keyed by the **label**, not the SkillID | **NO** |
| `base_value` | YES | `level.1.param_list` | `[0.07, 0.048, 2, 70, 48]` | **NO** — no param-index → field mapping exists |
| `ordered factors` | YES | same list, order preserved | `[0.07, 0.048, 2, 70, 48]` | **NO** — no factor meaning/ordering contract |
| `resource_cost` | PARTIAL | `sp_base` / `SPBase` / `BPNeed` | `sp_base=30, bp_need=1` | **NO** — no artifact picks the cost field |
| `resource_owner` | NO | — | — | **NO** |
| `toughness_delta` | PARTIAL | `show_stance_list` | `[0, 0, 0]` | **NO** — no reduction contract |
| `survival_closed` | NO | — | — | **NO** |
| `events_closed` | NO (reverse artifact only) | `real_skill_heal_boundary_30.json` | `DispelStatus` then `HealHP` | **NO** — 4.4.53-labelled reverse evidence; the artifact itself records the positive HealData consumer as unresolved |

**REF02 field-closure candidates: 0.** Static parameters were **not** mapped onto
packet fields anywhere, because no artifact establishes that mapping.

## 5. Repository-wide counts (664 static skills)

| Class | Count |
| --- | --- |
| `STATIC_ONLY` | **664** |
| `EXACT_BEHAVIOR_JOIN_FOUND` | **0** |
| `EXACT_BEHAVIOR_JOIN_FOUND_BUT_VERSION_WEAK` | **0** |
| `REF02_FIELD_CANDIDATE` | **0** |

### Discovery-only counters — NOT joins, NOT coverage

| Counter | Value |
| --- | --- |
| AvatarConfig skill-list entries examined (91 avatars) | 620 |
| … whose `SkillTriggerKey` exactly equals a CharacterConfig `SkillList[].Name` | **528** |
| … whose `SkillTriggerKey` is empty | 92 |
| Same-index positions contradicted by the label route | **175** |

The same-index hypothesis (`AvatarConfig.SkillList[i] ↔ CharacterConfig.SkillList[i]`)
is **mechanically contradicted** — e.g. avatar 1105 index 5, and avatar 1109
index 3, and 173 further positions. These counters quantify an opportunity; they
must never be added to a Golden or coverage denominator.

## 6. New evidence found (none of it a promoted join)

1. **NE-1** — The declared digest mismatch is resolved as `DIFFERENT_SERIALIZATION`. Removes `PROVENANCE_DIGEST_MISMATCH` for that artifact; `SOURCE_VERSION_UNVERIFIED` remains.
2. **NE-2** — The same-index SkillList shortcut is disproven in 175 positions; the label route is consistent in 528 of 620 entries. Evidence, not a declared relation.
3. **NE-3** — For **all five** audited candidates the ledger's `behavior_candidate` differs from the owner CharacterConfig's explicit `EntryAbility` for the corresponding label; for 110503 the candidate matches `PrepareAbility` instead of `EntryAbility`. Nothing here decides correctness; it does mean the audited candidate column is not corroborated by the most explicit available content field.
4. **NE-4** — The missing edge already exists in *declared* form for the monster family and is undeclared for avatars. This names the decision precisely.

## 7. Version discipline

Reported as **both** facts wherever they differ; nothing was upgraded.

- `EXACT_4_4_54` — `data/db/hsr_content_4.4.54.sqlite` (skills provenance `source_version = 4.4.54`), `data/content/4.4.54/nanoka/*` (fetch log records version 4.4.54, 1,055 records, 20 errors).
- `4_4_53_PATH_LABEL` — `natasha_skill02_healhp_content_30.json`, `ability_file_container_natasha_30.json`, `ability_file_container_black_swan_validation_30.json`, `data/raw/4.4.53/manifest/*`. All declare `game_version 4.4.54` while their `source.archive` path sits under `D:\StarRail_4.4.53\`.
- `CLOSE_4_4_0` — all `external_refs/TurnBasedGameData/*`, pinned at `b11066beacc4de454b625fafc7ea3dd540c5bbf3` with `version_relation: CLOSE_4.4.0_TO_4.4.54`.

## 8. Validation performed

- JSON parses; duplicate keys rejected (`tools/control/validate_json_no_duplicate_keys.mjs` → PASS).
- Every referenced file was verified to exist.
- Every reported SHA-256 recomputes (6 artifact hashes re-verified byte-for-byte).
- Every exact relation is reproducible from the cited file and key path.
- No fuzzy join, numeric-proximity join or same-index join was promoted; the one same-index candidate was explicitly disproven.
- No production Python was written. No existing M12 record was modified. No Git write was issued (read-only `ls-files`, `log`, `log --full-history`, `show`, `rev-parse`, `hash-object`, `config`, `status` only).
