"""Source-backed modifier reference primitives executed exclusively by R15.

Definitions, instances, listeners and contributions live in BehaviorBattleState.
No native numeric policy or opaque event ID acquires an invented meaning here.
"""
from __future__ import annotations
import copy
from dataclasses import asdict
from hsr_battle_agent.battle_ir.behavior import IRNode, TaskIR, TaskSequenceIR, stable_hash
from .behavior_state import ModifierInstance
from .behavior_primitives import raw_checked, fixed_binary, NumericSemanticGap
from .behavior import GapError

POLICY_ID = 'r17_modifier_event_reference_v1'
APPLICATIONS = ('INSERT_NEW_REFERENCE', 'REFRESH_EXISTING_REFERENCE',
                'REPLACE_EXISTING_REFERENCE', 'INCREMENT_STACK_REFERENCE', 'REJECT_DUPLICATE_REFERENCE')
IDENTITIES = ('definition_id', 'config_identity', 'owner', 'caster', 'original_caster', 'source_ability', 'target')
CALLBACK_DONE = ('CALLBACK_COMPLETE', 'CALLBACK_CANCELLED_REFERENCE')

def fail(node, kind, detail): raise GapError(node, kind+': '+detail)
def need(node, mapping, key, kind='MODIFIER_LIFECYCLE_POLICY_MISSING'):
    if not isinstance(mapping, dict) or key not in mapping: fail(node, kind, 'explicit '+str(key))
    return mapping[key]
def integer(node, value, kind='MODIFIER_LIFECYCLE_POLICY_MISSING', minimum=0):
    if type(value) is not int or value < minimum: fail(node, kind, 'integer >= '+str(minimum))
    return value
def policy(engine, node):
    p=engine.policies.get(POLICY_ID)
    if (not isinstance(p,dict) or p.get('identity')!=POLICY_ID or p.get('authority')!='REFERENCE_MODEL' or
        p.get('listener_order')!='PRIORITY_INSTANCE_REGISTRATION_REFERENCE'):
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','versioned reference policy')
    if not engine.state.scheduler.action_execution:
        fail(node,'CALLBACK_CONTEXT_MISSING','R15 ActionExecutionRoot')
    return p
def reference_policy():
    """A policy shell. Applications and definitions must be explicitly configured."""
    return {'identity':POLICY_ID,'authority':'REFERENCE_MODEL',
            'listener_order':'PRIORITY_INSTANCE_REGISTRATION_REFERENCE',
            'applications':{},'definitions':{},'removals':{},'property_tasks':{},'heal_stages':{}}

def bind_definitions(state, catalog):
    definitions=catalog.modifier_definitions()
    for key,definition in definitions.items():
        if definition['graph_hash']!=stable_hash(definition['decoded_graph']):
            raise ValueError('modifier definition graph hash mismatch')
        if key in state.modifier_definitions and state.modifier_definitions[key]!=definition:
            raise ValueError('conflicting bound modifier definition')
    state.modifier_definitions.update(copy.deepcopy(definitions))
    return len(definitions)

def metric(engine,key,amount=1):
    m=engine.state.scheduler.action_execution['metrics'];m[key]=m.get(key,0)+amount
def boundary(engine,instance,stage,**extra):
    engine.state.modifier_history.append({'instance_id':instance.instance_id,'definition_id':instance.definition_id,
        'boundary':stage,'semantic_authority':'REFERENCE_MODEL','native_effective_state':'UNKNOWN',**extra})
def moment(engine): return engine.state.scheduler.action_execution['logical_time']
def operand(engine,node,value,state=None):
    if isinstance(value,dict) and value.get('kind')=='ExpressionIR': value=IRNode.from_dict(value)
    try: return engine.evaluate(value,state) if isinstance(value,IRNode) else value
    except NumericSemanticGap as exc: fail(node,'DYNAMIC_PROVIDER_MISSING',str(exc))
def ir(value): return value if isinstance(value,IRNode) else IRNode.from_dict(value)

def roles(node,binding):
    values=dict(node.payload.get('reference_binding',{}).get('roles',node.payload.get('roles',{})))
    f=node.payload.get('fields',{})
    for old,new in [('TargetType','target'),('ModifierName','modifier'),('LifeTime','lifetime'),
                    ('DynamicValues','dynamic_values'),('CasterType','original_caster')]:
        if old in f: values[new]=f[old]
    slots=node.payload.get('reference_binding',{}).get('unknown_slots',[])
    mapping=binding.get('operand_roles',{})
    for slot in slots:
        name=need(node,mapping,str(slot['mask']),'REFERENCE_INSTANCE_INPUT_MISSING')
        if name=='OPAQUE_DATA_REFERENCE': continue
        if name not in ('target','modifier','original_caster','caster','lifetime','dynamic_values','stack','count'):
            fail(node,'REFERENCE_INSTANCE_INPUT_MISSING','unknown operand role '+str(name))
        if name in values: fail(node,'REFERENCE_INSTANCE_INPUT_MISSING','ambiguous operand '+name)
        values[name]=f['unbound_bit_'+str(slot['field_index'])]
    return values

def definition_policy(engine,node,definition,p):
    spec=need(node,p['definitions'],definition['definition_id'])
    if spec.get('graph_hash')!=definition['graph_hash']:
        fail(node,'CONTENT_GRAPH_MISSING','exact definition policy graph hash')
    fields=definition['decoded_graph'].get('fields',[])
    coverage=need(node,spec,'field_bindings')
    if set(coverage)!={str(f['mask']) for f in fields}:
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','all decoded definition fields must be classified')
    if any(v not in ('DATA_ONLY_EXPLICIT_REFERENCE','LISTENERS_REFERENCE','DYNAMIC_DECLARATIONS_REFERENCE') for v in coverage.values()):
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','unknown definition field operation')
    if spec.get('activation') not in ('ACTIVATE_REFERENCE','CONSTRUCT_ONLY_REFERENCE'):
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','explicit activation')
    if spec.get('pending_callbacks') not in ('RETAIN_ENQUEUED_REFERENCE','CANCEL_NOT_STARTED_REFERENCE'):
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','pending callback retention/cancellation')
    if (spec['pending_callbacks']=='RETAIN_ENQUEUED_REFERENCE' and
        spec.get('retained_read_policy')!='LIVE_THEN_DISPATCH_SNAPSHOT_REFERENCE'):
        fail(node,'CALLBACK_CONTEXT_MISSING','explicit retained callback read policy')
    precedence=need(node,spec,'provider_precedence','DYNAMIC_PROVIDER_MISSING')
    if (not isinstance(precedence,list) or not precedence or len(set(precedence))!=len(precedence) or
        any(x not in ('MODIFIER_LOCAL','SNAPSHOT','SOURCE_PROVIDER') for x in precedence)):
        fail(node,'DYNAMIC_PROVIDER_MISSING','explicit distinct provider precedence')
    return spec

def callback_context(engine,node,instance,event,spec):
    if spec.get('context_policy')!='OWNER_CASTER_TARGET_EVENT_EXPLICIT_REFERENCE':
        fail(node,'CALLBACK_CONTEXT_MISSING','explicit context inheritance')
    context=copy.deepcopy(instance.provider_binding['application_context'])
    context['modifier_source_context']=copy.deepcopy(context)
    context['ability_context']=copy.deepcopy(engine.state.target_context)
    context.update(owner=instance.owner,caster=instance.caster,original_caster=instance.original_caster,
        modifier_owner=instance.owner,modifier_instance_id=instance.instance_id,
        ability_target=instance.target,ability_targets=[instance.target],param_entity=instance.target,
        param_entity_stack=[instance.target],event_source=need(node,event,'source','CALLBACK_CONTEXT_MISSING'),
        event_payload=copy.deepcopy(event.get('payload',{})),event_target=event.get('target',instance.target),
        source_ability=instance.source_ability,
        dynamic_provider_parent=instance.provider_binding['source_provider'])
    # Dispatch ownership belongs to the current action, even for persistent instances.
    for key in ('action_root_id','ability_instance_id','parent_ability_id','parent_task_id','current_ability'):
        if key in engine.state.target_context: context[key]=engine.state.target_context[key]
    if instance.provider_binding['definition_policy']['pending_callbacks']=='RETAIN_ENQUEUED_REFERENCE':
        context['retained_modifier_state']=asdict(instance)
    return context

def listeners(engine,node,instance,definition,spec):
    result=[]
    compiled=definition['compiled_decoded']
    for f in compiled.get('fields',[]):
        if spec['field_bindings'][str(f['mask'])]!='LISTENERS_REFERENCE': continue
        for value in f.get('values',[]):
            if value.get('kind')!='list': fail(node,'EVENT_REGISTRATION_UNKNOWN','decoded callback list')
            for callback in value.get('children',[]):
                if callback.get('type')!='RPG.GameCore.TurnBasedModifierCallbackConfig':
                    fail(node,'EVENT_REGISTRATION_UNKNOWN','callback structural type')
                exact=stable_hash(callback)
                binding=need(node,spec.get('callbacks',{}),exact,'EVENT_REGISTRATION_UNKNOWN')
                fields={str(x['mask']):x['values'] for x in callback.get('fields',[])}
                mapping=need(node,binding,'fields','EVENT_REGISTRATION_UNKNOWN')
                if set(mapping)!=set(fields) or len(set(mapping.values()))!=len(mapping):
                    fail(node,'EVENT_REGISTRATION_UNKNOWN','all callback fields exactly once')
                r={role:fields[mask] for mask,role in mapping.items()}
                opaque=r.pop('OPAQUE_DATA_EXPLICIT_REFERENCE',None)
                if set(r)-{'event_id','predicate','tasks'}:
                    fail(node,'EVENT_REGISTRATION_UNKNOWN','unsupported callback field')
                event=need(node,r,'event_id','EVENT_REGISTRATION_UNKNOWN')
                tasks=need(node,r,'tasks','EVENT_REGISTRATION_UNKNOWN')
                if len(event)!=1 or type(event[0]) not in (int,str) or len(tasks)!=1 or tasks[0].get('kind')!='list':
                    fail(node,'EVENT_REGISTRATION_UNKNOWN','event ID and compiled task list')
                predicate=r.get('predicate')
                if predicate is not None and (len(predicate)!=1 or not isinstance(predicate[0],dict) or
                    predicate[0].get('kind')!='PredicateIR'):
                    fail(node,'EVENT_REGISTRATION_UNKNOWN','compiled predicate IR; numeric fields are not predicates')
                if binding.get('context_policy')!='OWNER_CASTER_TARGET_EVENT_EXPLICIT_REFERENCE':
                    fail(node,'CALLBACK_CONTEXT_MISSING','listener context')
                priority=integer(node,need(node,binding,'priority','EVENT_REGISTRATION_UNKNOWN'),minimum=-2**31)
                body=TaskSequenceIR(node.node_id+'/modifier_callback/'+exact,'immediate_sequence',node.authority,
                    {'tasks':[ir(x) for x in tasks[0]['children']], 'decoded_callback_hash':exact})
                engine.state.next_listener_id+=1
                result.append({'event_id':event[0],'modifier_instance_id':instance.instance_id,
                    'registration_id':'listener:'+str(engine.state.next_listener_id),'order':priority,
                    'owner':instance.owner,'caster':instance.caster,'original_caster':instance.original_caster,
                    'source_context':definition['source_identity'],'callback_target':instance.target,
                    'condition':predicate[0] if predicate else None,'callback':body.to_dict(),
                    'opaque_decoded_fields':copy.deepcopy(opaque),
                    'context_policy':binding['context_policy'],'decoded_callback_hash':exact,
                    'authority':['EVENT_ID_STRUCTURALLY_DECODED','LISTENER_REFERENCE_CONFIGURED',
                                 'NATIVE_EVENT_MEANING_UNKNOWN','NATIVE_EFFECTIVE_LISTENER_UNKNOWN']})
    return result

def dynamic_initial(engine,node,r,binding,spec,definition,provider):
    from .behavior_expansion import dynamic_dictionary
    local=engine.state.clone()
    local.target_context['reference_application_provider']={'source_provider':provider,'lookup_scopes':spec['lookup_scopes']}
    values={str(k):raw_checked(operand(engine,node,v,local)) for k,v in need(node,binding,'initial_dynamic_values','DYNAMIC_PROVIDER_MISSING').items()}
    if 'dynamic_values' in r:
        decoded=dynamic_dictionary(engine,node,local,r['dynamic_values'])
        collision=set(values)&set(decoded)
        merge=need(node,binding,'dynamic_initialization_policy','DYNAMIC_PROVIDER_MISSING')
        if merge not in ('SERIALIZED_OVERRIDES_REFERENCE','EXPLICIT_OVERRIDES_REFERENCE','REJECT_COLLISION_REFERENCE'):
            fail(node,'DYNAMIC_PROVIDER_MISSING','dynamic initialization precedence')
        if collision and merge=='REJECT_COLLISION_REFERENCE': fail(node,'DYNAMIC_PROVIDER_MISSING','duplicate initializer')
        values={**decoded,**values} if merge=='EXPLICIT_OVERRIDES_REFERENCE' else {**values,**decoded}
    for f in definition['compiled_decoded'].get('fields',[]):
        if spec['field_bindings'][str(f['mask'])]!='DYNAMIC_DECLARATIONS_REFERENCE': continue
        for value in f['values']:
            if value.get('type')!='DynamicValueLookup': fail(node,'DYNAMIC_PROVIDER_MISSING','unknown declaration structure')
            for entry in value.get('entries',[]):
                if str(entry['id']) not in values: fail(node,'DYNAMIC_PROVIDER_MISSING','explicit declared initializer '+str(entry['id']))
    return values

def apply(engine,node):
    p=policy(engine,node);state=engine.state
    binding=need(node,p['applications'],node.stable_hash(),'REFERENCE_INSTANCE_INPUT_MISSING')
    definition_id=need(node,binding,'definition_id','CONTENT_GRAPH_MISSING')
    definition=need(node,state.modifier_definitions,definition_id,'CONTENT_GRAPH_MISSING')
    spec=definition_policy(engine,node,definition,p)
    r=roles(node,binding)
    selector=need(node,r,'target','MODIFIER_TARGET_BINDING_MISSING')
    targets=engine.select(selector)
    name=operand(engine,node,need(node,r,'modifier','CONTENT_GRAPH_MISSING'))
    if name!=definition['config_identity']: fail(node,'CONTENT_GRAPH_MISSING','serialized reference/config mismatch')
    def entity(key):
        value=need(node,binding,key,'MODIFIER_TARGET_BINDING_MISSING')
        if value=='RESOLVED_TARGET_REFERENCE' and key=='owner': return value
        if isinstance(value,dict) and set(value)=={'context'}:
            value=need(node,state.target_context,value['context'],'MODIFIER_TARGET_BINDING_MISSING')
        if value not in state.entities: fail(node,'MODIFIER_TARGET_BINDING_MISSING','resolved '+key)
        return value
    owner,caster,original=entity('owner'),entity('caster'),entity('original_caster')
    for key,expected in [('caster',caster),('original_caster',original)]:
        if key in r and engine.select(r[key])!=[expected]:
            fail(node,'MODIFIER_TARGET_BINDING_MISSING','serialized '+key+' mismatch')
    source=need(node,binding,'source_ability','CALLBACK_CONTEXT_MISSING')
    if source=='CURRENT_ABILITY_REFERENCE': source=need(node,state.target_context,'current_ability','CALLBACK_CONTEXT_MISSING')
    if not isinstance(source,str) or not source: fail(node,'CALLBACK_CONTEXT_MISSING','source ability identity')
    provider=need(node,binding,'source_provider','DYNAMIC_PROVIDER_MISSING')
    if provider not in state.dynamic_values: fail(node,'DYNAMIC_PROVIDER_MISSING','existing source provider '+str(provider))
    if (owner!='RESOLVED_TARGET_REFERENCE' and targets!=[owner] and
        binding.get('owner_target_relation')!='EXPLICIT_DISTINCT_REFERENCE'):
        fail(node,'MODIFIER_TARGET_BINDING_MISSING','explicit owner/target agreement')
    duration=copy.deepcopy(need(node,binding,'duration'))
    if duration.get('units')!='EXPLICIT_REFERENCE_UNITS' or duration.get('expiry') not in ('EXPLICIT_ADVANCE_REFERENCE','EXPLICIT_EVENT_REFERENCE','MANUAL_REFERENCE'):
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','duration/expiry units')
    remaining=duration.get('remaining')
    if remaining is not None: integer(node,remaining)
    if duration['expiry']=='EXPLICIT_ADVANCE_REFERENCE' and remaining is None:
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','finite duration for advance')
    if duration['expiry']=='EXPLICIT_EVENT_REFERENCE': need(node,duration,'event_id','EVENT_REGISTRATION_UNKNOWN')
    if 'lifetime' in r and operand(engine,node,r['lifetime'])!=duration.get('serialized_lifetime_raw'):
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','serialized lifetime operand match')
    duration.setdefault('original',remaining)
    dynamics=dynamic_initial(engine,node,r,binding,spec,definition,provider)
    snapshots={}
    for key,request in need(node,binding,'snapshot_properties','DYNAMIC_PROVIDER_MISSING').items():
        target={'OWNER_REFERENCE':owner,'CASTER_REFERENCE':caster,'ORIGINAL_CASTER_REFERENCE':original}.get(request['entity'],request['entity'])
        if target=='RESOLVED_TARGET_REFERENCE': fail(node,'DYNAMIC_PROVIDER_MISSING','snapshot requires per-target identity')
        snapshots[str(key)]=raw_checked(need(node,state.properties.get(target,{}),request['property'],'DYNAMIC_PROVIDER_MISSING'))
    operation=need(node,binding,'application_policy')
    if operation not in APPLICATIONS: fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','NATIVE_POLICY_UNKNOWN: '+str(operation))
    keys=need(node,binding,'match_identity')
    if (not isinstance(keys,list) or len(set(keys))!=len(keys) or not {'definition_id','owner','target'}<=set(keys) or
        any(k not in IDENTITIES for k in keys)):
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','explicit relevant identities')
    stack=integer(node,operand(engine,node,r.get('stack',need(node,binding,'stack'))))
    count=integer(node,operand(engine,node,r.get('count',need(node,binding,'count'))))
    metric(engine,'modifier_applications_attempted',len(targets))
    result=[]
    for target in targets:
        actual_owner=target if owner=='RESOLVED_TARGET_REFERENCE' else owner
        probe={'definition_id':definition_id,'config_identity':name,'owner':actual_owner,'target':target,
               'caster':caster,'original_caster':original,'source_ability':source}
        matches=[m for m in state.modifiers.values() if all(getattr(m,k)==probe[k] for k in keys)]
        if len(matches)>1: fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','ambiguous existing instance')
        old=matches[0] if matches else None
        if old and operation=='REJECT_DUPLICATE_REFERENCE':
            boundary(engine,old,'REFERENCE_DUPLICATE_REJECTED');metric(engine,'modifier_applications_completed');continue
        if old and operation=='INSERT_NEW_REFERENCE': fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','insert collision')
        if operation in ('REFRESH_EXISTING_REFERENCE','REPLACE_EXISTING_REFERENCE','INCREMENT_STACK_REFERENCE') and old is None:
            fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','existing instance required')
        if old and operation in ('REFRESH_EXISTING_REFERENCE','INCREMENT_STACK_REFERENCE'):
            if any(getattr(old,k)!=probe[k] for k in IDENTITIES):
                if binding.get('cross_source_update')!='PRESERVE_EXISTING_IDENTITIES_REFERENCE':
                    fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','cross-source update requires identity policy')
            update=need(node,binding,'update_values')
            if update not in ('PRESERVE_REFERENCE','REINITIALIZE_REFERENCE'): fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','refresh value policy')
            instance=old
            provider_update=need(node,binding,'update_provider','DYNAMIC_PROVIDER_MISSING')
            if provider_update=='REBIND_PROVIDER_REFERENCE':
                instance.provider_binding.update(source_provider=provider,precedence=copy.deepcopy(spec['provider_precedence']),
                    lookup_scopes=copy.deepcopy(spec['lookup_scopes']),application_context=copy.deepcopy(state.target_context),
                    definition_policy=copy.deepcopy(spec))
            elif provider_update!='PRESERVE_PROVIDER_REFERENCE':
                fail(node,'DYNAMIC_PROVIDER_MISSING','refresh provider policy')
            if need(node,binding,'update_contributions')!='PRESERVE_EXPLICIT_CONTRIBUTIONS_REFERENCE':
                fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','contribution update policy')
            if update=='REINITIALIZE_REFERENCE':
                instance.dynamic_values=copy.deepcopy(dynamics);instance.snapshot_data=copy.deepcopy(snapshots)
            if operation=='REFRESH_EXISTING_REFERENCE':
                instance.duration=copy.deepcopy(duration);instance.refresh_count+=1
                metric(engine,'modifier_instances_refreshed')
            else:
                instance.stack+=stack;instance.count+=count
                metric(engine,'modifier_stacks_incremented')
            instance.reference_policy=copy.deepcopy(binding)
            boundary(engine,instance,'REFERENCE_INSTANCE_UPDATED',operation=operation)
            if need(node,binding,'update_activation_callbacks')=='DISPATCH_REFERENCE':
                for event_id in spec['activation_event_ids']:
                    result.extend(dispatch(engine,node,{'event_id':event_id,'source':caster,'target':target,'payload':{'update':operation}},only=instance.instance_id))
            elif binding['update_activation_callbacks']!='NO_REACTIVATION_REFERENCE':
                fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','update activation callback policy')
            metric(engine,'modifier_applications_completed');continue
        replacement=None
        if old:
            replacement=old.instance_id;remove_instance(engine,node,old,'REPLACED_REFERENCE',spec['pending_callbacks'])
        state.next_modifier_id+=1
        instance=ModifierInstance('modifier:'+str(state.next_modifier_id),name,actual_owner,caster,original,stack,count,
            copy.deepcopy(duration),copy.deepcopy(dynamics),copy.deepcopy(snapshots),definition_id=definition_id,
            source_ability=source,target=target,created_at=moment(engine),reference_policy=copy.deepcopy(binding),
            provider_binding={'source_provider':provider,'precedence':spec['provider_precedence'],
                'lookup_scopes':need(node,spec,'lookup_scopes','DYNAMIC_PROVIDER_MISSING'),
                'application_context':copy.deepcopy(state.target_context),'definition_policy':copy.deepcopy(spec)},
            replacement_of=replacement,authority={'semantic_authority':'REFERENCE_MODEL',
                'definition_graph_hash':definition['graph_hash'],'native_effective_state':'UNKNOWN'})
        state.modifiers[instance.instance_id]=instance
        metric(engine,'modifier_instances_created');boundary(engine,instance,'REFERENCE_INSTANCE_CONSTRUCTED')
        if spec['activation']=='ACTIVATE_REFERENCE':
            instance.activation_state='REFERENCE_INSTANCE_ACTIVE';instance.activated_at=moment(engine)
            boundary(engine,instance,'REFERENCE_INSTANCE_ACTIVE')
            instance.event_registrations=listeners(engine,node,instance,definition,spec)
            metric(engine,'listeners_registered',len(instance.event_registrations))
            boundary(engine,instance,'REFERENCE_LISTENERS_REGISTERED',count=len(instance.event_registrations))
            for event_id in need(node,spec,'activation_event_ids','EVENT_REGISTRATION_UNKNOWN'):
                result.extend(dispatch(engine,node,{'event_id':event_id,'source':caster,'target':target,'payload':{'activation':'REFERENCE'}},only=instance.instance_id))
        metric(engine,'modifier_applications_completed')
    return result

def _dispatch(engine,node,event=None,only=None):
    policy(engine,node)
    event=copy.deepcopy(event if event is not None else node.payload)
    event_id=need(node,event,'event_id','EVENT_REGISTRATION_UNKNOWN')
    if type(event_id) not in (int,str): fail(node,'EVENT_REGISTRATION_UNKNOWN','opaque scalar event ID')
    source=need(node,event,'source','CALLBACK_CONTEXT_MISSING')
    if source not in engine.state.entities: fail(node,'CALLBACK_CONTEXT_MISSING','resolved event source')
    selected=[]
    for instance in engine.state.modifiers.values():
        if instance.activation_state!='REFERENCE_INSTANCE_ACTIVE' or (only and instance.instance_id!=only): continue
        for registration in instance.event_registrations:
            if registration['event_id']==event_id:
                selected.append((registration['order'],instance.instance_id,registration['registration_id'],instance,registration))
    result=[]
    for _,_,_,instance,registration in sorted(selected,key=lambda x:x[:3]):
        context=callback_context(engine,node,instance,event,registration)
        local=engine.state.clone();local.target_context=context
        condition=registration.get('condition')
        if condition is not None and not engine.predicate(ir(condition),local):
            engine.state.rng=copy.deepcopy(local.rng);continue
        engine.state.rng=copy.deepcopy(local.rng)
        result.append(TaskIR(node.node_id+'/listener/'+registration['registration_id'],
            'reference_context_callback',node.authority,{'context':context,'callback':ir(registration['callback']),
                'mutation_result':'NORMAL_GENERIC_TASK_EXECUTION','modifier_instance_id':instance.instance_id,
                'registration_id':registration['registration_id'],'source_event':event}))
    # Explicit expiry event semantics are caller policy, never a native turn event.
    for instance in list(engine.state.modifiers.values()):
        if (not only and instance.duration.get('expiry')=='EXPLICIT_EVENT_REFERENCE' and
            instance.duration.get('event_id')==event_id):
            remove_instance(engine,node,instance,'EXPLICIT_EXPIRY_EVENT_REFERENCE',instance.provider_binding['definition_policy']['pending_callbacks'])
            if instance.provider_binding['definition_policy']['pending_callbacks']=='CANCEL_NOT_STARTED_REFERENCE':
                result=[n for n in result if n.payload['modifier_instance_id']!=instance.instance_id]
    metric(engine,'events_dispatched');return result

def dispatch(engine,node,event=None,only=None):
    try: return _dispatch(engine,node,event,only)
    except NumericSemanticGap as exc: fail(node,'DYNAMIC_PROVIDER_MISSING',str(exc))
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        fail(node,'EVENT_REGISTRATION_UNKNOWN',str(exc))

def cancel_pending(engine,instance):
    d=engine.state.scheduler.action_execution
    for event in d['events'].values():
        before=event['nodes'][:event['cursor']]
        after=[n for n in event['nodes'][event['cursor']:] if n.get('payload',{}).get('modifier_instance_id')!=instance.instance_id]
        event['nodes']=before+after
        if event['cursor']==len(event['nodes']):
            event['status']='COMPLETE'
            if event['frame_id'] in d['event_queue']: d['event_queue'].remove(event['frame_id'])
    for callback in d['callbacks'].values():
        if callback.get('modifier_instance_id')==instance.instance_id and callback['status']=='READY':
            callback['status']='CALLBACK_CANCELLED_REFERENCE'
            if callback['frame_id'] in d['callback_queue']: d['callback_queue'].remove(callback['frame_id'])
            metric(engine,'modifier_callbacks_cancelled')

def remove_instance(engine,node,instance,reason,pending):
    if pending not in ('RETAIN_ENQUEUED_REFERENCE','CANCEL_NOT_STARTED_REFERENCE'):
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','explicit removal pending callback policy')
    if pending=='CANCEL_NOT_STARTED_REFERENCE': cancel_pending(engine,instance)
    for contribution in list(instance.property_contributions):
        props=engine.state.properties[contribution['entity']]
        props[contribution['property']]=fixed_binary('sub',props[contribution['property']],contribution['value'])
    instance.property_contributions=[];instance.event_registrations=[]
    instance.activation_state='REFERENCE_INSTANCE_REMOVED';instance.removal_reason=reason;instance.removed_at=moment(engine)
    boundary(engine,instance,'REFERENCE_INSTANCE_REMOVED',removal_reason=reason,final_state=asdict(instance))
    del engine.state.modifiers[instance.instance_id];metric(engine,'modifier_instances_removed')

def remove(engine,node):
    p=policy(engine,node)
    binding=need(node,p['removals'],node.stable_hash())
    mode=need(node,binding,'selection')
    if mode=='INSTANCE_REFERENCE':
        identity=need(node,binding,'instance_id')
        if identity=='CURRENT_MODIFIER_REFERENCE': identity=need(node,engine.state.target_context,'modifier_instance_id','CALLBACK_CONTEXT_MISSING')
        selected=[need(node,engine.state.modifiers,identity)]
    elif mode in ('CONFIG_TARGET_REFERENCE','TARGET_FILTER_REFERENCE'):
        r=roles(node,binding)
        targets=engine.select(need(node,r,'target','MODIFIER_TARGET_BINDING_MISSING'))
        name=operand(engine,node,r['modifier']) if 'modifier' in r else None
        if mode=='CONFIG_TARGET_REFERENCE' and name is None: fail(node,'CONTENT_GRAPH_MISSING','remove config operand')
        filters=need(node,binding,'identity_filter')
        if any(k not in IDENTITIES for k in filters): fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','remove filter identity')
        selected=[m for m in engine.state.modifiers.values() if m.target in targets and (name is None or m.config_identity==name)
                  and all(getattr(m,k)==v for k,v in filters.items())]
    else: fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','explicit remove selection')
    for instance in selected: remove_instance(engine,node,instance,need(node,binding,'reason'),need(node,binding,'pending_callbacks'))
    return []

def lookup(engine,node,state):
    identity=state.target_context.get('modifier_instance_id')
    instance=state.modifiers.get(identity)
    if instance is None:
        # Retained callbacks retain a serialized read context after removal.
        saved=state.target_context.get('retained_modifier_state')
        if saved: instance=ModifierInstance(**saved)
    if instance is None: fail(node,'DYNAMIC_PROVIDER_MISSING','active or explicitly retained modifier')
    key=str(node.payload['key'])
    stores={'MODIFIER_LOCAL':instance.dynamic_values,'SNAPSHOT':instance.snapshot_data,
            'SOURCE_PROVIDER':state.dynamic_values.get(instance.provider_binding['source_provider'],{})}
    for provider in instance.provider_binding['precedence']:
        if key in stores[provider]: return raw_checked(stores[provider][key])
    fail(node,'DYNAMIC_PROVIDER_MISSING','key '+key+' under explicit precedence')

def property_contribution(engine,node):
    p=policy(engine,node);binding=need(node,p['property_tasks'],node.stable_hash())
    if binding.get('aggregation')!='ADDITIVE_REVERSIBLE_REFERENCE':
        fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','explicit property aggregation')
    identity=need(node,engine.state.target_context,'modifier_instance_id','CALLBACK_CONTEXT_MISSING')
    instance=need(node,engine.state.modifiers,identity,'CALLBACK_CONTEXT_MISSING')
    r=roles(node,binding)
    key=need(node,binding.get('properties',{}),str(need(node,r,'property')))
    value=raw_checked(operand(engine,node,need(node,r,'value')))
    for target in engine.select(need(node,r,'target','MODIFIER_TARGET_BINDING_MISSING')):
        props=need(node,engine.state.properties,target)
        props[key]=fixed_binary('add',need(node,props,key),value)
        instance.property_contributions.append({'entity':target,'property':key,'value':value,
            'aggregation_policy':copy.deepcopy(binding),'source_node_hash':node.stable_hash()})
    return []

def turn_duration(engine, node):
    """Explicit owner-normal-turn lifetime cursor, drained by the existing R15.

    New instances are selected by the R22 creation-turn policy. Expiry listeners
    run before removal in the same owned callback infrastructure.
    """
    policy(engine, node)
    from .battle_turn import ADAPTER, KEY
    adapter = engine.state.mechanics[ADAPTER]
    p = node.payload
    instance = engine.state.modifiers.get(p['instance_id'])
    if instance is None:
        return []
    if instance.owner != p['owner']:
        fail(node, 'MODIFIER_LIFECYCLE_POLICY_MISSING', 'turn duration owner mismatch')
    cursor = p['turn_id'] + '/' + instance.instance_id
    event = next(x for x in engine.state.mechanics[KEY]['boundary_work'] if x['boundary_id'] == p['boundary_id'])
    if node.op == 'r22_modifier_expire_reference':
        if adapter['duration_visits'].get(cursor + '/expiry'):
            return []
        if instance.pending_lifecycle_callbacks:
            fail(node, 'MODIFIER_LIFECYCLE_POLICY_MISSING', 'expiry callback drain required')
        remove_instance(engine, node, instance, 'OWNER_NORMAL_DURATION_EXPIRED_REFERENCE', p['spec']['pending_callbacks'])
        adapter['duration_visits'][cursor + '/expiry'] = True
        event['duration_instance_cursor'] += 1
        return []
    if p['stage'] == 'DURATION_PROGRESS':
        if adapter['duration_visits'].get(cursor):
            return []
        remaining = integer(node, instance.duration['remaining'])
        instance.duration['remaining'] = max(0, remaining - 1)
        adapter['duration_visits'][cursor] = True
        event['duration_instance_cursor'] += 1
        boundary(engine, instance, 'OWNER_NORMAL_DURATION_PROGRESS_REFERENCE', turn_id=p['turn_id'],
                 remaining=instance.duration['remaining'])
        return []
    if p['stage'] == 'EXPIRY_CHECK' and instance.duration['remaining'] == 0:
        nodes = []
        expiry_event = p['spec'].get('expiry_event')
        if expiry_event is not None:
            nodes.append(TaskIR(node.node_id + '/expiry-event', 'modifier_event_dispatch', node.authority,
                {'event_id': expiry_event, 'source': p['owner'], 'target': p['owner'],
                 'only_instance': instance.instance_id, 'payload': {'turn_id': p['turn_id'], 'expiry': 'REFERENCE'},
                 'drain_before_resume_reference': True}))
        nodes.append(TaskIR(node.node_id + '/remove', 'r22_modifier_expire_reference', node.authority, copy.deepcopy(p)))
        return nodes
    return []


def _execute(engine,node):
    if node.op in ('r22_modifier_duration_reference', 'r22_modifier_expire_reference'):
        return turn_duration(engine, node)
    short=node.op.rsplit('.',1)[-1]
    if short=='AddModifier': return apply(engine,node)
    if short=='RemoveModifier' or node.op=='modifier_remove_reference': return remove(engine,node)
    if short=='StackProperty': return property_contribution(engine,node)
    if node.op=='modifier_activate_reference':
        p=policy(engine,node)
        binding=need(node,p.get('activations',{}),node.stable_hash())
        instance=need(node,engine.state.modifiers,need(node,binding,'instance_id'))
        if instance.activation_state!='REFERENCE_INSTANCE_CONSTRUCTED':
            fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','constructed instance required for activation')
        if binding.get('activation')!='ACTIVATE_REFERENCE':
            fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','explicit delayed activation')
        definition=engine.state.modifier_definitions[instance.definition_id]
        spec=definition_policy(engine,node,definition,p)
        instance.activation_state='REFERENCE_INSTANCE_ACTIVE';instance.activated_at=moment(engine)
        boundary(engine,instance,'REFERENCE_INSTANCE_ACTIVE')
        instance.event_registrations=listeners(engine,node,instance,definition,spec)
        metric(engine,'listeners_registered',len(instance.event_registrations))
        boundary(engine,instance,'REFERENCE_LISTENERS_REGISTERED',count=len(instance.event_registrations))
        return [child for event_id in need(node,spec,'activation_event_ids','EVENT_REGISTRATION_UNKNOWN')
                for child in dispatch(engine,node,{'event_id':event_id,'source':instance.caster,
                     'target':instance.target,'payload':{'activation':'REFERENCE'}},only=instance.instance_id)]
    if short=='HealHP':
        p=policy(engine,node)
        spec=need(node,p['heal_stages'],node.stable_hash())
        if (node.payload.get('fields',{}).get('FormulaType')!=2 or spec.get('formula')!='FORMULA_TYPE2_REFERENCE' or
            spec.get('ordering')!=['pre_heal','effective_amount','settlement','hp_mutation','post_heal']):
            fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','explicit FormulaType2 heal stage order')
        result=[]
        for stage in spec['ordering']:
            event=need(node,need(node,spec,'events','EVENT_REGISTRATION_UNKNOWN'),stage,'EVENT_REGISTRATION_UNKNOWN')
            if stage=='effective_amount':
                result.append(TaskIR(node.node_id+'/amount','reference_heal_amount',node.authority,{'spec':spec}))
            if event is not None:
                result.append(TaskIR(node.node_id+'/'+stage,'modifier_event_dispatch',node.authority,
                    {'event_id':event,'source':need(node,spec,'event_source','CALLBACK_CONTEXT_MISSING'),
                     'payload':{'heal_stage':stage}}))
                result[-1] = TaskIR(result[-1].node_id,result[-1].op,result[-1].authority,
                    {**result[-1].payload,'drain_before_resume_reference':True})
            if stage=='hp_mutation':
                result.append(TaskIR(node.node_id+'/hp','reference_heal_hp_mutation',node.authority,
                    {'spec':spec,'target':node.payload['fields']['TargetType']}))
        return [TaskSequenceIR(node.node_id+'/heal_stages','immediate_sequence',node.authority,{'tasks':result})]
    if node.op=='reference_heal_amount':
        from .behavior_primitives import heal_formula2_core
        policy(engine,node);spec=node.payload['spec']
        provider=need(node,spec,'amount_provider','DYNAMIC_PROVIDER_MISSING')
        store=need(node,engine.state.dynamic_values,provider,'DYNAMIC_PROVIDER_MISSING')
        store[str(spec['amount_key'])]=heal_formula2_core(need(node,spec,'operands'),need(node,spec,'cap_enabled')).amount_raw
        return []
    if node.op=='reference_heal_hp_mutation':
        policy(engine,node);spec=node.payload['spec']
        if spec.get('settlement')!='CLAMP_HP_REFERENCE': fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','reference heal settlement')
        amount=raw_checked(need(node,engine.state.dynamic_values.get(spec['amount_provider'],{}),str(spec['amount_key']),'DYNAMIC_PROVIDER_MISSING'))
        if amount<0: fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','nonnegative healing amount')
        for target in engine.select(node.payload['target']):
            props=need(node,engine.state.properties,target)
            hp=raw_checked(need(node,props,'hp'));maximum=raw_checked(need(node,props,'max_hp'))
            if not 0<=hp<=maximum: fail(node,'MODIFIER_LIFECYCLE_POLICY_MISSING','bounded reference HP')
            props['hp']=min(maximum,fixed_binary('add',hp,amount))
        metric(engine,'reference_heal_settlements');return []
    if node.op=='combat_event_extension_reference':
        policy(engine,node)
        if node.payload.get('stage') not in ('before_damage','amount_modification','property_mutation','after_damage'):
            fail(node,'EVENT_REGISTRATION_UNKNOWN','explicit damage extension stage')
        # A configured event point, with no damage formula or implicit native ordering.
        event=TaskIR(node.node_id+'/event','modifier_event_dispatch',node.authority,
            {k:v for k,v in node.payload.items() if k!='stage'})
        return [event]
    if short=='SetDynamicValue' and 'modifier_instance_id' in engine.state.target_context:
        policy(engine,node)
        binding=need(node,engine.policies[POLICY_ID].get('dynamic_writes',{}),node.stable_hash(),'DYNAMIC_PROVIDER_MISSING')
        if binding.get('provider')!='MODIFIER_LOCAL_REFERENCE': fail(node,'DYNAMIC_PROVIDER_MISSING','explicit local write')
        m=need(node,engine.state.modifiers,engine.state.target_context['modifier_instance_id'],'DYNAMIC_PROVIDER_MISSING')
        f=node.payload['fields']
        if 'DynamicKey' in f and 'Value' in f:
            key,value=f['DynamicKey'],f['Value']
        else:
            mapping=need(node,binding,'operand_fields','DYNAMIC_PROVIDER_MISSING')
            if set(mapping)!= {'key','value'} or set(mapping.values())!=set(f) or len(f)!=2:
                fail(node,'DYNAMIC_PROVIDER_MISSING','exact key/value write operand coverage')
            key,value=f[mapping['key']],f[mapping['value']]
        m.dynamic_values[str(operand(engine,node,key))]=raw_checked(operand(engine,node,value))
        return []
    if node.op=='modifier_lifetime_advance_reference':
        policy(engine,node)
        delta=integer(node,need(node,node.payload,'delta'))
        for instance in list(engine.state.modifiers.values()):
            if instance.duration['expiry']=='EXPLICIT_ADVANCE_REFERENCE':
                instance.duration['remaining']=max(0,instance.duration['remaining']-delta)
                if instance.duration['remaining']==0:
                    remove_instance(engine,node,instance,'EXPLICIT_DURATION_EXPIRED_REFERENCE',instance.provider_binding['definition_policy']['pending_callbacks'])
        return []
    return None

def execute(engine,node):
    """Malformed/unknown serialized reference inputs are typed gaps, not crashes."""
    try: return _execute(engine,node)
    except NumericSemanticGap as exc: fail(node,'PROPERTY_DYNAMIC_PROVIDER',str(exc))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        fail(node,'REFERENCE_INSTANCE_INPUT_MISSING',str(exc))

def install(registry):
    previous=registry.handlers['expression']['lookup']
    def read_value(engine,node,state):
        application=state.target_context.get('reference_application_provider')
        if POLICY_ID in engine.policies and application and node.payload['scope'] in application['lookup_scopes']:
            store=need(node,state.dynamic_values,application['source_provider'],'DYNAMIC_PROVIDER_MISSING')
            return raw_checked(need(node,store,str(node.payload['key']),'DYNAMIC_PROVIDER_MISSING'))
        if POLICY_ID in engine.policies and 'modifier_instance_id' in state.target_context:
            m=state.modifiers.get(state.target_context['modifier_instance_id'])
            if m and node.payload['scope'] in m.provider_binding.get('lookup_scopes',[]): return lookup(engine,node,state)
            saved=state.target_context.get('retained_modifier_state')
            if saved and node.payload['scope'] in saved['provider_binding'].get('lookup_scopes',[]): return lookup(engine,node,state)
        return previous[1](engine,node,state)
    registry.handlers['expression']['lookup']=('reference_r17_provider_v1',read_value)
    registry.register('expression','modifier_snapshot_read',lambda e,n,s: snapshot_read(e,n,s),'reference_r17_v1')

def snapshot_read(engine,node,state):
    instance=state.modifiers.get(state.target_context.get('modifier_instance_id'))
    if instance is None and state.target_context.get('retained_modifier_state'):
        instance=ModifierInstance(**state.target_context['retained_modifier_state'])
    if instance is None: fail(node,'DYNAMIC_PROVIDER_MISSING','snapshot callback context')
    return raw_checked(need(node,instance.snapshot_data,str(node.payload['key']),'DYNAMIC_PROVIDER_MISSING'))
