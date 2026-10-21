"""R21 controls, handoff report, architecture audit and exact-member packaging."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import zipfile
from r21_checks import ROOT, AUDIT, read, write, sha, git, preservation
from r21_contract import contract, policy, FAILURES

CR='CR-R21-TRUE-TURN-AV-CONTRACT-20261011-001'
REPORT='docs/agent/handoffs/generic_runtime_true_turn_av_evidence_20261011_001.md'
CONTROLS=['generic_runtime_'+name+'_v1_20261011_001.json' for name in
          ['turn_av_evidence','turn_contract','turn_policy_matrix','turn_oracle_gaps','r22_implementation_plan']]
DEST=Path('D:/HSR_Battle_Agent/agent_handoffs')/(CR+'_changed_files.zip')
TOOLS=['tools/runtime/r21_'+name for name in ['checks.py','native.cjs','evidence.py','contract.py','specs.py','finalize.py']]

def approved_presence():
    rows=[]
    for phase in range(12,21):
        dirs=list((ROOT/'tmp/audit').glob('r'+str(phase)+'_*'))
        assert len(dirs)==1
        manifests=list(dirs[0].glob('*manifest*.json'));assert len(manifests)==1
        d=read(manifests[0]);members=d.get('members',d.get('files'))
        if isinstance(members,dict):names=list(members)
        elif isinstance(members,list):names=[x if isinstance(x,str) else x.get('path',x.get('relative_path')) for x in members]
        else:raise RuntimeError('unknown manifest '+str(manifests[0]))
        # Some archives have a top-level manifest alias; do not interpret that as repository production input.
        applicable=[n for n in names if n and n!='manifest.json']
        missing=[n for n in applicable if not (ROOT/n).is_file()]
        rows.append({'phase':'R'+str(phase),'manifest':manifests[0].relative_to(ROOT).as_posix(),
            'manifest_sha256':sha(manifests[0]),'members_checked':len(applicable),'missing':missing,
            'approval_hash_note':'Presence only; later approved R phases legitimately supersede earlier source hashes. Starting gate hashes govern R21 preservation.'})
    write('approved_file_presence.json',rows)
    if any(x['missing'] for x in rows):raise RuntimeError('approved member missing')
    return rows

def matrix():
    questions=[
      ('A','Global initiative clock',['E01','E05'],'Controller list selection, property 0x26, elapsed field/accessor; init config value unknown',
       'SAME_BUILD_NATIVE_CORE_PROVEN','REFERENCE_POLICY_REQUIRED','Absolute rational due_at and BattleClock',
       'initialize full interval with explicit caller speed/provider'),
      ('B','Speed relationship',['E03','E04'],'Positive speed property 0x20 and config-distance/speed base path; rebase trigger/rounding/config unclosed',
       'SAME_BUILD_NATIVE_CORE_PROVEN','DERIVED_CONDITIONALLY','Injectable K/s, preserve remaining distance rebase',
       'reference rationals now; native scale/rounding/config/notification oracle later'),
      ('C','Action ordering and turn owner',['E01','E02','E06'],'Packed comparator qword/boolean/int keys and separate owner/action storage; effective stable full tie unknown',
       'SAME_BUILD_NATIVE_CORE_PROVEN','REFERENCE_POLICY_REQUIRED','Stable total order and explicit ActiveTurn/action root',
       'declared reference tie rule now; no native legal_actions'),
      ('D','Advance/delay',['E04','E05'],'Stored delayed mutations and controller cost ratio; complete advance/delay basis/mapping unclosed',
       'STRUCTURALLY_EVIDENCED','REFERENCE_POLICY_REQUIRED','Adjust readiness with declared scalar/full-interval fraction',
       'caller policy and exact source effect mapping required'),
      ('E','Out-of-turn actions',['E07'],'Distinct insertion queue/comparator/use/finish; ultimate/FUA/extra accounting unclosed',
       'STRUCTURALLY_EVIDENCED','REFERENCE_POLICY_REQUIRED','Six proposed categories; pending insertions and safe-point interrupt stack',
       'post-settle reference insertion with caller permissions; interrupt typed gap until R15 adapter'),
      ('F','Turn boundaries',['E08'],'Finish guards and component -> modifier OnTurnEnd/event literal 0x13 path; full dispatch and durations unclosed',
       'SAME_BUILD_NATIVE_CORE_PROVEN','REFERENCE_POLICY_REQUIRED','Reference event keys and resumable R17/R15 boundary ownership',
       'reference order/lifetime profile + complete listeners; no fabricated native IDs'),
      ('G','Entity lifecycle',['E09'],'Death/revive handlers and revive setup-delay call; summons/removal/wave rules unknown',
       'STRUCTURALLY_EVIDENCED','REFERENCE_POLICY_REQUIRED','Participation generations and explicit lifecycle/stage adapter',
       'caller authority required; native initialization oracle pending'),
      ('H','Decision boundary',[],'No exact player/AI/ultimate decision legality dispatch joined in these bounded methods',
       'NOT_FOUND','REFERENCE_POLICY_REQUIRED','Eight distinct DecisionBoundary kinds',
       'reference action availability provider required; enemy/stage providers remain future work')]
    return [{'question_id':i,'question':title,'evidence_ids':refs,'known_data_layout':layout,
       'known_native_method_behavior_status':native,'effective_runtime_dispatch_status':'EFFECTIVE_RUNTIME_ORACLE_REQUIRED',
       'native_actor_initialization_status':'EFFECTIVE_RUNTIME_ORACLE_REQUIRED',
       'conditional_derivation_status':secondary,'reference_implementation_status':'REFERENCE_POLICY_REQUIRED',
       'reusable_runtime_abstraction':abstraction,'r22_disposition':disposition,
       'source_version':'4.6.51','source_sha256':'5177de36bc0961beb550aaa514056d00445969d80f660a1d3ad90833196aa40f',
       'status_is_not_transitive':'Known field/method behavior does not prove initialization, effective dispatch or native equivalence'}
       for i,title,refs,layout,native,secondary,abstraction,disposition in questions]

def gaps():
    specs=[
     ('OR21-01','Effective scheduler dispatch',['E01','E02','E05','E06'],['516441','516442','533850','516473'],
      'Minimum same-build selected method patch guard/patch identity + actual dispatch selection receipt; no global provider/archive rediscovery',
      'Observe exact source/native base paths independently; reference development proceeds',
      'EFFECTIVE_RUNTIME_ORACLE_REQUIRED'),
     ('OR21-02','Initial distance/AV/speed inputs',['E03'],['523121','523436'],
      'Resolve config field+0x190 and setup argument from pinned initialized actor/controller state, exact source hash and version; trace first due',
      'Use explicit K/initial placement/provider, label REFERENCE_MODEL; 10000 candidate not native-proven',
      'EFFECTIVE_RUNTIME_ORACLE_REQUIRED'),
     ('OR21-03','Native AV numeric and rounding',['E02','E03','E05'],['533850','523121','523436','516473'],
      'Exact selected arithmetic mode/tag/overflow and division rounding plus normal initialized AV scale; differential vectors',
      'Reduced rational arithmetic; explicit ordinary R12 speed decode only',
      'REQUIRES_NEW_STRUCTURAL_EVIDENCE'),
     ('OR21-04','Mid-cycle speed rescheduling',['E04'],['523276','523195'],
      'One exact speed change -> after-property notification -> remaining delay/rebase chain and before/after effective values at same AV',
      'Preserve remaining distance reference policy; active normal actor samples final speed after boundaries',
      'REQUIRES_NEW_STRUCTURAL_EVIDENCE'),
     ('OR21-05','Equal AV and eligibility',['E01','E02'],['516432','533850','516441'],
      'Packed key producer identity/value, exact equal-key stability, eligibility/lock/redirect filters under normal/zero/negative delay',
      'Explicit total-order key using immutable registration/enqueue ordinal + stable id',
      'EFFECTIVE_RUNTIME_ORACLE_REQUIRED'),
     ('OR21-06','Advance/delay effect mapping',['E04','E05'],['523246','516473','521101'],
      'Exact source executor/operand basis (full interval vs remaining, scalar vs percent), affected actor and captured delegate behavior; lock/redirect rule',
      'Typed gap for native/unknown source requests; explicit fraction-of-full-interval policy available independently',
      'REQUIRES_NEW_STRUCTURAL_EVIDENCE'),
     ('OR21-07','Insertion/ultimate/FUA accounting',['E07'],['516270','516417','516426','533796'],
      'Exact request priority and category mapping, safe interrupt point, current-turn/action-owner restoration, normal AV/counter/event consumption',
      'Post-settle category policy only; initial interrupt returns INTERRUPT_POLICY_MISSING; future explicit R15 adapter',
      'EFFECTIVE_RUNTIME_ORACLE_REQUIRED'),
     ('OR21-08','Turn event/duration order',['E08'],['523327','522868','516191','516373'],
      'One exact global turn-end/start dispatch -> modifier/resource listener order; literal 0x13 enum identity and config-5 duration behavior; effective callbacks',
      'Namespaced reference events, complete registration hash and resumable boundary cursors; persistent modifiers survive',
      'EFFECTIVE_RUNTIME_ORACLE_REQUIRED'),
     ('OR21-09','Death/revive/summon/wave participation',['E09'],['516469','516470'],
      'One exact lifecycle participation mutation and initialized revived/summoned delay; stage wave owner/terminal/carry rules',
      'Caller lifecycle/stage policy, generation invalidation, explicit full-interval register/revive',
      'EFFECTIVE_RUNTIME_ORACLE_REQUIRED'),
     ('OR21-10','Player/Monster decision legality',[],[],
      'Selected controller pause/request path with concrete actor/action/target/cost rights; Monster decision source and stage termination boundary',
      'Explicit reference ActionPermission and external provider contracts; native legal_actions not claimed',
      'EFFECTIVE_RUNTIME_ORACLE_REQUIRED')]
    evidence=read(AUDIT/'bounded_evidence.json');native={str(x['method']['index']):x['method'] for x in evidence['examined_methods']}
    return [{'ticket_id':i,'title':title,'source_version':'4.6.51',
      'source_sha256':'5177de36bc0961beb550aaa514056d00445969d80f660a1d3ad90833196aa40f',
      'evidence_ids':refs,'method_candidates':[native.get(m,{'index':int(m),'identity_authority':'direct call metadata inventory; body not selected'}) for m in methods],
      'status':status,'minimum_closure_evidence':minimum,'reference_continuation':continuation,
      'requires_live_work_in_R21':False,'blocks_R22_reference_engine':False,'native_equivalence_blocked':True,
      'no_effective_observation_obtained':True}
      for i,title,refs,methods,minimum,continuation,status in specs]

def acceptance():
    categories=[
      ('INITIALIZE','Missing speed/input/policy rejects atomically; explicit real actor identity and ordinary raw speed adapter accepted','R21 schema/algebra; R22 integration required'),
      ('NEXT_ACTOR','Different speeds, three-way order, equal readiness and input permutation yield exact expected actor/time','R21 3 arithmetic fixtures; R22 executable loop required'),
      ('SPEED_CHANGE','Waiting preserve-distance rebase, ready/active/disabled actor policies, stale revisions and final callback speed','R21 arithmetic/revision fixtures; active/disabled R22 required'),
      ('ADVANCE_DELAY','Full-current-interval basis, exact rational fractions, clamp, invalid negative and numeric overflow','R21 algebra; optional source mapping R22'),
      ('OWNERSHIP','Actor availability intersects local actions; no unrelated normal turn while R15 root active/suspended','R21 actual R15 guard/drain probe; R22 global guard required'),
      ('COMPLETION','Suffix callbacks/child work/resources/HP drain; root finish request never sufficient; consume receipt once','Existing R15-R20 tests pass; new R22 turn settlement tests required'),
      ('BOUNDARY_RESUME','Clone/restore before/after every dispatch/listener/expiry; no callback or duration double commit','R21 schema/phase snapshot coverage; R22 adapter tests required'),
      ('PERSISTENT_MODIFIERS','Action complete retains persistent R17 instances; turn count expiry explicit owner/creation rule','Existing R17 persistence; future R22 duration test'),
      ('INSERT_AFTER_ACTION','Queued FUA/insert/forced/extra placement, category flags and stable owner; unchanged normal due where no AV consumed','R21 declared transcript; R22 execution required'),
      ('INTERRUPT_GAP','Default rejects active-root insertion with typed gap; future adapter must save/resume parent queues/context without restoring shared state','R21 declared future transcript + actual R15 active guard; adapter unimplemented'),
      ('ENTITY_LIFECYCLE','Defeated before due skipped; pending requests cancelled; stale generation rejected; revive/summon explicit schedule','R21 defeat transcript/schema; R22 lifecycle adapter required'),
      ('DECISIONS','All 8 boundary kinds explicit; terminal/candidate/gap/input exclusivity; repeated read is pure','R21 schema kinds; R22 semantic validator/API required'),
      ('COSTS_TARGETS','Fresh permission exact owner/IR/targets/version; failed cost or target validation draws no RNG or mutates state','Existing R20 transactions; R22 permission integration required'),
      ('AI_STAGE','Enemy provider requested before action; pending wave not victory; stage unresolved emits typed gap','Interface only in R21; R22 fake explicit providers; no full AI/stage'),
      ('DETERMINISM','Identical command stream matches canonical state, full runtime hash, ordered trace across clone/restored/replay','R21 existing runtime serialization and explicit replay spec; R22 public-API replay required'),
      ('POLICY_HASH','Different tie/numeric/listener/provider policy changes full runtime hash; wrong restore policy rejected','R21 policy hash and snapshot tests'),
      ('BUDGETS','Zero-time cycles and callback/insertion depth yield resumable BUDGET_YIELD/gap; never fake time advance','Existing R15 budgets; R22 global transition budget required'),
      ('AUTHORITY','Old 4.4.54 IDs/offsets not native 4.6.51; formulas and synthetic trace facts remain reference','R21 pinned evidence audit/controls validation'),
      ('ARCHITECTURE','Only existing actor/resource/modifier/property/event/action/catalog state; frozen compiler/admission/modules untouched','R21 file-hash preservation; R22 opt-in regression gates')]
    return [{'id':'AT'+str(i+1).zfill(2),'scope':scope,'acceptance':text,'current_validation':validation,
             'native_validation':False} for i,(scope,text,validation) in enumerate(categories)]

def plan():
    return {'schema':'generic_runtime_r22_implementation_plan/1',
      'recommended_phase':'R22 GLOBAL TURN / AV REFERENCE ENGINE + DECISION BOUNDARY INTEGRATION',
      'no_automatic_new_evidence_phase':True,'authority':'REFERENCE_MODEL','contract_control':CONTROLS[1],
      'policy_control':CONTROLS[2],'oracle_control':CONTROLS[3],
      'integration_target':'Extend existing BehaviorRuntime with an opt-in global driver/helper; no second runtime/state/scheduler/event bus',
      'proposed_files':[
        {'path':'src/hsr_battle_agent/battle_runtime/battle_turn.py','role':'Generic helper operating on engine.state.mechanics[battle_turn_v1], schema validation, rational queue/clock, ownership/decision transitions; no independent BattleState or task scheduler'},
        {'path':'src/hsr_battle_agent/battle_runtime/behavior.py','role':'Explicit opt-in entry points/global run_until_decision branch; legacy calls remain prior behavior; reuse start_action/run_until_action_complete'},
        {'path':'src/hsr_battle_agent/battle_runtime/action_scheduler.py','role':'Minimal boundary envelope adapter using existing frames; root drain and local action guard preserved; no interrupt adapter initially'},
        {'path':'src/hsr_battle_agent/battle_runtime/modifier_lifecycle.py','role':'Explicit turn-duration progression adapter using existing instance/listener/removal state, with exactly-once cursor'},
        {'path':'tests/battle_runtime/test_behavior_r22.py','role':'Meaningful global decision/clock/R15/R17/R20 integration and replay tests from R21 acceptance matrix'}],
      'steps':[
        {'order':1,'deliverable':'Strict opt-in turn extension and policy validation','details':'Use exact state/policy schemas and cross-field invariants, serializable provider identities/hashes, ordinary mode0 speed adapter; missing policy/input yields typed failure. R21 sample state and schema are executable artifacts.'},
        {'order':2,'deliverable':'Deterministic queue/BattleClock','details':'Implement interval, initial due, total tie comparator, eligible next selection and registration generations; keep due_at authoritative with validated queue index. AV frozen during R15 work.'},
        {'order':3,'deliverable':'DecisionBoundary + ActionPermission','details':'Reference actor/action/target availability, state revision/IR/policy-bound permissions, player/Monster/forced separation and terminal/gap/yield results; previews pure; native legality not claimed.'},
        {'order':4,'deliverable':'R15 action ownership integration','details':'Submit binds context/cost and exact root, drives existing tasks/settlement, holds global turn on waiting/input/gap and drains completion. No SkillPerformFinish injection into real content.'},
        {'order':5,'deliverable':'R17 boundary dispatch/duration','details':'Reference event envelopes own callbacks in same R15 queues; start/before/after/end order explicit; exactly-once snapshot cursors; persistent modifiers remain; final speed sampled after all boundary/expiry work.'},
        {'order':6,'deliverable':'Basic lifecycle/stage/AI provider boundaries','details':'Explicit defeat/removal and new-generation register/revive; request enemy decisions without implementing AI; WAVE_PENDING/terminal policy provider; unresolved provider typed gaps.'},
        {'order':7,'deliverable':'Public API replay/hash/clone and regression gates','details':'Replay external commands and external posthash receipts, restore active/decision/boundary states and match independent expected traces; run unchanged R12-R20 and FAST_UNIT lanes.'},
        {'order':8,'deliverable':'Optional post-settle insertion/rebase arithmetic','details':'Implement only caller-authorized category flags and source mapping; ultimate interrupts remain typed gap until a dedicated safe-point adapter meets parent ownership acceptance. No broad archaeology.'}],
      'implementation_dispositions':{
        'CAN_IMPLEMENT_NOW_AS_REFERENCE_MODEL':['rational clock/due state','K/s configurable interval','stable total queue order','run_until_decision / current_turn_owner / next_actor_preview','R15 completion ownership gate','clone/snapshot/hash/replay','policy/schema validators'],
        'IMPLEMENT_ONLY_WITH_CALLER_POLICY':['actor speed/availability and source effects','speed change rebase/advance-delay basis','reference boundary event/listener/duration order','category AV/count/event/placement flags','revive/summon/wave carry/terminal input','Monster selection provider'],
        'REQUIRES_NEW_STRUCTURAL_EVIDENCE':['claim exact native AV rounding/tag/scale','native speed-change property-after-change join','complete captured advance/delay callback/source executor operand mapping'],
        'REQUIRES_EFFECTIVE_NATIVE_ORACLE':['claim active patch/base dispatch','native initialized config speed/readiness','exact native equal-key order and legality','ultimate/FUA/extra-turn consumption','effective native turn event/resource/lifetime order','native death/revive/summon/wave/terminal behavior']},
      'acceptance_matrix':acceptance(),'test_fixtures':'tmp/audit/r21_true_turn_av_20261011_001/policy_trace_fixtures.json',
      'exit_bar':'Deterministic REFERENCE_MODEL normal multi-actor battle loop + decision boundary integration; explicit pending typed gaps accepted; native equivalence separately not claimed',
      'independent_development_tracks':['Camera catalog gaps','unknown templates','modifier/provider input gaps','incomplete Heal semantics',
        'Shield','Toughness/Break','Monster AI content execution','stage/wave runtime','source-native action legality','search/adviser integration'],
      '160_skill_roots':'Not a success denominator for global Turn/AV; R21 neither resolves nor changes source-root support census',
      'r21_production_code_added':False,'frozen_M10_M15_modified':False,'ScenarioCompiler_modified':False,'strict_admission_modified':False}

def build():
    presence=approved_presence();preservation()
    evidence=read(AUDIT/'bounded_evidence.json');gate=read(AUDIT/'start_gate.json')
    tests=read(AUDIT/'final_tests.json');baseline=read(AUDIT/'baseline_tests.json');spec=read(AUDIT/'spec_tests.json')
    assert spec['pass'] and all(x['returncode']==0 for x in tests.values())
    common={'change_request':CR,'starting_head':gate['head'],'branch':gate['branch'],'research_version':'4.6.51',
      'product_version':'4.4.54','git_writes':'NONE','native_equivalent_turn_av':'NOT_CLAIMED',
      'verdict':'TRUE_TURN_AV_CONTRACT_READY'}
    gaps_doc={'schema':'generic_runtime_turn_oracle_gaps/1','tickets':gaps(),
      'native_uncertainty_does_not_block_reference_development':True,'effective_oracle_obtained':False}
    matrix_doc={'schema':'generic_runtime_turn_policy_matrix/1','evidence_statuses':[
      'SAME_BUILD_NATIVE_CORE_PROVEN','STRUCTURALLY_EVIDENCED','DERIVED_CONDITIONALLY','REFERENCE_POLICY_REQUIRED',
      'EFFECTIVE_RUNTIME_ORACLE_REQUIRED','NOT_FOUND'],'questions':matrix(),'reference_policy':policy(),
      'policy_schema_location':CONTROLS[1]+'#/policy_json_schema','categories_are_native_recovered':False,
      'traces':read(AUDIT/'policy_trace_fixtures.json'),
      'selection_precedence':'Active normal action first settles. Then eligible explicitly admitted pending insertions by declared placement/priority/enqueue/id before next normal selection. Missing interruption admission returns a typed gap.',
      'native_numeric_constants_verified':[],'candidate_K_10000_authority':'REFERENCE_MODEL'}
    contract_doc=contract()
    contract_doc['schema']='generic_runtime_turn_contract/1'
    outputs=[{'schema':'generic_runtime_turn_av_evidence/1',**evidence,'source_pins':read(AUDIT/'source_pins.json'),
      'exact_current_gap':{'ACTION_EXECUTION_SCHEDULER':'REFERENCE_EXECUTABLE','GLOBAL_BATTLE_TURN_SCHEDULER':'NOT_BOUND',
        'native_initiative':'NOT_CLOSED','actual_turn_ownership':'NOT_CLOSED','Action_Value':'NOT_CLOSED',
        'speed_to_AV_conversion':'NOT_CLOSED','speed_change_rescheduling':'NOT_CLOSED','advance_delay':'NOT_CLOSED',
        'interrupt_ultimate':'NOT_CLOSED','follow_up_extra':'NOT_CLOSED','end_turn_resource_event_boundaries':'PARTIAL_UNKNOWN'},
      'major_semantics':matrix(),'approved_file_presence':presence,'tests':{'baseline':baseline,'final':tests,'r21_spec':spec}},
      contract_doc,matrix_doc,gaps_doc,plan()]
    for name,d in zip(CONTROLS,outputs):
        d.update(common);p=ROOT/'data/control'/name;p.write_text(json.dumps(d,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    native_summary={c['id']:c['actual_evidence'] for c in evidence['conclusions']}
    text=[
      '# R21 True Battle Turn / Action Value Evidence and Generic Runtime Contract','',
      f'CR `{CR}`. Verdict **TRUE_TURN_AV_CONTRACT_READY**. Starting HEAD `{gate["head"]}`, branch `{gate["branch"]}`. Git writes NONE. Optional production turn engine implemented **NO**. Native-equivalent Turn/AV **NOT CLAIMED**.','',
      'R21 makes R22 reference execution possible while retaining exact native uncertainty. The global controller selects who may act; R15 schedules work inside the chosen action. These clocks and queues remain separate. No production runtime, test file, frozen M10–M15 file, ScenarioCompiler or strict admission code was edited.','',
      '## Start gate and authority','',
      'Read-only Git HEAD/branch/status/staged receipts and 1,520 starting-file SHA-256 values are in start_gate.json. R12–R20 approved handoff manifests were checked for file presence; later phase changes can supersede earlier file hashes. The current starting files are the R21 preservation authority. R12/R13 committed architecture and approved R14–R20 working-tree changes remain distinct from unrelated frontend/.workbuddy/old reverse changes. No inherited files are overwritten.','',
      'Research source is immutable `OSBETAWin4.6.51_20260924-0600_16677734`. Manifest SHA-256 `b702762039368badf25c1e2c0a3a4eea79d7b8ada79c6ce98a448492a97378ec`; GameAssembly SHA-256 `5177de36bc0961beb550aaa514056d00445969d80f660a1d3ad90833196aa40f`; global metadata SHA-256 `a8884e3850a676fb25b1a3734d10388cdf8b51e4782d2e0025b5199e0dbcbab2`. These pins were recomputed. Product ContentDatabase stays frozen 4.4.54. Astra 4.4.54 saved scheduler packets/body excerpts are identity candidates; every new core claim uses 4.6.51 body excerpts. No old RVA/property constant/comparator rule was promoted without same-build inspection.','',
      'Known type/field declarations, native base machine-code behavior, effective patch dispatch, initialized actor inputs and reference policy are separate columns in the A–H matrix. IFix guards exist on selected paths; no effective runtime oracle was acquired. Missing task types in the current corpus do not prove missing native initiative mechanics.','',
      '## Bounded native investigation','',
      'Budget: at most 3 subsystem paths, 120 selected method bodies, normal maximum 2 dependency hops. Actual: **3 paths, 48 bodies**. One permitted high-value third-hop join inspects M523327 → M522868 OnTurnEnd for modifier lifetime/event ownership. It is recorded with its exact path and reason. All other selected methods remain within the bounded controller/component families and at most 2 call/type joins. No registration/provider/archive rediscovery, live attach, game launch or patching occurred. Native research stopped after these paths; remaining joins become specific tickets.','',
      'Paths: initiative/controller selection/comparison/completion; directly reached actor delay/speed property behavior; insertion and turn/lifecycle boundaries. Inventory has per-method identity/RVA/span/body SHA-256, exact call sites, dependency path, review depth and patch uncertainty. Unresolved configuration field values, speed rebase notification, captured list-advance callback, packed key producers, effective insertion accounting, duration/event enum joins and initialization are explicitly listed.','',
      '| Evidence | Same-build base path finding |','|---|---|',
      *[f'| {k} | {v.replace("|","/")} |' for k,v in native_summary.items()], '',
      'Speed behavior has a concrete distance/speed division join, with speed read at property 0x20 and output mutation at 0x26. The config field value, tagged AV scale/range, full rounding and effective initialization are unresolved. `10000 / speed` remains a declared reference candidate. RefreshSpeed has separate modifier-sensitive and override property paths; this does not close native mid-cycle rebase.','',
      'Action ordering includes signed tagless qword readiness comparison and packed auxiliary keys. Equal zero values have special +09/+0c ordering distinct from negative delay. These machine-code facts do not prove final equal-key stability, key producer meanings or effective dispatch. Turn-owner candidate storage and current action entity are distinct; a source skill owner does not establish native turn rights.','',
      'Insertion uses a separate sort/use/finish path. Ultimate/FUA/extra categories and AV/counter consumption remain unclosed. Modifier OnTurnEnd contains event literal 0x13 and a config-literal-5 branch; the reference event interface uses namespaced keys and does not transplant these literals as global native event IDs.','',
      '## Generic state and explicit policy','',
      'The exact Draft 2020-12 JSON schemas are embedded in the turn contract control. BattleTurnState resides under existing BehaviorBattleState.mechanics["battle_turn_v1"]. It contains rational BattleClock; ordered participant bindings; ActorInitiativeState; normal queue index; ActiveTurn stack; separate pending insertions/interrupts; fresh ActionPermissions; boundary work/cursors; decision/failure; stage/terminal state; all ID/order/revision/counter state and a command journal.','',
      'Actor HP/resources/progression/properties/modifiers remain in their current authoritative stores. Effective speed samples are revision/hash-bound scheduling caches. Absolute due_at is the readiness authority; remaining=max(0,due_at-now) is derived. Queue copies are checked against initiative revision/due, so they cannot diverge silently. Explicit participant generations invalidate stale entries/permissions. No process object identity or wall clock participates.','',
      'Reference policy: reduced exact integer rationals, positive denominator, gcd normalization, zero=0/1, explicit 256-bit numeric bound, reject booleans/floats and unsupported tagged speed modes. Ordinary R12 mode0 speed raw is explicitly decoded using /2^33. Initial due=now+K/s; waiting speed changes preserve remaining distance, new_due=now+remaining*old_speed/new_speed; advance/delay uses a fraction of the full current interval; advance clamps to now. Every numeric choice is hash-bound REFERENCE_MODEL and injectable. Missing policy returns AV_REFERENCE_POLICY_MISSING.','',
      'Total queue order: due ascending, declared priority descending, participant registration ordinal ascending, enqueue ordinal ascending, then entry ID UTF-8 bytes ascending. Equal readiness acts at the same AV timestamp; no fabricated elapsed tick. Normal completion re-schedules only after end-boundary/duration/expiry callbacks drain, using final effective speed.','',
      'NORMAL_TURN, EXTRA_TURN, INSERTED_ACTION, FOLLOW_UP_ACTION, ULTIMATE_INTERRUPT and FORCED_ACTION are proposed reference categories. Each rule explicitly records placement, owner/parent, AV consumption, normal-turn count, start/end events and duration progression. The initial profile consumes AV/count only for NORMAL_TURN; EXTRA_TURN emits start/end but does not consume normal AV/count. Other insertions emit action boundaries only. Ultimate interruption remains a typed gap until a safe-point adapter exists. These choices are policy, not native categorization.','',
      '## R15, events and decision integration','',
      'Global select → caller player/Monster/forced decision → fresh permission and BEFORE_ACTION callbacks → existing ResourceEngine/context → R15 ActionExecutionRoot → tasks/events/resources/damage drain → exact completed/suspended/gap receipt → AFTER_ACTION/TURN_END/duration/expiry → final-speed interval → lifecycle/stage reconciliation. R15 logical time is never added to battle AV. Running/suspended work holds its normal turn.','',
      'Existing R15 start_action rejects while its current root is incomplete. R21 does not bypass that guard. A future interrupt adapter must save the parent root/context at an explicit safe point, retain all parent-owned queues/cursors, execute a distinct root, and restore parent current-root/context without restoring shared actor/resource/modifier state. Absent adapter/policy/token or an open damage/resource transaction returns INTERRUPT_POLICY_MISSING.','',
      'Reference turn events reuse R17 listeners and R15 frames through labeled boundary envelopes. They require complete explicit listener registration hashes, including an explicitly empty set. Event IDs/status/listener cursors and duration/expiry cursors prevent duplicate dispatch after snapshot/resume. Persistent modifiers survive skill completion; declared owner-normal-end duration policy skips creation turn, runs turn-end callbacks before duration progress and drains expiry callbacks before reset. Automatic energy/SP gains are not fabricated.','',
      'APIs: initialize_turns, run_until_decision, current_turn_owner, next_actor_preview, legal_action_candidates, submit_action, run_until_next_turn, is_terminal, notify_speed_change, adjust_readiness, request_insertion, plus existing clone/snapshot/hash/replay. Distinct boundary kinds are player normal, enemy AI, out-of-turn window, forced action, suspended input, terminal, SemanticGap and budget yield. Candidates are reference permissions; native legal_actions is not claimed.','',
      'MonsterDecisionProvider and lifecycle/stage interfaces specify input snapshot, exact candidate permission, stable provider/hash, deterministic RNG ownership and wave/terminal results. Full AI/stage/waves are not implemented. WAVE_PENDING does not imply victory. Defeat/removal removes waiting entries and cancels invalid insertions; active work has an explicit settlement rule; revival/new summons require new generation/registration and full binding.','',
      'Clone/canonical snapshot/hash reuse existing runtime methods and include policies/catalog/registry/provider identities plus every pending turn/action/event cursor. Canonical equality rejects unreduced rational alternatives. Replay stores prehash/arguments in the state journal; external receipts hold the posthash after journal append, avoiding a self-referential snapshot hash.','',
      'Typed failures: '+', '.join('`'+x+'`' for x in FAILURES)+'. Missing native behavior never becomes a silent no-op. Rejected commands preserve state/RNG; resumable action gaps preserve earlier committed task prefixes.','',
      '## Policy-only traces and validation','',
      'Nine explicit traces: two speeds, three-way order, equal readiness, waiting speed change, advance/delay, inserted action, interrupted action, defeated-before-turn and turn-end callback. Arithmetic traces have independently handwritten expected rational results. Insertion/interrupt/event transcripts are declared protocol specifications, not executable global engine/native tests. The interrupt fixture explicitly expects the initial profile gap and documents a future adapter transcript.','',
      'R21 executable specification lane: **21 PASS**. It checks rational arithmetic, noncanonical/malformed/overflow inputs, deterministic order, policy hash mismatch, stale queue generations/revisions, all boundary kinds/active phases, existing BehaviorRuntime/state clone/snapshot/hash and an explicit replay command specification. A separate actual R15 compatibility probe verifies active-root rejection, callback drain, cloned/restored action completion and unchanged battle AV while its logical-time wait advances. No existing tests were edited.','',
      '| Regression lane | Baseline | Final |','|---|---|---|',
      *[f'| {n} | {baseline[n]["tests"]} PASS | {tests[n]["tests"]} PASS |' for n in tests], '',
      'Validation: immutable source pin/body/hash references PASS; exact-vs-inferred joins and bounded inventory PASS; JSON schemas/policy/example serialization PASS; policy trace repeat/hash PASS; inherited file preservation PASS; architecture PASS. The tests do not establish native Turn/AV or an implemented full battle loop.','',
      '## R22 executable plan and independent tracks','',
      'Recommended **R22 GLOBAL TURN / AV REFERENCE ENGINE + DECISION BOUNDARY INTEGRATION**. Implement strict opt-in state/provider policy validation; rational queue/clock; actor-bound permissions/decisions; R15 ownership/completion; R17 reference boundary envelopes and duration cursors; lifecycle/stage/Monster request adapters; public-command replay and regression tests. The plan control provides proposed files, ordered deliverables, API/call graph links, and 19 acceptance rows.','',
      'Implement reference clock/order/decisions now. Require caller policy for speed/availability, source readiness effects, insertion/lifetimes/lifecycle/stage choices. Reserve structural tickets for exact native rounding/rebase/effect mappings and effective oracle tickets for initialized inputs/patch dispatch/native insertion/events/legality. No new broad evidence phase is a prerequisite.','',
      'Camera catalog gaps, unknown templates, modifier inputs, incomplete Heal, Shield, Toughness/Break, Monster AI content, stage/waves and adviser/search are independent tracks. R21 global subsystem readiness is not judged by completion of the 160 skill roots and does not upgrade that census.','',
      '## Deliverables and handoff','',
      'Five requested control JSONs and this report are accompanied by six R21 tooling/specification files and the R21 audit directory. Production files modified: NONE. Existing tests modified: NONE. Optional reference turn engine: NO. Native-equivalent Turn/AV: NOT CLAIMED. Git writes: NONE.','',
      'Reproduce: python tools/runtime/r21_evidence.py; python tools/runtime/r21_contract.py; python tools/runtime/r21_specs.py; python tools/runtime/r21_checks.py final; python tools/runtime/r21_finalize.py; python tools/runtime/r21_finalize.py --package. Never regenerate the start gate. Native extraction script uses only pinned static sources; previously selected bodies are retained.','',
      f'Handoff target: `{DEST.as_posix()}`. Package includes only R21-owned files and manifest. Selected bounded text disassembly is included; game binaries/payloads, process dumps, prior reverse audit trees and unrelated work are excluded. External handoff_verification.json records CRC, exact members, sizes, member SHA-256, ZIP SHA-256 and archive size. The verification receipt is kept outside the archive to avoid self-reference.','']
    (ROOT/REPORT).write_text('\n'.join(text),encoding='utf-8')
    validate()
    print('R21 controls/report ready; architecture and preservation PASS')

def validate():
    import jsonschema
    from r21_specs import validate_state,trace_specs
    docs=[read(ROOT/'data/control'/n) for n in CONTROLS]
    c=docs[1];p=docs[2]['reference_policy'];e=docs[0]
    jsonschema.Draft202012Validator.check_schema(c['state_json_schema'])
    jsonschema.Draft202012Validator.check_schema(c['policy_json_schema'])
    jsonschema.Draft202012Validator(c['policy_json_schema']).validate(p)
    validate_state(read(AUDIT/'sample_turn_state.json'),p)
    assert len(e['examined_methods'])==48 and e['budget']['subsystem_paths_used']==3
    assert len(docs[2]['questions'])==8 and len(docs[3]['tickets'])==10
    ids={x['id'] for x in e['conclusions']}
    assert all(set(x['evidence_ids'])<=ids for x in docs[2]['questions']+docs[3]['tickets'])
    for m in e['examined_methods']:assert sha(AUDIT/m['body_file'])==m['body_sha256']
    assert trace_specs()==trace_specs()==docs[2]['traces']['traces']
    assert not read(AUDIT/'preservation.json')['unexpected_changes']
    architecture={'PASS':True,'production_files_modified':[],'existing_tests_modified':[],
      'new_state_runtime_scheduler_event_bus_catalog_compiler':False,
      'global_AV_and_R15_logical_time_separate':True,'character_specific_production_branches':False,
      'native_equivalence_claimed':False,'contract_schema_valid':True,'policy_schema_valid':True,
      'trace_determinism':True,'snapshot_hash_design':'existing runtime + rational mechanics extension, external posthash receipts',
      'code_scope':'R21 tooling/schema/algebra/specification only; no production reference turn engine'}
    write('validation.json',architecture)

def package(destination):
    # Reversible CR-owned archive only; never overwrite a pre-existing unrelated file.
    if destination.exists():raise RuntimeError('handoff destination exists; inspect before replacement')
    validate();preservation()
    files=[ROOT/n for n in TOOLS]+[ROOT/'data/control'/n for n in CONTROLS]+[ROOT/REPORT]
    files += [p for p in AUDIT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'test_tmp' not in p.parts
      and p.name not in ('manifest.json','handoff_verification.json') and p.suffix!='.zip']
    files=sorted(set(files));members={p.relative_to(ROOT).as_posix():{'size':p.stat().st_size,'sha256':sha(p)} for p in files}
    manifest={'change_request':CR,'starting_head':read(AUDIT/'start_gate.json')['head'],'members':members,
      'scope':'R21-owned additions only; no inherited source files or prior audit trees',
      'git_writes':'NONE','excluded':['game binaries','whole payloads','process dumps','prior reverse trees','test temp files','unrelated dirty files']}
    write('manifest.json',manifest);files.append(AUDIT/'manifest.json')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
    expected={**members,(AUDIT/'manifest.json').relative_to(ROOT).as_posix():{'size':(AUDIT/'manifest.json').stat().st_size,'sha256':sha(AUDIT/'manifest.json')}}
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None and len(z.namelist())==len(expected) and set(z.namelist())==set(expected)
        import hashlib
        for name,info in expected.items():
            blob=z.read(name);assert len(blob)==info['size'] and hashlib.sha256(blob).hexdigest()==info['sha256']
    receipt={'path':destination.as_posix(),'CRC':'PASS','exact_members':'PASS','sizes':'PASS','per_member_SHA256':'PASS',
      'archive_sha256':sha(destination),'archive_size':destination.stat().st_size,'member_count':len(expected),'members':expected}
    write('handoff_verification.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='members'},indent=2))

def verify_export():
    import hashlib
    receipt=read(AUDIT/'handoff_verification.json')
    assert DEST.is_file() and sha(DEST)==receipt['archive_sha256'] and DEST.stat().st_size==receipt['archive_size']
    with zipfile.ZipFile(DEST) as z:
        assert z.testzip() is None and len(z.namelist())==len(receipt['members']) and set(z.namelist())==set(receipt['members'])
        for name,info in receipt['members'].items():
            blob=z.read(name)
            assert len(blob)==info['size'] and hashlib.sha256(blob).hexdigest()==info['sha256']
    receipt['path']=DEST.as_posix();receipt['export_verified']=True
    write('handoff_verification.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='members'},indent=2))

if __name__=='__main__':
    if '--verify-export' in sys.argv:verify_export()
    elif '--package' in sys.argv:package(DEST)
    elif '--package-local' in sys.argv:package(ROOT/'tmp'/DEST.name)
    else:build()
