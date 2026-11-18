"""R30 bounded authority stop, preservation and fresh regression receipts. No Git writes."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tools/runtime')]
AUDIT=ROOT/'tmp/audit/r30_dynamic_context_closure_20261108_001'
OLD=ROOT/'tmp/audit/r29_original_executor_context_20261108_001'
CR='CR-R30-DYNAMIC-CONTEXT-CLOSURE-20261108-001'
def read(p): return json.loads(p.read_text(encoding='utf8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(n,v):
    p=AUDIT/n;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')
def git(*a): return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
def gate():
    assert not (AUDIT/'start_gate.json').exists()
    names=set(git('ls-files','-z').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').split('\0'))
    write('start_gate.json',dict(head=git('rev-parse','HEAD'),branch=git('branch','--show-current'),status=git('status','--short'),staged=git('diff','--cached','--name-status'),timestamp=now(),file_hashes={n:sha(ROOT/n) for n in sorted(names) if n and (ROOT/n).is_file() and not n.startswith('tools/runtime/r30_')},timing='After read-only evidence inspection and creation of R30-owned collectors; no inherited edits'))
    controls={p.name:read(p) for p in (ROOT/'data/control').glob('generic_runtime_r29_*.json')}
    write('inherited_controls.json',dict(controls=controls,hashes={p.name:sha(p) for p in (ROOT/'data/control').glob('generic_runtime_r29_*.json')}))
    write('evidence_inputs.json',{p.relative_to(ROOT).as_posix():sha(p) for folder in [OLD,ROOT/'data/overlays/r28_4651_v1',ROOT/'tmp/audit/r27_real_character_monster_20261022_001'] for p in folder.rglob('*') if p.is_file() and p.suffix in ('.json','.txt','.gz','.log','.cjs') and 'test_tmp' not in p.parts})
def replays():
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
    from hsr_battle_agent.battle_ir.behavior import IRNode
    rows=[]
    # Replay every saved baseline and each R29 explicit reference stage, without new policies.
    folders=sorted(set(p.parent for p in OLD.rglob('commands.json') if (p.parent/'initial_runtime.json').exists() and (p.parent/'final_runtime.json').exists()))
    for folder in folders:
        initial=read(folder/'initial_runtime.json');commands=read(folder/'commands.json')
        final,_=BehaviorRuntime.from_snapshot(initial).replay_turn_commands(commands)
        assert final.snapshot()==read(folder/'final_runtime.json'),folder
        assert final.clone().stable_hash()==BehaviorRuntime.from_snapshot(json.loads(json.dumps(final.snapshot()))).stable_hash()
        again,_=BehaviorRuntime.from_snapshot(initial).replay_turn_commands(commands)
        assert final.stable_hash()==again.stable_hash()
        rel=folder.relative_to(OLD).as_posix()
        for n,v in [('initial_runtime.json',initial),('commands.json',commands),('final_runtime.json',final.snapshot())]:write('replays/'+rel+'/'+n,v)
        rows.append(dict(folder=rel,commands=len(commands),final_hash=final.stable_hash(),clone_snapshot_replay='PASS',new_policy=False))
    original=[]
    bindings=read(ROOT/'data/control/generic_runtime_r29_original_task_bindings_v1_20261108_001.json')
    for row in read(OLD/'character/results.json'):
        root=row['root'];baseline=next(x for x in bindings['roots'] if x['root']==root)
        original.append(dict(root=root,before=baseline['after'],after=baseline['after'],task_hash=row['task_hash'],original_IR_hash=row['original_IR_hash'],task=row['current_task'],next_blocker=baseline['next_gap'],new_original_execution=False,cohort='STRUCTURAL_ONLY',source_task_hash_verified=IRNode.from_dict(row['current_task']).stable_hash()==row['task_hash']))
    write('replays.json',dict(saved_scenarios=rows,original_parents=original,timestamp=now(),no_fabricated_finish=True))
    print('replayed',len(rows),'saved stages',flush=True)
def tests():
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),TMP=str(AUDIT/'test_tmp'),TEMP=str(AUDIT/'test_tmp'))
    (AUDIT/'test_tmp').mkdir(exist_ok=True)
    inputs={p.relative_to(ROOT).as_posix():sha(p) for d in ['src','tests','tools/runtime','data/control','data/overlays'] for p in (ROOT/d).rglob('*') if p.is_file() and p.suffix in ('.py','.json','.gz','.cjs')}
    write('tests/input_hashes.json',inputs)
    lanes={n:['-m','unittest','discover','-s','tests/'+n,'-t','.','-p','test_*.py'] for n in ['battle_runtime','battle_ir','battle_sandbox']}
    lanes['R21']=['-m','unittest','discover','-s','tools/runtime','-p','r21_specs.py']
    receipts={}
    for name,args in lanes.items():
        started=now();print('START',name,flush=True)
        p=subprocess.run([sys.executable,*args],cwd=ROOT,env=env,capture_output=True)
        output=(p.stdout+p.stderr).decode('utf8',errors='replace');log=AUDIT/'tests'/(name+'.log');log.write_text(output,encoding='utf8')
        m=re.search(r'Ran (\d+) tests?',output)
        receipts[name]=dict(command=[sys.executable,*args],case_count=int(m[1]) if m else None,actual_exit_code=p.returncode,started=started,finished=now(),completion_status='PASS' if p.returncode==0 else 'FAIL',input_hash_manifest='tests/input_hashes.json',input_hash_manifest_sha256=sha(AUDIT/'tests/input_hashes.json'),log_sha256=sha(log))
        write('tests/results.json',receipts);print(name,receipts[name]['case_count'],p.returncode,flush=True)
    assert all(r['actual_exit_code']==0 for r in receipts.values())
def regressions(mode):
    # Historical runner logic, redirected exclusively to this CR's audit folder.
    import r25_regressions as r
    r.AUDIT=AUDIT/'regressions';r.write=lambda n,v:write('regressions/'+n,v)
    if mode=='encounters':
        import r25_scenarios as s
        s.write=lambda n,v:write('regressions/r25/'+n,v);s.main()
    elif mode=='planner':
        import r26_scenarios as s
        s.AUDIT=AUDIT/'regressions/r26';s.main()
    else:r.main(mode)
def preserve():
    g=read(AUDIT/'start_gate.json');changed=[n for n,h in g['file_hashes'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    pin=read(ROOT/'tmp/audit/r27_real_character_monster_20261022_001/resume/input_hashes.json')
    drift=[n for n,h in pin['files'].items() if sha(ROOT/n)!=h]
    result=dict(changed_starting_files=changed,frozen_input_drift=drift,head_unchanged=git('rev-parse','HEAD')==g['head'],branch_unchanged=git('branch','--show-current')==g['branch'],staged_unchanged=git('diff','--cached','--name-status')==g['staged'],git_writes='NONE',frozen=[632,160,161])
    write('preservation.json',result);assert not changed and not drift and all(result[k] for k in ['head_unchanged','branch_unchanged','staged_unchanged'])
def scenario_tests():
    receipts={}
    for mode,count in [('frozen',632),('skills',160),('defense',18),('encounters',18),('planner',20)]:
        args=[sys.executable,str(Path(__file__).resolve()),'regressions',mode];started=now()
        print('START scenario',mode,flush=True)
        p=subprocess.run(args,cwd=ROOT,capture_output=True)
        output=(p.stdout+p.stderr).decode('utf8',errors='replace')
        (AUDIT/'tests'/('scenario_'+mode+'.log')).write_text(output,encoding='utf8')
        receipts[mode]=dict(command=args,case_count=count,case_count_kind='scenario_or_root_count',actual_exit_code=p.returncode,started=started,finished=now(),completion_status='PASS' if p.returncode==0 else 'FAIL',input_hash_manifest='tests/input_hashes.json',input_hash_manifest_sha256=sha(AUDIT/'tests/input_hashes.json'))
        write('tests/scenarios.json',receipts);print(mode,p.returncode,flush=True)
    assert all(x['actual_exit_code']==0 for x in receipts.values())
if __name__=='__main__':
    mode=sys.argv[1]
    if mode in ['gate','replays','tests','preserve','scenario_tests']:globals()[mode]()
    elif mode=='regressions':regressions(sys.argv[2])
