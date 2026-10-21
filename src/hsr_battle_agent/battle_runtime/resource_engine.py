"""R20 explicit resource settlement using R15 ownership and R17 events.

The R18 scheduler checkpoint stack is reused for atomic source transactions.
No resource label implies a native domain, cost, formula, capacity or event.
"""
from __future__ import annotations
import copy
from hsr_battle_agent.battle_ir.behavior import IRNode, TaskIR, stable_hash
from .behavior import GapError
from .behavior_primitives import raw_checked, fixed_binary, NumericSemanticGap

POLICY_ID='r20_resource_reference_v1'
DOMAINS=('ACTOR_RESOURCE','TEAM_RESOURCE','ENTITY_RESOURCE','ABILITY_LOCAL_RESOURCE','UNKNOWN_NATIVE_RESOURCE')
SOURCE_OPS=('resource_mutation_reference','resource_cost_reference','RPG.GameCore.ModifySPNew')
STAGES=('PRE_RESOURCE','RESOURCE_CHANGE','POST_RESOURCE')
OPERATIONS=('READ','SET','ADD','SUBTRACT','CLAMP','COMPARE')

def fail(node,kind,detail): raise GapError(node,kind+': '+str(detail))
def reference_policy():
    return {'identity':POLICY_ID,'authority':'REFERENCE_MODEL','evidence':'explicit reference resource transactions',
            'bindings':{},'action_costs':{}}
def policy(engine,node):
    p=engine.policies.get(POLICY_ID)
    if not isinstance(p,dict) or p.get('identity')!=POLICY_ID or p.get('authority')!='REFERENCE_MODEL' or not p.get('evidence'):
        fail(node,'RESOURCE_POLICY_MISSING','explicit versioned resource policy')
    return p
def store(state):
    return state.mechanics.setdefault(POLICY_ID,{'requests':{},'history':[],'next_id':0,'entity_resources':{},'ability_resources':{}})
def metric(engine,key):
    m=engine.state.scheduler.action_execution['metrics'];m[key]=m.get(key,0)+1
def operand(engine,node,value):
    if isinstance(value,dict) and value.get('kind')=='ExpressionIR': value=IRNode.from_dict(value)
    return raw_checked(engine.evaluate(value) if isinstance(value,IRNode) else value)

def resolve(engine,node,spec):
    state=engine.state;domain=spec.get('domain');owner=spec.get('owner');key=spec.get('resource_key')
    if domain not in DOMAINS or domain=='UNKNOWN_NATIVE_RESOURCE': fail(node,'RESOURCE_DOMAIN_UNKNOWN',domain)
    if not isinstance(key,str) or not key: fail(node,'RESOURCE_IDENTITY_MISSING','explicit resource key')
    if isinstance(owner,dict):
        if set(owner)!={'context'}: fail(node,'RESOURCE_OWNERSHIP_GAP','exact context owner')
        owner=state.target_context.get(owner['context'])
    if spec.get('owner_resolution')=='TEAM_OF_ACTOR_REFERENCE':
        if domain!='TEAM_RESOURCE' or owner not in state.entities: fail(node,'RESOURCE_OWNERSHIP_GAP','team of resolved actor')
        owner=state.entities[owner].get('team')
    elif spec.get('owner_resolution')!='EXACT_OWNER_REFERENCE': fail(node,'RESOURCE_OWNERSHIP_GAP','owner resolution policy')
    if not isinstance(owner,str) or not owner: fail(node,'RESOURCE_OWNERSHIP_GAP','nonempty owner')
    if domain in ('ACTOR_RESOURCE','ENTITY_RESOURCE') and owner not in state.entities:
        fail(node,'RESOURCE_OWNERSHIP_GAP','existing owner entity')
    if domain=='TEAM_RESOURCE' and not any(e.get('team')==owner for e in state.entities.values()):
        fail(node,'RESOURCE_OWNERSHIP_GAP','team membership evidence')
    if domain=='ACTOR_RESOURCE': values=state.actor_resources
    elif domain=='TEAM_RESOURCE': values=state.team_resources
    elif domain=='ENTITY_RESOURCE': values=state.mechanics.get(POLICY_ID,{}).get('entity_resources',{})
    else:
        d=state.scheduler.action_execution
        if owner not in d.get('abilities',{}) or d['abilities'][owner]['action_root_id']!=d['current_root']:
            fail(node,'RESOURCE_OWNERSHIP_GAP','current action ability instance')
        values=state.mechanics.get(POLICY_ID,{}).get('ability_resources',{})
    if key not in values.get(owner,{}): fail(node,'RESOURCE_INITIAL_VALUE_MISSING',domain+'/'+owner+'/'+key)
    return values,owner,key

def binding(engine,node):
    p=policy(engine,node);spec=p.get('bindings',{}).get(node.payload.get('binding',node.stable_hash()))
    if not isinstance(spec,dict) or spec.get('authority')!='REFERENCE_MODEL' or not spec.get('evidence'):
        fail(node,'RESOURCE_BINDING_MISSING','exact source resource identity/policy')
    if spec.get('numeric')!='R12_FIXED_RAW_STEP2_REFERENCE' or spec.get('overflow')!='GAP_REFERENCE':
        fail(node,'RESOURCE_NUMERIC_POLICY_MISSING','raw fixed-point, rounding and overflow')
    if spec.get('operation') not in OPERATIONS: fail(node,'RESOURCE_OPERATION_UNKNOWN',spec.get('operation'))
    bounds=spec.get('bounds')
    if not isinstance(bounds,dict) or set(bounds)!={'minimum','maximum','handling','initial_overcap'}:
        fail(node,'RESOURCE_BOUNDS_UNKNOWN','explicit finite bounds and overcap policy')
    lo=raw_checked(bounds['minimum']);hi=raw_checked(bounds['maximum'])
    if lo>hi or bounds['handling'] not in ('CLAMP_REFERENCE','REJECT_REFERENCE') or bounds['initial_overcap'] not in ('ALLOW_REFERENCE','REJECT_REFERENCE'):
        fail(node,'RESOURCE_BOUNDS_UNKNOWN','capacity policy')
    if node.op=='RPG.GameCore.ModifySPNew':
        mapping=spec.get('source_fields')
        fields=node.payload.get('fields',{})
        if not isinstance(mapping,dict) or set(mapping)!=set(fields) or not mapping:
            fail(node,'MODIFY_SP_SOURCE_MAPPING_GAP','every serialized field must be accounted for')
        if any(v not in ('TARGET_REFERENCE','AMOUNT_REFERENCE','OPAQUE_RETAINED_REFERENCE') for v in mapping.values()):
            fail(node,'MODIFY_SP_SOURCE_MAPPING_GAP','unsupported field role')
        target_fields=[k for k,v in mapping.items() if v=='TARGET_REFERENCE']
        amount_fields=[k for k,v in mapping.items() if v=='AMOUNT_REFERENCE']
        if len(target_fields)!=1 or len(amount_fields)!=1 or spec.get('amount_interpretation')!='SERIALIZED_OPERAND_AS_DELTA_REFERENCE':
            fail(node,'MODIFY_SP_SOURCE_MAPPING_GAP','explicit target and authored operand interpretation')
        if spec['operation'] not in ('ADD','SUBTRACT'): fail(node,'MODIFY_SP_SOURCE_MAPPING_GAP','delta operation')
        spec=copy.deepcopy(spec)
        # Policies in BattleState must retain canonical IR envelopes, rather than
        # dataclass internals produced by asdict during scheduler checkpoints.
        source_amount=fields[amount_fields[0]]
        spec['amount']=source_amount.to_dict() if isinstance(source_amount,IRNode) else source_amount
        targets=engine.select(fields[target_fields[0]])
        _,owner,_=resolve(engine,node,spec)
        expected=spec.get('target_entity')
        if not isinstance(expected,str) or targets!=[expected]: fail(node,'RESOURCE_OWNERSHIP_GAP','exact decoded target agreement')
        if spec['domain'] in ('ACTOR_RESOURCE','ENTITY_RESOURCE') and owner!=expected:
            fail(node,'RESOURCE_OWNERSHIP_GAP','actor/entity target owner agreement')
        if spec['domain']=='TEAM_RESOURCE' and engine.state.entities[expected].get('team')!=owner:
            fail(node,'RESOURCE_OWNERSHIP_GAP','target team owner agreement')
    return spec

def listener_contract(engine,node,spec):
    from .modifier_lifecycle import POLICY_ID as MODIFIER
    events=spec.get('events')
    if spec.get('event_order')!=list(STAGES) or not isinstance(events,dict) or set(events)!=set(STAGES):
        fail(node,'RESOURCE_EVENT_POLICY_MISSING','explicit pre/change/post order')
    if any(not isinstance(v,list) or any(type(x) not in (str,int) for x in v) for v in events.values()):
        fail(node,'RESOURCE_EVENT_POLICY_MISSING','explicit event IDs, including explicit disabled lists')
    if spec.get('listeners')!='EXPLICIT_ACTIVE_R17_REFERENCE' or MODIFIER not in engine.policies:
        fail(node,'RESOURCE_LISTENER_STATE_UNKNOWN','R17 policy and explicit effective reference set')
    expected=spec.get('listener_registrations')
    actual=sorted(r['registration_id'] for m in engine.state.modifiers.values() if m.activation_state=='REFERENCE_INSTANCE_ACTIVE' for r in m.event_registrations)
    if not isinstance(expected,list) or sorted(expected)!=actual or len(expected)!=len(set(expected)):
        fail(node,'RESOURCE_LISTENER_STATE_UNKNOWN','complete explicit active listener IDs')

def _begin(engine,node,frame):
    spec=binding(engine,node);listener_contract(engine,node,spec)
    _,owner,key=resolve(engine,node,spec)
    if spec.get('event_source') not in engine.state.entities: fail(node,'RESOURCE_EVENT_POLICY_MISSING','event source entity')
    tx=engine.state.damage_transactions[-1]
    if tx.get('kind')!='RESOURCE' or tx['source_task']!=node.to_dict(): fail(node,'RESOURCE_TRANSACTION_OWNERSHIP_GAP','scheduler source checkpoint')
    tx['source_task_id']=frame['frame_id']
    data=store(engine.state);data['next_id']+=1;rid='resource:'+str(data['next_id'])
    request={'id':rid,'source_task':node.to_dict(),'spec':spec,'domain':spec['domain'],'owner':owner,'resource_key':key,
        'action_root_id':frame['action_root_id'],'ability_instance_id':frame['ability_instance_id'],
        'source_task_id':frame['frame_id'],'status':'REQUEST_CREATED','native_oracle_status':'NATIVE_ORACLE_PENDING'}
    data['requests'][rid]=request;metric(engine,'resource_mutations_attempted')
    nodes=[]
    for stage in STAGES:
        if stage=='RESOURCE_CHANGE': nodes.append(TaskIR(node.node_id+'/settlement','resource_settle_reference',node.authority,{'request_id':rid}))
        for i,event in enumerate(spec['events'][stage]):
            nodes.append(TaskIR(node.node_id+'/'+stage+'/'+str(i),'resource_event_reference',node.authority,
                                {'request_id':rid,'stage':stage,'event_id':event}))
    nodes.append(TaskIR(node.node_id+'/commit','resource_commit_reference',node.authority,{'request_id':rid}))
    return nodes

def _execute(engine,node):
    policy(engine,node);data=store(engine.state);request=data['requests'][node.payload['request_id']];spec=request['spec']
    if node.op=='resource_event_reference':
        payload={k:copy.deepcopy(v) for k,v in request.items() if k not in ('source_task','spec')}
        payload['resource_stage']=node.payload['stage']
        return [TaskIR(node.node_id+'/dispatch','modifier_event_dispatch',node.authority,
            {'event_id':node.payload['event_id'],'source':spec['event_source'],'target':spec.get('target_entity',spec['event_source']),
             'payload':payload,'drain_before_resume_reference':True})]
    if node.op=='resource_settle_reference':
        values,owner,key=resolve(engine,node,spec);before=raw_checked(values[owner][key]);bounds=spec['bounds']
        lo,hi=raw_checked(bounds['minimum']),raw_checked(bounds['maximum'])
        if not lo<=before<=hi and bounds['initial_overcap']!='ALLOW_REFERENCE': fail(node,'RESOURCE_INITIAL_OVERCAP',before)
        op=spec['operation'];amount=operand(engine,node,spec['amount']) if op in ('SET','ADD','SUBTRACT','COMPARE') else None
        if op=='SET': after=amount
        elif op=='ADD': after=fixed_binary('add',before,amount)
        elif op=='SUBTRACT':
            if node.payload.get('is_cost') or request['source_task']['op']=='resource_cost_reference':
                if amount<0: fail(node,'RESOURCE_COST_POLICY_GAP','nonnegative explicit cost')
                if before-amount<lo: fail(node,'RESOURCE_COST_INSUFFICIENT',key)
            after=fixed_binary('sub',before,amount)
        elif op=='CLAMP': after=min(hi,max(lo,before))
        else: after=before
        if op not in ('READ','COMPARE'):
            if bounds['handling']=='REJECT_REFERENCE' and not lo<=after<=hi: fail(node,'RESOURCE_BOUNDS_REJECTED',after)
            after=min(hi,max(lo,after))
        comparison=None
        if op=='COMPARE':
            comparators={'EQ':lambda a,b:a==b,'GE':lambda a,b:a>=b,'GT':lambda a,b:a>b,'LE':lambda a,b:a<=b,'LT':lambda a,b:a<b}
            if spec.get('comparison') not in comparators: fail(node,'RESOURCE_COMPARISON_POLICY_MISSING','comparator')
            comparison=comparators[spec['comparison']](before,amount)
        values[owner][key]=after
        request.update(status='SETTLED_PENDING_CALLBACKS',pre_value=before,post_value=after,
            applied_delta=fixed_binary('sub',after,before),amount=amount,comparison=comparison,
            policy_hash=stable_hash(spec))
        return []
    if node.op=='resource_commit_reference':
        d=engine.state.scheduler.action_execution
        events=[e for e in d['events'].values() if e['source_event'].get('payload',{}).get('id')==request['id']]
        callbacks=[c for c in d['callbacks'].values() if c['source_event'].get('payload',{}).get('id')==request['id']]
        if any(e['status']!='COMPLETE' for e in events) or any(c['status'] not in ('CALLBACK_COMPLETE','CALLBACK_CANCELLED_REFERENCE') for c in callbacks):
            fail(node,'RESOURCE_CALLBACKS_PENDING',request['id'])
        tx=engine.state.damage_transactions[-1]
        if tx.get('kind')!='RESOURCE' or tx['source_task_id']!=request['source_task_id']: fail(node,'RESOURCE_TRANSACTION_OWNERSHIP_GAP','commit owner')
        request.update(status='RESOURCE_REFERENCE_COMPLETE',events_processed=[e['frame_id'] for e in events],
                       callbacks_processed=[c['frame_id'] for c in callbacks])
        final_store,final_owner,final_key=resolve(engine,node,spec)
        request['balance_at_commit']=raw_checked(final_store[final_owner][final_key])
        data['history'].append(copy.deepcopy(request));engine.state.damage_transactions.pop()
        metric(engine,'resource_operations_committed')
        if spec['operation'] not in ('READ','COMPARE'): metric(engine,'resource_mutations_committed')
        return []
    fail(node,'RESOURCE_OPERATION_UNKNOWN',node.op)

def execute(engine,node,frame=None):
    try:
        if node.op in SOURCE_OPS:
            if frame is None: fail(node,'RESOURCE_OWNERSHIP_GAP','R15 owned action task required')
            if node.op=='resource_cost_reference':
                spec=binding(engine,node)
                if spec.get('operation')!='SUBTRACT' or spec.get('cost_authority')!='EXPLICIT_SCENARIO_INPUT' or not spec.get('cost_source'):
                    fail(node,'RESOURCE_COST_POLICY_GAP','explicit cost source and policy')
            return _begin(engine,node,frame)
        return _execute(engine,node)
    except NumericSemanticGap as exc: fail(node,'RESOURCE_NUMERIC_GAP',str(exc))
    except (KeyError,TypeError,ValueError,AttributeError,IndexError) as exc: fail(node,'RESOURCE_INPUT_GAP',str(exc))

def install(registry):
    for op in ('resource_settle_reference','resource_commit_reference','resource_event_reference'):
        registry.register('task',op,lambda e,n,s:execute(e,n),version=POLICY_ID)
