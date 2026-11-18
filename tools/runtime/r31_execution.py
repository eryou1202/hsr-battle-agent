"""R31 real unchanged Jade replay and isolated regression runner."""
from r30_closure import *
from dataclasses import asdict
AUDIT=ROOT/'tmp/audit/r31_original_task_breakthrough_20261108_001'
OLD=ROOT/'tmp/audit/r29_original_executor_context_20261108_001'

def write(n,v):
    p=AUDIT/n;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')

def original():
    from hsr_battle_agent.battle_ir.behavior import IRNode
    folder=OLD/'reference/Avatar_Jade_00_Skill02_Phase01'
    return folder, IRNode.from_dict(read(folder/'receipt.json')['next_gap']['node'])

def bound_runtime():
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
    from hsr_battle_agent.battle_runtime.original_bindings import bind_compare_target_reference
    folder,node=original()
    r=BehaviorRuntime.from_snapshot(read(folder/'initial_runtime.json'))
    receipt=bind_compare_target_reference(r,node,
        selector_policy='MASK15_CALLER_RESOLVED_REFERENCE',
        result_policy='BOOLEAN_TO_R15_BRANCH_REFERENCE')
    return r,node,receipt

def execute(target='b'):
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
    r,node,binding=bound_runtime()
    if target == 'false':
        # Separate explicit resolved-alias reference scenario. The template in
        # the saved canonical input inherits Caster as AbilityTargetEntity.
        from hsr_battle_agent.battle_ir.behavior import IRNode
        alias=r.aliases['AbilityTargetEntity'].to_dict()
        alias.update(op='explicit',payload={'entities':['b']})
        r.aliases['AbilityTargetEntity']=IRNode.from_dict(alias)
    before_ir={k:v.stable_hash() for k,v in r.abilities.items()}
    initial=r.snapshot();commands=[]
    cmd,decision=r.record_turn_command('advance',{'budget':10000});commands.append(cmd)
    permission=r.legal_action_candidates(decision['decision_id'])[0]
    cmd,_=r.record_turn_command('submit',dict(permission=permission,targets=['b'],expected_revision=decision['state_revision']));commands.append(cmd)
    cmd,out=r.record_turn_command('complete',{'budget':10000});commands.append(cmd)
    out=out.to_dict()
    final=r.snapshot()
    again,_=BehaviorRuntime.from_snapshot(initial).replay_turn_commands(commands)
    assert again.snapshot()==final
    assert r.clone().stable_hash()==BehaviorRuntime.from_snapshot(json.loads(json.dumps(final))).stable_hash()
    assert before_ir=={k:v.stable_hash() for k,v in r.abilities.items()}
    diag=r.clone().run_until_blocked()
    decisions=[t for t in out.get('trace',[]) if 'predicate_result' in t]
    # Turn receipts may summarize traces; preserve the direct engine trace too.
    decisions += [t for t in r.trace if 'predicate_result' in t and t not in decisions]
    row=dict(target=target,before=8,after=r.state.scheduler.action_execution['metrics']['tasks_completed'],
        binding=binding,output=out,next_gap=asdict(diag.gap) if diag.gap else None,
        decisions=decisions,unchanged_ability_hashes=before_ir,original_predicate_hash=node.stable_hash(),
        clone_snapshot_replay='PASS',native_effective_validated=False)
    for n,v in [('initial_runtime.json',initial),('commands.json',commands),('final_runtime.json',final),('receipt.json',row)]:write('jade/'+target+'/'+n,v)
    return row

def replays():
    import r30_closure as old
    old.AUDIT=AUDIT
    old.replays()
    rows=[execute('b'),execute('false')]
    write('jade/results.json',rows)
    print([(r['target'],r['before'],r['after'],r['next_gap']['task_type'] if r['next_gap'] else None) for r in rows],flush=True)

def main():
    import r30_closure as old
    old.AUDIT=AUDIT
    if sys.argv[1]=='replays':replays()
    elif sys.argv[1]=='tests':old.tests()
    elif sys.argv[1]=='fresh':
        old.AUDIT=AUDIT/'fresh';old.AUDIT.mkdir(exist_ok=True)
        old.tests()
    elif sys.argv[1]=='scenario_tests':
        # Original runner invokes its own file; run modes here with CR-local paths.
        receipts={}
        for mode,count in [('frozen',632),('skills',160),('defense',18),('encounters',18),('planner',20),('turns',14)]:
            started=now();args=[sys.executable,__file__,'regressions',mode]
            p=subprocess.run(args,cwd=ROOT,capture_output=True)
            write('tests/scenario_'+mode+'.json',dict(command=args,actual_exit_code=p.returncode,started=started,finished=now(),count=count))
            (AUDIT/'tests'/('scenario_'+mode+'.log')).write_bytes(p.stdout+p.stderr)
            receipts[mode]=dict(actual_exit_code=p.returncode,count=count)
            write('tests/scenarios.json',receipts);print(mode,p.returncode,flush=True)
        assert all(v['actual_exit_code']==0 for v in receipts.values())
    elif sys.argv[1]=='regressions':old.regressions(sys.argv[2])
if __name__=='__main__':main()
