"""Derive R25 controls/report and package only owned additions and baseline patches."""
import difflib
import hashlib
import json
import sys
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'tools/runtime')]
from r25_checks import AUDIT, EXISTING, write, preserve
from r21_checks import read, sha
from hsr_battle_agent.battle_runtime.encounter_runtime import reference_policy, TRANSITIONS, PREDICATES, CARRY, EncounterDefinition
from hsr_battle_agent.battle_ir.behavior import stable_hash

CR = 'CR-R25-REFERENCE-ENCOUNTER-LIFECYCLE-20261021-001'
SUFFIX = '20261021_001'
NEW = ['src/hsr_battle_agent/battle_runtime/encounter_runtime.py', 'tests/battle_runtime/test_behavior_r25.py'] + [
    'tools/runtime/r25_'+name+'.py' for name in ('checks', 'evidence', 'reference_fixtures', 'regressions', 'scenarios', 'run', 'finalize')]
NAMES = ['encounter_contract_v1', 'stage_objective_policy_v1', 'wave_lifecycle_v1',
         'encounter_execution_census_v1', 'stage_semantic_gaps_v1', 'whole_battle_capability_v3']
CONTROLS = [f'data/control/generic_runtime_{n}_{SUFFIX}.json' for n in NAMES]
REPORT = 'docs/agent/handoffs/generic_runtime_reference_encounter_lifecycle_'+SUFFIX+'.md'

def control(name, value):
    (ROOT/f'data/control/generic_runtime_{name}_{SUFFIX}.json').write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)+'\n', encoding='utf-8')

def prior_audit_preservation():
    archive = ROOT.parent/'agent_handoffs/CR-R24-TOUGHNESS-BREAK-SHIELD-20261021-001_changed_files.zip'
    checked = []; drift = []
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not name.startswith('tmp/audit/r24_defense_break_shield_20261021_001/'): continue
            checked.append(name)
            if not (ROOT/name).is_file() or (ROOT/name).read_bytes() != z.read(name): drift.append(name)
    receipt = {'status': 'PASS' if not drift else 'FAIL', 'archived_audit_members_checked': len(checked),
               'drift': drift, 'comparison': 'Exact bytes against delivered R24 archive'}
    write('r24_archived_audit_preservation.json', receipt)
    assert not drift, receipt

def main():
    gate = read(AUDIT/'start_gate.json')
    baseline = read(AUDIT/'baseline_tests.json'); tests = read(AUDIT/'final_tests.json')
    assert all(x['returncode'] == 0 for x in [*baseline.values(), *tests.values()]), tests
    summary = read(AUDIT/'execution_summary.json'); scenarios = read(AUDIT/'functional_scenarios.json')
    assert summary['passed'] == 18 and all(x['PASS'] for x in scenarios['scenarios'])
    frozen = read(AUDIT/'frozen_regression.json')
    assert frozen['all_original_state_hashes_equal']
    for name in ('r22_regression', 'r23_regression', 'r24_regression'):
        assert read(AUDIT/(name+'.json'))['status'] == 'PASS'
    assert read(AUDIT/'r17_stage_callback_receipt.json')['status'] == 'PASS'
    assert read(AUDIT/'independent_budgeted_branches.json')['status'] == 'PASS'
    assert read(AUDIT/'architecture_review.json')['status'] == 'PASS'
    architecture = preserve(); prior_audit_preservation()
    evidence = read(AUDIT/'stage_evidence.json')
    policy = reference_policy()
    common = {'change_request': CR, 'starting_head': gate['head'], 'branch': gate['branch'],
        'source_version': '4.6.51', 'product_baseline': 'FROZEN_4.4.54', 'authority': 'REFERENCE_MODEL',
        'native_equivalence': 'NOT_CLAIMED', 'git_writes': 'NONE'}
    terminal = {row['id']: read(AUDIT/row['id']/'receipt.json')['terminal_receipt'] for row in scenarios['scenarios']}
    assert terminal['E02']['result'] == 'VICTORY' and terminal['E02']['wave_index'] == 1
    assert terminal['E04']['result'] == 'DEFEAT'
    e02_initial = read(AUDIT/'E02/commands.json')[0]['arguments']['definition']
    EncounterDefinition.from_dict(e02_initial)
    control('encounter_contract_v1', {**common, 'schema': 'generic_runtime_encounter_contract/1',
        'definition_schema': 'reference_encounter_definition/1', 'policy': policy, 'policy_hash': stable_hash(policy),
        'authored_complete_example': e02_initial, 'provenance': 'Every definition leaf has a source-version/evidence/authority entry',
        'unknown': 'Missing content and unknown life state reject; empty content is never inferred',
        'actor_authority': 'R20 ActorRuntimeBinding with exact identity, team, content pins, HP and life input',
        'stage_authority': ['battle_turn_v1.stage', 'battle_turn_v1.terminal', 'battle_turn_adapter_v1.stage_status'],
        'coordinator_storage': 'BehaviorBattleState.mechanics.reference_encounter_v1',
        'public_APIs': ['initialize_encounter', 'current_encounter', 'evaluate_encounter_objectives',
            'run_until_encounter_boundary', 'current_wave', 'next_wave_preview', 'encounter_result',
            'prepare_next_wave', 'record_encounter_command', 'replay_encounter_commands'],
        'reference_profile_limits': 'Unique identities per spawn; preserve carryover; alternate reset/transform/reuse/interrupt policies require a new implementation and return typed gaps today'})
    control('stage_objective_policy_v1', {**common, 'schema': 'generic_runtime_stage_objective_policy/1',
        'predicates': list(PREDICATES), 'evaluation': 'Pure, no mutation, no RNG; AND/OR evaluate every operand and fail on unknown',
        'scope': 'Current-wave target side plus persistent player actors; prior retired waves do not contaminate objectives',
        'conflict': 'SEMANTIC_GAP_REFERENCE', 'callback_revalidation': True,
        'life_policy': policy['life_state'], 'life_authority': 'Existing R20 provenance and entity.alive; R22 generation/participation',
        'distinctions': ['HP_REACHED_ZERO', 'ENTITY_LIFE_STATE_CHANGED', 'DEFEAT_CONFIRMED_REFERENCE',
            'ACTOR_PARTICIPATION_REMOVED', 'WAVE_OBJECTIVE_SATISFIED'],
        'bridge': 'Record candidate within R18/R24 transaction; no participant removal until R15 action and R22 turn boundaries drain',
        'no_native_death_claim': True, 'repeated_zero_observations': 'One defeat receipt/event per actor generation',
        'terminal_receipts': {'E02': terminal['E02'], 'E04': terminal['E04']}})
    control('wave_lifecycle_v1', {**common, 'schema': 'generic_runtime_wave_lifecycle/1',
        'transitions': TRANSITIONS, 'transition_receipts': ['exact prior', 'next', 'request_id', 'sequence',
            'policy/provider identity', 'wave/stage generation', 'actor generations', 'receipt_hash'],
        'prepare': 'Read-only full R20 construction/R22 registration probe on a clone; immutable prepared input/context receipt',
        'commit': 'Single R22 atomic candidate; retire previous wave, bind/register spawns, change explicit availability, update stage/wave generation',
        'safe_point': policy['safe_point'], 'initiative': policy['initiative'],
        'carryover': {k: policy['carryover'][k] for k in CARRY},
        'events': policy['callbacks'], 'event_execution': 'Existing R15 reference boundary envelopes and R17 modifier_event_dispatch',
        'mandatory_insertions': 'Invalidate defeated-owner insertions via R22; surviving insertions drain before stage commit',
        'no_second_event_bus_or_scheduler': True, 'terminal': 'Callbacks and final objective revalidation precede R22 BATTLE_TERMINAL; actor lifecycle sealed afterward'})
    control('encounter_execution_census_v1', {**common, 'schema': 'generic_runtime_encounter_execution_census/1',
        **summary, 'scenarios': scenarios['scenarios'], 'victory_trace': 'E02', 'defeat_trace': 'E04',
        'replayable_traces': ['E01', 'E02', 'E04', 'E15', 'E16'],
        'frozen_denominators': [632, 160, 161], 'source_closed_joined_transitions': 0,
        'stable_R23_nonempty_prefixes': 72, 'archived_R23_nonempty_prefixes': 73})
    gaps = evidence['tickets'] + [
        {'id': 'R25-MONSTER-NATIVE-AI', 'status': 'UNKNOWN', 'required_evidence': 'Exact Monster content and effective AI execution binder'},
        {'id': 'R25-JOINED-SKILL-CLOSURE', 'status': 'BLOCKED_SOURCE_EVIDENCE', 'source_closed_joined_transitions': 0},
        {'id': 'R25-NATIVE-LEGALITY-ULTIMATE', 'status': 'UNKNOWN', 'required_evidence': 'Native legal-action and ultimate interruption contracts'},
        {'id': 'R25-DEFENSE-NATIVE-BINDER', 'status': 'UNKNOWN', 'native_defense_source_bindings': 0},
        {'id': 'R25-ALTERNATE-REFERENCE-PROFILES', 'status': 'NOT_IMPLEMENTED',
            'required_evidence': 'Explicit implemented reset/transform carryover, reused identity spawn or alternate AV/insertion policy; current preserve/unique profile rejects alternatives'}]
    control('stage_semantic_gaps_v1', {**common, 'schema': 'generic_runtime_stage_semantic_gaps/1',
        'bounded_evidence': evidence, 'gaps': gaps, 'native_stage_content_bound': 0,
        'native_event_ids_and_order': 'UNKNOWN', 'frozen_source_coverage_increased': False})
    verdict = 'REFERENCE_ENCOUNTER_LIFECYCLE_ESTABLISHED'
    control('whole_battle_capability_v3', {**common, 'schema': 'generic_runtime_whole_battle_capability/3',
        'verdict': verdict, 'encounter': 'EXECUTABLE_REFERENCE', 'automatic_two_wave_victory': 'PASS',
        'committed_damage_defeat': 'PASS', 'stage_safe_points': 'PASS', 'R15_R17_callback_drain': 'PASS',
        'R22_actor_generation_AV': 'PASS', 'R24_carryover': 'PASS', 'terminal_idempotence': 'PASS',
        'clone_snapshot_public_command_replay': 'PASS', 'functional_scenarios': '18/18',
        'original_damage_primitive': 'E15 unchanged decoded source task inside explicitly authored reference encounter',
        'canonical_source_closed_joined_skills': 0, 'native_monster_AI': 'NOT_BOUND',
        'native_stage_content': 'NOT_BOUND', 'native_defense_bindings': 0,
        'reference_profiles': {'carryover': 'PRESERVE_REFERENCE for all declared categories', 'spawn_identity': 'UNIQUE_ONLY'},
        'baseline_tests': baseline, 'final_tests': tests, 'frozen_corpus_drift': 'NONE',
        'R26_ranked': [{'rank': 1, 'system': 'BATTLE_PLANNER_BRIDGE',
            'reason': 'Complete deterministic terminal encounters now support executable candidate scoring and cloned search branches'},
            {'rank': 2, 'system': 'MONSTER_CONTENT_AI_REFERENCE_EXECUTION',
            'reason': 'Current explicit first-permission provider closes the loop; real Monster content/AI remains unbound'}]})
    text = f'''# R25 Reference Encounter Lifecycle

CR: {CR}. Starting HEAD: `{gate['head']}`. Branch: `{gate['branch']}`. Git writes: **NONE**.

Verdict: **{verdict}** within the explicitly implemented authored reference profile. Native stage/encounter equivalence: **NOT CLAIMED**.

The public BehaviorRuntime API initializes pinned R20 actors, runs the existing rational R22 Turn/AV engine, admits fresh player/enemy permissions, executes R15 actions, settles R18/R24 HP, confirms reference defeat after owned work drains, evaluates explicit objectives, registers a second wave atomically, resumes normal decisions and produces immutable BATTLE_TERMINAL receipts. E02 reaches VICTORY automatically after two waves. E04 reaches DEFEAT from a deterministic enemy action. Neither trace manually declares a terminal outcome. E01/E02/E04/E15/E16 retain executable initial snapshots, full command receipts and final snapshots under the R25 audit. Enemy-side fixtures are authored actor surrogates using existing pinned R20 Avatar inputs and the MONSTER_AI reference controller; no native Monster spawn/content binding is claimed.

## Contract and authority

EncounterDefinition is versioned, rejects missing identities/content and requires evidence, source version and explicit scenario authority for every leaf. All actor/wave identities, sides, availability, objective rules, limits, policy hashes and R20 bindings are caller inputs. No character or enemy identity occurs in the controller. R22 stage, terminal and adapter fields remain the stage authority; the encounter state contains only lifecycle cursors, candidates, objective history, event envelopes and immutable receipts. Legacy callers without R25 take their existing paths.

The bounded 4.6.51 pass read {evidence['catalog_records']} trusted catalog records ({evidence['decoded_records']} decoded), retained {len(evidence['structural_candidates'])} structural candidates and {len(evidence['direct_metadata_anchors'])} direct metadata anchors, and selected zero new native method bodies. Names, spans and metadata do not establish an effective stage rule. Native stage bindings remain zero. Four exact source tickets are retained. The frozen 4.4.54 product evidence is background only. No broad IFix/Lua work, live attach, memory patch or game launch occurred.

## Objectives, life state and safe points

All seven predicates execute: current target side defeated, player side defeated, specific actor defeated, surviving N normal turns, explicit boolean flag, AND and OR. Evaluation is pure and reads the existing entity life state with R20 provenance. Unknown operands fail closed, including within composite expressions. Conflicting outcomes are semantic gaps. Objectives are revalidated after stage callbacks before wave or terminal commit.

The R18 settle_hp hook records a zero-HP candidate inside the existing damage transaction, so R18/R24 rollback also restores the candidate. HP_REACHED_ZERO is distinct from life-state change, reference defeat, participation removal and objective satisfaction. The versioned reference life policy authorizes zero HP to become reference defeat only after the action, children, R15/R17 callbacks and R22 turn boundaries drain. R22 DEFEAT increments the existing actor generation, removes initiative and cancels defeated-owner insertions. Surviving mandatory insertions drain before stage commit. Required callbacks survive zero HP; action gaps preserve ownership and block transitions. Repeated observations do not repeat defeat events. Explicit REVIVE uses R22 fresh-generation and HP contracts.

## Waves, events and persistence

Wave preparation runs full R20 construction and R22 participant validation on a throwaway clone. Failed preparation exposes no actors or queue entries. Commit checks the prepared receipt and battle input fingerprint, retires prior-wave actors, constructs/registers new entities, replaces explicit per-wave availability, advances R22 wave/stage generation and resumes normal scheduling in one atomic candidate. A completed previous turn is never rolled back because a next wave fails. E12 rejects bad explicit preparation input and accepts the corrected input. Additional checks invalidate prepared input after AV changes.

The implemented profile explicitly PRESERVES HP, actor resources, team SP, energy, persistent modifiers, shields, toughness/break, player speed/AV, progression and RNG. No full heal, SP reset or modifier wipe occurs. R22 rational clock and survivor due_at persist; new actors receive its full interval at current time. This profile requires unique spawn identities. Alternate RESET_EXPLICIT_REFERENCE/TRANSFORM_EXPLICIT_REFERENCE carryover, identity reuse and alternate AV/insertion policies require another implemented policy and currently reject with typed gaps; no native policy is inferred.

ENCOUNTER_START, WAVE_START, ENTITY_DEFEATED, WAVE_CLEAR, BEFORE/AFTER_WAVE_TRANSITION and terminal events use namespaced reference keys in the existing R15 boundary envelope and R17 dispatcher. Persistent event IDs/cursors enforce at most one dispatch per wave/actor generation. Every owned child, callback, transaction and boundary must drain before the next normal actor. WAVE_PENDING is nonterminal.

Terminal receipt includes R22 result, encounter/wave identity, objective evidence, participants/generations, policy version/hash, reason, settled events/listeners and final BattleState hash. The hash is taken after storing the terminal boundary and before attaching the receipt itself, preventing self-reference; removing only terminal_receipt reproduces it. Repeated reads/advances preserve the receipt, state hash and event count. Old permissions, direct action admission and postterminal actor lifecycle reject.

## Executable validation

E01-E18: **18/18 PASS**. Census: **{summary['actions']} completed actions**, **{summary['waves_completed']} cleared waves**, terminal outcomes **{summary['terminal_outcomes']}**. Counts cover the required scenario cohort only; intentional gap/checkpoint scenarios need not terminate. Pure authored scenarios: {summary['cohorts']['PURE_REFERENCE_ENCOUNTER']}; real-primitive scenarios: {summary['cohorts']['REAL_PRIMITIVE_REFERENCE_ENCOUNTER']}.

E15 executes an unchanged decoded real damage primitive through R18/R19 and explicit R24 defense inputs, inside an authored wrapper/encounter. Source task hash remains unchanged. This is not a complete canonical SkillList transition. Native defensive source bindings remain zero.

Clone/JSON restore and exact suffix comparisons cover active action, pending zero-HP candidate, pending stage callback, WAVE_CLEAR_PENDING, TRANSITION_DRAINING, WAVE_READY, prepared input, newly registered second wave, active second wave and terminal victory/defeat. Full external command replay preserves complete snapshots/hashes. Three independent budget-suspended branches reach the same terminal hash while the parent remains unchanged. An additional R17 listener owned by an already defeated actor drains its stage callback exactly once and preserves snapshot suffix equality. Boundary budgets suspend and resume without repeated stage events. Registration/transition/objective/callback/normal-turn/scheduler/zero-time limits are explicit; hitting a declared total cap yields without inventing a terminal result. Call budgets may be increased on resumption; a declared total cap remains a cap.

Baseline: `{json.dumps(baseline, sort_keys=True)}`.

Final: `{json.dumps(tests, sort_keys=True)}`.

The unchanged 632 combat / 160 joined / 161 joined-row corpus has no frozen hash or source-IR drift. R22 A-L observables remain exact; full hashes across implementations differ as expected because the R22 policy hashes battle_turn.py bytes. Same-version replay remains exact. All 160 R23 probes match the stable R24 results: 72 nonempty prefixes, 18 HP roots, 15 original child finishes, zero full source-closed joined transitions. The historical archived 73 is retained unchanged. All 18 R24 defense scenarios pass. Preservation checks cover {architecture['checked_starting_files']} starting files; only the three authorized R25 production adapters changed. Historical M10-M15, ScenarioCompiler, strict admission, tests, unrelated dirty files and R24 archived audit members remain unchanged. The legacy baseline helper summary-path mistake was repaired from exact archived R24 bytes; baseline_summary_recovery.json records the recovery.

## R26 and reproduction

Recommended R26: **BATTLE PLANNER BRIDGE**, because complete deterministic encounters now permit terminal scoring over cloned branches. Second: **MONSTER CONTENT / AI REFERENCE EXECUTION**; current deterministic first-permission reference AI is executable, while real Monster content and AI remain unbound. Remaining major systems: canonical joined-skill source closure, native legality, native ultimate interruption, stage source binding, real shield/break binding and planner/search integration. No broad reverse campaign is automatically reopened.

Use scripts/python/resolve_python.ps1 with the verified interpreter path; this session resolved Python 3.14.3 explicitly because the documented local 3.11 fallback was absent. Commands: r25_checks.py baseline/final; r25_evidence.py; r25_scenarios.py; r25_regressions.py frozen/turns/skills/defense; r25_finalize.py --package. Run r25_run.py --outcome VICTORY or DEFEAT, or --replay E02 / E04 / E15 / E16. Never regenerate the retained start gate.

Production: {', '.join(EXISTING + [NEW[0]])}. Tests: {NEW[1]}. Controls: six generic_runtime R25 records dated 20261021_001. Audit: tmp/audit/r25_reference_encounter_20261021_001/.

Handoff: D:/HSR_Battle_Agent/agent_handoffs/{CR}_changed_files.zip. The ZIP contains R25 additions, patches against exact starting bytes, derived controls, audit traces and a member manifest. It excludes inherited full source files, source snapshots, native payloads, game binaries, dumps, starting backups, old reverse trees and unrelated changes. CRC, exact member set, sizes, per-member SHA-256 and complete ZIP SHA-256 are recorded externally in handoff_verification.json.
'''
    (ROOT/REPORT).write_text(text, encoding='utf-8')
    write('delivery_summary.json', {**common, 'verdict': verdict, 'summary': summary, 'tests': tests,
        'production': EXISTING+[NEW[0]], 'new_files': NEW+CONTROLS+[REPORT], 'recommended_R26': 'BATTLE_PLANNER_BRIDGE'})
    if '--package' in sys.argv: package()
    print('R25 derived controls/report PASS', flush=True)

def package():
    patches = AUDIT/'patches'; patches.mkdir(exist_ok=True)
    gate = read(AUDIT/'start_gate.json')
    manifest = {'change_request': CR, 'starting_head': gate['head'], 'existing_file_patches': [], 'members': []}
    for name in EXISTING:
        before = (AUDIT/'starting_files'/Path(name).name).read_bytes()
        assert hashlib.sha256(before).hexdigest() == gate['file_hashes'][name]
        after = (ROOT/name).read_bytes()
        delta = ''.join(difflib.unified_diff(before.decode('utf-8-sig').splitlines(True),
            after.decode('utf-8-sig').splitlines(True), fromfile='a/'+name, tofile='b/'+name))
        target = patches/(Path(name).name+'.patch'); target.write_text(delta, encoding='utf-8')
        manifest['existing_file_patches'].append({'target': name, 'required_base_sha256': hashlib.sha256(before).hexdigest(),
            'result_sha256': hashlib.sha256(after).hexdigest(), 'patch': target.relative_to(ROOT).as_posix()})
    paths = [ROOT/n for n in NEW+CONTROLS+[REPORT]]
    # Curated R25 audit, generated runtime traces and historical regression receipts.
    # No copied source/native assets or starting backups enter the archive.
    for p in AUDIT.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ('starting_files', 'test_tmp', '__pycache__')): continue
        if p.name in ('handoff_verification.json', 'member_manifest.json'): continue
        paths.append(p)
    paths = sorted(set(paths))
    for p in paths:
        manifest['members'].append({'path': p.relative_to(ROOT).as_posix(), 'size': p.stat().st_size, 'sha256': sha(p)})
    write('member_manifest.json', manifest)
    paths.append(AUDIT/'member_manifest.json')
    output = ROOT/'agent_handoffs'/(CR+'_changed_files.zip')
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in paths: z.write(p, p.relative_to(ROOT).as_posix())
    expected = {p.relative_to(ROOT).as_posix(): p for p in paths}
    members = []
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(expected) and set(z.namelist()) == set(expected)
        for info in z.infolist():
            data = z.read(info.filename); pin = hashlib.sha256(data).hexdigest()
            assert info.file_size == expected[info.filename].stat().st_size and pin == sha(expected[info.filename])
            members.append({'path': info.filename, 'size': info.file_size, 'sha256': pin})
    write('handoff_verification.json', {'status': 'PASS', 'zip_path': str(output), 'CRC': 'PASS',
        'exact_member_set': 'PASS', 'sizes': 'PASS', 'per_member_SHA256': 'PASS',
        'zip_sha256': sha(output), 'zip_size': output.stat().st_size, 'members': members})
    print('R25 package verified', output, sha(output), flush=True)

if __name__ == '__main__': main()
