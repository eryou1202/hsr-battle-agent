"""R29 isolated evidence and replay receipts; no Git writes or inherited audit writes."""
import datetime
from dataclasses import asdict
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime')]
AUDIT = ROOT/'tmp/audit/r29_original_executor_context_20261108_001'
OLD = ROOT/'tmp/audit/r28_original_combat_semantics_20261022_001'
R27 = ROOT/'tmp/audit/r27_real_character_monster_20261022_001'
def read(p): return json.loads(p.read_text(encoding='utf8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):
    p=AUDIT/n; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def gate():
    assert not (AUDIT/'start_gate.json').exists()
    names=set(git('ls-files','-z').split('\0'))
    names.update(git('ls-files','--others','--exclude-standard','-z').split('\0'))
    files={n:sha(ROOT/n) for n in sorted(names) if n and (ROOT/n).is_file() and not n.startswith('tools/runtime/r29_')}
    write('start_gate.json',dict(head=git('rev-parse','HEAD'),branch=git('branch','--show-current'),
        status=git('status','--short'),staged=git('diff','--cached','--name-status'),file_hashes=files,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        timing='Recorded after initial read-only Git gate and R29-only source collector creation; no inherited file edited'))

def replay():
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
    from hsr_battle_agent.battle_ir.behavior import IRNode
    rows=[]
    for row in read(OLD/'character/results.json'):
        root=row['root']; folder=OLD/'character'/root
        before=read(folder/'after.json'); initial=read(folder/'initial_runtime.json')
        name=before['canonical_binding']['binding_hash'][:16]+'_template'
        commands=read(OLD/'character/scenarios'/name/'commands.json')
        r=BehaviorRuntime.from_snapshot(initial)
        final,events=r.replay_turn_commands(commands)
        assert final.snapshot()==read(folder/'final_runtime.json')
        assert final.stable_hash()==before['full_runtime_hash']
        assert final.clone().stable_hash()==BehaviorRuntime.from_snapshot(json.loads(json.dumps(final.snapshot()))).stable_hash()
        again,_=BehaviorRuntime.from_snapshot(initial).replay_turn_commands(commands)
        assert again.stable_hash()==final.stable_hash()
        node=before['gap_node']
        # Resolve the actual failing identity rather than relying on report prose.
        import re
        hashes=re.findall(r'\b[0-9a-f]{64}\b',before['required_capability'])
        if hashes and IRNode.from_dict(node).stable_hash()!=hashes[-1]:
            found=[]
            def scan(value):
                if isinstance(value,dict):
                    if value.get('kind')=='TaskIR' and IRNode.from_dict(value).stable_hash()==hashes[-1]:found.append(value)
                    for v in value.values():scan(v)
                elif isinstance(value,list):
                    for v in value:scan(v)
            scan(final.snapshot())
            assert found, (root,hashes[-1])
            node=found[0]
        receipt=dict(root=root,canonical_owner=before['canonical_binding'],original_IR_hash=before['canonical_IR_hash'],
            current_task=node,task_hash=IRNode.from_dict(node).stable_hash(),native_source_span=node['payload'].get('span'),
            operand_classification=node['payload'],initial_runtime_hash=r.stable_hash(),final_runtime_hash=final.stable_hash(),
            before_completed=row['after'],after_completed=row['after'],next_SemanticGap=before['required_capability'],
            required_capability=before['required_capability'],authority='UNCHANGED_R28_REFERENCE_INPUTS',
            clone='PASS',json_snapshot='PASS',replay='PASS',actions_completed=before['actions_completed'])
        for n,v in [('before.json',receipt),('after.json',receipt),('initial_runtime.json',initial),('commands.json',commands),('final_runtime.json',final.snapshot())]:write('character/'+root+'/'+n,v)
        rows.append(receipt)
        print(root,row['after'],final.stable_hash(),flush=True)
    write('character/results.json',rows)
    monsters=[]
    for p in sorted((R27/'monster/execution').glob('*/commands.json')):
        initial=read(p.parent/'initial_runtime.json'); commands=read(p)
        final,_=BehaviorRuntime.from_snapshot(initial).replay_turn_commands(commands)
        assert final.snapshot()==read(p.parent/'final_runtime.json')
        assert final.clone().stable_hash()==BehaviorRuntime.from_snapshot(json.loads(json.dumps(final.snapshot()))).stable_hash()
        receipt=dict(prior=read(p.parent/'result.json'),final_runtime_hash=final.stable_hash(),replay='PASS',clone_snapshot='PASS')
        for n,v in [('before_after.json',receipt),('initial_runtime.json',initial),('commands.json',commands),('final_runtime.json',final.snapshot())]:write('monster/'+p.parent.name+'/'+n,v)
        monsters.append(receipt)
    write('monster/results.json',monsters)

def validate():
    gate_doc=read(AUDIT/'start_gate.json')
    changed=[n for n,h in gate_doc['file_hashes'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    assert not changed,changed
    assert git('rev-parse','HEAD')==gate_doc['head'] and git('branch','--show-current')==gate_doc['branch']
    assert git('diff','--cached','--name-status')==gate_doc['staged']
    pin=read(R27/'resume/input_hashes.json')
    assert all(sha(ROOT/n)==h for n,h in pin['files'].items())
    write('tests/inherited.json',dict(mode='REVALIDATED_PRIOR_PASS_NOT_FRESH',input_hashes=pin,receipts=read(R27/'release_tests.json'),runtime_cases=651))
    write('preservation.json',dict(starting_files_checked=len(gate_doc['file_hashes']),changed_files=[],frozen_drift=0,head=gate_doc['head'],git_writes='NONE'))

def advance_reference():
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
    from hsr_battle_agent.battle_ir.behavior import IRNode
    from hsr_battle_agent.battle_runtime.original_bindings import bind_remove_reference
    rows=[]
    for before in read(AUDIT/'character/results.json'):
        root=before['root']
        if 'Fugue' not in root and 'Jade' not in root:continue
        folder=AUDIT/'character'/root
        r=BehaviorRuntime.from_snapshot(read(folder/'initial_runtime.json'))
        node=IRNode.from_dict(before['current_task'])
        bindings=[]
        for step in range(16):
            bindings.append(bind_remove_reference(r,node,pending_callbacks='CANCEL_NOT_STARTED_REFERENCE',identity_filter={}))
            initial=r.snapshot();commands=[]
            command,decision=r.record_turn_command('advance',{'budget':10000});commands.append(command)
            permission=r.legal_action_candidates(decision['decision_id'])[0]
            command,_=r.record_turn_command('submit',dict(permission=permission,targets=['b'],expected_revision=decision['state_revision']));commands.append(command)
            command,out=r.record_turn_command('complete',{'budget':10000});commands.append(command)
            final=r
            again,_=BehaviorRuntime.from_snapshot(initial).replay_turn_commands(commands)
            assert final.stable_hash()==again.stable_hash()==final.clone().stable_hash()
            assert BehaviorRuntime.from_snapshot(json.loads(json.dumps(final.snapshot()))).stable_hash()==final.stable_hash()
            diag=final.clone().run_until_blocked()
            assert diag.gap
            stage=dict(binding=bindings[-1],next_gap=asdict(diag.gap),completed=final.state.scheduler.action_execution['metrics']['tasks_completed'])
            for n,v in [('initial_runtime.json',initial),('commands.json',commands),('final_runtime.json',final.snapshot()),('receipt.json',stage)]:write('reference/'+root+'/steps/'+str(step)+'/'+n,v)
            if diag.gap.node['op']!='RPG.GameCore.RemoveModifier':break
            node=IRNode.from_dict(diag.gap.node)
            r=BehaviorRuntime.from_snapshot(initial)
        else:raise RuntimeError('bounded original removal cohort exceeded')
        receipt=dict(root=root,before_completed=before['after_completed'],after_completed=final.state.scheduler.action_execution['metrics']['tasks_completed'],
            bindings=bindings,authority='EXPLICIT_REFERENCE_POLICY_INPUT',native_effective_validated=False,
            original_IR_hash=before['original_IR_hash'],task_hash=node.stable_hash(),next_gap=asdict(diag.gap),
            final_runtime_hash=final.stable_hash(),clone_snapshot_replay='PASS',new_task_family=False)
        for n,v in [('initial_runtime.json',initial),('commands.json',commands),('final_runtime.json',final.snapshot()),('receipt.json',receipt)]:write('reference/'+root+'/'+n,v)
        rows.append(receipt)
        print(root,receipt['after_completed'],str(receipt['next_gap'])[:500],flush=True)
    write('reference/results.json',rows)

def fresh():
    import r28_validation as v
    v.AUDIT=AUDIT
    v.write=write
    v.fresh()

if __name__=='__main__': {'gate':gate,'replay':replay,'reference':advance_reference,'validate':validate,'fresh':fresh}[sys.argv[1]]()
