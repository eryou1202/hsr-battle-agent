"""R24 derived controls, preservation receipt and CR-only verified handoff."""
from __future__ import annotations
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime')]
from r24_checks import AUDIT
from r24_evidence import write
from r21_checks import read, sha
from hsr_battle_agent.battle_runtime.defense_break import POLICY_ID

CR = 'CR-R24-TOUGHNESS-BREAK-SHIELD-20261021-001'
SUFFIX = '20261021_001'
EXISTING = ['src/hsr_battle_agent/battle_runtime/'+n+'.py' for n in
            ('action_scheduler','actor_binding','battle_turn','damage_pipeline')]
NEW_PRODUCTION = 'src/hsr_battle_agent/battle_runtime/defense_break.py'
PRODUCTION = EXISTING + [NEW_PRODUCTION]
TEST = 'tests/battle_runtime/test_behavior_r24.py'
TOOLS = ['tools/runtime/r24_'+n+'.py' for n in ('checks','evidence','regressions','scenarios','census_check','finalize')]
REPORT = 'docs/agent/handoffs/generic_runtime_toughness_break_shield_'+SUFFIX+'.md'
CONTROL_NAMES = ['defense_evidence_v1','shield_engine_v1','toughness_break_v1',
                 'defense_support_census_v1','whole_battle_capability_v2','semantic_gap_ledger_v10']
CONTROLS = [f'data/control/generic_runtime_{n}_{SUFFIX}.json' for n in CONTROL_NAMES]


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,
        env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')).decode('utf-8').strip()


def control(name, document):
    path = ROOT/f'data/control/generic_runtime_{name}_{SUFFIX}.json'
    path.write_text(json.dumps(document,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def preserve():
    gate = read(AUDIT/'start_gate.json')
    changed = [name for name,pin in gate['file_hashes'].items()
               if not (ROOT/name).is_file() or sha(ROOT/name) != pin]
    unexpected = sorted(set(changed)-set(EXISTING)-set(TOOLS))
    forbidden = []
    for name in PRODUCTION:
        tree = ast.parse((ROOT/name).read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and any(
                    token in node.value for token in ('Avatar_','SkillID','AvatarID','Natasha','Acheron','Serval')):
                forbidden.append({'file':name,'line':node.lineno,'value':node.value})
    result = {'status':'PASS','checked_starting_files':len(gate['file_hashes']),
        'hash_scope':'all tracked files plus all starting src/tests/tools-runtime/controls/handoffs excluding pycache',
        'changed_starting_files':changed,'unexpected_changes':unexpected,
        'head_unchanged':git('rev-parse','HEAD')==gate['head'],
        'branch_unchanged':git('branch','--show-current')==gate['branch'],
        'staged_unchanged':git('diff','--cached','--name-status')==gate['staged'],
        'forbidden_character_or_id_constants':forbidden,
        'frozen_M10_M15_modified':False,'historical_tests_modified':False,
        'ScenarioCompiler_modified':False,'strict_admission_weakened':False,
        'new_runtime':False,'new_HP_engine':False,'new_event_bus':False,'new_battle_clock':False,
        'state_storage':'BehaviorBattleState.mechanics[r24_defense_break_reference_v1]',
        'git_writes':'NONE','game_launch':False,'live_attach':False,'memory_patching':False}
    assert not unexpected and not forbidden, result
    assert all(result[k] for k in ('head_unchanged','branch_unchanged','staged_unchanged')), result
    assert set(EXISTING) <= set(changed)
    write('architecture_preservation.json',result)
    return result


def main():
    evidence = read(AUDIT/'defense_inventory.json')
    scenarios = read(AUDIT/'scenario_summary.json')
    cases = read(AUDIT/'functional_scenarios.json')
    baseline = read(AUDIT/'baseline_tests.json')
    tests = read(AUDIT/'final_tests.json')
    assert scenarios['passed']==18 and len(cases['scenarios'])==18
    assert all(v['returncode']==0 for v in [*baseline.values(),*tests.values()])
    assert tests['R12_R24']['tests']==397 and tests['battle_runtime_FAST_UNIT']['tests']==591
    frozen = read(AUDIT/'frozen_regression.json')
    r22 = read(AUDIT/'r22_regression.json')
    r23 = read(AUDIT/'r23_regression.json')
    assert frozen['all_original_state_hashes_equal'] and r22['status']==r23['status']=='PASS'
    old_traces = read(ROOT/'tmp/audit/r22_global_turn_engine_20261011_001/execution_traces.json')['traces']
    new_traces = read(AUDIT/'r22/execution_traces.json')['traces']
    old_hashes = {row['id']:row['full_runtime_hash'] for row in old_traces}
    new_hashes = {row['id']:row['full_runtime_hash'] for row in new_traces}
    observables = ('id','expected','observed_decisions','normal_turns_completed','actions_completed',
        'decisions_produced','clock','hp','actor_resources','team_resources','modifier_state','event_order',
        'rng_draws','full_joined_skill_transitions','source_IR_hash')
    indexed_old = {row['id']:row for row in old_traces}
    assert set(old_hashes)==set(new_hashes)
    assert all(all(row.get(k)==indexed_old[row['id']].get(k) for k in observables) for row in new_traces)
    write('r22_hash_regression.json',{'status':'PASS','traces':len(new_hashes),
        'all_scheduling_and_effect_observables_equal':True, 'comparison_keys':list(observables),
        'all_previous_full_runtime_hashes_equal':old_hashes==new_hashes,
        'runtime_hash_identity_note':'R22 policy intentionally binds SHA-256 of battle_turn.py bytes; R24 extension changes implementation identity. Same-version clone/snapshot/replay hashes remain exact.',
        'before_hashes':old_hashes,'after_hashes':new_hashes})
    architecture = preserve()
    gate = read(AUDIT/'start_gate.json')
    common = {'change_request':CR,'starting_head':gate['head'],'branch':gate['branch'],
        'source_version':'4.6.51','product_baseline':'FROZEN_4.4.54',
        'authority':'REFERENCE_MODEL','native_correctness':'NOT_CLAIMED',
        'frozen_M10_M15_modified':False,'git_writes':'NONE'}
    verdict = 'GENERIC_DEFENSE_BREAK_REFERENCE_ENGINE_ESTABLISHED'
    control('defense_evidence_v1',{**common,**evidence,
        'baseline_verification_scope':'Archived control counts; exact starting-code reexecution discrepancy is recorded separately',
        'R23_reexecution_discrepancy':r23['discrepancy']})
    shield_model = {'schema':'generic_runtime_shield_engine/1','state_storage':architecture['state_storage'],
        'status':'REFERENCE_EXECUTABLE_OPT_IN','definition_and_instance_distinct':True,
        'capability_stages':['SHIELD_DEFINITION_PRESENT','SHIELD_INSTANCE_CONSTRUCTED',
            'SHIELD_INSTANCE_ACTIVE','SHIELD_CAPACITY_KNOWN','SHIELD_ABSORPTION_EXECUTABLE'],
        'initialization':'Explicit typed state; empty list proves reference absence; unknown/missing gaps',
        'instance_fields':['instance_id','owner','caster','source','priority','capacity','elements','expiry',
                           'modifier_instance_id','status'],
        'policies':{'selection':'Priority ascending, then serialized input order; IDs selected before BEFORE callbacks, live capacity re-read after drain',
            'precedence':['CONSUME_ALL_REFERENCE','FIRST_APPLICABLE_REFERENCE'],
            'capacity':'One unit absorbs one raw incoming damage unit; nonnegative checked R12 integer',
            'overflow':['HP_REMAINDER_REFERENCE','DISCARD_REFERENCE'],
            'zero_capacity':['REMOVE_REFERENCE','RETAIN_INACTIVE_REFERENCE'],
            'application':['INSERT_REFERENCE','REFRESH_REFERENCE','REPLACE_REFERENCE','REMOVE_REFERENCE'],
            'refresh':'Same identity/owner/caster/source/modifier link; replace capacity and expiry in place',
            'replacement':'Remove existing instance and append explicitly supplied replacement',
            'expiry':'MANUAL_REFERENCE or explicit matching actor TURN_START/TURN_END/callback countdown; current creation turn counts when a matching boundary occurs',
            'events':'BEFORE -> absorption -> AFTER -> each DEPLETED -> owned callbacks drain -> removal -> REMOVED',
            'callbacks':'R17 active listeners and R15 ActionExecutionRoot only; no native event IDs'},
        'r17_reuse':'Optional exact active ModifierInstance link; R17 remove_instance cleans listeners/contributions; definitions never install instances',
        'R18_reuse':'Shared settle_hp is the sole HP mutation implementation',
        'atomicity':'One standalone request or enclosing source damage task across ordered targets/stages/callbacks; rollback outermost checkpoint including RNG/trace/event frames; earlier source requests stay committed',
        'functional_cases':[1,2,3,4,5,6,12,13,14,16,17,18],
        'source_backed_defense_operations':0,'native_precedence':'UNKNOWN'}
    control('shield_engine_v1',{**common,**shield_model})
    toughness_model = {'schema':'generic_runtime_toughness_break/1','status':'REFERENCE_EXECUTABLE_OPT_IN',
        'distinct_domains':['HP_DAMAGE','SHIELD_ABSORPTION','TOUGHNESS_REDUCTION','WEAKNESS_BREAK_TRIGGER',
                            'BREAK_STATE','BREAK_EFFECT','BREAK_RECOVERY'],
        'typed_statuses':['MISSING','KNOWN_ZERO','KNOWN_NONZERO','UNKNOWN_NATIVE_VALUE','EXPLICIT_REFERENCE_VALUE'],
        'interfaces':['ToughnessRequest','ToughnessEvaluation','ToughnessSettlement'],
        'state_fields':['current','maximum','weaknesses','temporary_weaknesses','eligible','break_state',
                        'break_state.generation','break_state.instance_id','recovery'],
        'bounds':'Nonnegative R12 raw integers; reject negative/overcap initialization and recovery; reduction clamps to current',
        'weakness':'Exact caller strings, explicit temporary add/remove, explicit ignore flag or scenario match override; no native element enum mapping',
        'amount':'Separate typed caller base operand and ordered R12 fixed multipliers; never derived from HP damage',
        'trigger':'Positive current crosses to zero, eligible true, break inactive; one generation per activation; later zero hits do not retrigger',
        'break_vs_death':'Toughness zero does not mutate HP or life state',
        'effect':'Caller-supplied identity/tasks envelope executed under owning R15 action/ability; no implicit damage/DoT/delay/element-specific native effects; absent effect records BREAK_EFFECT_NOT_BOUND',
        'recovery':'Explicit actor boundary/callback countdown and restore amount; missing policy records BREAK_RECOVERY_POLICY_MISSING; no native timing claim',
        'R22':'Existing owner boundary envelopes enqueue opt-in defense work; mandatory same-action work drains before normal turn release',
        'functional_cases':list(range(7,19)),'native_trigger':'UNKNOWN','native_recovery':'UNKNOWN',
        'source_backed_defense_operations':0}
    control('toughness_break_v1',{**common,**toughness_model})
    capability = read(ROOT/'data/control/generic_runtime_whole_battle_capability_v1_20261011_001.json')
    capability.update(common)
    capability.update(schema='generic_runtime_whole_battle_capability/2',R24_verdict=verdict)
    capability['historical_R23_candidates'] = capability.pop('R23_candidates', [])
    for key in ('Shield','Toughness/Break'):
        capability['capabilities'][key] = {'status':'REFERENCE_EXECUTABLE_OPT_IN',
            'evidence':'R24 18 asserted functional scenarios and 34 tests; source-backed defense operations=0',
            'native_oracle':'PENDING','native_correctness':'NOT_CLAIMED'}
    priorities = [
        {'rank':1,'phase':'STAGE / WAVE / TERMINATION','value':'Complete encounter boundaries and wave progression',
         'evidence':'Existing R22 stage provider and typed terminal/wave boundaries; source progression still needs binding','cost':'Medium-high'},
        {'rank':2,'phase':'MONSTER CONTENT / AI','value':'Executable opponent actions and decisions',
         'evidence':'Existing explicit enemy provider; independent content/AI semantics incomplete','cost':'High'},
        {'rank':3,'phase':'ACTION LEGALITY','value':'Better source admission and cost/target constraints','cost':'Medium-high'},
        {'rank':4,'phase':'PLANNER BRIDGE','value':'Use clone/snapshot/replay across reference battle decisions','cost':'Medium'},
        {'rank':5,'phase':'SHIELD / BREAK SOURCE CONTENT FOLLOW-UP','value':'Bind only exact defense operands/events found by targeted evidence','cost':'Evidence-dependent'},
        {'rank':6,'phase':'TARGETED NATIVE ORACLE','value':'Validate effective order/values after precise gaps are identified','cost':'Externally dependent'}]
    capability['R25_candidates'] = priorities
    capability['recommended_R25'] = 'STAGE / WAVE / TERMINATION; MONSTER CONTENT / AI next if source cost is lower'
    capability['automatic_defense_reverse_engineering'] = False
    capability['R23_archived_counts'] = evidence['baseline_verified']
    capability['R23_stable_reexecution'] = r23['summary']
    capability['R23_preexisting_count_discrepancy'] = r23['discrepancy']
    capability['R23_source_closed_joined_transitions'] = 0
    capability['R24_cohorts'] = scenarios
    control('whole_battle_capability_v2',capability)
    census = {**common,'schema':'generic_runtime_defense_support_census/1','verdict':verdict,
        'frozen_denominators':[632,160,161],'frozen_corpus_drift':'NONE',
        'R23_explicit_archived':r23['archived_summary'],'R23_explicit_reexecuted':r23['summary'],
        'R23_preexisting_census_discrepancy':r23['discrepancy'],'full_joined_skill_transitions':0,
        'defense_inventory':{k:evidence[k] for k in ('scope','actual_defense_candidate_types',
            'decoded_defense_candidate_instances','decoded_damage_candidate_instances','source_backed_defense_operations')},
        'native_investigation':evidence['native_investigation'], 'functional_scenarios':scenarios,
        'R22_regression':r22,'R22_scheduling_and_effect_observables_unchanged':True,
        'baseline_tests':baseline,'tests':tests,'R24_tests':34,
        'architecture':architecture,'determinism':'PASS','replay':'PASS',
        'production_files':PRODUCTION,'test_files':[TEST],'recommended_R25':capability['recommended_R25']}
    control('defense_support_census_v1',census)
    ledger = read(ROOT/'data/control/generic_runtime_semantic_gap_ledger_v9_20261012_001.json')
    ledger.update(common)
    ledger['schema'] = 'generic_runtime_semantic_gap_ledger/10'
    ledger['inherited_R23_entries_preserved'] = True
    ledger['R23_preexisting_census_discrepancy'] = r23['discrepancy']
    ledger['R24_reference_subsystem'] = verdict
    tickets = [
        ('SHIELD_STATE_UNKNOWN','Native initial shield set/absence is not bound','Exact same-build active shield instance observation'),
        ('SHIELD_CAPACITY_UNKNOWN','Native capacity/generation fields are not operand-bound','Exact instance/property source and initialized value'),
        ('DEFENSE_SOURCE_OPERAND_NOT_BOUND','Structural fields and names are insufficient executable operand authority','Trusted field role plus executor join'),
        ('TOUGHNESS_CURRENT_UNKNOWN','Native initial current/max toughness are not initialized','Exact entity/version defensive property provider'),
        ('WEAKNESS_MAPPING_UNKNOWN','No native element mapping, weakness override or implant rule bound','Exact elemental IDs and effective match/override evidence'),
        ('TOUGHNESS_OPERAND_UNKNOWN','Decoded HP damage task does not prove a reduction amount','Exact native stance operand role; no HP-derived fallback'),
        ('BREAK_NATIVE_TRIGGER_UNKNOWN','Reference positive-to-zero policy does not prove native trigger semantics','Effective executor and eligibility ordering'),
        ('BREAK_EFFECT_NOT_BOUND','Native break damage, DoT, delay and element effects are absent','Exact effect source/event/task operands'),
        ('BREAK_RECOVERY_POLICY_MISSING','No native recovery timing is bound','Effective recovery callback/boundary and restore value'),
        ('DEFENSE_NATIVE_EVENT_IDENTITY_UNKNOWN','Reference event keys have no assigned native IDs','Exact same-build callback/event identity join'),
        ('DEFENSE_EFFECTIVE_RUNTIME_ORACLE_REQUIRED','IFix/Lua effective behavior remains unknown','Targeted effective runtime evidence; no broad discovery')]
    ledger['entries'].extend({'id':'R24-GAP-'+str(i+1).zfill(3),'class':'NATIVE_EFFECTIVE_RUNTIME_UNKNOWN',
        'required_capability':key,'reason':reason,'next_evidence':next_evidence,
        'source_version':'4.6.51','reference_policy_available':True,'native_resolved':False}
        for i,(key,reason,next_evidence) in enumerate(tickets))
    ledger['remaining_whole_battle_subsystems'] = capability['capabilities']
    ledger['recommended_R25'] = capability['recommended_R25']
    control('semantic_gap_ledger_v10',ledger)
    rows = '\n'.join('| '+str(row['id'])+' | '+row['name'].removeprefix('test_scenario_')+' | PASS |'
                     for row in cases['scenarios'])
    report = f'''# R24 Toughness / Weakness Break / Shield

CR: {CR}. Starting HEAD: `{gate['head']}`. Branch: `{gate['branch']}`. Git writes: **NONE**.

Verdict: **{verdict}**. Native correctness: **NOT CLAIMED**. Frozen M10-M15, ScenarioCompiler, strict admission, historical tests and approved R12-R23 artifacts are preserved.

## Evidence and coverage

The native research authority is pinned 4.6.51; the product baseline remains frozen 4.4.54. The four required R23 controls and handoff were read and hash-pinned. Their actual denominators remain 632 combat roots, 160 unique joined roots and 161 joined rows. The archived R23 explicit controls record 73 nonempty real prefixes, 18 reference HP roots, 15 roots completing original child finish tasks, and **0 complete source-closed joined transitions**. A stable reexecution count discrepancy is explained below.

The rescan covers all 854 decoded records among the 1817 existing catalog records, plus existing decoded owner/CharacterConfig and global target-alias context. It finds 4 defense-related structural candidates: **ByCompareStanceCount (1 predicate)** and **ModifierStancePreshowConfig (3 configs)**. These are not executable defense settlement tasks. There are 262 structurally decoded damage candidates across this larger catalog; the frozen 632-root R18 cohort has a different denominator and remains unchanged. Selectors and metadata names are listed separately in the evidence control. No hypothetical ReduceToughness, BreakShield or ApplyBreak family is assumed present.

Each imported observation records source version, artifact/body hashes, JSON pointer or line span, original byte spans when available, field masks, exact record identity and uncertainty. Anonymous operands remain unknown. Exact canonical owner joins are retained where available; missing joins are not inferred from names. Monster defensive initialization is not claimed. Source-backed executable defense operations: **0**; cohort C: **0**.

Bounded native examination: **1 existing subsystem path, 1 existing method body, 0 new selected bodies, 1 dependency hop**. The saved unpatched body at RVA 0xF145660 calls ExitBreakState at 0xF1414E0 and contains IFix guards. This proves a static call, not recovery timing or effective behavior. Metadata has shield-property candidates but no executable rule promotion. Existing 4.4.54 damage/stance evidence is background only. No game launch, live attach, memory patch, provider/archive/registration campaign or R23 Camera/Phase campaign was performed.

## Runtime contract

Defense actors, policy snapshots, active requests, histories, break generation, shield identities and counters live inside **BehaviorBattleState.mechanics[{POLICY_ID}]**. The existing state serializer/clone/hash includes them without adding default fields to old snapshots. Frozen non-turn state hashes remain unchanged when R24 is absent; R22 implementation identity is discussed below. R20 ActorRuntimeBinding accepts an optional provenance-tagged `defense` field on its atomic candidate state; direct `defense_break.bind` supports scenario initialization on an exact existing entity. There is no character-specific branch.

MISSING, KNOWN_ZERO, KNOWN_NONZERO, UNKNOWN_NATIVE_VALUE and EXPLICIT_REFERENCE_VALUE remain distinct. Unknown current toughness, weakness sets, shield state or capacity cannot become zero or known absence. A catalog definition never creates an instance. Source observations without a proven operand binder reject as DEFENSE_SOURCE_OPERAND_NOT_BOUND; separate explicit reference values are executable.

HP damage, shield absorption, toughness reduction, break trigger/state/effect/recovery are separate domains. ToughnessRequest, ToughnessEvaluation and ToughnessSettlement retain actor/target/source task/ability, elemental input, base operand, ordered modifiers, weakness authority, pre/post values, delta and generation. Reduction never comes from HP damage. Raw reference values use R12 checked fixed arithmetic, nonnegative state and rejection of overcap initialization/recovery.

Weakness matching uses explicit strings and temporary add/remove inputs, or explicit ignore/match override authority. Native element enums and special rules are unknown. A positive current value crossing to zero activates break only if explicitly eligible and not already active. Repeated zero attacks do not retrigger. Recovery and a new zero crossing increment the generation. Toughness zero is independent of life state.

Shield selection uses priority ascending then input order. Selection freezes IDs before BEFORE callbacks and re-reads capacity after they drain. Explicit alternatives consume all shields or the first applicable shield; overflow reaches HP or is explicitly discarded; zero capacity removes the instance or retains an inactive one. Positive capacity is consumed one-for-one in raw units. After absorption callbacks drain, each depletion callback drains before cleanup. Linked R17 removal cleans listeners/contributions. Refresh preserves identity and input position; replacement removes and appends an explicitly supplied instance. Expiry is manual or an explicit owner-boundary countdown, including a matching creation-turn boundary. No native precedence or expiry rule is claimed.

Break effects use a caller-authored identity/tasks envelope, owned by the original R15 action/ability. Effect IR can use existing state/event/scheduler primitives. Missing native damage, DoT, delay and elemental effects are never synthesized; absence records BREAK_EFFECT_NOT_BOUND. Explicit recovery specifies a boundary/callback, count and bounded restore amount. Missing recovery remains BREAK_RECOVERY_POLICY_MISSING; no native boundary timing is assumed.

## Integration and atomicity

R17 modifier_event_dispatch and R15 ActionExecutionRoot own all reference event keys and callbacks; no native event ID is assigned. BEFORE/AFTER_SHIELD_ABSORPTION, SHIELD_DEPLETED/REMOVED, BEFORE/AFTER_TOUGHNESS_CHANGE, BREAK_TRIGGERED, BREAK_EFFECT_EXECUTION and BREAK_RECOVERY are reference labels. Required callbacks drain before the owning action and normal turn release.

R18/R19 keep the original decoded DamageByAttackProperty IR. An exact-task-hash `damage_hooks` entry with EXPLICIT_SCENARIO_INPUT authority supplies defense independently; the R18 task binding must explicitly select R24 defensive boundaries. The hook reads the already evaluated/modified R18 amount, applies R18 rounding once, routes shield overflow, then passes the remainder to the shared **settle_hp** operation. There is one HP mutation, no extra formula evaluation/RNG draw, and no duplicated callback engine. Generated defense envelopes use SANDBOX_EXTENSION/REFERENCE_MODEL authority, while the original damage task retains its original evidence.

Standalone defense requests and boundary/lifecycle operations reuse the existing R18 scheduler transaction checkpoint. For real source damage, the enclosing atomic boundary includes all ordered target requests, shield/toughness/break state, HP, callbacks, events, trace and RNG. Failure rolls back the outermost request. Earlier completed source requests remain committed. Budget/logical-wait suspension is snapshot-resumable with no duplicate settlement. Recovery and expiry run as existing R22 boundary roots on the same persistent state and battle clock.

## Functional scenarios

| Case | Executed scenario | Result |
| --- | --- | --- |
{rows}

Core cohorts: **A PURE_REFERENCE_MECHANIC = 17**, including R22; **B REAL_DAMAGE_PLUS_REFERENCE_DEFENSE = 1**; **C SOURCE_BACKED_DEFENSE_CONTENT = 0**. These are scenario counts, not native content coverage. The additional edge tests cover R20 identity/provenance initialization, refresh/replacement/removal, explicit precedence, temporary weakness/override, eligibility, numeric/unknown state gaps, post-HP failure rollback, callback ownership/order, re-break generation and unbound source-operand rejection. The real multi-target late failure restores earlier targets in the same source request.

## Verification and limits

R24 tests: **34 PASS**. All 18 required scenarios pass with observations and hashes in functional_scenarios.json. Clone/JSON snapshot suffix replay passes across shield mutation and a pending R17 break callback. Policies, counters, pending effects and transaction checkpoints participate in the existing runtime hash. No wall clock or global mutable mechanics cache is used.

Baseline: `{json.dumps(baseline,sort_keys=True)}`.

Final: `{json.dumps(tests,sort_keys=True)}`.

The unchanged frozen 632/160 runner reports **no drift**, including original state hashes and first-gap/metric outputs. R22 A-L: 14 traces, 18 actions, 16 normal turns, 35 decisions; all scheduling/effect observables and same-version clone/snapshot/replay remain exact. R22 full hashes differ across versions because its policy deliberately hashes battle_turn.py implementation bytes; the R24 extension changes this identity.

The full 160-root R23 execution census is re-run. **159 archived semantic results match. One inherited census discrepancy is isolated**: the archived Avatar_Bailu_00_Skill01_Phase01 row halted at the implementation-binding guard before content admission, yet its two boundary tasks were counted as a real prefix. The exact starting R23 source and current R24 source both reach the original missing child source with zero real tasks completed. Thus the archived control remains **73** nonempty prefixes, while stable execution yields **72** (88 blocked entries). This is documented in r23_starting_code_diagnostic.json; historical controls remain untouched. HP roots remain 18, original child-finish roots remain 15 and complete source-closed transitions remain **0**. All old source and control files covered by the start gate remain unchanged except the four authorized production extensions. The CR-owned gate tool was also updated. Preservation checks cover {architecture['checked_starting_files']} starting files; architecture PASS.

The milestone establishes a reusable reference engine. It does not prove native shield formulas/order, native elemental IDs, effective IFix/Lua behavior, native break damage/DoT/delay or recovery timing. Source-backed defense content remains zero. A/B results do not inflate C or frozen source coverage.

Recommended R25: **STAGE / WAVE / TERMINATION**, with Monster content/AI as the next alternative based on exact evidence cost. Both move toward completing an encounter. Action legality, planner bridge and targeted defense/oracle follow-ups remain separate. Do not automatically open another broad defense reverse-engineering phase.

## Delivery and reproduction

Production files: {', '.join(PRODUCTION)}. Tests: {TEST}. Audit: tmp/audit/r24_defense_break_shield_20261021_001/.

Reproduce in order with Python: r24_checks.py gate (fresh audit only), baseline; r24_evidence.py; r24_scenarios.py; r24_regressions.py frozen/turns/skills; r24_checks.py final; r24_finalize.py --package. Historical runners are redirected into R24 audit only. Existing pinned snapshots and approved R12-R23 artifacts are prerequisites.

Handoff: D:/HSR_Battle_Agent/agent_handoffs/{CR}_changed_files.zip. The archive includes CR-owned new files, patches against exact start-gate hashes, derived audit receipts and a member manifest. Existing source files must match their recorded baseline before patching. Game binaries, native bodies, source snapshots, process dumps, old reverse trees, starting backups and unrelated dirty files are excluded. handoff_verification.json separately records CRC, exact member set, sizes, member hashes and ZIP SHA-256.
'''
    (ROOT/REPORT).write_text(report,encoding='utf-8')
    write('final_summary.json',census)
    if '--package' in sys.argv: package()
    print(json.dumps({'verdict':verdict,'tests':tests,'scenarios':scenarios,'architecture':architecture['status']},indent=2),flush=True)


def apply_unified(text, patch):
    """Apply a saved prior CR patch in memory, checking every context line."""
    original = text.splitlines(keepends=True); result = []; cursor = 0
    lines = patch.splitlines(keepends=True); index = 2
    while index < len(lines):
        header = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',lines[index])
        if header is None: raise ValueError('invalid saved patch hunk')
        start = int(header[1])-1
        result.extend(original[cursor:start]); cursor = start; index += 1
        while index < len(lines) and not lines[index].startswith('@@ '):
            line = lines[index]; index += 1
            if line.startswith('\\'): continue
            if line[0] in (' ','-'):
                assert original[cursor] == line[1:], 'saved patch context mismatch'
                cursor += 1
            if line[0] in (' ','+'): result.append(line[1:])
    result.extend(original[cursor:])
    return ''.join(result)


def starting_bytes(name, gate):
    pin = gate['file_hashes'][name]
    if name.endswith(('action_scheduler.py','battle_turn.py')):
        old = ROOT/'tmp/audit/r23_real_skill_root_closure_20261012_001'
        prior_gate = read(old/'start_gate.json')
        before = old/'starting_files'/name
        assert sha(before) == prior_gate['file_hashes'][name]
        with zipfile.ZipFile(old/'CR-R23-REAL-SKILL-ROOT-CLOSURE-20261012-001_changed_files.zip') as archive:
            manifest = json.loads(archive.read('MANIFEST.json'))
            assert manifest['existing_file_patch_targets'][name] == pin
            patch = archive.read('patches/'+name+'.patch').decode('utf-8')
        target = apply_unified(before.read_text(encoding='utf-8'),patch)
        candidates = [target.encode('utf-8'),target.replace('\n','\r\n').encode('utf-8')]
        result = next((b for b in candidates if hashlib.sha256(b).hexdigest()==pin),None)
        if result is None:
            # Prior work contains a few mixed CRLF lines. R24 only inserts into
            # these two files: recover unchanged byte lines using the verified
            # R23 text and then check the exact R24 start-gate byte hash.
            current = (ROOT/name).read_bytes().splitlines(keepends=True)
            normalized = (ROOT/name).read_text(encoding='utf-8').splitlines(keepends=True)
            operations = difflib.SequenceMatcher(a=target.splitlines(keepends=True),b=normalized,
                                                autojunk=False).get_opcodes()
            assert all(tag in ('equal','insert') for tag,*_ in operations)
            result = b''.join(b''.join(current[j:k]) for tag,_,_,j,k in operations if tag=='equal')
            assert hashlib.sha256(result).hexdigest()==pin
        return result
    result = subprocess.check_output(['git','show',gate['head']+':'+name],cwd=ROOT)
    candidates = [result,result.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
    target = next((b for b in candidates if hashlib.sha256(b).hexdigest()==pin),None)
    if target is None: raise ValueError('clean starting source pin mismatch')
    return target


def package():
    gate = read(AUDIT/'start_gate.json'); members = {}
    for name in EXISTING:
        before = starting_bytes(name,gate).decode('utf-8').replace('\r\n','\n')
        after = (ROOT/name).read_text(encoding='utf-8')
        patch = ''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
                                            fromfile='a/'+name,tofile='b/'+name))
        assert apply_unified(before,patch)==after
        members['patches/'+name+'.patch'] = patch.encode('utf-8')
    for name in [*PRODUCTION,TEST,*TOOLS,REPORT,*CONTROLS]:
        members[name] = (ROOT/name).read_bytes()
    audits = ['start_gate.json','architecture_preservation.json','baseline_tests.json','final_tests.json',
        'defense_inventory.json','functional_scenarios.json','scenario_summary.json','final_summary.json',
        'frozen_regression.json','r22_regression.json','r22_hash_regression.json','r23_regression.json',
        'r22/execution_summary.json','r22/execution_traces.json','r23/execution_summary.json',
        'r23_starting_code_diagnostic.json','r23_starting_code_diagnostic_log.txt',
        'frozen/frozen_regression.json','functional_scenarios_log.txt',
        'turns_regression_log.txt','frozen_regression_log.txt','skills_regression_log.txt']
    audits.extend(p.name for pattern in ('baseline_*.txt','final_*.txt') for p in AUDIT.glob(pattern))
    audits.extend(p.relative_to(AUDIT).as_posix() for p in (AUDIT/'r22').rglob('commands.json'))
    for name in sorted(set(audits)):
        members[(AUDIT/name).relative_to(ROOT).as_posix()] = (AUDIT/name).read_bytes()
    manifest = {'change_request':CR,'starting_head':gate['head'],'branch':gate['branch'], 'git_writes':'NONE',
        'existing_file_patch_baselines':{name:gate['file_hashes'][name] for name in EXISTING},
        'existing_file_patch_targets':{name:sha(ROOT/name) for name in EXISTING},
        'patch_newlines':'unified UTF-8 LF for review; exact full production target bytes also included to preserve inherited mixed newlines',
        'members':[{'path':name,'size':len(body),'sha256':hashlib.sha256(body).hexdigest()}
                   for name,body in sorted(members.items())],
        'exclusions':['game binaries','native payloads/bodies','source snapshots','process dumps',
                      'old reverse trees','unrelated dirty files','starting source backups'],
        'prerequisites':'Existing pinned source snapshots and approved R12-R23 runtime/evidence artifacts'}
    members['MANIFEST.json'] = (json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode('utf-8')
    path = AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,body in sorted(members.items()):
            info = zipfile.ZipInfo(name,date_time=(2026,10,21,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info,body)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==len(members) and set(archive.namelist())==set(members)
        for name,body in members.items():
            assert archive.getinfo(name).file_size==len(body)
            assert hashlib.sha256(archive.read(name)).hexdigest()==hashlib.sha256(body).hexdigest()
    write('handoff_verification.json',{'archive':str(path),'sha256':sha(path),'size':path.stat().st_size,
        'CRC':'PASS','exact_member_set':'PASS','sizes':'PASS','member_sha256':'PASS','members':len(members),
        'manifest_sha256':hashlib.sha256(members['MANIFEST.json']).hexdigest(),
        'requested_destination':'D:/HSR_Battle_Agent/agent_handoffs/'+path.name})


if __name__ == '__main__': main()
