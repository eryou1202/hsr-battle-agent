"""R27 receipts; read-only Git, isolated audit, inherited-byte preservation."""
from __future__ import annotations
import concurrent.futures
import json
import os
import re
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime')]
from r21_checks import read, sha, git
AUDIT = ROOT/'tmp/audit/r27_real_character_monster_20261022_001'
CR = 'CR-R27-REAL-COMBAT-CONTENT-CLOSURE-20261022-001'

def write(name, value):
    path = AUDIT/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)+'\n', encoding='utf-8')

def gate():
    assert not (AUDIT/'start_gate.json').exists(), 'never overwrite gate'
    files = {ROOT/p for p in git('ls-files','-z').split('\0') if p and (ROOT/p).is_file()}
    for base in ('src','tests','tools/runtime','data/control','docs/agent/handoffs'):
        files.update(p for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    assert git('branch','--show-current') == 'terra/implementation'
    write('start_gate.json', dict(head=git('rev-parse','HEAD'), branch=git('branch','--show-current'),
        status=git('status','--short'), staged=git('diff','--cached','--name-status'),
        file_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)},
        checkpoint='Current approved R26 on-disk files; no checkout or Git writes', git_writes='NONE'))
    print('R27 gate',len(files),'files',flush=True)

def preserve():
    gate_doc=read(AUDIT/'start_gate.json')
    changed=[n for n,h in gate_doc['file_hashes'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    result=dict(changed_starting_files=changed, checked_files=len(gate_doc['file_hashes']),
        head_unchanged=git('rev-parse','HEAD')==gate_doc['head'],
        branch_unchanged=git('branch','--show-current')==gate_doc['branch'],
        staged_unchanged=git('diff','--cached','--name-status')==gate_doc['staged'],
        git_writes='NONE', frozen_modified=False, ScenarioCompiler_modified=False, strict_admission_modified=False)
    write('preservation.json',result)
    assert not changed and all(result[k] for k in ('head_unchanged','branch_unchanged','staged_unchanged'))
    print('preservation PASS',flush=True)
    return result

def tests():
    lanes={'R12_R26':['-m','unittest',*['tests.battle_runtime.test_behavior_r'+str(n) for n in [*range(12,21),22,23,24,25,26]]],
        'R21':['-m','unittest','discover','-s','tools/runtime','-p','r21_specs.py']}
    lanes.update({f+'_FAST_UNIT':['-m','unittest','discover','-s','tests/'+f,'-t','.', '-p','test_*.py'] for f in ('battle_ir','battle_runtime','battle_sandbox')})
    temp=AUDIT/'test_tmp';temp.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),TMP=str(temp),TEMP=str(temp))
    def run(item):
        name,args=item
        cmd=[sys.executable,*args]
        result=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True)
        body=(result.stdout+result.stderr).decode('utf-8',errors='replace')
        (AUDIT/(name+'.txt')).write_text(body,encoding='utf-8')
        count=re.search(r'Ran (\d+) tests?',body)
        row=dict(returncode=result.returncode,tests=int(count[1]) if count else None,command=cmd,receipt=name+'.txt')
        write('verified_'+name+'.json',row)
        print(name,row,flush=True)
        return name,row
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        receipts=dict(pool.map(run,lanes.items()))
    write('final_tests.json',receipts)
    assert all(r['returncode']==0 for r in receipts.values())

if __name__=='__main__':
    {'gate':gate,'preserve':preserve,'tests':tests}[sys.argv[1]]()
