"""Derive final R27 controls/report only from current asserted audit receipts."""
import collections
import json
import re
from r27_checks import ROOT,AUDIT,CR,read,write,sha,preserve
from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes

SUFFIX='20261022_001'
CONTROL_NAMES=['real_character_skill_closure_v1','exact_source_acquisition_v1','real_monster_content_v1',
    'real_monster_action_coverage_v1','real_content_gap_ledger_v1']
REPORT='docs/agent/handoffs/generic_runtime_real_character_monster_closure_'+SUFFIX+'.md'

def main():
    gate=read(AUDIT/'start_gate.json');tests=read(AUDIT/'final_tests.json')
    assert all(r['returncode']==0 for r in tests.values())
    focused=(AUDIT/'R27_focused.txt').read_text()
    assert re.search(r'Ran 8 tests',focused) and focused.strip().endswith('OK')
    tests['R27_focused']=dict(returncode=0,tests=8,command=['python','-m','unittest','tests.battle_runtime.test_behavior_r27'],receipt='R27_focused.txt')
    write('release_tests.json',tests)
    regression=AUDIT/'regressions'
    frozen=read(regression/'frozen_regression.json')
    assert frozen['all_original_state_hashes_equal']
    for name in ('r22_regression','r23_regression','r24_regression'):
        assert read(regression/(name+'.json'))['status']=='PASS'
    assert read(regression/'r25/functional_scenarios.json')['passed']==18
    turns=read(regression/'r22/execution_traces.json')['traces']
    approved={r['id']:r for r in read(ROOT/'tmp/audit/r26_battle_planner_bridge_20261022_001/r22/execution_traces.json')['traces']}
    drift=[r['id'] for r in turns if r['full_runtime_hash']!=approved[r['id']]['full_runtime_hash']]
    assert not drift
    assert read(AUDIT/'character/independent_replay.json')['status']=='PASS'
    write('determinism_and_preservation.json',dict(status='PASS',frozen_state_hash_drift=0,
        current_R22_full_runtime_hash_drift=drift,R22_traces=len(turns),
        character_command_replay='PASS',monster_command_replay='PASS',original_root_IR_unchanged=True,
        frozen_denominators=dict(combat_roots=632,joined_roots=160,joined_rows=161)))
    preservation=preserve()
    character=read(AUDIT/'character/recovery_summary.json')
    stages=read(AUDIT/'character/dependency_stages.json')
    diversity=read(AUDIT/'character/diversity/results.json')
    cohort=[s['whole_original_parent'] for s in stages]+diversity
    assert len(stages)==7 and len(cohort)==9 and all(r['source_IR_unchanged'] and r['replay']=='PASS' for r in cohort)
    assert all(r['actions_completed']==0 and r['turn_owner']=='a' for r in cohort)
    stable_rows=read(regression/'r23/joined_execution_results.json')
    baseline={r['root']:r for r in stable_rows}
    assert len(stable_rows)==160 and sum(r['metrics']['tasks_completed']>0 for r in stable_rows)==72
    changed=[dict(root=r['root'],before=baseline[r['root']]['required_capability'],after=r['required_capability'],
        tasks_before=baseline[r['root']]['metrics']['tasks_completed'],tasks_after=r['metrics']['tasks_completed']) for r in cohort
        if r['required_capability']!=baseline[r['root']]['required_capability']]
    new_prefixes=sum(r['metrics']['tasks_completed']>0 and baseline[r['root']]['metrics']['tasks_completed']==0 for r in cohort)
    sites=set();types=set()
    for record in read(AUDIT/'character/catalog_additions.json'):
        for n in walk_nodes(IRNode.from_dict(record['ir'])):
            if n.kind=='TaskIR' or n.kind=='UnsupportedSemanticIR' and 'task_type' in n.payload:
                span=n.payload.get('span')
                if span:sites.add((record['source_shard_sha256'],*span,n.op));types.add(n.op)
    task_census=dict(source_task_spans=len(sites),task_types=sorted(types),sites=[list(k) for k in sorted(sites)],
        note='Physical serialized task spans deduplicated; executable support not implied')
    write('character/new_task_body_census.json',task_census)
    monster=read(AUDIT/'monster/recovery_summary.json')
    results=read(AUDIT/'monster/execution_results.json')
    assert len(results)==3 and all(r['source_IR_unchanged'] and r['actor_kind']=='Monster' and r['clone_snapshot_replay']=='PASS' for r in results)
    assert not any(r['action_reference_complete'] for r in results)
    ai=read(AUDIT/'monster/AI_source_attempt.json')
    acquisition=read(AUDIT/'acquisition_tickets.json')
    additions={r['identity']:r for r in read(AUDIT/'character/catalog_additions.json')}
    contracts={
        'RPG.GameCore.RemoveModifier':'Original instance selection/removal and lifecycle policy; exact target and modifier identity binding',
        'RPG.GameCore.AddModifier':'Original modifier definition/application context, owner/caster/source provider and lifecycle policy',
        'RPG.GameCore.Attack':'Original damage operands, source actor/progression/property inputs and damage policy authority',
        'RPG.GameCore.SetDynamicValueByProperty':'Original source/target property resolution and dynamic-provider write binding',
        'RPG.GameCore.FireProjectile':'Original projectile executor, target/position context, child ownership and completion contract',
        'RPG.GameCore.SetDynamicValueByCharacterCount':'Original character selection/count predicate, provider write and task completion contract'}
    for stage in stages:
        row=stage['whole_original_parent'];node=row['gap_node'];record=additions[stage['resolved_dependency']]
        acquisition.append(dict(ticket_id='R27-CHARACTER-RUNTIME-'+str(row['canonical_binding']['avatar_id']),
            workstream='CHARACTER',kind='ORIGINAL_RUNTIME_EXECUTOR_OR_CONTEXT_REQUIRED',
            owner_root=row['root'],canonical_binding=row['canonical_binding'],
            recovered_child=stage['resolved_dependency'],recovered_source_identity=stage['exact_source_identity'],
            source_path=record['entry']['config']['path'],parent_source_identity=row['source_identity'],
            current_failure=row['required_capability'],primitive=row['primitive'],failure_node=node,
            required_artifact=contracts.get(row['primitive'],'Exact original executor operands/context and task completion contract'),
            provider_authority='Reference context may test mechanics; native correctness requires original provider/semantic authority',
            source_body_available=True,whole_original_parent_rerun=True,completion_claimed=False))
    for row in results:
        acquisition.append(dict(ticket_id='R27-MONSTER-RUNTIME-'+str(row['monster_id']),workstream='MONSTER',
            kind='ORIGINAL_RUNTIME_EXECUTOR_REQUIRED',exact_join=row['exact_join'],
            source_span=row['gap_node'].get('payload',{}).get('span') if row['gap_node'] else None,
            primitive=row['primitive'],current_failure=row['required_capability'],
            required_artifact='Exact original task/predicate executor binding and position/formation state contract; active patch/provider authority if native semantics are claimed',
            native_selection_policy='UNKNOWN',authored_reference_attack_substituted=False))
    acquisition.append(dict(ticket_id='R27-MONSTER-AI-READER',workstream='MONSTER',kind='ORIGINAL_AI_READER_REQUIRED',
        owner_ids=ai['owners'],source_path=ai['asset']['path'],asset=ai['asset'],source_pin=ai['pin'],
        current_failure=ai['result'],expected_type='RPG.GameCore.ConsiderationAxisConfig',
        required_artifact='Exact discriminator-minus-one native branch and selected child reader for 0x1E50C200; original bytes are present',
        semantics='Conditions, selection order, weights, priorities and cooldown effects remain unbound; source presence is not native rule execution'))
    common=dict(change_request=CR,starting_head=gate['head'],branch=gate['branch'],source_version='4.6.51',
        source_manifest_sha256=read(AUDIT/'authoritative_inputs.json')['snapshot_manifest_sha256'],product_baseline='SEPARATE_FROZEN_4.4.54',
        native_correctness='NOT_CLAIMED',git_writes='NONE')
    def control(name,doc):
        path=ROOT/f'data/control/generic_runtime_{name}_{SUFFIX}.json'
        path.write_text(json.dumps({**common,**doc},indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    assessment=read(AUDIT/'character/ranking_summary.json')
    control('real_character_skill_closure_v1',dict(schema='generic_runtime_real_character_skill_closure/1',
        frozen_denominators=dict(canonical_skill_rows=660,exact_owner_config_joins=309,exact_root_joins=306,decoded_joined_roots=160,decoded_joined_rows=161),
        new_canonical_skill_root_joins=0,new_exact_compiled_child_bodies=7,new_original_task_spans=task_census['source_task_spans'],
        body_decoding_caveat='Kafka/Sampo body storage is fully consumed, including three unresolved JsonEnum references. No missing provider value is invented.',
        ranking=assessment,ranking_artifact='tmp/audit/r27_real_character_monster_20261022_001/character/all_160_ranked.json',
        selected_unique_characters=len({r['canonical_binding']['avatar_id'] for r in cohort}),selected_original_roots=len(cohort),
        selected_nonempty_original_prefixes=sum(r['metrics']['tasks_completed']>0 for r in cohort),new_observed_nonempty_prefix_roots=new_prefixes,
        full_source_closed_joined_skill_transitions=0,stable_frozen_nonempty_prefixes=72,archived_historical_nonempty_prefixes=73,
        frozen_hp_setting_roots=18,frozen_original_child_finish_roots=15,
        entire_R27_overlay_reexecuted=False,entire_overlay_prefix_total='NOT_MEASURED; selected improvements never overwrite frozen 72 or archived 73',
        source_dependency_stages=stages,selected_diversity=diversity,actual_blocker_changes=changed,
        completed_unjoined_parent_recovery=read(AUDIT/'character/completed_unjoined_parent_recovery.json'),
        original_IR_modified=False,finish_nodes_added=False,presentation_assumptions_added=False,R25_whole_skill_action='NOT_APPLICABLE_NO_COMPLETE_SKILL'))
    control('exact_source_acquisition_v1',dict(schema='generic_runtime_exact_source_acquisition/1',
        external_source_artifacts_acquired=0,approved_offline_recovery=True,
        source_snapshot_gate='43/43 original files verified against immutable manifest',
        prior_evidence_inventory='tmp/audit/r27_real_character_monster_20261022_001/authoritative_inputs.json',
        repeated_R23_Camera_directory_searches=0,Camera_required_bodies_unavailable=68,
        Phase_original_bodies_newly_decoded=7,Phase_remaining_structural_reader_gaps=0,JsonEnum_unresolved_provider_sites=3,
        original_117_site_progress=read(AUDIT/'character/original_reader_site_progress.json'),
        native_methods_examined=len(read(AUDIT/'native_reader_receipt.json')['methods']),native_method_budget=100,
        reader_capabilities=['Native enum arrays with exact descriptor/underlying type','Native primitive/struct array delegates',
            'AL bitmap fields','Exact high-mask integer strings','Conservative local polymorphic reader tables',
            'JsonEnum serialized lookup keys retained without provider evaluation'],
        source_task_semantics_added=False,source_provider_values_invented=False,
        tickets=acquisition,stop='No further path-family searches. Source body decoding progressed to actual executor/provider blockers; unsupported native factories are explicit tickets.'))
    control('real_monster_content_v1',dict(schema='generic_runtime_real_monster_content/1',**monster,
        source_tables=[dict(name=name,asset=read(AUDIT/'monster'/f'{name}_table.json')['asset'],
            pin=read(AUDIT/'monster'/f'{name}_table.json')['pin'],decoded=read(AUDIT/'monster'/f'{name}_table.json')['decoded'],
            full_table_consumption=read(AUDIT/'monster'/f'{name}_table.json')['complete'])
            for name in ('MonsterConfig','MonsterTemplateConfig','MonsterSkillConfig')],
        exact_identity_actors=read(AUDIT/'monster/selected_actors.json')['actors'],exact_skill_root_joins=read(AUDIT/'monster/exact_joins.json'),
        native_identity_evidence=read(AUDIT/'monster/exact_native_relationships.json'),
        static_properties='Original numeric fields retained; effective property initialization not reconstructed',
        AI_source=ai,AI_record_found=True,AI_record_fully_decoded=False,AI_rule_decoded=False,
        native_selection_weights='UNKNOWN',native_priorities='UNKNOWN',native_cooldown_semantics='UNKNOWN'))
    prefix_count=sum(r['metrics']['tasks_completed']>0 for r in cohort)
    acceptance=dict(A_ORIGINAL_CHARACTER_SKILL_PREFIX=dict(selected=prefix_count,new_observed_roots=new_prefixes,frozen_stable=72,historical_archived=73),
        B_FULL_SOURCE_CLOSED_JOINED_SKILL_TRANSITION=0,C_EXACT_MONSTER_SKILL_ROOT_JOIN=3,
        D_ORIGINAL_MONSTER_ACTION_EXECUTED=0,E_SOURCE_BACKED_MONSTER_AI_RULE_EXECUTED=0,F_NATIVE_VALIDATED_TRANSITION=0)
    control('real_monster_action_coverage_v1',dict(schema='generic_runtime_real_monster_action_coverage/1',
        exact_root_joins=3,decoded_original_ability_bodies=4,R20_Monster_bindings=3,R22_enemy_action_admissions=3,
        original_action_completions=0,source_backed_AI_rules_executed=0,original_task_completions=sum(r['executed_original_tasks'] for r in results),
        native_validated_transitions=0,execution_results=results,
        decision_provider='FIRST_PERMISSION_REFERENCE only; not original AI',authored_monster_reference_actions_added=0,
        acceptance=acceptance,R25_action='NOT_APPLICABLE_NO_COMPLETE_MONSTER_ACTION'))
    verdict='EXACT_CONTENT_RECOVERED_FULL_ACTION_CLOSURE_BLOCKED'
    control('real_content_gap_ledger_v1',dict(schema='generic_runtime_real_content_gap_ledger/1',verdict=verdict,
        acceptance=acceptance,remaining_Camera=68,remaining_Phase_reader=0,remaining_JsonEnum_provider_sites=3,
        character_current_blockers=changed,monster_current_blockers=[{k:r[k] for k in ('monster_id','skill_id','root','primitive','required_capability')} for r in results],
        acquisition_tickets=acquisition,determinism='PASS',tests=tests,frozen_corpus_drift=0,
        production_files_modified=[],inherited_files_modified=preservation['changed_starting_files'],
        next='R28 P0 exact Camera/JsonEnum provider acquisition and original executor/context binding; P1 Monster formation/distance and AI reader/action semantics; Beam/MCTS remain deferred.'))
    summary=dict(verdict=verdict,starting_head=gate['head'],exact_character_child_sources=7,original_task_spans=task_census['source_task_spans'],
        canonical_skill_joins_added=0,full_joined_transitions=0,Camera_gaps=68,Phase_reader_gaps=0,JsonEnum_provider_sites=3,
        monster_records_decoded=2779,monster_template_records=664,monster_skill_records=3729,monster_skill_root_joins=3,
        decoded_original_monster_abilities=4,original_monster_actions_executable=0,AI_rules=0,
        determinism='PASS',tests=tests,native_correctness='NOT_CLAIMED',git_writes='NONE',production_files=[])
    write('final_summary.json',summary)
    text=f'''# R27 Real Character and Monster Content Recovery

CR `{CR}`. Starting HEAD `{gate['head']}`, branch `{gate['branch']}`. Verdict: **{verdict}**. Native correctness: **NOT CLAIMED**.

R27 recovered seven exact original character Phase bodies, representing {task_census['source_task_spans']} distinct serialized task spans, and three exact Monster skill/root owner chains. It did not complete a whole joined character skill or Monster action. No runtime semantics, original source tasks, finish nodes, presentation assumptions, native selection rules or reference attacks were invented. All inherited production files, approved R12–R26 implementations, frozen M10–M15, ScenarioCompiler, strict admission, prior controls and unrelated dirty bytes remain unchanged. No Git writes, game launch or live attachment occurred.

The approved on-disk R26 checkpoint was tested at the current HEAD. The start gate records the full dirty state and {preservation['checked_files']} starting hashes. The immutable 4.6.51 snapshot manifest and all 43 payload sizes/SHA-256 hashes were verified; 132 prior controls, reports and source/reader/dependency evidence artifacts were read and pinned. The separate 4.4.54 product baseline was not rebased.

## Character closure

The 660 canonical ownership rows, 309 owner/config joins, 306 exact root joins, 160 decoded joined roots and 161 joined rows are unchanged. All 160 roots were ranked using an explicit R27 catalog overlay, source availability, remaining dependency count/depth, original finish structures, observed executable prefixes, provider needs and authored remaining-work estimates. Frozen inputs were not changed. The ranked table is `character/all_160_ranked.json` in this audit.

Seven targeted original Phase02 records now achieve full bounded storage consumption and compile through the existing Behavior IR: Fugue, Herta, Jade, Kafka, Klara, Lynx and Sampo. They required enum-array/field/reader repairs and a native damage factory branch; Kafka and Sampo also contain three original JsonEnum lookup sites. Native `JsonEnum.ParseFromBinary` reads two integers, then resolves them through a lazy backing table. R27 retains the exact signed indices and byte spans as unresolved source references. It does not claim that the referenced enum/provider content was recovered. Thus seven decoded body records do not imply seven source-closed skills.

Each recovered dependency was added to the existing ContentCatalog in an explicit R27 process-local overlay and its original canonical parent was rerun immediately through R20 → R22 permission → R15 ownership. Root IR hashes remain unchanged. Next actual blockers are:

| Original canonical parent | Completed tasks | Next actual blocker |
| --- | ---: | --- |
'''+ '\n'.join(f"| {s['whole_original_parent']['root']} | {s['whole_original_parent']['metrics']['tasks_completed']} | {s['whole_original_parent']['required_capability']} |" for s in stages)+f'''

Huohuo basic attack executes 53 original tasks and Bronya ultimate-related content executes two; both retain their original Camera dependency and stop there. Together with the seven repaired parents, nine distinct characters/roots were probed, with {prefix_count} replayable nonempty selected prefixes and {new_prefixes} newly observed nonempty roots relative to the stable frozen run. No full R27-overlay 160-root prefix census is claimed.

Historical archived R23 **73** remains preserved. Stable reexecution remains **72**, with 18 HP-setting roots and 15 original child-finish roots. Child finishes do not release an unresolved canonical parent. Full source-closed joined transitions and R22 completed turns for the selected real skills remain **0**. R25 whole-skill execution is therefore not applicable.

The three previously completed unjoined R22 Ability roots were examined by source hash/span and original serialized call edges. Anaxa Phase02 has an exact canonical Phase01 caller, whose Camera body is still missing. Lingsha and Sparkle Phase02 have no direct canonical parent proven in the current owner/config/reader view. None was promoted by a name-based join.

## Source acquisition

R23's failed Camera path-family searches were not repeated. All 68 exact Camera tickets retain canonical owner/root chains where proven, caller file/directory identities, serialized keys, source spans, prior directory/inline evidence, missing provider authority and original artifact requirements. Expected body paths remain explicitly unknown where no path is proven. The fixed snapshot excludes full-client Unity/ASB/Lua payloads; absence in the bounded catalog does not establish absence in the game. No Camera was skipped or declared presentation-only.

The seven original Phase first-reference reader gaps reduce to **zero structural body-reader gaps** in this selected cohort. Of R23's original 117 structural reader-gap sites, seven are now exact compiled sites and **110 remain**. Klara's `0x1E5255A0` factory is decoded using its exact native discriminator branches. The three JsonEnum provider sites remain additional source dependencies, independently of this structural count. Broader transitive reader gaps are not claimed closed. Exact keys, parent identities and native cache/resolver coordinates are acquisition tickets. Unknown dynamic/provider values and task/executor semantics remain explicit. New source artifacts acquired externally: **0**; recovered content came from the already approved offline snapshot.

The new readers are opt-in tooling over the existing readers/catalog/compiler, with enum array descriptors, primitive/struct array delegates, AL bitmap branches, exact integer mask storage, bounded local native dispatch and JsonEnum key preservation. Duplicate masks are rejected; unsupported custom factories stop typed. New structural decoding never registers a task's executable meaning. The frozen readers and old source IR are unchanged.

## Monster content and original actions

All original tables fully consume their exact DesignV asset ranges: **2779 Monster rows**, **664 template rows**, **3729 skill rows**. Native metadata and writer/consumer instructions prove numeric MonsterID/TemplateID joins, template JsonPath, Monster.SkillList, SkillID and SkillTriggerKey. Original CharacterConfig SkillConfig.Name/EntryAbility then joins the unique trusted serialized Ability directory. Filename transformations discover candidate assets only; they never establish an owner edge.

Three exact owner chains are proven: `1002013 → 100201301`, `1002014 → 100201401`, and `1002040 → 100204001`. Four original Ability bodies decode/compile, with every unknown field/span retained. The original numeric static-property records are available, but effective HP/attack/speed initialization remains unbound. Actor properties used for execution are explicitly labelled reference inputs.

All three exact actions were bound using real `ActorRuntimeBinding` kind `Monster`, admitted by R22's enemy action path and started through R15 unchanged. They stop at SetTeamFormation (two roots) or ByDistance (Soldier). **Original Monster action completions = 0**, original completed task prefixes = 0, reference attack substitutions = 0. R22 admission is reported separately from execution completion. The decision provider is explicitly FIRST_PERMISSION_REFERENCE, not original Monster AI.

All three selected templates reference the exact 140-byte `Monster_Common_SequenceThree_AI` source asset. Its original source identity and variable/decision dispatch were recovered, but full decoding stops at native polymorphic reader `0x1E50C200`, source cursor 27101179 of 27101210. AI record found = yes; fully decoded AI rule = no; source-backed AI rule executed = **0**. Selection weights, priorities and effective cooldown semantics remain unknown. No metadata-only AI claim is made.

## Acceptance and regression

| Acceptance cohort | Result |
| --- | --- |
| A ORIGINAL_CHARACTER_SKILL_PREFIX | {prefix_count} selected; {new_prefixes} new prefixes; frozen stable 72 and historical archived 73 preserved |
| B FULL_SOURCE_CLOSED_JOINED_SKILL_TRANSITION | 0 |
| C EXACT_MONSTER_SKILL_ROOT_JOIN | 3 |
| D ORIGINAL_MONSTER_ACTION_EXECUTED | 0 completed actions |
| E SOURCE_BACKED_MONSTER_AI_RULE_EXECUTED | 0 |
| F NATIVE_VALIDATED_TRANSITION | 0 |

R12–R26 focused tests, R21 specifications and battle_ir/battle_runtime/battle_sandbox FAST_UNIT lanes pass on the unchanged current production files. The original two long lanes were interrupted without final logs or exit codes; process inspection on resumption found no surviving Python worker. They were never reported as PASS. Completed R21 (21), battle_ir (586), battle_sandbox (918) and eight R27 case receipts were retained after input verification. The missing validation uses one runtime discovery case set (651), with the identical R12–R26 case IDs (449) reported as an explicit subset. These overlapping suites were not run twice. The full R26 scenarios, including corrected P20 and contracts, are covered by that shared execution. The durable runner resumed pending cases after one Windows receipt-file sharing error; its recorded hashes establish that tested code and generated inputs did not change. Per-case results, process IDs, invocation outcomes and input hashes are in `resume/`; exact commands/counts/logs are in `release_tests.json`. Beam/MCTS were not modified.

The older R26 643-case PASS was also reviewed against its final package hashes. Its full run overlapped the P20 fixture/assertion correction, with a separate seven-case correction receipt; it was not relabelled as a current fixed-input full run. That historical record remains intact in its original audit, with this review in `resume/older_R26_test_version_review.json`.

Unchanged historical runners pass: frozen 632 combat roots / 160 joined roots / 161 rows; stable R23 160-root execution and public replay; R22 A–L; R24 18 defense scenarios; R25 E01–E18. All frozen original state hashes match, and all {len(turns)} R22 full runtime hashes equal the approved R26 rerun. Clone, JSON snapshot, stable hash and public command replay remain deterministic. Source compilation repeats and round trips; representative first/middle/last records across all three Monster tables are re-read from pinned bytes.

## Reproduction and R28

Prerequisites are the exact pinned snapshot and approved R12–R26 repository/audit inputs. R27 owns only new tooling, tests, controls, this report and its audit. No production file changed.

```powershell
python tools/runtime/r27_monster.py
python tools/runtime/r27_character.py
python tools/runtime/r27_assessment.py
python tools/runtime/r27_selected.py
python tools/runtime/r27_replay.py
python tools/runtime/r27_monster_execute.py
python tools/runtime/r27_regressions.py
python tools/runtime/r27_resume_tests.py
python -m unittest tests.battle_runtime.test_behavior_r27
python tools/runtime/r27_checks.py preserve
python tools/runtime/r27_finalize.py
```

Do not regenerate the retained start gate. The shipped R27 native-reader schema/dispatch/evidence caches make selected-root reproduction independent of another reverse campaign. Character `dependency_stages.json`, original command receipts, independently reconstructed `character/replay/*` snapshots and Monster `execution/*/initial_runtime.json`, `commands.json`, `final_runtime.json` provide exact replay inputs. Full provenance and acquisition tickets are in the five R27 controls and audit.

Recommended R28 keeps P0 on exact Camera/JsonEnum provider acquisition and original executor/context bindings, then P1 on Monster formation/distance semantics and the exact AI reader/action chain. Beam/MCTS remain deferred. Preferred full-skill and original-Monster-action milestones were not achieved; the strongest established result is exact source recovery with measured next blockers.

Handoff: `D:/HSR_Battle_Agent/agent_handoffs/{CR}_changed_files.zip`. The manifest and separate verification receipt establish exact file set, sizes, member SHA-256, CRC and archive SHA-256. Game binaries, raw payloads, old audit trees and unrelated dirty files are excluded.
'''
    (ROOT/REPORT).write_text(text,encoding='utf-8')
    print(json.dumps({**summary,'tests':{name:{k:row[k] for k in ('returncode','tests')} for name,row in tests.items()}},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
