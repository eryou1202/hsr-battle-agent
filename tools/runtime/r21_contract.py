"""Generate R21 implementation-ready JSON schemas and explicit reference policies.

This describes a future extension of BehaviorRuntime; it is not a second engine.
"""
from __future__ import annotations
from r21_checks import ROOT, AUDIT, read, write

AUTH='REFERENCE_MODEL'
POLICY_ID='r21_turn_distance_rational_reference_v1'
CATEGORIES=['NORMAL_TURN','EXTRA_TURN','INSERTED_ACTION','FOLLOW_UP_ACTION','ULTIMATE_INTERRUPT','FORCED_ACTION']
BOUNDARIES=['PLAYER_NORMAL_TURN','ENEMY_AI_DECISION','OUT_OF_TURN_WINDOW','PENDING_FORCED_ACTION',
            'SUSPENDED_ACTION_INPUT','BATTLE_TERMINAL','SEMANTIC_GAP','BUDGET_YIELD']
FAILURES=['INITIATIVE_INPUT_MISSING','SPEED_PROVIDER_MISSING','TURN_OWNER_UNKNOWN','AV_REFERENCE_POLICY_MISSING',
          'NATIVE_ORDER_UNKNOWN','INTERRUPT_POLICY_MISSING','TURN_BOUNDARY_EVENT_UNKNOWN','ENTITY_STATE_UNRESOLVED',
          'ACTION_NOT_COMPLETE','SEMANTIC_GAP']
HOOKS=['speed_to_action_interval','initial_initiative_placement','elapsed_time_advancement',
       'remaining_time_update','speed_change_rebase','advance_delay_adjustment','tie_break']

def obj(fields):
    return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}
def enum(*values): return {'enum':list(values)}
def array(items): return {'type':'array','items':items}
def ref(name): return {'$ref':'#/$defs/'+name}
def nullable(value): return {'anyOf':[value,{'type':'null'}]}
def mapping(value): return {'type':'object','additionalProperties':value}
S={'type':'string','minLength':1}
N={'type':'integer','minimum':0}
P={'type':'integer','minimum':1}
B={'type':'boolean'}
H={'type':'string','pattern':'^[0-9a-f]{64}$'}

def schemas():
    d={}
    d['Rational']=obj({'n':{'type':'integer'},'d':P})
    d['NonnegativeRational']=obj({'n':N,'d':P})
    d['PositiveRational']=obj({'n':P,'d':P})
    d['Authority']=obj({'kind':enum('REAL_CONTENT_STATIC','REAL_CONTENT_RECONSTRUCTED',AUTH,
         'EXPLICIT_SCENARIO_INPUT','EFFECTIVE_RUNTIME_UNKNOWN'),'source_version':nullable(S),
         'artifact':S,'sha256':H,'pointer':{'type':'string'}})
    d['SpeedProviderRef']=obj({'base_property_key':S,'effective_provider_id':S,'provider_policy_hash':H,
         'authority':ref('Authority')})
    d['SpeedSample']=obj({'value':ref('PositiveRational'),'provider_revision':N,'observed_at':ref('NonnegativeRational'),
         'input_state_hash':H})
    d['Participant']=obj({'actor_id':S,'entity_ref':S,'generation':N,'registration_ordinal':N,
         'controller':enum('PLAYER','MONSTER_AI','FORCED','STAGE'),'speed_ref':ref('SpeedProviderRef'),
         'participation':enum('ENABLED','DISABLED','REMOVED'),'entity_revision':N,'summon_parent_actor':nullable(S),
         'availability_provider_id':S,'authority':ref('Authority')})
    d['ActorInitiativeState']=obj({'actor_id':S,'generation':N,'due_at':nullable(ref('NonnegativeRational')),
         'effective_speed_sample':nullable(ref('SpeedSample')),'cycle_index':N,'normal_entry_id':nullable(S),
         'disabled_remaining':nullable(ref('NonnegativeRational')),'disabled_since':nullable(ref('NonnegativeRational')),
         'revision':N,'authority':enum(AUTH)})
    d['TurnQueueEntry']=obj({'entry_id':S,'actor_id':S,'generation':N,'category':enum(*CATEGORIES),
         'due_at':ref('NonnegativeRational'),'priority':{'type':'integer'},'registration_ordinal':N,
         'enqueue_ordinal':N,'initiative_revision':N,'insertion_id':nullable(S)})
    d['BattleClock']=obj({'now':ref('NonnegativeRational'),'unit':enum('REFERENCE_AV'),
         'advance_count':N,'transition_count':N})
    d['ActiveTurn']=obj({'turn_id':S,'queue_entry_id':S,'turn_owner_actor_id':S,'action_actor_id':S,
         'category':enum(*CATEGORIES),'phase':enum('START_BOUNDARY','DECISION','BEFORE_ACTION','ACTION_RUNNING',
         'ACTION_SUSPENDED','AFTER_ACTION','END_BOUNDARY','DURATION_EXPIRY','SETTLED'),
         'selected_at':ref('NonnegativeRational'),'normal_turn_index':N,'action_index':N,
         'parent_turn_id':nullable(S),'parent_action_root_id':nullable(S),'action_root_id':nullable(S),
         'saved_r15_current_root':nullable(S),'saved_target_context':nullable({'type':'object'}),
         'permission_id':nullable(S),'insertion_id':nullable(S),'completion_consumed':B})
    d['ActionPermission']=obj({'permission_id':S,'decision_id':S,'turn_id':nullable(S),'actor_id':S,
         'category':enum(*CATEGORIES),'action_id':S,'action_ir_hash':H,'target_ids':array(S),
         'state_revision':N,'policy_hash':H,'availability_provider_id':S,'cost_policy_hash':nullable(H),
         'authority':enum(AUTH,'EXPLICIT_SCENARIO_INPUT')})
    d['ActionInsertion']=obj({'insertion_id':S,'category':enum(*CATEGORIES[1:]),'owner_actor_id':S,
         'action_actor_id':S,'generation':N,'requested_at':ref('NonnegativeRational'),'enqueue_ordinal':N,
         'priority':{'type':'integer'},'placement':enum('AFTER_ACTIVE_SETTLES','NEXT_SAFE_POINT','AT_EXPLICIT_TIME'),
         'due_at':nullable(ref('NonnegativeRational')),'parent_turn_id':nullable(S),'parent_action_root_id':nullable(S),
         'action_permission_id':nullable(S),'policy_id':S,'policy_hash':H,'cancellation':enum('PENDING','ADMITTED','CANCELLED','COMPLETED'),
         'cancellation_reason':nullable(S),'consumes_normal_av':B,'counts_normal_turn':B,
         'emits_turn_start':B,'emits_turn_end':B,'safe_point_token':nullable(S)})
    d['TurnBoundaryEvent']=obj({'boundary_id':S,'turn_id':S,'event_kind':enum('TURN_START','BEFORE_ACTION','AFTER_ACTION',
         'TURN_END','DURATION_PROGRESS','EXPIRY_CHECK'),'reference_event_key':S,'owner_actor_id':S,
         'action_actor_id':S,'normal_turn_index':N,'event_ordinal':N,'status':enum('PENDING','DISPATCHED','DRAINING','COMMITTED'),
         'r15_root_id':nullable(S),'listener_policy_hash':H,'emitted_listener_ids':array(S),
         'duration_instance_cursor':N,'authority':enum(AUTH)})
    d['TypedFailure']=obj({'code':enum(*FAILURES),'message':S,'evidence_ids':array(S),
         'operation':S,'actor_id':nullable(S),'turn_id':nullable(S),'action_root_id':nullable(S),
         'resume_token':nullable(S),'input_state_hash':H,'required_policy_or_input':array(S)})
    d['DecisionBoundary']=obj({'decision_id':S,'kind':enum(*BOUNDARIES),'actor_id':nullable(S),
         'turn_id':nullable(S),'action_root_id':nullable(S),'state_revision':N,'policy_hash':H,
         'candidate_permission_ids':array(S),'input_request':nullable({'type':'object'}),
         'failure':nullable(ref('TypedFailure')),'terminal_reason':nullable(S)})
    d['Terminal']=obj({'status':enum('RUNNING','WAVE_PENDING','VICTORY','DEFEAT','ABORTED'),
         'reason':nullable(S),'stage_policy_hash':H})
    d['StageBoundary']=obj({'stage_id':S,'wave_index':N,'provider_id':S,'pending_request_id':nullable(S),
         'generation':N,'policy_hash':H})
    d['ReplayCommand']=obj({'command_id':S,'expected_revision':N,'expected_hash':H,'policy_hash':H,
         'kind':enum('SUBMIT_ACTION','SPEED_CHANGED','ADJUST_READINESS','INSERT_ACTION','SAFE_POINT',
           'RELEASE_BARRIER','DEFEAT','DISABLE','REVIVE','REGISTER_ENTITY','REMOVE_ENTITY','STAGE_TRANSITION'),
         'arguments':{'type':'object'}})
    d['BattleTurnState']=obj({'schema':enum('generic_battle_turn_state/1'),'policy_id':S,'policy_hash':H,
         'clock':ref('BattleClock'),'participants':array(ref('Participant')),
         'initiative':mapping(ref('ActorInitiativeState')),'normal_queue':array({'allOf':[ref('TurnQueueEntry'),
           {'properties':{'category':enum('NORMAL_TURN')}}]}),
         'active_stack':array(ref('ActiveTurn')),'pending_insertions':array(ref('ActionInsertion')),
         'pending_interrupts':array(ref('ActionInsertion')),'permissions':array(ref('ActionPermission')),
         'boundary_work':array(ref('TurnBoundaryEvent')),'decision':nullable(ref('DecisionBoundary')),
         'terminal':ref('Terminal'),'stage':ref('StageBoundary'),'revision':N,
         'next_turn_id':N,'next_entry_id':N,'next_insertion_id':N,'next_decision_id':N,
         'next_permission_id':N,'next_event_id':N,'next_command_id':N,'next_enqueue_ordinal':N,
         'next_registration_ordinal':N,'normal_turn_count':N,'action_count':N,
         'command_journal':array(ref('ReplayCommand')),'failure':nullable(ref('TypedFailure'))})
    state={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:hsr:r21:turn-state:1',
           '$ref':'#/$defs/BattleTurnState','$defs':d}
    category=obj({'placement':enum('NORMAL_DUE','AFTER_ACTIVE_SETTLES','NEXT_SAFE_POINT'),
         'priority':{'type':'integer'},'consumes_normal_av':B,'counts_normal_turn':B,
         'emits_turn_start':B,'emits_turn_end':B,'parent_ownership':enum('ROOT','RETAIN_PARENT','SUSPEND_PARENT'),
         'resume':enum('NONE','AFTER_INSERTION_SETTLES'),'admission':enum('CALLER_PERMISSION','TYPED_GAP'),
         'duration_progress':enum('OWNER_NORMAL_TURN_END','NONE')})
    hook=obj({'provider_id':S,'version':S,'implementation_hash':H,'semantic_authority':enum(AUTH),
              'parameters':{'type':'object'}})
    policy=obj({'schema':enum('generic_battle_turn_policy/1'),'identity':S,'semantic_authority':enum(AUTH),
         'operation_bindings':obj({name:hook for name in HOOKS}),
         'numeric':obj({'representation':enum('REDUCED_RATIONAL'),'distance':ref('PositiveRational'),
          'speed_decode':enum('R12_MODE0_RAW_DIV_2_POW_33'),'rounding':enum('EXACT_RATIONAL'),
          'max_integer_bits':P,'nonpositive_speed':enum('SPEED_PROVIDER_MISSING'),
          'initial':enum('FULL_INTERVAL_FROM_CURRENT_CLOCK'),'elapsed':enum('ABSOLUTE_DUE_CLOCK_ADVANCE'),
          'speed_change':enum('PRESERVE_REMAINING_DISTANCE'),'advance_delay_basis':enum('FULL_CURRENT_INTERVAL'),
          'past_due':enum('CLAMP_TO_NOW'),'normal_reset':enum('AFTER_ALL_END_BOUNDARY_WORK')}),
         'order':array(enum('DUE_ASC','PRIORITY_DESC','REGISTRATION_ASC','ENQUEUE_ASC','ENTRY_ID_UTF8_ASC')),
         'category_rules':obj({c:category for c in CATEGORIES}),
         'boundary_order':array(enum('TURN_START','BEFORE_ACTION','AFTER_ACTION','TURN_END','DURATION_PROGRESS','EXPIRY_CHECK')),
         'boundary_event_keys':obj({c:S for c in ['TURN_START','BEFORE_ACTION','AFTER_ACTION','TURN_END','DURATION_PROGRESS','EXPIRY_CHECK']}),
         'boundary_listener_policy_hash':H,'duration_policy':enum('OWNER_NORMAL_END_NEW_INSTANCE_SKIPS_CREATION_TURN'),
         'r15_running_clock':enum('FREEZE_AV'),'interrupts':enum('GAP_UNTIL_SAFE_POINT_ADAPTER'),
         'defeat':enum('REMOVE_NORMAL_ENTRY_CANCEL_PENDING_RETAIN_ACTIVE_UNTIL_SETTLED'),
         'disable':enum('FREEZE_REMAINING_DISTANCE'),'revive':enum('FULL_INTERVAL_NEW_GENERATION'),
         'summon':enum('EXPLICIT_REGISTER_FULL_INTERVAL'),'terminal_provider_id':S,
         'max_zero_time_transitions':P,'max_insert_depth':P,'availability_provider_id':S})
    policy_schema={'$schema':state['$schema'],'$id':'urn:hsr:r21:turn-policy:1',**policy,
                   '$defs':{k:d[k] for k in ['PositiveRational']}}
    return state,policy_schema

def policy():
    rules={}
    specs=[('NORMAL_TURN','NORMAL_DUE',0,True,True,True,True,'ROOT','NONE','CALLER_PERMISSION'),
           ('EXTRA_TURN','AFTER_ACTIVE_SETTLES',50,False,False,True,True,'RETAIN_PARENT','NONE','CALLER_PERMISSION'),
           ('INSERTED_ACTION','AFTER_ACTIVE_SETTLES',60,False,False,False,False,'RETAIN_PARENT','NONE','CALLER_PERMISSION'),
           ('FOLLOW_UP_ACTION','AFTER_ACTIVE_SETTLES',70,False,False,False,False,'RETAIN_PARENT','NONE','CALLER_PERMISSION'),
           ('ULTIMATE_INTERRUPT','NEXT_SAFE_POINT',100,False,False,False,False,'SUSPEND_PARENT','AFTER_INSERTION_SETTLES','TYPED_GAP'),
           ('FORCED_ACTION','AFTER_ACTIVE_SETTLES',80,False,False,False,False,'RETAIN_PARENT','NONE','CALLER_PERMISSION')]
    for c,place,priority,av,count,start,end,parent,resume,admission in specs:
        rules[c]={'placement':place,'priority':priority,'consumes_normal_av':av,'counts_normal_turn':count,
          'emits_turn_start':start,'emits_turn_end':end,'parent_ownership':parent,'resume':resume,
          'admission':admission,'duration_progress':'OWNER_NORMAL_TURN_END' if c=='NORMAL_TURN' else 'NONE'}
    import hashlib
    # Empty listeners is an explicit fixture choice, not a native no-callback conclusion.
    listener_hash=hashlib.sha256(b'r21-explicit-empty-listeners-fixture-v1').hexdigest()
    return {'schema':'generic_battle_turn_policy/1','identity':POLICY_ID,'semantic_authority':AUTH,
      'operation_bindings':{name:{'provider_id':'r21.reference.'+name,'version':'1',
         'implementation_hash':hashlib.sha256(('r21-declared-policy-spec-v1:'+name).encode()).hexdigest(),
         'semantic_authority':AUTH,'parameters':{}} for name in HOOKS},
      'numeric':{'representation':'REDUCED_RATIONAL','distance':{'n':10000,'d':1},
        'speed_decode':'R12_MODE0_RAW_DIV_2_POW_33','rounding':'EXACT_RATIONAL','max_integer_bits':256,
        'nonpositive_speed':'SPEED_PROVIDER_MISSING','initial':'FULL_INTERVAL_FROM_CURRENT_CLOCK',
        'elapsed':'ABSOLUTE_DUE_CLOCK_ADVANCE','speed_change':'PRESERVE_REMAINING_DISTANCE',
        'advance_delay_basis':'FULL_CURRENT_INTERVAL','past_due':'CLAMP_TO_NOW','normal_reset':'AFTER_ALL_END_BOUNDARY_WORK'},
      'order':['DUE_ASC','PRIORITY_DESC','REGISTRATION_ASC','ENQUEUE_ASC','ENTRY_ID_UTF8_ASC'],
      'category_rules':rules,'boundary_order':['TURN_START','BEFORE_ACTION','AFTER_ACTION','TURN_END','DURATION_PROGRESS','EXPIRY_CHECK'],
      'boundary_event_keys':{k:'reference.turn.'+k.lower() for k in
        ['TURN_START','BEFORE_ACTION','AFTER_ACTION','TURN_END','DURATION_PROGRESS','EXPIRY_CHECK']},
      'boundary_listener_policy_hash':listener_hash,'duration_policy':'OWNER_NORMAL_END_NEW_INSTANCE_SKIPS_CREATION_TURN',
      'r15_running_clock':'FREEZE_AV','interrupts':'GAP_UNTIL_SAFE_POINT_ADAPTER',
      'defeat':'REMOVE_NORMAL_ENTRY_CANCEL_PENDING_RETAIN_ACTIVE_UNTIL_SETTLED',
      'disable':'FREEZE_REMAINING_DISTANCE','revive':'FULL_INTERVAL_NEW_GENERATION',
      'summon':'EXPLICIT_REGISTER_FULL_INTERVAL','terminal_provider_id':'explicit-stage-fixture-v1',
      'max_zero_time_transitions':1000,'max_insert_depth':16,'availability_provider_id':'explicit-caller-actions-v1'}

def contract():
    state_schema,policy_schema=schemas()
    return {'schema':'generic_runtime_turn_contract/1','semantic_authority':AUTH,
      'scope':'Implementation-ready extension contract; no production global engine in R21',
      'state_storage':'BehaviorBattleState.mechanics["battle_turn_v1"] contains BattleTurnState; absent key preserves existing callers',
      'state_json_schema':state_schema,'policy_json_schema':policy_schema,
      'authority_separation':{'native_names':'Proposed concepts are generic abstractions, not recovered class names',
        'research':'4.6.51 immutable pinned snapshot','product':'4.4.54 frozen baseline; no cross-version data merge',
        'initialization':'Every participant/availability/provider/modifier registration is explicit with provenance; constructor validity is not native legality'},
      'invariants':[
        'Every rational is reduced by gcd; denominator positive; zero is 0/1; no bool/float admitted as numeric input. Compare by integer cross-products.',
        'Native R12 tagged raw values are not decoded as speed; ordinary mode0 positive signed int64 raw/2^33 is explicit adapter scope. Unsupported numeric modes return a gap.',
        'Rational n,d and cross-products obey explicit max_integer_bits; reject overflow atomically as SEMANTIC_GAP before state mutation; no truncation or global floating-point context.',
        'Actor id is a stable string, entity_ref joins existing entities; unique registration ordinal never reused; resurrection/removal increments generation and invalidates stale entries/permissions.',
        'Actor properties/resources/progression/modifiers remain authoritative in existing stores. SpeedSample is a read-only scheduling cache bound to provider revision and input hash, not a second writable speed.',
        'Participation is scheduler membership, not a duplicate HP/alive flag. Entity status comes from explicit lifecycle adapter and matching entity_revision.',
        'Enabled waiting actor has exactly one current normal entry. Active NORMAL_TURN removes its entry until settled. Disabled/removed actor has no selectable entry.',
        'due_at is the sole readiness authority; remaining=max(0,due_at-clock.now) is derived, never a second stored writable AV.',
        'normal_queue is canonically sorted by policy comparator. initiative due_at and normal entry due_at must match with identical revision; mutations atomically update both. Queue is a validated index, not independent AV state.',
        'Priority numbers are reference only; UTF8 byte order is the final total-order tie. Arrays preserve semantic order; maps are canonically key-sorted.',
        'No R15 logical_time or WaitSecond value is added to clock.now. Running/suspended action freezes AV unless an explicit future interruption policy admits work at the same timestamp.',
        'Active stack empty admits a normal selection. With active stack, only top frame owns R15 current_root; suspended parent retains every task/event/continuation ownership identifier.',
        'Permissions bind decision/turn/actor/action IR hash/targets/state_revision/policy_hash; stale/foreign/dead-owner requests reject without cost or RNG draw.',
        'Completion must be ACTION_REFERENCE_COMPLETE for the exact bound root after owned work drain. SkillPerformFinish request, empty local queue or waiting status alone is insufficient.',
        'A root completion is consumed once; duplicate settle commands reject. Source task prefix commits persist on a resumable gap; failed turn transition/boundary effect rolls back only its atomic candidate.',
        'Boundary events carry stable id, dispatch/drain status and emitted listener ids/cursors. Snapshot at any phase resumes exactly once; never redispatch a committed event or decrement duration twice.',
        'Persistent modifiers survive root completion; turn-end duration updates visit live instance IDs in explicit registration order, skip newly created instances for that owner turn, expire only after callbacks drain.',
        'Unknown entity/stage/AI availability/native ordering is not a no-op. Policy absence emits typed gaps; absence differs from explicit empty-listener policy.',
        'All counters/next ids, pending queues, stack, boundaries, provider revisions, policy identities/hashes, terminal/stage and replay cursors serialize; process object identity/wall clock excluded.',
        'State terminal status and BehaviorBattleState.terminal synchronize in one transaction; WAVE_PENDING is not terminal; pending waves prevent victory unless stage policy explicitly declares it.',
        'Budget exhaustion returns BUDGET_YIELD with resumable state. Zero-time transitions, insertion depth and R15 work have separate explicit budgets. No fabricated time tick resolves a cycle.'],
      'numeric_operations':{
        'interval':'I(s)=K/s with K from supplied policy; sample fixture K=10000 is REFERENCE_MODEL, no native constant claim',
        'initial_placement':'due=now+I(effective_speed); caller may supply initial due only under a separately hashed placement policy',
        'advance_clock':'select eligible minimum due; now=max(now,due); every remaining time is derived from unchanged absolute due; zero elapsed ties still act',
        'speed_change_waiting':'At old clock t, r=max(0,due-t); new_due=t+r*s_old/s_new. Apply old sample before replacement, then sort; ready r=0 remains ready.',
        'speed_change_active':'Update authoritative provider and observed sample; do not reinsert active normal actor. Settlement samples final post-callback speed for next interval.',
        'advance':'advance fraction f>=0 changes due to max(now,due-f*I(current_speed)); not percent remaining',
        'delay':'delay fraction f>=0 changes due to due+f*I(current_speed); negative operands rejected; absolute deltas require different policy id',
        'completion':'After AFTER_ACTION/TURN_END/duration/expiry callbacks drain, normal due=now+I(final_effective_speed); increment normal cycle/count once. Out-of-turn rule decides AV consumption.',
        'disabled':'Save remaining distance via remaining time and speed sample; remove normal entry. Re-enable policy is distinct from revival; re-enable uses saved_remaining*s_old/s_new at unchanged clock.',
        'revive_summon':'Explicit new generation/registration at current now with full interval; removed actor id cannot be silently reused. Native initialization unknown.'},
      'injectable_policy_interface':{
        'binding':'Seven required operation_bindings resolve through a caller-supplied deterministic registry keyed by provider_id/version/implementation_hash. No serialized Python callables or object identity. Unknown provider/hash returns AV_REFERENCE_POLICY_MISSING.',
        'spec_hashes':'The R21 example hashes identify declared specifications only; R22 must replace them with validated implementation identities when code exists, and store that complete policy in runtime snapshot. They are not fake native/code hashes.',
        'speed_to_action_interval':'(positive speed Rational, numeric parameters) -> positive Rational',
        'initial_initiative_placement':'(participant ref, now Rational, interval Rational, explicit inputs) -> due_at Rational >= now',
        'elapsed_time_advancement':'(now Rational, selected due Rational, phase) -> new_now Rational >= now; reference profile freezes action execution',
        'remaining_time_update':'(now Rational, due_at Rational) -> nonnegative Rational; pure derived read, not an independent writable field',
        'speed_change_rebase':'(now, old_due, old_speed, new_speed, participation/active phase) -> new_due or deferred resample instruction',
        'advance_delay_adjustment':'(now, due_at, speed, kind, operand, source_ref) -> due_at Rational under declared basis',
        'tie_break':'(two eligible entries and immutable participant metadata) -> -1/0/1 with strict total order after final id key; pure, no RNG or container order',
        'conformance':'Numeric fields/order in this profile are declared requirements. A replacement hook must conform to them, or use a new fully serialized policy profile/schema version that states changed requirements. Registry identity and full parameters participate in stable_hash.',
        'purity':'Hooks consume canonical values and produce candidate values, never mutate external stores or depend on wall clock/process floating state; bounds and cross-field validators apply before atomic commit.'},
      'runtime_apis':{
        'initialize_turns(participant_bindings, policy, provider_contracts)':'Validate complete inputs on existing runtime clone; commit mechanics extension only on success.',
        'run_until_decision(budget) -> DecisionBoundary':'Global API added as explicit opt-in path or facade over same BehaviorRuntime. Drives boundaries/R15/stage requests, pauses before player/enemy/out-of-turn/forced selection or input; emits terminal/gap/yield distinctly.',
        'current_turn_owner() -> actor_id | null':'Read owner of top ActiveTurn; normal parent owner stays separately available on interrupt stack. Returns null at idle/terminal, typed gap for unresolved ownership.',
        'next_actor_preview(limit) -> TurnQueueEntry[]':'Pure eligible queue preview plus labeled insertion precedence; no RNG, callbacks, AI, mutations, or extrapolated completion beyond current state.',
        'legal_action_candidates(decision_id) -> ActionPermission[] | TypedFailure':'Intersect local R15 actions with explicit actor mapping, source cost/resource sufficiency, target and category availability provider. Reference candidates only, no native legal_actions claim.',
        'submit_action(permission, targets, expected_revision) -> ExecutionResult | DecisionBoundary':'Revalidate permission; commit selection/context and before-action work; transact existing source cost; start exactly one R15 root after BEFORE_ACTION drains. Root commit may later gap without undoing prior successful tasks.',
        'run_until_next_turn(budget) -> DecisionBoundary':'Drive current admitted action and all boundaries until the next newly selected normal turn, or earlier unresolved input/AI/gap/terminal/yield. Never auto-select external actor actions.',
        'is_terminal() -> bool':'True only stage-declared VICTORY/DEFEAT/ABORTED; unresolved termination emits gap in drive, not false inferred victory.',
        'notify_speed_change(actor_id, provider_revision)':'Atomic rebase from prior cached speed, validate R19 authoritative effective value, invalidate candidate permissions.',
        'adjust_readiness(actor_id, kind, fraction, source_ref)':'Execute only under declared basis policy and exact owner/version/authority, append replay command.',
        'request_insertion(ActionInsertion)':'Explicit category policy/owner/generation/parent validation. Unsupported interrupt remains typed gap; no R15 child TriggerAbility inferred as a global insertion.',
        'clone/snapshot/stable_hash/replay':'Reuse BehaviorRuntime methods; replay new commands through same public APIs and verify each pre/post hash with full policy/catalog/registry identity.'},
      'decision_kind_requirements':{
        'PLAYER_NORMAL_TURN':'ENABLED live PLAYER participant, normal ActiveTurn DECISION, actor/turn populated, no running action root or unresolved start/before work; permissions freshly validated',
        'ENEMY_AI_DECISION':'ENABLED live MONSTER_AI participant and exact selected turn; provider request/input populated, candidate permissions explicit; do not auto-pick from local actions if provider absent',
        'OUT_OF_TURN_WINDOW':'Explicit insertion/interrupt availability policy and owner; window input request/safe point if active root, no implicit ultimate rights from energy balance alone',
        'PENDING_FORCED_ACTION':'Exactly one admitted forced request/owner/action permission identified; driver pauses to report it, then explicit caller auto-submit policy may progress; no fabricated choice',
        'SUSPENDED_ACTION_INPUT':'Exact active turn/action root and serialized input/barrier request; candidate permissions empty unless same input policy explicitly defines them; AV frozen',
        'BATTLE_TERMINAL':'Stage-declared terminal reason/status, candidate permissions empty and no unresolved owned settlement; actor/turn/root null after settled terminal transaction',
        'SEMANTIC_GAP':'TypedFailure populated with exact owner/source/resume; candidates empty; stage or actor unknown cannot masquerade as terminal/decision',
        'BUDGET_YIELD':'Resumable exact revision/phase/cursor with no new semantic claim; candidates empty, input_request reports which deterministic budget was exhausted',
        'invalidation':'Any committed actor/provider/resource/target/readiness/listener mutation increments turn-state revision and invalidates prior permissions/decision receipt. Preview and repeated same-boundary reads are pure.',
        'priority':'Existing unresolved gap/input/owned action drain first; terminal only after settlement; forced/inserted request policy before next normal selection; external actor decision never auto-executed without policy.'},
      'integration_call_graph':[
        'BehaviorRuntime opt-in global driver -> lifecycle/stage status provider -> queue select -> ActiveTurn START_BOUNDARY',
        'Boundary dispatcher -> existing R17 listeners / EventIR -> existing R15-owned boundary root -> drain -> DECISION',
        'Explicit PLAYER or MonsterAI provider -> ActionPermission -> submit_action -> BEFORE_ACTION boundary drain',
        'Existing ResourceEngine cost transaction + ActorRuntimeBinding context -> BehaviorRuntime.start_action -> ActionExecutionRoot',
        'R15 tasks/children/continuations/events -> R17 / R18 / R19 / R20 settlement -> exact root result',
        'ACTION_REFERENCE_COMPLETE -> AFTER_ACTION -> TURN_END -> duration/expiry -> readiness reset -> stage/lifecycle reconciliation -> next selection',
        'SUSPENDED_INPUT / external barrier -> SUSPENDED_ACTION_INPUT; WAITING_SCHEDULER without input -> ACTION_NOT_COMPLETE; SemanticGap -> SEMANTIC_GAP; no normal AV advance'],
      'ownership_transitions':[
        {'from':'IDLE','to':'START_BOUNDARY','guard':'valid eligible minimum entry and empty active stack','owner':'battle engine selects turn_owner and action_actor'},
        {'from':'START_BOUNDARY','to':'DECISION','guard':'all owned boundary callback work drains','owner':'player/AI/forced provider'},
        {'from':'DECISION','to':'BEFORE_ACTION','guard':'fresh category-bound permission','owner':'turn frame retains actor; event callback may have different modifier owner'},
        {'from':'BEFORE_ACTION','to':'ACTION_RUNNING','guard':'callbacks drain, cost/context validated, prior R15 root complete','owner':'exact ActionExecutionRoot id'},
        {'from':'ACTION_RUNNING','to':'ACTION_SUSPENDED','guard':'input request or future explicit safe-point interrupt adapter','owner':'parent root retained; no normal advance'},
        {'from':'ACTION_RUNNING','to':'AFTER_ACTION','guard':'exact root ACTION_REFERENCE_COMPLETE and owned work drained','owner':'turn frame, completion receipt consumed once'},
        {'from':'AFTER_ACTION','to':'END_BOUNDARY','guard':'after callbacks complete','owner':'explicit turn boundary root'},
        {'from':'END_BOUNDARY','to':'DURATION_EXPIRY','guard':'all turn-end work drained','owner':'existing R17 instance IDs, cursors in boundary state'},
        {'from':'DURATION_EXPIRY','to':'SETTLED','guard':'expiry callbacks complete, final speed sampled, category accounting committed','owner':'battle queue engine'},
        {'from':'SETTLED','to':'IDLE','guard':'stage/lifecycle reconciliation; insertion precedence evaluated','owner':'battle owner'}],
      'extension_points':{
        'BehaviorBattleState':'Use mechanics dictionary, existing clone/snapshot/hash; no second BattleState',
        'ActorRuntimeBinding':'Entity identity, caller initialization provenance, controller/availability/speed refs; no character branches',
        'R19 properties':'Generic explicit provider resolver reads effective speed; notification must rebase scheduling cache after authoritative write; missing notification is invalid provider contract',
        'ResourceEngine':'Existing cost/pre/change/post ownership; turn effects via explicit listener IR; no fabricated SP/energy gains',
        'ModifierLifecycle':'Existing event registration/context/removal; future owner-turn duration transition adapter, preserving persistent instances',
        'ActionExecutionRoot':'Existing root drain/completion; boundary adapter reuses EventIR and a labeled REFERENCE_MODEL envelope, never changes real-content skill finish nodes',
        'local legal_actions':'Still returns sorted local action IDs; global API intersects caller availability. R15 current-root guard must remain intact',
        'legacy BattleState/turns.py':'Historical Semantics29 ordinary 4.4.54 sandbox model is retained unchanged; not a 4.6.51 global controller and not the R21 store',
        'ContentCatalog/ScenarioCompiler/strict admission':'Reuse catalog identities; no compiler/admission changes'},
      'interrupt_adapter_contract':{
        'current_limit':'Existing R15 start_action calls local legal_actions and rejects an active root. R21/R22 initial policy returns INTERRUPT_POLICY_MISSING.',
        'future_safe_point':'Adapter must expose a serialized safe-point token only between committed task transitions with no open resource/damage transaction. Approval requires caller policy, not native name guesses.',
        'save':'Atomically mark parent ACTION_SUSPENDED, retain current_root/target_context, all parent queues/frame cursors/events, turn and action root ids.',
        'child':'Future adapter starts new root without weakening public local legality guard; binds its distinct category/owner. All parent work is filtered by root id while suspended.',
        'resume':'After child and its policy-defined boundaries drain, restore exact parent current_root and context. Child commits remain in shared actor/resource/modifier state; do not restore whole battle snapshot.',
        'failure':'Unimplemented adapter, absent safe token, active transaction or unknown cancel policy yields typed gap; never reset or overwrite parent queues'},
      'boundary_dispatch_contract':{
        'reference_keys':'Namespaced reference.turn.* keys only; native literal 0x13 is evidence and is never transplanted as a global dispatch ID',
        'listeners':'Caller must provide a complete registration policy/hash per event, including explicit empty registration. Existing R17 stable priority/ordinal order and callback context apply.',
        'boundary_roots':'Reference boundary envelope owns callbacks using existing R15 frames; it is not a real source ability or a second scheduler. Boundary completion independent from the skill root.',
        'resource':'No automatic energy gain or costs at turn start/end; declared listeners invoke existing resource engine with exact mappings and provenance',
        'duration':'Only explicit owner-normal-turn-END counters in this profile; lifecycle callback at turn end runs before duration progress; expiries drain before next interval is sampled; other native duration kinds gap',
        'gap_resume':'Persist boundary_id, listener cursor/IDs and modifier instance cursor; failed callback candidate rolls back existing R18 checkpoint, committed earlier listeners persist'},
      'enemy_stage_interfaces':{
        'MonsterDecisionProvider':'request(decision_id, actor_id, canonical_snapshot, permissions, policy_hash) -> selected permission + targets + explicit RNG changes or typed gap. No wall-clock/client dependency. AI remains unimplemented.',
        'LifecycleProvider':'Explicit actor/entity revision transitions: defeat/remove cancel waiting entries and invalid owned insertions; active work settles under declared policy; revival creates new generation; summons allocate unique stable IDs/ordinal and full explicit binding.',
        'StageProvider':'reconcile(snapshot, settled_boundary_id) -> CONTINUE | WAVE_PENDING | REGISTER_WAVE(participants, source refs) | TERMINAL(reason) | gap. Wave transition only at quiescent boundary, explicit carry/reset clock/modifier/resource policy required.',
        'Wave_policy':'This reference profile carries AV clock and survivor due values; new-wave actors full interval at now. Complete wave engine, defeat handling and terminal rules are caller/provider work, not supplied native behavior.'},
      'failure_contract':{code:{'kind':code,'no_silent_default':True,'resume':'serialize exact failure/source/owner/root and required policy/input; preserve committed R15 prefix; rejected command changes no battle state'} for code in FAILURES},
      'serialization':{
        'canonical':'Reuse canonical_json/stable_hash. Extension requires JSON model, reduced rationals, no floats, finite strings, stable unique ids; reject malformed/missing/extra schema fields.',
        'hash':'Full BehaviorRuntime snapshot includes extension, policies, IR catalog/actions/aliases/events and registry identity. Include policy hashes and provider bindings; do not exclude journals or pending ownership.',
        'equality':'Canonical full snapshot equality; equivalent unreduced rationals are rejected rather than producing alternate hashes.',
        'replay':'Initial full runtime snapshot + ordered command records with prehash/revision/policy + per-command posthash. Restore providers by registered identity/hash; in-memory callable identity is not authority.',
        'clone':'Existing state/runtime deep copy. Pending roots/interrupt stack/modifiers/resource checkpoints remain isolated.',
        'resume':'Validate cross-field references, policy hash match, generation/revision, active root ownership and listener cursors before drive. The state command journal stores prehash and arguments only. Per-command posthash lives in an external replay receipt computed after the journal append; it is not stored in the snapshot being hashed.'},
      'r22_scope_boundary':'Implement ordinary global clock/decisions/boundary integration now under opt-in reference policies; default interrupts typed gap. Optional arithmetic advance/delay and queued post-action insertions can follow without new archaeology.'}

def main():
    write('contract_source.json',contract())
    write('reference_policy.json',policy())
    print('contract schemas and explicit REFERENCE_MODEL policy generated')

if __name__=='__main__': main()
