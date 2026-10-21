"""Generic source-backed damage reference operations, driven exclusively by R15.

4.6.51 readers prove structure, not formula roles. Every executable formula,
event mapping, boundary and rounding rule below is caller-authored REFERENCE_MODEL.
No 4.4.54 formula/constants or native event ordering are transferred.
"""
from __future__ import annotations
import copy
from hsr_battle_agent.battle_ir.behavior import (
    DamageRequestIR, IRNode, TaskIR, encode, stable_hash)
from .behavior import GapError
from .behavior_primitives import SCALE, NumericSemanticGap, fixed_binary, raw_checked

POLICY_ID = 'r18_damage_hp_reference_v1'
STAGES = ['BEFORE_DAMAGE', 'DAMAGE_AMOUNT_MODIFICATION', 'BEFORE_HP_MUTATION',
          'HP_MUTATION', 'AFTER_HP_MUTATION', 'AFTER_DAMAGE']
NUMERIC = 'R12_MODE0_INT64_STEP2_TOWARD_ZERO_REFERENCE'
SOURCE_OPS = ('RPG.GameCore.DamageByAttackProperty', 'RPG.GameCore.DamageByAttackPropertyNew')
LIFECYCLE = ('REQUEST_CREATED', 'AMOUNT_EVALUATED', 'SETTLEMENT_PENDING',
             'HP_COMMITTED', 'CALLBACKS_PENDING', 'DAMAGE_REFERENCE_COMPLETE')

def lifecycle(record, status):
    """R19 reference labels; HP_COMMITTED is provisional until transaction commit."""
    transitions = record.setdefault('lifecycle_transitions', [])
    index = len(transitions)
    if index >= len(LIFECYCLE) or LIFECYCLE[index] != status:
        raise ValueError('invalid reference damage lifecycle transition')
    record['lifecycle_status'] = status
    transitions.append({'sequence': index, 'status': status, 'authority': 'REFERENCE_MODEL'})

def owned_abilities(d, aid):
    result = {aid}
    while True:
        children = {a['frame_id'] for a in d['abilities'].values() if a['parent_ability_id'] in result}
        if children <= result: return result
        result |= children

def assert_drained(engine, node, aid):
    d = engine.state.scheduler.action_execution
    if aid not in d['abilities']:
        fail(node, 'DAMAGE_OWNERSHIP_MISSING', 'current ability instance')
    owners = owned_abilities(d, aid)
    if any(r['status'] != 'COMPLETE' and r['request']['payload']['ownership']['ability_instance_id'] in owners
           for r in engine.state.damage_requests.values()):
        fail(node, 'DAMAGE_LIFECYCLE_PENDING', 'owned request settlement/callback drain')
    for table, complete in (('callbacks', ('CALLBACK_COMPLETE', 'CALLBACK_CANCELLED_REFERENCE')),
                            ('events', ('COMPLETE',)), ('continuations', ('COMPLETE',))):
        if any(f['ability_instance_id'] in owners and f['status'] not in complete for f in d[table].values()):
            fail(node, 'DAMAGE_LIFECYCLE_PENDING', 'owned ' + table)
    if any(d['abilities'][child]['status'] != 'ABILITY_COMPLETE' for child in owners - {aid}):
        fail(node, 'DAMAGE_LIFECYCLE_PENDING', 'required child continuation')
    if engine.state.damage_transactions or engine.state.pending_events:
        fail(node, 'DAMAGE_LIFECYCLE_PENDING', 'pending transaction/event mutation')

def fail(node, kind, detail): raise GapError(node, kind+': '+detail)
def need(node, mapping, key, kind='DAMAGE_REFERENCE_INPUT_MISSING'):
    if not isinstance(mapping,dict) or key not in mapping: fail(node,kind,str(key))
    return mapping[key]
def policy(engine,node):
    p=engine.policies.get(POLICY_ID)
    if not isinstance(p,dict) or p.get('identity')!=POLICY_ID or p.get('authority')!='REFERENCE_MODEL':
        fail(node,'DAMAGE_POLICY_MISSING','versioned explicit reference policy')
    if not engine.state.scheduler.action_execution:
        fail(node,'DAMAGE_OWNERSHIP_MISSING','R15 ActionExecutionRoot')
    return p
def reference_policy():
    return {'identity':POLICY_ID,'authority':'REFERENCE_MODEL','origin':'R18 caller-authored sandbox',
            'source_version':'4.6.51','native_semantics':'UNKNOWN','numeric':NUMERIC,
            'tasks':{},'amount_callbacks':{},'finish_tasks':{}}
def metric(engine,key,n=1):
    m=engine.state.scheduler.action_execution['metrics'];m[key]=m.get(key,0)+n
def slot(node,mask):
    raw=need(node,node.payload,'decoded','STRUCTURAL_DAMAGE_GAP')
    fields=need(node,need(node,raw,'structure','STRUCTURAL_DAMAGE_GAP'),'fields','STRUCTURAL_DAMAGE_GAP')
    matches=[i for i,f in enumerate(fields) if f.get('mask')==mask]
    if len(matches)!=1: fail(node,'STRUCTURAL_DAMAGE_GAP','exact task mask '+str(mask))
    return need(node,node.payload['fields'],'unbound_bit_'+str(matches[0]),'STRUCTURAL_DAMAGE_GAP')
def attack_fields(node,attack):
    while isinstance(attack,dict) and isinstance(attack.get('child'),dict): attack=attack['child']
    if not isinstance(attack,dict) or attack.get('type')!='RPG.GameCore.AttackData':
        fail(node,'STRUCTURAL_DAMAGE_GAP','selected concrete AttackData reader')
    return need(node,attack,'fields','STRUCTURAL_DAMAGE_GAP')
def source_expression(node,fields,mask):
    found=[f['values'] for f in fields if f['mask']==mask]
    if len(found)!=1 or len(found[0])!=1 or not isinstance(found[0][0],IRNode) or found[0][0].kind!='ExpressionIR':
        fail(node,'STRUCTURAL_DAMAGE_GAP','exact AttackData expression mask '+str(mask))
    return found[0][0]

def _begin(engine,node,frame):
    p=policy(engine,node)
    if p.get('numeric')!=NUMERIC: fail(node,'DAMAGE_NUMERIC_POLICY_UNKNOWN','R12 numeric contract')
    spec=copy.deepcopy(need(node,p['tasks'],node.stable_hash()))
    if spec.get('authority')!='REFERENCE_MODEL' or spec.get('source_task_hash')!=node.stable_hash():
        fail(node,'DAMAGE_BINDING_UNKNOWN','exact task hash and reference authority')
    target=slot(node,need(node,spec,'target_mask'))
    if not isinstance(target,IRNode) or target.kind!='TargetSelectorIR': fail(node,'STRUCTURAL_DAMAGE_GAP','target selector')
    attack=slot(node,need(node,spec,'attack_mask'));fields=attack_fields(node,attack)
    task_masks={str(f['mask']) for f in node.payload['decoded']['structure']['fields']}
    if set(need(node,spec,'task_fields'))!=task_masks or set(need(node,spec,'attack_fields'))!={str(f['mask']) for f in fields}:
        fail(node,'DAMAGE_BINDING_UNKNOWN','all decoded task/AttackData fields explicitly classified')
    for classifications in (spec['task_fields'],spec['attack_fields']):
        if any(v not in ('TARGET_REFERENCE','ATTACK_DATA_REFERENCE','FORMULA_OPERAND_REFERENCE','OPAQUE_REFERENCE_UNUSED') for v in classifications.values()):
            fail(node,'DAMAGE_BINDING_UNKNOWN','unknown field classification')
    if (spec['task_fields'].get(str(spec['target_mask']))!='TARGET_REFERENCE' or
        spec['task_fields'].get(str(spec['attack_mask']))!='ATTACK_DATA_REFERENCE'):
        fail(node,'DAMAGE_BINDING_UNKNOWN','selected target/AttackData roles')
    if need(node,spec,'ordered_stages')!=STAGES: fail(node,'DAMAGE_EVENT_ORDER_UNKNOWN','explicit reference stages')
    from .modifier_lifecycle import policy as modifier_policy
    modifier_policy(engine,node)
    if need(node,spec,'listener_scope')!='EXPLICIT_ACTIVE_REFERENCE_INSTANCES_ONLY':
        fail(node,'DAMAGE_EVENT_LISTENERS_UNKNOWN','explicit reference listener scope')
    events=need(node,spec,'events')
    if set(events)!=set(STAGES) or any(not isinstance(v,list) or any(type(e) not in (int,str) for e in v) for v in events.values()):
        fail(node,'DAMAGE_EVENT_ORDER_UNKNOWN','every stage explicitly configured, including empty stages')
    boundaries=need(node,spec,'boundaries')
    for key,expected in {'shield':'BYPASS_EXPLICIT_SANDBOX','toughness':'NO_MUTATION_EXPLICIT_SANDBOX',
                         'break':'NO_PROCESSING_EXPLICIT_SANDBOX','resources':'NO_PROCESSING_EXPLICIT_SANDBOX'}.items():
        if boundaries.get(key)!=expected: fail(node,'DAMAGE_'+key.upper()+'_POLICY_UNKNOWN','explicit sandbox boundary')
    settlement=need(node,spec,'settlement')
    for key,expected in {'storage':'MODE0_RAW_REFERENCE','clamp':'ZERO_MAX_HP_REFERENCE',
                         'death_callbacks':'NO_PROCESSING_EXPLICIT_SANDBOX','battle_end':'NO_PROCESSING_EXPLICIT_SANDBOX'}.items():
        if settlement.get(key)!=expected: fail(node,'DAMAGE_SETTLEMENT_POLICY_UNKNOWN',key)
    if settlement.get('life_state') not in ('PRESERVE_EXPLICIT_REFERENCE','SET_ALIVE_FROM_HP_REFERENCE'):
        fail(node,'DAMAGE_DEATH_POLICY_UNKNOWN','explicit life state policy')
    if spec.get('critical') not in ('NO_CRIT_EXPLICIT_REFERENCE','FORMULA_SUPPLIED_EXPLICIT_REFERENCE'):
        fail(node,'DAMAGE_CRITICAL_POLICY_UNKNOWN','no implicit sampling')
    if spec.get('negative') not in ('REJECT_REFERENCE','CLAMP_ZERO_REFERENCE') or spec.get('rounding') not in ('RAW_STEP2_REFERENCE','WHOLE_HP_TOWARD_ZERO_REFERENCE'):
        fail(node,'DAMAGE_NUMERIC_POLICY_UNKNOWN','negative/final rounding')
    attacker=need(node,spec,'attacker');original=need(node,spec,'original_caster')
    if attacker not in engine.state.entities or original not in engine.state.entities:
        fail(node,'DAMAGE_TARGET_UNKNOWN','resolved attacker/original caster')
    targets=engine.select(target)
    duplicate=need(node,spec,'duplicates')
    if duplicate not in ('PRESERVE_SERIALIZED_REFERENCE','REJECT_REFERENCE') or (duplicate=='REJECT_REFERENCE' and len(set(targets))!=len(targets)):
        fail(node,'DAMAGE_TARGET_DUPLICATION_UNKNOWN','explicit target duplication policy')
    if not targets: fail(node,'DAMAGE_TARGET_UNKNOWN','nonempty ordered targets')
    txn=engine.state.damage_transactions[-1];txn['source_task_id']=frame['frame_id']
    requests=[];nodes=[]
    for index,eid in enumerate(targets):
        engine.state.next_damage_id+=1;rid='damage:'+str(engine.state.next_damage_id)
        request=DamageRequestIR(rid,'damage_request',node.authority,{
            'source_task':node.to_dict(),'source_task_hash':node.stable_hash(),
            'source_ability':engine.state.target_context.get('current_ability'),
            'attacker':attacker,'original_caster':original,'target':eid,'ordered_targets':targets,
            'target_index':index,'attack_data':attack,'raw_operands':node.payload['decoded'],
            'compiled_attack_fields':fields,'amount_expression':need(node,spec,'formula'),
            'damage_kind':spec.get('damage_kind'),'per_hit':spec.get('per_hit'),
            'unknown_roles':{'native_formula':'UNKNOWN','native_crit':'UNKNOWN','native_hit_split':'UNKNOWN'},
            'reference_policy_id':POLICY_ID,'reference_policy_hash':stable_hash(spec),
            'spec':spec,'ownership':{k:frame[k] for k in ('action_root_id','ability_instance_id','task_frame_id','callback_owner')}})
        engine.state.damage_requests[rid]={'request':request.to_dict(),'status':'PENDING','events_processed':[],
            'evaluated_operands':[],'property_inputs':[],'amount_changes':[],'pending_callbacks':[],
            'request_id':rid,'attacker':attacker,'target':eid,'source_task_id':node.stable_hash(),
            'source_evidence':node.authority.to_dict(),'reference_policy_id':POLICY_ID}
        lifecycle(engine.state.damage_requests[rid], 'REQUEST_CREATED')
        requests.append(rid)
        def step(op,**payload):
            nodes.append(TaskIR(node.node_id+'/'+rid+'/'+str(len(nodes)),op,node.authority,{'request_id':rid,**payload}))
        step('reference_damage_event_stage',stage=STAGES[0])
        step('reference_damage_evaluate')
        for stage in STAGES[1:]:
            if stage=='HP_MUTATION': step('reference_damage_hp_mutation')
            step('reference_damage_event_stage',stage=stage)
        step('reference_damage_target_complete')
    txn['request_ids']=requests
    nodes.append(TaskIR(node.node_id+'/damage_commit','reference_damage_commit',node.authority,{'request_ids':requests}))
    metric(engine,'damage_operations_attempted',len(requests))
    return nodes

def evaluate_formula(engine,node,request,formula,record,depth=0):
    if depth>64: fail(node,'DAMAGE_FORMULA_UNKNOWN','formula depth bound')
    op=need(node,formula,'op');p=request.payload
    if op=='source_expression':
        mask=need(node,formula,'mask')
        if p['spec']['attack_fields'].get(str(mask))!='FORMULA_OPERAND_REFERENCE':
            fail(node,'DAMAGE_BINDING_UNKNOWN','formula operand classification')
        expr=source_expression(node,p['compiled_attack_fields'],mask)
        amount=raw_checked(engine.evaluate(expr))
        record['evaluated_operands'].append({'mask':mask,'expression':expr.to_dict(),'raw':amount})
        return amount
    if op=='property':
        actor=need(node,formula,'entity')
        eid=p['attacker'] if actor=='ATTACKER_REFERENCE' else p['target'] if actor=='TARGET_REFERENCE' else actor
        key=need(node,formula,'key')
        if eid not in engine.state.entities: fail(node,'DAMAGE_PROPERTY_INPUT_MISSING','resolved entity')
        if 'binding' in formula:
            from .dynamic_property import policy as property_policy, read as property_read
            binding=need(node,property_policy(engine,node)['property_bindings'],formula['binding'],'PROPERTY_PROVIDER_POLICY_MISSING')
            if any(v.get('source') in ('BASE_PROPERTY','EFFECTIVE_PROPERTY','MODIFIER_CONTRIBUTION') and v.get('entity')!=eid
                   for v in binding.get('providers',[])):
                fail(node,'PROPERTY_PROVIDER_INPUT_MISSING','request/provider entity mismatch')
            amount,provenance=property_read(engine,node,engine.state,binding,key)
        else:
            amount=raw_checked(need(node,engine.state.properties.get(eid,{}),key,'DAMAGE_PROPERTY_INPUT_MISSING'))
            provenance={'source':'R18_EXPLICIT_PROPERTY_STORAGE_REFERENCE'}
        record['property_inputs'].append({'entity':eid,'key':key,'raw':amount,**provenance});return amount
    if op=='literal_reference': return raw_checked(need(node,formula,'raw'))
    if op not in ('add','sub','mul','div','min','max'): fail(node,'DAMAGE_FORMULA_UNKNOWN',str(op))
    args=need(node,formula,'args')
    if not isinstance(args,list) or len(args)!=2: fail(node,'DAMAGE_FORMULA_UNKNOWN','binary arithmetic arity')
    left,right=[evaluate_formula(engine,node,request,f,record,depth+1) for f in args]
    return min(left,right) if op=='min' else max(left,right) if op=='max' else fixed_binary(op,left,right)

def _execute(engine,node):
    p=policy(engine,node)
    if node.op=='RPG.GameCore.DamagePerformFinish':
        spec=need(node,p['finish_tasks'],node.stable_hash(),'DAMAGE_LIFECYCLE_UNKNOWN')
        if spec.get('mode')!='ASSERT_OWNED_DAMAGE_DRAINED_REFERENCE' or spec.get('authority')!='REFERENCE_MODEL':
            fail(node,'DAMAGE_LIFECYCLE_UNKNOWN','explicit local drain assertion')
        aid=engine.state.target_context.get('ability_instance_id')
        assert_drained(engine,node,aid)
        engine.state.damage_history.append({'boundary':'DAMAGE_PERFORM_FINISH_REFERENCE','ability_instance_id':aid,
            'source_task':node.to_dict(),'action_completion_requested':False,'ability_completion_requested':False,
            'request_completion_requested':False,'reference_policy_id':POLICY_ID,'reference_policy_hash':stable_hash(spec),
            'native_signal':'UNKNOWN','drained_request_ids':[rid for rid,r in engine.state.damage_requests.items()
                if r['request']['payload']['ownership']['ability_instance_id'] in owned_abilities(engine.state.scheduler.action_execution,aid)]})
        metric(engine,'damage_perform_finish_completed')
        return []
    if node.op=='reference_damage_amount_modify':
        spec=need(node,p['amount_callbacks'],node.stable_hash(),'DAMAGE_CALLBACK_AUTHORITY_MISSING')
        payload=need(node,engine.state.target_context,'event_payload','DAMAGE_CALLBACK_PAYLOAD_MISSING')
        rid=need(node,payload,'damage_request_id','DAMAGE_CALLBACK_PAYLOAD_MISSING')
        record=need(node,engine.state.damage_requests,rid)
        if (payload.get('damage_stage')!='DAMAGE_AMOUNT_MODIFICATION' or record.get('stage')!='DAMAGE_AMOUNT_MODIFICATION' or
            spec.get('authority')!='REFERENCE_MODEL' or spec.get('aggregation')!='SERIALIZED_R17_LISTENER_ORDER_REFERENCE'):
            fail(node,'DAMAGE_CALLBACK_AUTHORITY_MISSING','exact amount-modification stage/aggregation')
        operation=need(node,spec,'operation');before=need(node,record,'amount_raw')
        value=raw_checked(engine.evaluate(node.payload['value']))
        if operation not in ('set','add','mul'): fail(node,'DAMAGE_CALLBACK_AUTHORITY_MISSING','operation')
        record['amount_raw']=value if operation=='set' else fixed_binary(operation,before,value)
        record['amount_changes'].append({'callback':node.to_dict(),'before':before,'after':record['amount_raw'],
            'event_payload':copy.deepcopy(payload),'policy':copy.deepcopy(spec)})
        return []
    if node.op=='reference_damage_commit':
        txn=engine.state.damage_transactions[-1]
        if txn['request_ids']!=node.payload['request_ids']: fail(node,'DAMAGE_TRANSACTION_UNKNOWN','request group')
        if any(engine.state.damage_requests[r]['status']!='COMPLETE' for r in txn['request_ids']):
            fail(node,'DAMAGE_LIFECYCLE_PENDING','all target requests complete')
        metric(engine,'damage_operations_committed',len(txn['request_ids']))
        engine.state.damage_transactions.pop();return []
    record=need(node,engine.state.damage_requests,node.payload['request_id'])
    request=IRNode.from_dict(record['request']);spec=request.payload['spec']
    if node.op=='reference_damage_evaluate':
        amount=evaluate_formula(engine,node,request,spec['formula'],record)
        if not record['evaluated_operands']:
            fail(node,'DAMAGE_FORMULA_UNKNOWN','a real decoded source expression is required')
        record.update(evaluated_amount_raw=amount,amount_raw=amount,status='EVALUATED')
        lifecycle(record,'AMOUNT_EVALUATED');return []
    if node.op=='reference_damage_hp_mutation':
        eid=request.payload['target'];s=spec['settlement'];props=need(node,engine.state.properties,eid,'DAMAGE_PROPERTY_INPUT_MISSING')
        hpkey=need(node,s,'hp_property');maxkey=need(node,s,'max_hp_property')
        before=raw_checked(need(node,props,hpkey,'DAMAGE_PROPERTY_INPUT_MISSING'))
        maximum=raw_checked(need(node,props,maxkey,'DAMAGE_PROPERTY_INPUT_MISSING'))
        if maximum<=0 or not 0<=before<=maximum: fail(node,'DAMAGE_HP_STATE_INVALID','bounded initial HP/max HP')
        amount=raw_checked(need(node,record,'amount_raw'))
        if amount<0 and spec['negative']=='REJECT_REFERENCE': fail(node,'DAMAGE_NEGATIVE_AMOUNT','explicit rejection')
        amount=max(0,amount)
        if spec['rounding']=='WHOLE_HP_TOWARD_ZERO_REFERENCE': amount=amount//SCALE*SCALE
        applied=min(before,amount);after=fixed_binary('sub',before,applied)
        props[hpkey]=after
        if s['life_state']=='SET_ALIVE_FROM_HP_REFERENCE': engine.state.entities[eid]['alive']=after>0
        record.update(effective_amount_raw=amount,hp_before_raw=before,hp_after_raw=after,
            applied_hp_delta_raw=-applied,overkill_raw=fixed_binary('sub',amount,applied),status='HP_SETTLED')
        lifecycle(record,'HP_COMMITTED')
        metric(engine,'hp_mutations');return []
    if node.op=='reference_damage_event_stage':
        stage=node.payload['stage'];record['stage']=stage
        if stage=='BEFORE_HP_MUTATION': lifecycle(record,'SETTLEMENT_PENDING')
        if stage=='AFTER_HP_MUTATION': lifecycle(record,'CALLBACKS_PENDING')
        payload={'damage_request_id':request.node_id,'damage_stage':stage,
                 'attacker':request.payload['attacker'],'target':request.payload['target'],
                 'amount_raw':record.get('amount_raw'),'reference_policy_id':POLICY_ID}
        return [TaskIR(node.node_id+'/'+str(i),'modifier_event_dispatch',node.authority,
            {'event_id':event,'source':request.payload['attacker'],'target':request.payload['target'],
             'payload':payload,'drain_before_resume_reference':True}) for i,event in enumerate(spec['events'][stage])]
    if node.op=='reference_damage_target_complete':
        d=engine.state.scheduler.action_execution
        matching=[e for e in d['events'].values() if e['source_event'].get('payload',{}).get('damage_request_id')==request.node_id]
        callbacks=[c for c in d['callbacks'].values() if c['source_event'].get('payload',{}).get('damage_request_id')==request.node_id]
        pending=[c['frame_id'] for c in callbacks if c['status'] not in ('CALLBACK_COMPLETE','CALLBACK_CANCELLED_REFERENCE')]
        if pending: fail(node,'DAMAGE_LIFECYCLE_PENDING','owned callbacks')
        if any(e['status']!='COMPLETE' for e in matching):
            fail(node,'DAMAGE_LIFECYCLE_PENDING','owned event mutations')
        record.update(status='COMPLETE',pending_callbacks=[],events_processed=[{
            'event_frame_id':e['frame_id'],'payload':e['source_event']['payload'],'status':e['status']} for e in matching],
            callbacks_processed=[c['frame_id'] for c in callbacks])
        lifecycle(record,'DAMAGE_REFERENCE_COMPLETE')
        engine.state.damage_history.append(copy.deepcopy(record)|{'request_id':request.node_id,
            'evidence_level':'REFERENCE_MODEL','reference_policy_id':POLICY_ID,'boundary':'REFERENCE_DAMAGE_HP_SETTLED'})
        return []
    fail(node,'DAMAGE_PRIMITIVE_UNKNOWN',node.op)

def execute(engine,node,frame=None):
    try:
        if node.op in SOURCE_OPS:
            if frame is None: fail(node,'DAMAGE_OWNERSHIP_MISSING','owned source task frame')
            return _begin(engine,node,frame)
        return _execute(engine,node)
    except NumericSemanticGap as exc: fail(node,'DAMAGE_NUMERIC_GAP',str(exc))
    except (KeyError,TypeError,ValueError,AttributeError,IndexError) as exc:
        fail(node,'DAMAGE_REFERENCE_INPUT_MISSING',str(exc))

def within_transaction(d,frame,txn):
    """Only work descended from the damage task can run while its transaction is open."""
    target=txn['source_task_id'];pending=[frame];seen=set()
    tables=('tasks','sequences','callbacks','abilities','events','continuations')
    while pending:
        f=pending.pop();fid=f.get('frame_id')
        if fid==target: return True
        if fid in seen: continue
        seen.add(fid)
        refs=[f.get(k) for k in ('task_frame_id','parent_task_id','sequence_frame_id','callback_owner','parent_ability_id')]
        for ref in refs:
            for table in tables:
                if ref in d[table]: pending.append(d[table][ref]);break
    return False

def install(registry):
    for op in ('reference_damage_event_stage','reference_damage_evaluate','reference_damage_hp_mutation',
               'reference_damage_target_complete','reference_damage_commit','reference_damage_amount_modify'):
        registry.register('task',op,lambda engine,node,state: execute(engine,node),version=POLICY_ID)
