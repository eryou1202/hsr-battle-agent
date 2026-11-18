"""R28 evidence controls and reviewable handoff; never writes Git."""
import datetime
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from r28_execution import ROOT,AUDIT,OLD,read,write
CR='CR-R28-REAL-COMBAT-SEMANTICS-20261022-001'
CONTROL=ROOT/'data/control'
REPORT=ROOT/'docs/agent/handoffs/generic_runtime_original_combat_semantics_20261022_001.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def control(name,value):
    p=CONTROL/(name+'_20261022_001.json')
    p.write_text(json.dumps(dict(change_request=CR,**value),indent=2,sort_keys=True)+'\n',encoding='utf8')


def main():
    gate=read(AUDIT/'start_gate.json')
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==gate['head']
    assert subprocess.check_output(['git','diff','--cached','--name-status'],cwd=ROOT,text=True).strip()==gate['staged']
    assert all(sha(ROOT/n)==h for n,h in gate['file_hashes'].items())
    rows=read(AUDIT/'character/results.json');ai=read(AUDIT/'monster/AI_result.json')
    provider=read(AUDIT/'provider/result.json');sites=read(AUDIT/'provider/resolved_sites.json')
    monsters=read(AUDIT/'monster/results.json');native=read(AUDIT/'native_reader_receipt.json')
    assert len(native['methods'])<=30
    oldledger=read(CONTROL/'generic_runtime_real_content_gap_ledger_v1_20261022_001.json')
    tickets=read(OLD/'acquisition_tickets.json')
    camera=[t for t in tickets if 'CAMERA' in str(t.get('ticket_type','')).upper()]
    if not camera:
        camera=[t for t in tickets if t.get('status')=='BLOCKED_ORIGINAL_ARTIFACT_REQUIRED']
    denominator=dict(canonical_skill_rows=660,exact_owner_config_joins=309,exact_root_joins=306,
        decoded_joined_roots=160,joined_rows=161,frozen_combat_roots=632,
        stable_nonempty_prefixes=72,historical_archived_prefixes=73,
        original_Phase_bodies=7,original_task_spans=220,remaining_original_structural_sites=110,
        monster_rows=2779,monster_template_rows=664,monster_skill_rows=3729,
        monster_exact_skill_joins=3,monster_original_ability_bodies=4)
    notes={
      'Fugue/Jade':'Original RemoveModifier has decoded target/name. Existing R17 CONFIG_TARGET_REFERENCE selection used with explicit CANCEL_NOT_STARTED_REFERENCE and empty identity filter. No instance created. Next AddModifier lacks application binding. Native removal lifetime not claimed.',
      'Herta':'Actual blocker is AddModifier application binding, not a lookup of an existing first instance. Original caster/name exist, but exact construction, definition event coverage, application source identity and listener initialization remain unbound. No instance injected.',
      'Kafka':'R18/R19 damage pipeline exists. Original DamageByAttackProperty task hash retains native damage structure, target and dynamic operands. Missing per-task reference stage/role binding and numeric providers are not supplied. JsonEnum source strings resolved separately; damage arithmetic and HP settlement remain blocked.',
      'Lynx':'SetDynamicValueByProperty fields: DynamicKey, ContextScope, ReadTargetType, Value:AbilityProperty. Serialized masks 2/8/16, absent ContextScope requires constructor/executor scope evidence. Existing R19 provider storage reused in future. No property enum-to-provider or omitted scope default inferred.',
      'Klara':'SetDynamicValueByCharacterCount fields: DynamicKey, ContextScope, ReadTargetType, Predicate, AliveOnly. Original key Skill02_TargetNumber, AllEnemy selector and ByIsContainModifier(ParamEntity,MAvatar_Klara_00_BPSkill_Revenge). Requires exact candidate context, alive filtering, omitted defaults, numeric scaling and destination owner. No name-only count executor.',
      'Sampo':'FireProjectile original fields include inherited task list mask 256, bool 512 and ProjectileData 2048. Original callbacks are present. Projectile lifecycle, collision targets and continuation authority remain unknown. No instant no-op.',
      'SetTeamFormation':'Original task configuration has Team, FormationTarget, FormationType and further servant/config/center/counting operands. Native reader 0x1E9FAC80. R20 participant order is not a native formation model. Formation provider/config and executor dispatch/storage/event semantics remain required.',
      'ByDistance':'Original From/To target evaluators, CompareType, CompareValue:DynamicFloat, IgnoreRadius. Native reader 0x1E423810. No authoritative source/target spatial positions, units, radius adjustment, fixed arithmetic/rounding or executor comparison binding. Typed gap retained.'}
    control('generic_runtime_original_skill_semantics_v1',dict(starting_head=gate['head'],denominators=denominator,
        selected=[{k:v for k,v in r.items() if k!='original_task'} for r in rows],
        full_canonical_skill_transitions=0,native_validated_outcomes=0,
        native_source_cohort_improvement=0,reference_policy_cohort_tasks_advanced=2,
        notes=notes,authority_separation='Two reference policy input bindings; no native lifecycle recovery claim'))
    control('generic_runtime_original_task_executor_v1',dict(new_task_executor_families=[],
        new_capabilities=['Pinned ContentCatalog overlay','R17 original RemoveModifier policy bridge','Bounded JsonEnum source dictionary reader/resolver','Monster AI branch 14 reader'],
        task_evidence=[dict(root=r['root'],hash=r['original_task_hash'],original_node=r['original_task']) for r in rows],
        native_evidence=native,investigation_budget=dict(method_limit=30,methods_consulted=len(native['methods']),max_chain_depth=8),
        limitations=notes,no_second_executor=True,no_original_IR_mutation=True))
    storage=Path('D:/HSR_Battle_Agent/source_snapshots')
    manifests=[]
    for p in sorted(storage.glob('*/**/*MANIFEST.json')):
        manifests.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size))
    control('generic_runtime_camera_provider_status_v1',dict(unresolved_before=68,unresolved_after=68,
        source_resolved=0,bodies_decoded=0,runtime_semantics_supported=0,
        approved_storage_manifests=manifests,
        status='BLOCKED_ORIGINAL_OWNING_PROVIDER_ARTIFACT_REQUIRED',
        required='Pinned full-client owning Camera archive/provider and exact caller key-to-body scope mapping. Known fixed snapshot and runtime-context inventory do not provide that mapping.',
        evidence=read(OLD/'character/ranking_summary.json'),tickets=camera,
        no_blind_path_search=True,no_automatic_skip=True))
    control('generic_runtime_jsonenum_source_status_v1',dict(unresolved_sites_before=3,unresolved_sites_after=0,
        original_keys_unchanged=True,provider=provider,resolved_sites=sites,source_values_recovered=3,
        effective_native_oracle='NOT_VALIDATED',runtime_semantic_task_completion_from_provider=0,
        evidence='Global 0x9BF82B0 literal 43608 -> exact path; 0x1E6D7C30 dictionary delegates; category cache construction 0x1E6D7D20; reverse lookup 0x1E6D79B0; Parse resolver 0x1E6D6E90. Original strings, not guessed integer enums.'))
    control('generic_runtime_monster_original_execution_v1',dict(denominators=denominator,exact_actions=monsters,
        completed_before=0,completed_after=0,source_backed_AI_rules_executed=0,notes={k:notes[k] for k in ('SetTeamFormation','ByDistance')},
        admission='Existing R22 Monster admission and R15 only; FIRST_PERMISSION_REFERENCE is not source AI'))
    control('generic_runtime_monster_ai_reader_v1',dict(**ai,milestone='ORIGINAL_MONSTER_AI_BODY_FULLY_DECODED',
        dispatch='Serialized discriminator 14; dec eax -> table index 13 at 0x1E50C850 -> 0x1E4E5580 ChoseSequencedSkillAxis',
        action='Original UseSequencedSkill reader 0x1EBABBE0; source 1002013/1002014/1002040 ownership retained',
        executable_policy=False,source_semantics_completely_evidenced=False))
    control('generic_runtime_real_content_gap_ledger_v2',dict(historical_v1=oldledger,denominators=denominator,
        character_reference_cohort=rows,JsonEnum_source_sites_resolved=sites,
        source_native_semantic_task_gaps_closed=0,reference_policy_task_sites_advanced=2,
        monster_AI_reader_gaps_closed=1,AI_record_fully_decoded=True,
        remaining=notes,full_character_transitions=0,full_monster_actions=0,native_effective_validated=0))
    tests={n:read(AUDIT/'tests'/(n+'.json')) for n in ('battle_ir','battle_sandbox','R21','R27','R28')}
    assert all(t['exit_code']==0 for t in tests.values())
    inherited=read(AUDIT/'tests/inherited_exact_input_receipts.json')
    write('final_tests.json',dict(fresh=tests,inherited=inherited,
        distinction='651 inherited runtime cases (including 449 R12-R26 focused cases) revalidated with identical tested bytes, not rerun. Fresh R27 and R28 shown separately. No unfinished suite reported PASS.'))
    table='\n'.join('| '+r['root']+' | '+str(r['before'])+' | '+str(r['after'])+' | '+r['after_blocker']+' |' for r in rows)
    text=f'''# R28 original combat semantics

CR `{CR}`. Starting HEAD `{gate['head']}`, branch `terra/implementation`.

Verdict: **ORIGINAL_COMBAT_EXECUTOR_COVERAGE_ADVANCED**, limited to exact provider/reader gain and explicitly separate reference policy replay progress. **ORIGINAL_MONSTER_AI_BODY_FULLY_DECODED** independently established. Full canonical character transitions, original Monster actions completed, source-backed AI rules executed and native validated outcomes all remain **0**. Native lifecycle semantics have not been recovered by supplying reference policy.

The opt-in, pinned `data/overlays/r28_4651_v1/manifest.json` carries seven unchanged original Phase IR bodies in a deterministic compressed payload, source shard hashes/spans, parent dependencies, build and reader implementation identities. The production `catalog_overlay.load_overlay` validates payload, identities, graph and IR hashes against the existing catalog. Frozen catalog files, M10-M15, ScenarioCompiler and strict admission remain unchanged. No second execution subsystem is introduced.

| Original canonical parent | R27 completed tasks | R28 reference cohort | Actual next blocker |
| --- | ---: | ---: | --- |
{table}

All seven R27 initial states/commands reproduced their original final runtime hashes before reference policy changes. Fugue and Jade then used the same generic bridge into existing R17 RemoveModifier, selecting by the original serialized target/name, with explicit callback policy and no injected instance. Each advances exactly one original task to its next AddModifier gap. These are reference scenario policy bindings, **not source-native modifier completeness**. The five other parents retain their original blocker. Huohuo basic (53 completed tasks) and Bronya ultimate-related control (2) remain the approved separate Camera-blocked controls, unchanged and hash revalidated.

The exact JsonEnum provider was available in approved offline storage after recovering the native literal: `Config/GlobalConfig/JsonEnumDefineConfig.json`, binary `BakedConfig/Config/GlobalConfig/JsonEnumDefineConfig.bytes`, span **63722878–63732296**, shard SHA-256 `12884d3c8b1907d3a68c922d75655981d0348cd449381c1ba286f6f06e7287be`. All **9418 bytes** decode, repeat and byte-round-trip. The native generic delegates prove category/config and string/int dictionaries. Cache construction places category values in indexed slots; reverse lookup resolves numeric IDs to original strings. Kafka `[4,1]` twice resolves `DOT`; Sampo `[4,4]` resolves `DOT_Poison`. Provider sites unresolved **3 → 0**. Their original serialized keys/IR hashes stay unchanged; results are sidecar resolutions. The reusable JsonEnumProvider loads the pinned compressed provider from the overlay. Unknown or ambiguous keys fail. Damage/property/projectile runtime completion is not implied.

The original 140-byte `Monster_Common_SequenceThree_AI` now consumes **27101070–27101210**, graph hash `{ai['result']['graph_hash']}`. The bounded factory addition handles exactly serialized branch 14, `ChoseSequencedSkillAxis`, plus the original `UseSequencedSkill` action branch. Unknown dispatch variants remain gaps. The decoded graph preserves nested types, variables, condition/action fields, owner linkage and structural round trip. This proves a complete original AI body, **not executable priorities, weights, cooldowns or skill-selection policy**.

The exact Monster chains 1002013→100201301, 1002014→100201401 and 1002040→100204001 replay unchanged through existing R20/R22/R15. Two still stop at SetTeamFormation, one at ByDistance; action completions **0 → 0**. Field identities and same-build readers are retained in `target_types.json` and native descriptions. Team formation has config, servant, center and member-counting fields, so R20 participant order cannot stand in for its state. ByDistance needs original From/To selectors plus spatial authority, units, radius behavior, comparison binding and rounding; no coordinates or zero fallback were supplied. No authored enemy substitution occurred.

Camera acquisition stopped at the approved storage/provider boundary, without repeating R23 path guesses: unresolved original bodies **68 → 68**, resolved/decoded/executable camera bodies 0. The required artifact is the exact original owning full-client provider/archive and caller key-to-body mapping. JsonEnum, unlike Camera, was located through an exact native provider identity and decoded.

The three new task families remain unsupported: Lynx SetDynamicValueByProperty needs context scope and property-provider binding; Klara SetDynamicValueByCharacterCount needs selector/predicate iteration context, alive/default semantics and write ownership; Sampo FireProjectile needs projectile event/continuation and targeting semantics. Exact bodies and field metadata alone do not justify execution. Herta AddModifier needs an application/definition/listener initialization contract, not an arbitrary existing instance. Kafka retains per-task damage role/stage/provider gaps in the existing R18/R19 pipeline. Full task nodes, source spans, hashes, operand fields and parent/child execution ownership are saved in per-parent before/after traces and executor control.

Investigation budget: 30 methods maximum, 8 layers per chain. Actual method evidence entries: **{len(native['methods'])}** (including inherited evidence reused). No global asset extraction, game launch or live attachment. Frozen denominators remain 632 combat roots, 160 joined roots, 161 joined rows; 660 ownership rows, 309 owner/config joins, 306 root joins. Historical 73 and stable 72 are separate. Seven Phase bodies/220 spans and four Monster Ability bodies remain their original cohorts; no claim that all 160 roots gained bodies.

Fresh tests: battle_ir **586**, battle_sandbox **918**, R21 **21**, R27 **8**, R28 **7**, all exit code **0**. R28 validates original provider sites, typed unknowns/corruption, bounded reader failures, AI full read, two actual original parent replays, unchanged task operands and overlay hashes. The existing **651 runtime cases** including the **449 R12-R26 focused cases** are **revalidated prior PASS, not a fresh full-suite run**: every recorded tested input hash still matches. Prior R22 A-L, R24 defense, R25 E01-E18, R26 P01-P20/contracts, frozen hashes and R27 package members were likewise pinned/verified. The prior runtime run cost about 2821 seconds; it was not needlessly repeated. An initial fresh IR run failed five temporary-directory permission checks; its exit 1/log are retained. It was rerun in a repository-local temp directory and all 586 pass. Every final receipt has exact command, timestamp, actual exit code/count and source/input hash manifest. No interrupted work is called PASS.

Clone, JSON snapshot, hash and public command replay pass on the seven selected parents and three unchanged Monster actions; source decode and provider byte round trip repeat. Native policy cohort hashes are not conflated with the two changed reference-policy hashes. Starting files and unrelated dirty files remain byte-identical. Frozen drift **0**. Git writes **NONE**.

Recommended R29: recover the exact task executor dispatch/default context for Lynx/Klara and bridge to R19 without changing serialized operands; bind original AddModifier definitions/events before claiming native modifier progress; use the recovered JsonEnum provider while closing Kafka damage operands; implement the original sequenced-skill AI decision only after stepper/state and skill-trigger linkage are evidenced. Then formation/spatial source authority and Camera owning provider acquisition. Beam/MCTS remain deferred.

Reproduce with `python tools/runtime/r28_execution.py provider`, `ai`, `characters`, `monsters`; `python tools/runtime/r28_validation.py inherited`; and `python tools/runtime/r28_validation.py fresh`. Native additions are opt-in `r28_sources.cjs`; provider descriptor logs and caches are included. Never regenerate the starting gate or overwrite R27 audits. Reconstructing reader evidence requires the approved pinned same-build snapshot, while the promoted overlay is reusable without re-extraction.

Production additions: `battle_ir/catalog_overlay.py`, `battle_ir/jsonenum_provider.py`, `battle_runtime/original_bindings.py`; pinned overlay data; one R28 test module. Remaining outputs are CR-owned tooling, seven controls and audit evidence. No existing production file changed.

Handoff archive is `{CR}_changed_files.zip` in `D:/HSR_Battle_Agent/agent_handoffs`. Exact members/sizes/SHA-256 are in its manifest; separate verification includes ZIP CRC and full archive SHA-256. Raw game archives/full binaries, prior audit trees, unrelated files and test temp directories are excluded.
'''
    REPORT.write_text(text,encoding='utf8')
    write('final_summary.json',dict(verdict='ORIGINAL_COMBAT_EXECUTOR_COVERAGE_ADVANCED',
        starting_head=gate['head'],full_character_skills=0,full_monster_actions=0,AI_bodies_fully_decoded=1,
        AI_rules_executed=0,native_validated_outcomes=0,source_JsonEnum_sites_resolved=3,
        reference_task_sites_advanced=2,tests=tests,git_writes='NONE'))
    owned=[ROOT/'src/hsr_battle_agent'/n for n in ('battle_ir/catalog_overlay.py','battle_ir/jsonenum_provider.py','battle_runtime/original_bindings.py')]
    owned += [ROOT/'tests/battle_runtime/test_behavior_r28.py',REPORT]
    owned += list((ROOT/'tools/runtime').glob('r28_*'))
    owned += list((ROOT/'data/overlays/r28_4651_v1').glob('*'))
    names=['original_skill_semantics_v1','original_task_executor_v1','camera_provider_status_v1','jsonenum_source_status_v1','monster_original_execution_v1','monster_ai_reader_v1','real_content_gap_ledger_v2']
    owned += [CONTROL/('generic_runtime_'+n+'_20261022_001.json') for n in names]
    owned += [p for p in AUDIT.rglob('*') if p.is_file() and 'test_tmp' not in p.parts and p.suffix!='.zip' and p.name not in ('handoff_manifest.json','handoff_verification.json','delivery.json')]
    files=sorted(set(owned))
    manifest=dict(change_request=CR,files={p.relative_to(ROOT).as_posix():dict(size=p.stat().st_size,sha256=sha(p)) for p in files})
    write('handoff_manifest.json',manifest)
    files.append(AUDIT/'handoff_manifest.json')
    archive=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert sorted(z.namelist())==sorted(p.relative_to(ROOT).as_posix() for p in files)
        verified={n:dict(size=len(z.read(n)),sha256=hashlib.sha256(z.read(n)).hexdigest(),CRC=z.getinfo(n).CRC) for n in z.namelist()}
        for n,pin in manifest['files'].items():assert verified[n]['sha256']==pin['sha256'] and verified[n]['size']==pin['size']
    write('handoff_verification.json',dict(archive=str(archive),sha256=sha(archive),CRC='PASS',members=verified))
    print(archive,sha(archive),len(files),flush=True)


if __name__=='__main__':main()
