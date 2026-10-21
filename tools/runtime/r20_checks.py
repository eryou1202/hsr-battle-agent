"""R20 read-only Git start gate, tests and inherited baseline preservation."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'tmp/audit/r20_actor_resource_progression_20261010_001'
OWNED_EXISTING = ['src/hsr_battle_agent/battle_runtime/behavior.py',
                  'src/hsr_battle_agent/battle_runtime/action_scheduler.py']

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(name, value):
    path = AUDIT/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)+'\n', encoding='utf-8')

def gate():
    if (AUDIT/'start_gate.json').exists(): raise RuntimeError('start gate already recorded')
    def git(*args): return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()
    files = {ROOT/p for p in git('ls-files', '-z').split('\0') if p and (ROOT/p).is_file()}
    for base in ['src','tests','tools/runtime','data/control','docs/agent/handoffs','tmp/audit']:
        files.update(p for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts
                     and 'test_tmp' not in p.parts and AUDIT not in p.parents)
    write('start_gate.json', {'head':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),
          'status':git('status','--short'),'staged':git('diff','--cached','--name-status'),
          'file_hashes':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}})
    for name in OWNED_EXISTING:
        target=AUDIT/'starting_files'/name; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())

def tests(stage):
    temp=AUDIT/'test_tmp';temp.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,TMP=str(temp),TEMP=str(temp),PYTHONPATH=str(ROOT/'src'))
    lanes={'R12_R20' if stage=='final' else 'R12_R19':['-m','unittest',*[
        'tests.battle_runtime.test_behavior_r'+str(n) for n in range(12,21 if stage=='final' else 20)]]}
    lanes.update({f+'_FAST_UNIT':['-m','unittest','discover','-s','tests/'+f,'-t','.', '-p','test_*.py']
                  for f in ['battle_ir','battle_runtime','battle_sandbox']})
    receipt={}
    for name,args in lanes.items():
        p=subprocess.run([sys.executable,*args],cwd=ROOT,env=env,capture_output=True)
        output=(p.stdout+p.stderr).decode('utf-8',errors='replace')
        (AUDIT/(stage+'_'+name+'.txt')).write_text(output,encoding='utf-8')
        count=re.search(r'Ran (\d+) tests?',output)
        receipt[name]={'returncode':p.returncode,'tests':int(count[1]) if count else None}
        print(stage,name,receipt[name],flush=True)
    write(stage+'_tests.json',receipt)
    if any(r['returncode'] for r in receipt.values()): raise RuntimeError('test gate failed')

def preservation():
    original=read(AUDIT/'start_gate.json')['file_hashes']
    changed=[n for n,h in original.items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    unexpected=[n for n in changed if n not in OWNED_EXISTING]
    write('preservation.json',{'changed_starting_files':changed,'unexpected_changes':unexpected,
          'frozen_modules_modified':bool(unexpected),'checked_files':len(original), 'git_writes':'NONE'})
    if unexpected: raise RuntimeError('preservation failure')

if __name__=='__main__':
    {'gate':gate,'preservation':preservation}.get(sys.argv[1],lambda:tests(sys.argv[1]))()
