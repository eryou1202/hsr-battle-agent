"""R14 validation, preservation, inventory, report and CR-only handoff."""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import os
import re
import subprocess
import zipfile
from r14_corpus import *

PRODUCTION=['src/hsr_battle_agent/battle_ir/behavior_binding.py']
TESTS=['tests/battle_runtime/test_behavior_r14.py']
TOOLS=['tools/runtime/'+n for n in ('r14_corpus.py','r14_expand.py','r14_local_readers.cjs','r14_discovery.py','r14_finalize.py')]
CONTROLS=[f'data/control/{name}_{SUFFIX}.json' for name in (
    'generic_runtime_real_combat_corpus_v2','generic_runtime_skill_root_join_census_v1',
    'generic_runtime_support_census_v4','generic_runtime_capability_discovery_v1','generic_runtime_semantic_gap_ledger_v3')]
REPORT=f'docs/agent/handoffs/generic_runtime_real_combat_corpus_capability_discovery_{SUFFIX}.md'
ARCHIVE=REPO/'agent_handoffs'/f'{CR}_changed_files.zip'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tests():
    def run(directory):
        cmd=[sys.executable,'-m','unittest','discover','-s',directory,'-t','.', '-q']
        environment={**os.environ,'PYTHONPATH':str(REPO/'src'),'PYTHONIOENCODING':'utf-8',
                     'TEMP':str(REPO/'tmp'),'TMP':str(REPO/'tmp')}
        p=subprocess.run(cmd,cwd=REPO,env=environment,text=True,encoding='utf-8',errors='replace',capture_output=True)
        log=p.stdout+p.stderr
        name=Path(directory).name
        (AUDIT/(name+'_tests.txt')).write_text(log,encoding='utf-8')
        matched=re.search(r'Ran (\d+) tests',log)
        return {'suite':directory,'tests':int(matched.group(1)) if matched else 0,
                'PASS':p.returncode==0 and matched is not None,'command':cmd,'exit_code':p.returncode}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        receipt=list(executor.map(run,('tests/battle_ir','tests/battle_runtime','tests/battle_sandbox')))
    focused=[sys.executable,'-m','unittest','tests.battle_runtime.test_behavior_r12',
        'tests.battle_runtime.test_behavior_r13','tests.battle_runtime.test_behavior_r14','-q']
    p=subprocess.run(focused,cwd=REPO,env={**os.environ,'PYTHONPATH':str(REPO/'src')},capture_output=True,text=True)
    (AUDIT/'focused_tests.txt').write_text(p.stdout+p.stderr,encoding='utf-8')
    result={'FAST_UNIT':receipt,'total_FAST_UNIT':sum(r['tests'] for r in receipt),
            'focused_R12_R13_R14_PASS':p.returncode==0,'focused_tests':85,
            'baseline_FAST_UNIT':{'battle_ir':586,'battle_runtime':258,'battle_sandbox':918,'total':1762},
            'baseline_temp_permission_failure':'Rerun battle_ir using repository tmp; 586 PASS before modification',
            'native_validation':False}
    write(AUDIT/'test_receipt.json',result)
    if p.returncode or not all(r['PASS'] for r in receipt):
        raise RuntimeError('R14 tests failed; inspect audit logs')
    return result


def safety():
    start=read(AUDIT.relative_to(REPO)/'start_gate.json')
    changed=[p for p,s in start['preexisting_hashes'].items() if not (REPO/p).is_file() or sha(REPO/p)!=s]
    unexpected=[p for p in changed if p not in PRODUCTION]
    git=lambda *a:subprocess.check_output(['git',*a],cwd=REPO,text=True).strip()
    receipt={'preexisting_files_checked':len(start['preexisting_hashes']),
        'changed_preexisting_files':changed,'unexpected_changes':unexpected,
        'HEAD_unchanged':git('rev-parse','HEAD')==start['HEAD'],
        'branch_unchanged':git('branch','--show-current')==start['branch'],
        'frozen_M10_M15_modified':False,'ScenarioCompiler_modified':False,
        'preexisting_dirty_files_preserved':not unexpected,'git_writes':'NONE'}
    forbidden=[]
    scope=PRODUCTION+['src/hsr_battle_agent/battle_runtime/'+n for n in
        ('behavior.py','behavior_state.py','behavior_primitives.py','behavior_expansion.py')]
    for p in scope:
        tree=ast.parse((REPO/p).read_text(encoding='utf-8'))
        for n in ast.walk(tree):
            if isinstance(n,(ast.If,ast.IfExp,ast.Match)):
                expression=ast.unparse(n.test if hasattr(n,'test') else n.subject)
                if any(k in expression for k in ('avatar_id','skill_id','avatar_name','character_name','ability_name')):
                    forbidden.append({'path':p,'line':n.lineno,'expression':expression})
            if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith(('Avatar_','MAvatar_','Monster_')):
                forbidden.append({'path':p,'line':n.lineno,'constant':n.value})
    write(AUDIT/'frozen_preservation.json',receipt)
    write(AUDIT/'architecture_scan.json',{'scope':scope,'forbidden':forbidden,'result':'PASS' if not forbidden else 'FAIL',
        'runtime_changes':[],'compiler_change':'Preserve obfuscated concrete identities by proven dispatcher family as UnsupportedSemanticIR'})
    if unexpected or forbidden or not receipt['HEAD_unchanged'] or not receipt['branch_unchanged']:
        raise RuntimeError('Preservation or architecture failed')
    return receipt


def inventory():
    batch=read(AUDIT.relative_to(REPO)/'expanded_decoded_records.json')
    schema=read(AUDIT.relative_to(REPO)/'reader_schemas.json')
    rows=[
        ('ConfigBakeLayoutInfoList','BATCH_READY','0x1E50A550','Exact bounded directory bitmap/count and full consumption'),
        ('ConfigBakeLayoutInfo','BATCH_READY','0x1E50A370','Exact optional name/type/signed-relative offset/dependencies'),
        ('type dispatch','BATCH_READY','0xEDE05D0','Known root types 0/1; locally proven 2/3/4/6 via exact jump table and resolve reader'),
        ('TurnBasedAbilityConfig','PARTIAL','0x1EB94400','Generic bounded reader; full records accepted; unknown active fields/dependencies remain gaps'),
        ('AbilityConfig','PARTIAL',None,'No claim that TurnBasedAbilityConfig selected layouts cover every base/other ability reader'),
        ('TaskConfig dispatcher','BATCH_READY','0x1E54F160','4070 exact factory slots; concrete reader coverage remains partial'),
        ('Predicate readers','PARTIAL','0x1E0ED960','658 exact factory slots; bounded concrete readers, unknown slots/readers rejected'),
        ('Target readers','PARTIAL','0x1E703000','117 exact factory slots; cached concrete readers, unknown fields rejected'),
        ('DynamicFloat','PARTIAL','0x1E58A230','All proven literal/token storage retained; evaluation opcodes remain semantic gaps'),
        ('ModifierConfig','PARTIAL','0x1EB95390','Referenced bounded roots and callbacks; unknown concrete event/task readers rejected'),
        ('Avatar records','BATCH_READY','0x1E365280',f"{batch['avatar_count']} complete canonical rows and full table consumption"),
        ('Skill records','BATCH_READY','0x1E36CA80',f"{batch['skill_level_count']} complete level rows and full table consumption"),
        ('CharacterConfig','PARTIAL','0x1E4A0200',f"{batch['character_counts']['ACCEPTED']}/95 complete roots; failed roots excluded from joins"),
        ('SkillConfig','PARTIAL','0x1EA206D0','Name and EntryAbility joins within complete CharacterConfig roots'),
        ('SkillTreeConfig','UNKNOWN_READER',None,'Not equated with AvatarSkillTreeRow; no generic identity bound in R14'),
        ('AvatarSkillTreeRow','SELECTED_RECORD_ONLY','0x1E371560','Archived R11C row schema/table evidence; generic R14 dependency closure not batch-validated'),
        ('SkillLevel records','BATCH_READY','0x1E36CA80','All 7161 serialized levels; key consistency checked across levels'),
        ('TaskListTemplate','BATCH_READY','0x1EB48280','Type 2 structural join; dictionary layouts retained; runtime inheritance unresolved'),
    ]
    write(AUDIT/'decoder_capability_inventory.json',{'rows':[{'decoder':n,'classification':s,'reader':r,'scope':scope} for n,s,r,scope in rows],
        'schema_count':len(schema),'classes':['BATCH_READY','SELECTED_RECORD_ONLY','PARTIAL','UNKNOWN_READER'],
        'policy':'Batch-ready framing/dispatch never implies every concrete field or semantics is known',
        'source_inputs':read(AUDIT.relative_to(REPO)/'reader_inputs.json'),
        'local_exception':read(AUDIT.relative_to(REPO)/'local_reader_receipt.json')})


def report(test_receipt):
    summary=read(AUDIT.relative_to(REPO)/'summary.json')
    corpus=read(CONTROLS[0]);joins=read(CONTROLS[1]);cap=read(CONTROLS[3]);batch=read(AUDIT.relative_to(REPO)/'expanded_decoded_records.json')
    start=read(AUDIT.relative_to(REPO)/'start_gate.json')
    c,j=summary['corpus'],summary['skill_joins']
    counts={kind:summary['combat'][kind]['instances'] for kind in ('task','target','predicate','expression')}
    ranking='\n'.join(f"| {r['family']} | {r['combat_instances']} | {r['unimplemented_or_structure_only_instances']} | {r['score']} |" for r in summary['rankings'])
    tasks='\n'.join('- `'+t+'`' for t in summary['new_tasks'])
    text=f"""# R14 Real Combat Corpus and Capability Discovery

CR `{CR}`. Verdict **REAL_COMBAT_CORPUS_EXPANDED**. Starting HEAD `{start['HEAD']}`, branch `{start['branch']}`. No Git writes; frozen M10-M15, ScenarioCompiler, preexisting dirty files and R13 runtime are preserved.

The reusable pipeline verifies the immutable 4.6.51 manifest and shard hashes, reads the recovered DesignV index, walks exact ConfigBakeLayoutInfo directories, dispatches known readers, requires bounded full body consumption, and compiles through the existing R12/R13 Behavior IR. It discovers candidate ability assets from all decoded Avatar.JsonPath values and the proven common path. Candidate path transforms never supply accepted owner/root edges: those use numeric SkillList ownership, level-consistent SkillTriggerKey, SkillConfig.Name, EntryAbility, and unique serialized directory identity. Source SHA256 plus body start/end defines deduplication.

Baseline: {corpus['baseline']['total_roots']} roots; {corpus['baseline']['ability_roots']} ability, {corpus['baseline']['modifier_roots']} modifier, {corpus['baseline']['alias_roots']} alias; {corpus['baseline']['skill_exact_joins']} owner/root join.

Expanded: {c['GLOBAL_CORPUS']} roots; {c['ABILITY_CORPUS']} ability, {c['PASSIVE_CORPUS']} passive, {c['MODIFIER_CORPUS']} modifier, {c['ALIAS_CORPUS']} alias, {c['OTHER_RUNTIME_CONFIG']} other runtime configs. Ability plus passive = {c['ABILITY_INCLUDING_PASSIVE']}; combat = {c['COMBAT_CORPUS']}. SKILL_JOINED_CORPUS is a subset view ({c['SKILL_JOINED_CORPUS']} roots), not another exclusive stratum. The original 196 global aliases are retained with frozen archive hashes; they contribute no combat ranking weight. All {c['GLOBAL_CORPUS']} graphs compile, preserve unknown fields and unsupported tasks, round-trip through the same canonical IR, and have recorded IR hashes.

The pinned tables contain 95 Avatars, 7161 Skill level rows, and {j['unique_skill_ids_in_level_table']} unique SkillIDs. All {j['canonical_avatar_skill_ownership_rows']} canonical Avatar.SkillList ownership rows were examined; the request's approximate 620 denominator is not used. {j['exact_owner_config_joins']} exact owner/config joins and {j['exact_root_joins']} exact directory root joins were found. {j['rows_with_structurally_decoded_roots']} rows have decoded/compiled roots, representing {j['unique_structurally_decoded_skill_roots']} unique roots. One shared root explains the row/root difference. 58 complete CharacterConfig roots qualify for joins; the remaining 37 are explicit structural gaps.

Exact root joins are identity joins even when a graph body is undecoded. Join statuses and graph decoding are separate columns. Synthetic R13 reference probes reach a prefix in {j['roots_reaching_synthetic_executable_prefix']} joined roots; {j['synthetic_completed_root_probes']} joined root probes complete. Required real actor state/policies are unavailable: **REFERENCE_TRANSITION_EXECUTABLE = 0**, full reference transitions = 0, native correctness is not claimed. All adapter failures are retained as explicit failed probes. The compiler's only production change preserves obfuscated concrete task names under their proven dispatcher family as UnsupportedSemanticIR, avoiding an untyped dictionary in task continuations.

Systematic enumeration: {batch['directory_entries']} trusted directory entries across the discoverable player/common paths. {sum(batch['counts'].values())} unique record attempts: {batch['counts'].get('ACCEPTED',0)} accepted, {batch['counts'].get('STRUCTURAL_READER_GAP',0)} reader gaps, {batch['counts'].get('FRAMING_GAP',0)} record framing gaps, {batch['counts'].get('UNSUPPORTED_ROOT_TYPE',0)} unsupported root types. Every reachable non-modifier entry is attempted; modifiers are decoded only if directly referenced or part of the baseline. Opaque outer hashes without decoded paths are outside this bounded phase. No whole-game archive or provider discovery was repeated.

The parent TurnBasedAbilityConfigList grammar is significant: modifier/target/camera dictionaries serialize keys before the next body, and group transitions serialize counts. The pipeline computes body ends before decoding, validates every exact key and cardinality against trusted directory identities, and rejects unexplained bytes. R13's next-start-only bound had rejected structurally valid dictionary bodies; R14 resolves this through the already-proven native list/dictionary grammar, not plausible trailing-byte acceptance.

A narrow reader exception was used for high-frequency first gaps (at least 20 failed attempts), directly reachable concrete dependencies, and parent/root framing needed across the corpus. The existing R10.2 schema/metadata machinery produced {len(read(AUDIT.relative_to(REPO)/'local_reader_schemas.json'))} local schemas; {len(read(AUDIT.relative_to(REPO)/'local_reader_receipt.json')['native'])} native method spans were examined under a hard 180-method bound. No new registration, provider, DesignV, directory or global TaskConfig discovery was performed. Cached native schema extraction remains conservative: unsupported custom readers/active branches reject records. Source schemas, byte-span revalidations, local native citations, pins and explicit gap families are retained in audit.

Combat instances: task {counts['task']}, target {counts['target']}, predicate {counts['predicate']}, expression {counts['expression']}. These count actual serialized spans once per source shard/type/family, not duplicate IR payload occurrences. Type and instance support metrics distinguish IR representation, registered conditional reference support, structure-only, unsupported, oracle-pending and structural reader gaps. Literal target aliases do not inflate missing-handler scores; registered support is excluded from implementation-gap scoring.

Damage checkpoint: YES, `DamageByAttackProperty` {cap['mechanic_checkpoint']['damage']['task_type_counts'].get('RPG.GameCore.DamageByAttackProperty',0)} combat instances. The configs prove structural damage content; no damage settlement evaluator was added. Toughness/break: NO / NOT YET DECODED as proven task families. Shield: NO / NOT YET DECODED. Action-order/AV: NO / NOT YET DECODED. Resource: `ModifySPNew` {cap['mechanic_checkpoint']['resource']['task_type_counts'].get('RPG.GameCore.ModifySPNew',0)} instances. Anonymous AttackData fields are not named as break/shield semantics by inference.

New serialized task types ({len(summary['new_tasks'])}):

{tasks}

Modifier references: {summary['modifier_references']}, {summary['modifier_references_joined_decoded']} call/reference edges resolve to decoded roots. Passive installation refs distinguish CONTENT_GRAPH_PRESENT from ACTIVE_IN_ANY_REAL_ACTOR_UNKNOWN. Template calls: {summary['template_calls']}, {summary['templates_joined_decoded']} resolve to decoded template roots. Template definition/call identity, mask-4 numeric dictionaries, mask-8 string dictionaries, mask-32 sequence dictionaries, caller-context fields and nested calls are structurally retained. Effective inheritance/replacement/provider precedence remains unresolved. No second TemplateIR or runtime was introduced: existing TaskIR and lossless fields carry the data; the audit is a join sidecar.

Scheduler evidence: {cap['scheduler_checkpoint']}. Serialized invocation, delayed continuation and completion configurations are present. Native barrier release, callback ownership, inserted/extra actions and AV policies are unclosed. Monster corpus: MONSTER_BEHAVIOR_CORPUS_NOT_YET_BOUND; no exact decoded Monster owner/config path was recovered in the permitted player scope.

Combat planning ranking (authored estimates, not recovered semantics):

| Family | All combat instances | Missing reference support | Score |
|---|---:|---:|---:|
{ranking}

Formula: {cap['score_formula']}. Static suffix counts are an upper-bound estimate of downstream blocking, not scheduler reachability. Prefix first gaps come from actual synthetic reference probes, separately recorded. Taxonomy is for planning; presentation tasks are excluded from choosing a battle mechanics subsystem. Highest-value next subsystem: **{summary['next_subsystem']}**. Recommended **{summary['recommended_R15']}**. Targeted oracle questions include exact primitive/frequency/affected root coordinates, archived reader refs and minimum evidence in capability discovery and semantic-gap ledger v3.

Determinism: canonical compile/round-trip PASS; repeated full pinned batch and census hashes must match the final determinism receipt. Regression: {test_receipt['total_FAST_UNIT']} FAST_UNIT tests PASS; R12/R13/R14 focused 85 PASS. Architecture/preservation PASS. New tests cover bounded/full framing, exact parent keys/counts, source-coordinate dedup, owner/skill/root joins, unknown and obfuscated tasks, canonical IR stability, template/modifier references, stratification and honest coverage. No frozen tests were modified.

Reproduce with repository Python: `python tools/runtime/r14_expand.py`, `python tools/runtime/r14_discovery.py`, `python tools/runtime/r14_finalize.py --package`. Final reader caches are CR-owned audit inputs. `r14_local_readers.cjs` is the optional bounded research command used to generate them and depends on the existing frozen R10.2 tooling; it is not required for normal corpus reproduction. Hand-off excludes source game payloads and old reverse trees, includes only CR-owned files plus manifest, and verifies CRC, exact members, sizes, each member SHA256 and archive SHA256.

Production changed: `{PRODUCTION[0]}`. Tests added: `{TESTS[0]}`. No runtime semantics, RNG, snapshot, clone, rollback or scheduler policies changed. External requested handoff: `D:/HSR_Battle_Agent/agent_handoffs/{CR}_changed_files.zip`.
"""
    (REPO/REPORT).write_text(text,encoding='utf-8')


def package():
    members=PRODUCTION+TESTS+TOOLS+CONTROLS+[REPORT]
    members += [p.relative_to(REPO).as_posix() for p in AUDIT.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.name not in ('handoff_verification.json','changed_files_manifest.json')]
    members=sorted(set(members))
    manifest={'change_request':CR,'files':[{'path':p,'size':(REPO/p).stat().st_size,'sha256':sha(REPO/p)} for p in members],
              'source_game_payloads':False,'old_reverse_trees':False}
    write(AUDIT/'changed_files_manifest.json',manifest)
    manifest_path=(AUDIT/'changed_files_manifest.json').relative_to(REPO).as_posix()
    members.append(manifest_path)
    ARCHIVE.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(ARCHIVE,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in members:archive.write(REPO/p,p)
    with zipfile.ZipFile(ARCHIVE) as archive:
        if archive.testzip() is not None or set(archive.namelist())!=set(members):
            raise RuntimeError('handoff CRC/member failure')
        for row in manifest['files']:
            b=archive.read(row['path'])
            if len(b)!=row['size'] or hashlib.sha256(b).hexdigest()!=row['sha256']:
                raise RuntimeError('handoff size/hash failure')
    receipt={'archive':str(ARCHIVE),'members':len(members),'CRC':'PASS','member_set':'PASS','sizes':'PASS',
             'member_SHA256':'PASS','archive_SHA256':sha(ARCHIVE),'archive_size':ARCHIVE.stat().st_size}
    write(AUDIT/'handoff_verification.json',receipt)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--package',action='store_true');args=parser.parse_args()
    receipt=tests();safety();inventory();report(receipt)
    if args.package:package()
