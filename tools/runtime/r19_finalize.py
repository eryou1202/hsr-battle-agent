"""R19 controls/report and exact changed-file archive, without Git writes."""
from __future__ import annotations
import collections
import difflib
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from r19_checks import ROOT,AUDIT,PRODUCTION,read,write,sha,preservation

CR='CR-R19-DAMAGE-CONTINUATION-PROPERTY-20261010-001'
SUFFIX='20261010_001'
REPORT='docs/agent/handoffs/generic_runtime_damage_continuation_property_'+SUFFIX+'.md'
CONTROLS=['data/control/generic_runtime_'+n+'_'+SUFFIX+'.json' for n in
          ('damage_lifecycle_v1','dynamic_property_v1','damage_continuation_census_v1','support_census_v9','semantic_gap_ledger_v7')]
DEST=Path('D:/HSR_Battle_Agent/agent_handoffs')/(CR+'_changed_files.zip')

def emit(name,value):
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')

def slim(row):return {k:v for k,v in row.items() if k not in ('settlements','initial_checkpoint')}

def main():
    preservation();start=read(AUDIT/'start_gate.json');tests=read(AUDIT/'final_tests.json')
    assert all(r['returncode']==0 for r in tests.values())
    for name,expected in read(AUDIT/'source_pins.json').items():assert sha(ROOT/name)==expected,name
    joined=read(AUDIT/'joined_summary.json');frozen=read(AUDIT/'frozen_summary.json');broader=read(AUDIT/'broader_summary.json')
    follows=read(AUDIT/'followup_summary.json');mainrows=read(AUDIT/'continuation_expression_results.json')
    rankrows=read(AUDIT/'explicit_rank_results.json');ability=read(AUDIT/'real_ability_results.json')
    after=joined['cohorts']['continuation_expression'];rank=joined['cohorts']['explicit_rank']
    assert joined['before']['hp_mutated']==11 and joined['before']['settlements']==22
    assert after['hp_mutated']==15 and after['settlements']==29 and after['damage_lifecycle_complete']==14
    assert rank['damage_lifecycle_complete']==15 and after['actions_reference_complete']==rank['actions_reference_complete']==0
    assert not frozen['drift'] and frozen['damage_attempts']==74 and not read(AUDIT/'frozen_state_hash_comparison.json')['state_hash_drift']
    assert follows['real_ability_roots']['reference_actions_complete']==2
    shared={'change_request':CR,'starting_head':start['head'],'branch':start['branch'],'source_version':'4.6.51',
        'semantic_authority':'REFERENCE_MODEL','native_correctness':False,'git_writes':'NONE','frozen_modules_modified':False}
    verdict='GENERIC_DAMAGE_CONTINUATION_REFERENCE_ESTABLISHED'
    native=read(AUDIT/'damage_finish_native_evidence.json')
    lifecycle=shared|{'schema':'generic_runtime_damage_lifecycle/1','verdict':verdict,
        'states':['REQUEST_CREATED','AMOUNT_EVALUATED','SETTLEMENT_PENDING','HP_COMMITTED','CALLBACKS_PENDING','DAMAGE_REFERENCE_COMPLETE'],
        'labels':'REFERENCE_MODEL abstraction, not native state labels',
        'HP_COMMITTED':'provisional HP storage mutation inside R18 atomic damage transaction; rollback restores it until source primitive commit',
        'storage':'existing damage_requests/damage_history/transaction checkpoint; no new runtime/state cache',
        'ownership':'R15 ActionExecutionRoot + current ability and descendants; R17 owned callbacks/events/continuations',
        'finish_policy':'R18 ASSERT_OWNED_DAMAGE_DRAINED_REFERENCE, strengthened rather than replaced',
        'completion_distinctions':native['signals_distinct'],
        'finish_effects':'local assertion/serialized boundary/metric only; no request/ability/action completion requested',
        'pending_work':'requests, settlements, callbacks, event frames/mutations, descendant abilities and continuations block the assertion',
        'action_completion':'existing source SkillPerformFinish + all R15 owned work + damage requests/transactions and pending events drained',
        'native_finish_evidence':native,'structural_instances':118,'finish_probes':broader,
        'transaction':'R18 descendant-only scheduler and source checkpoint retained; unsupported primitive effects roll back atomically; earlier source commits persist',
        'determinism':'all lifecycle records in snapshots/hash; budgets suspend resumably; clone/restore/replay PASS','tests':tests}
    property_control=shared|{'schema':'generic_runtime_dynamic_property/1',
        'property_sources':['BASE_PROPERTY','EFFECTIVE_PROPERTY','MODIFIER_CONTRIBUTION','ABILITY_DYNAMIC_VALUE',
            'MODIFIER_LOCAL_DYNAMIC_VALUE','SNAPSHOT_VALUE','CONTEXT_OVERRIDE','UNKNOWN_PROVIDER'],
        'provider_order':'serialized caller-authored ordered chain, explicit GAP or CONTINUE per provider; no silent actor/global fallback',
        'provider_hash':'entire policies in BehaviorRuntime snapshot/hash; chosen property provenance and contributions in damage records',
        'R11_R11C_compatibility':'same pinned 4.6.51 evidence; automatic callback/parent/override/scoped native provider partial order exists; effective initialization/IFix bindings remain unknown',
        'aggregation':'R17_STORAGE_INCLUDES_ADDITIVE_REVERSIBLE_REFERENCE; R17 writes effective storage; BASE subtracts explicit contributions, EFFECTIVE reads storage once; removal uses R17 inverse operation',
        'aggregation_scope':'explicit complete ordered active reference modifier IDs; native listener/modifier set UNKNOWN',
        'unknown_programs':{'before':4,'after':0,'denominator':'same 15 joined roots; no changes to historical serialized IR or all-program census'},
        'new_opcode':{'4':'native unpatched jump table -> FixPoint multiply; generic stack family 0/1/2/4/17 only'},
        'programs':read(AUDIT/'dynamic_program_evidence.json'),
        'numeric':'unchanged R12 mode0 signed int64, scale 2^33, raw step2 toward zero after each operation; AST left/right preserved; tagged/mixed/overflow/unknown opcode rejected',
        'raw_source_preservation':'original ExpressionIR unknown_opcode retained; bounded expansion at evaluation under explicit R19 policy; no literal substitution',
        'input_changes':'no additional dynamic values in joined cohorts; existing supplied -1126825319=17179869184 explicitly bound',
        'rank':read(AUDIT/'rank_evidence.json'),
        'rank_cohort':'separate explicit_rank cohort adds actor rank=0 and per-key threshold=1; original R18 comparison state retained in main cohort',
        'property_pipeline':slim(read(AUDIT/'property_pipeline_checkpoint.json')),'cache':'NONE; existing serializable state only'}
    levels={'A_ISOLATED_REAL_DAMAGE_PRIMITIVE':follows['isolated'],
        'B_REAL_GRAPH_PREFIX_HP_MUTATION':{'joined_before':11,'joined_after':15,'denominator':15,'settlements_before':22,'settlements_after':29},
        'C_REAL_DAMAGE_LIFECYCLE_COMPLETE':{'joined_before':0,'joined_after':14,'denominator':15,'explicit_rank_after':15,
            'definition':'HP committed plus reached/completed original DamagePerformFinish under explicit owned drain policy; C does not imply D'},
        'D_FULL_REAL_SKILL_REFERENCE_TRANSITION':{'before':0,'after':0,'denominator':15,'explicit_rank_after':0},
        'E_NATIVE_VALIDATED_TRANSITION':{'completed':0,'status':'NOT CLAIMED'},
        'ORIGINAL_NONJOINED_REAL_ABILITY_ROOT_ACTIONS':{'completed':2,'denominator':6,
            'warning':'actual real ability actions with original SkillPerformFinish; not joined whole-skill transitions',
            'completed_roots':[r['root'] for r in ability if r['status']=='ACTION_REFERENCE_COMPLETE']}}
    census=shared|{'schema':'generic_runtime_damage_continuation_census/1','result_levels':levels,
        'frozen_denominators':{'combat_roots':632,'decoded_joined_skill_roots':160,'joined_rows':161,'damage_instances':207,'damage_shapes':9,'finish_instances':118},
        'frozen':frozen,'joined':joined,'broader_finish':broader,'followups':follows,
        'joined_records':[slim(r) for r in mainrows],'explicit_rank_records':[slim(r) for r in rankrows],
        'real_ability_records':[slim(r) for r in ability],
        'structural_count_is_execution_count':False,'source_finish_nodes_added_to_real_graphs':False,
        'historical_R18_controls_modified':False,'native_oracle_blocked':118}
    subsystems={
        'damage_HP':'generic reference formula/HP settlement/lifecycle and transaction engine established; native formula, events, death and defensive rules unresolved',
        'heal':'FormulaType2 reference core and explicit R17 staged heal/event integration; native inputs/provider/listener/settlement still partial; frozen HEAL gaps=4',
        'shield':'full subsystem absent; explicit sandbox bypass only; missing native shield input remains a gap',
        'toughness_break':'full subsystem absent; no toughness mutation/break processing inferred from damage',
        'resources_energy':'explicit actor/team reference stores exist; actual energy/SP costs, gains, listeners, joins not closed; frozen RESOURCE gaps=4',
        'true_turn_AV':'not implemented; R15 logical scheduler is not native turn/AV initiative, ownership or speed engine',
        'modifier_event':'R17 generic reference instances/listeners/contributions/owned callbacks available; native effective instance/listener/provider state unknown; frozen gaps=181 combat/43 joined',
        'Monster_AI':'no independent real-content-driven behavior runtime closure; not investigated or implemented in R19',
        'stage_wave_mode':'full stage/wave/mode runtime not implemented; progression/termination remains separate precise blockers'}
    ranking=[
        {'rank':1,'phase':'R20 CORE PROPERTY / RESOURCE ENGINE','reason':'R19 expressions now run but actor progression/resource/provider initialization and effective property joins remain fundamental across damage/heal/modifier/AI; frozen property/progression/resource gaps=25/26/4 combat and 4/8/0 joined'},
        {'rank':2,'phase':'R20 CONTENT CATALOG / READER EXPANSION','reason':'largest raw missing catalog family 145 combat/75 joined; explicit prefixes now reach 12 camera catalog gaps plus one template context gap; content remains independent backlog'},
        {'rank':3,'phase':'R20 TRUE TURN / AV FOUNDATION','reason':'battle reconstruction needs actual turn order/action ownership/resource spend opportunities beyond logical callback time'},
        {'rank':4,'phase':'R20 TOUGHNESS / BREAK / SHIELD','reason':'missing core survival and weakness interactions; current damage bypass is explicit sandbox only'},
        {'rank':5,'phase':'R20 MONSTER BEHAVIOR CORPUS','reason':'real battle opponent decisions and content coverage absent'},
        {'rank':6,'phase':'R20 TARGETED NATIVE ORACLE','reason':'effective IFix/Lua, finish task executor/events/death and provider precedence still unproved; target specific joins, never reopen broad damage archaeology'}]
    support=shared|{'schema':'generic_runtime_support_census/9','verdict':verdict,'groups':levels,
        'frozen':{'combat':frozen['combat'],'joined':frozen['joined'],'historical_denominators':[632,160,161]},
        'structural_damage':{'instances':207,'field_shapes':9},'finish':broader,
        'whole_battle_subsystems':subsystems,'recommended_R20':ranking[0]['phase'],'R20_ranking':ranking,
        'top_raw_blocker':{'family':'CONTENT_CATALOG_BINDING','combat':145,'joined':75},
        'determinism':'PASS','replay':'PASS','architecture':'PASS','tests':tests,'native_skill_completions':0}
    tickets=[{'identity':'DAMAGE_FINISH_EFFECTIVE_RUNTIME_ORACLE_REQUIRED','status':'ORACLE_BLOCKED',
        'question':'exact config->runtime task executor/IFix/Lua effective state, request/settlement/death/controller/barrier/bookkeeping/event effects',
        'evidence':'damage_finish_native_evidence.json','instances':118,'reference_policy_is_native_equivalence':False},
        {'identity':'PROPERTY_EFFECTIVE_PROVIDER_ORACLE_REQUIRED','status':'ORACLE_BLOCKED',
        'question':'bind automatic scope callback/parent/override/scoped providers and actual state initialization; no silent fallback',
        'evidence':'dynamic_program_evidence.json and R11C native_semantic_continuation.json'},
        {'identity':'RANK_ACTIVATION_NATIVE_COMPARISON_REQUIRED','status':'ORACLE_BLOCKED',
        'question':'TriggerKey StringHash -> actor progression activation rows/threshold and actual comparison predicate',
        'evidence':'rank_evidence.json','reference_comparison_only':'KEYED_THRESHOLD_GE_REFERENCE'}]
    ledger=shared|{'schema':'generic_runtime_semantic_gap_ledger/7',
        'frozen_first_gaps':{'combat':frozen['combat']['first_gap_distribution'],'joined':frozen['joined']['first_gap_distribution']},
        'explicit_joined_remaining_gaps':[{'root':r['root'],'source_identity':r['source_identity'],'primitive':r['primitive'],
            'required_capability':r['required_capability'],'node':r['gap_node']} for r in mainrows],
        'explicit_rank_remaining_gaps':[{'root':r['root'],'primitive':r['primitive'],'required_capability':r['required_capability']} for r in rankrows],
        'oracle_tickets':tickets,'whole_battle_subsystems':subsystems,'R20_ranking':ranking,
        'zero_first_gap_frequency_means_implemented':False,'historical_R18_ledger_preserved':True}
    for name,value in zip(CONTROLS,(lifecycle,property_control,census,support,ledger)):emit(name,value)
    write('oracle_tickets.json',tickets);write('whole_battle_assessment.json',{'subsystems':subsystems,'ranking':ranking})
    changed=[name for name in PRODUCTION if name not in start['file_hashes'] or sha(ROOT/name)!=start['file_hashes'][name]]
    for name in changed:
        before=AUDIT/'starting_files'/name;old=before.read_text(encoding='utf-8') if before.exists() else ''
        target=AUDIT/'diffs'/(Path(name).name+'.diff');target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(''.join(difflib.unified_diff(old.splitlines(True),(ROOT/name).read_text(encoding='utf-8').splitlines(True),
            fromfile='approved_R18/'+name,tofile='R19/'+name)),encoding='utf-8')
    frozenrows=read(AUDIT/'frozen_results.json');previous={tuple(r['source_identity']):r for r in read(ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001/frozen_probes.json')}
    assert all(r['state_hash']==previous[tuple(r['source_identity'])]['state_hash'] for r in frozenrows)
    report=f'''# R19 Generic Damage Continuation + Property

CR `{CR}`. Verdict **{verdict}**. Starting HEAD `{start['head']}`, branch `{start['branch']}`. Git writes NONE; no live capture/game launch. Frozen M10–M15 and ScenarioCompiler remain unchanged. Preservation verifies {read(AUDIT/'preservation.json')['checked_files']} starting files; R18 controls, source pins and handoff CRC/member sizes/hashes PASS.

R19 extends the existing R12 ExpressionIR/evaluator, R15 action scheduler, R17 modifier/event engine and R18 damage transactions. It adds no second runtime, event bus or unsnapshotted property cache. Original real source graphs, unsupported IR envelopes and numeric operands remain intact. No SkillPerformFinish was inserted into real graphs.

## Damage lifecycle and native boundary

The six serialized REFERENCE_MODEL states are REQUEST_CREATED → AMOUNT_EVALUATED → SETTLEMENT_PENDING → HP_COMMITTED → CALLBACKS_PENDING → DAMAGE_REFERENCE_COMPLETE. HP_COMMITTED means provisional storage mutation inside the R18 source transaction; a later primitive gap restores HP, callbacks, modifiers, RNG, queues and lifecycle records together. Earlier committed source tasks persist. Snapshot/clone/hash/resume/replay include pending requests and checkpoints.

R18 ASSERT_OWNED_DAMAGE_DRAINED_REFERENCE is retained and strengthened. It checks current ability and descendants, settlements, owned callbacks/events/continuations, child completion and pending transaction/event mutations. It completes only the finish task/local reference boundary. TASK_COMPLETION, DAMAGE_REQUEST_COMPLETION, DAMAGE_SETTLEMENT_COMPLETION, ABILITY_COMPLETION and ACTION_COMPLETION are separate. Action completion still requires an original source completion request and drained owned work.

The pinned 4.6.51 metadata maps DamagePerformFinish to config type 23016, reader 0x1E5265C0, and fields SkipDeathSettlement/IsFakeAvatarAttack. All 118 selected instances have bitmap 0. Reader/config fields do not prove runtime executor semantics or defaults. Related TurnBasedAbilityComponent.CharmDamagePerformFinish@0xF1418A0 emits an event through 0xE26CD70 → EventManager.FireEvent@0xEF632B0; CharacterHudComponent._OnAbilityDamagePerformFinish@0xEEC5F80 is a related consumer. The exact config/task-to-method join remains UNPROVEN. IFix guard RVA 0x978E100 / patch ID 0x7FC20 and effective Lua Type.Name hook maps remain unbound. Request finalization, settlement waiting, callback/event effects, controller/barrier behavior, bookkeeping and death settlement are UNKNOWN for the effective task. **Native correctness NOT CLAIMED.** Exact blocker: DAMAGE_FINISH_EFFECTIVE_RUNTIME_ORACLE_REQUIRED.

## DynamicFloat and property sources

All four selected unknown programs share `[1,0,0,0,4,17]`: push int32-key lookup, push int64 raw literal, multiply, terminate. Native evaluator 0x1E196300 uses table 0x1E197720; opcode 4 table slot 0x1E197730 points to 0x1E196678 and calls FixPoint.op_Multiply@0x1EC1BCF0 at 0x1E1966B3. The generic family reuses 0/1/2/17 and expands opcode 4 only under explicit R19 policy. Unknown opcodes, malformed indices/stacks/termination and tagged/mixed/overflow domains reject. R12 signed raw int64, scale 2^33, step2 toward-zero quantization and AST evaluation order are preserved.

The four source spans are 10713432–10713452, 11037846–11037866, 11101005–11101025 and 11314173–11314193; source artifacts/hashes, decoded programs and expanded ASTs are in dynamic_program_evidence.json. Their provider key -1126825319 already has raw value 17179869184 in the unchanged R18 fixture. No value was injected or substituted. R19 explicitly binds that existing store. Same-version R11/R11C evidence describes partial unpatched callback/parent/override/scoped lookup order, but active IFix/source identities and initialized effective provider precedence remain unknown.

BASE_PROPERTY, EFFECTIVE_PROPERTY, MODIFIER_CONTRIBUTION, ABILITY_DYNAMIC_VALUE, MODIFIER_LOCAL_DYNAMIC_VALUE, SNAPSHOT_VALUE, CONTEXT_OVERRIDE and UNKNOWN_PROVIDER are explicit runtime source abstractions. Ordered provider policies, missing behavior and evidence labels serialize/hash/replay. R17 already writes additive contributions into property storage: EFFECTIVE_PROPERTY reads once, BASE_PROPERTY subtracts documented contributions, and removal reuses R17 inverse mutation. Active reference modifier IDs/order and aggregation are explicit. The property checkpoint uses real decoded damage with an explicit R17 sandbox contribution: base attack 10 + contribution 3 = effective 13; coefficient 2 gives damage 26 and HP 100 → 74. It is separate from joined skill cohorts.

ByRankActivated's mask 8 decodes TriggerKey StringHash 2089636447, not an ordinal rank. Native comparison/runtime executor semantics remain unknown. Main R18 comparison inputs are preserved and return RANK_POLICY_MISSING; a separate explicit_rank cohort supplies actor rank 0 and keyed threshold 1 under KEYED_THRESHOLD_GE_REFERENCE. It closes that predicate by explicit policy and advances to the next source task. Missing actor rank/keyed threshold remains RANK_INPUT_MISSING. No AvatarID/SkillID dispatch exists.

## Measured results

| Scope | R18 | R19 |
|---|---:|---:|
| A. Isolated original damage primitive | 6/6 | 6/6 |
| B. Same joined roots reaching HP mutation | 11/15, 22 settlements | 15/15, 29 settlements |
| Selected unknown DynamicFloat first gaps | 4 | 0 |
| C. Joined damage lifecycle including original finish | 0/15 | 14/15; 15/15 with separately supplied rank |
| D. Complete joined whole-skill reference transition | 0/15 | 0/15, including rank cohort |
| E. Native validated transition | 0 | 0; NOT CLAIMED |
| Same six nonjoined real ability roots reaching HP | 3/6 | 3/6 |
| Complete original nonjoined ability-root reference actions | 0/6 | 2/6 |

C does not imply D; D does not imply E. Isolated damage wrappers retain R18's explicitly synthetic completion and are excluded from real graph completion claims. The two naturally complete actions are Avatar_AventurineW_00_Skill01_Phase02 and Avatar_TheHerta_00_Skill01_Phase02. Both retain their original real graph and original SkillPerformFinish, all owned work drains, no SemanticGap remains, and source-backed regressions verify snapshot/replay hashes. They are real ability-root actions, **not joined complete skill transitions**.

The three joined cohorts use exactly R18's selected 15 roots: finish-only gives 10 lifecycle closures and leaves four unknown programs; continuation_expression gives 14 closures with no additional state values; explicit_rank gives 15 closures with progression additions recorded separately. Main cohort next blockers: 12 missing Camera catalog entries, one template parameter/context mapping, one missing rank policy, and one skill-tree progression input. Rank cohort leaves 13 missing Camera entries, one template context and one skill-tree input. Per-root audit records HP, finish reach/completion, next task or drained sequence, next exact gap, ability completion, action status and final BattleState hash.

All 118 structurally decoded finish instances were probed. Original graph reach/context-ready/completed: 50. Remaining structure-only-in-original-graph: 68. All 118 pass separately labelled isolated real-finish local assertions in explicit contexts with no injected damage and no inserted completion task; those assertions do not count as damage lifecycle or full skill execution. Native oracle blocked: 118, an overlapping classification. The 116 distinct source roots include basic/skill/Skill03-related, child and maze patterns across many actors. Structural count is not original graph execution count.

Unchanged frozen inputs: 632 combat roots, 160 decoded joined roots, 161 joined rows. Combat tasks reached/completed 1025/494; joined 300/121. Damage attempts/commits 74/0. HP mutations, DamagePerformFinish completions and action completions all 0. First-gap distributions, task metrics and all 632 final BattleState hashes have zero drift from R18. No policies, progression rows or operands were injected into frozen inputs.

## Whole battle reassessment

'''+'\n'.join('- **'+k+'**: '+v+'.' for k,v in subsystems.items())+f'''

Largest raw catalog family remains 145 combat / 75 joined; modifier/event context/state gaps remain 181 / 43. These first-gap counts do not measure unvisited or absent battle subsystems. Recommended next phase is **R20 CORE PROPERTY / RESOURCE ENGINE**, followed by content catalog/reader expansion, true turn/AV foundation, toughness/break/shield, Monster behavior corpus, and targeted effective native oracle closure. See whole_battle_assessment.json for ranking/basis. R20 is not automatically another damage or Natasha follow-up.

## Validation and delivery

Determinism/replay/architecture/preservation PASS. Transaction tests cover post-HP expression/callback gaps, earlier task retention, RNG rollback, finish gaps, multi-target/child continuations, pending work, budget exhaustion and every lifecycle checkpoint. Provider/aggregation/rank tests include missing inputs, ordering/hash changes, R17 contribution and removal, overflow and malformed unknown programs. R12–R19 and FAST_UNIT lanes: {', '.join(k+' '+str(v['tests'])+' PASS' for k,v in tests.items())}. Frozen tests remain unchanged.

Production: {', '.join('`'+n+'`' for n in changed)}. Tests: `tests/battle_runtime/test_behavior_r19.py` (32 tests). Controls: five R19 JSON controls listed in the change request. Audit: `tmp/audit/r19_damage_continuation_20261010_001/`.

Reproduce: `python tools/runtime/r19_probes.py`; `python tools/runtime/r19_probes.py --frozen-only`; `python tools/runtime/r19_probes.py --broader-only`; `python tools/runtime/r19_followups.py`; `python tools/runtime/r19_evidence.py`; `python tools/runtime/r19_checks.py final`; `python tools/runtime/r19_finalize.py --package`. The start gate is preserved and must not be regenerated after edits. Native text evidence is bounded to directly relevant pinned methods; no provider/archive/registration discovery or live observation occurred.

Handoff: `{DEST.as_posix()}`. Only R19-owned changed production/tests/tools/controls/report/audits, diffs and manifest are included. No binaries/native payloads/dumps/old reverse trees/starting file copies. CRC/member sets/sizes/per-member SHA-256 and ZIP SHA-256 are verified; receipt is external to the ZIP to avoid self-reference. Git writes NONE. Native correctness NOT CLAIMED.
'''
    (ROOT/REPORT).write_text(report,encoding='utf-8')
    write('final_summary.json',shared|{'verdict':verdict,'result_levels':levels,'joined':joined,'broader':broader,
        'tests':tests,'production_files':changed,'recommended_R20':ranking[0]['phase'],'determinism':'PASS','replay':'PASS','architecture':'PASS'})
    if '--package' in sys.argv:package(changed)

def package(changed):
    files={ROOT/name for name in [*changed,*CONTROLS,REPORT,'tests/battle_runtime/test_behavior_r19.py']}
    files.update((ROOT/'tools/runtime').glob('r19_*'))
    files.update(p for p in AUDIT.rglob('*') if p.is_file() and not any(x in p.parts for x in ('test_tmp','starting_files','__pycache__'))
        and p.name not in ('handoff_manifest.json','handoff_verification.json','delivery_receipt.json'))
    assert all(p.is_file() and p.suffix not in ('.dll','.exe','.dat','.bytes','.zip','.pyc') for p in files)
    members={p.relative_to(ROOT).as_posix():{'size':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)}
    manifest={'change_request':CR,'starting_head':read(AUDIT/'start_gate.json')['head'],'files':members,
        'ownership':'R19 changes only; preexisting modified production files included as final content plus R18-to-R19 diffs',
        'git_writes':'NONE','excluded':['binaries','native payloads','dumps','old reverse trees','starting_files','test_tmp','pycache']}
    write('handoff_manifest.json',manifest)
    local=ROOT/'agent_handoffs'/DEST.name;local.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(local,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):z.write(p,p.relative_to(ROOT).as_posix())
        z.write(AUDIT/'handoff_manifest.json','manifest.json')
    with zipfile.ZipFile(local) as z:
        assert z.testzip() is None and set(z.namelist())==set(members)|{'manifest.json'}
        for name,expected in members.items():
            b=z.read(name);assert len(b)==expected['size'] and hashlib.sha256(b).hexdigest()==expected['sha256']
        manifest_bytes=z.read('manifest.json')
    write('handoff_verification.json',{'local_archive':str(local),'destination':str(DEST),'ZIP_sha256':sha(local),
        'ZIP_size':local.stat().st_size,'crc':'PASS','exact_member_set':'PASS','per_member_size_sha256':'PASS',
        'manifest_size':len(manifest_bytes),'manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
        'members':members,'external_copy':'PENDING'})
    print('R19 local ZIP verified',local,sha(local),flush=True)

if __name__=='__main__':main()
