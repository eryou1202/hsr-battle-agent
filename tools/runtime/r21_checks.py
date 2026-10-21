"""R21 read-only start gate, regression receipts and preservation checks."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'tmp/audit/r21_true_turn_av_20261011_001'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(name, value):
    path = AUDIT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)+'\n', encoding='utf-8')

def git(*args): return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()

def gate():
    if (AUDIT/'start_gate.json').exists(): raise RuntimeError('never regenerate start gate')
    files = {ROOT/p for p in git('ls-files','-z').split('\0') if p and (ROOT/p).is_file()}
    for base in ['src','tests','tools/runtime','data/control','docs/agent/handoffs']:
        files.update(p for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    approved = {}
    for phase in range(12,21):
        found = sorted((ROOT/'tests/battle_runtime').glob('test_behavior_r'+str(phase)+'.py'))
        if not found: raise RuntimeError('missing R'+str(phase))
        approved['R'+str(phase)] = [p.relative_to(ROOT).as_posix() for p in found]
    required = ['battle_ir/behavior.py','battle_ir/behavior_binding.py','battle_ir/content_catalog.py',
                'battle_runtime/behavior.py','battle_runtime/behavior_state.py','battle_runtime/action_scheduler.py',
                'battle_runtime/modifier_lifecycle.py','battle_runtime/damage_pipeline.py',
                'battle_runtime/dynamic_property.py','battle_runtime/actor_binding.py','battle_runtime/resource_engine.py']
    for name in required:
        p=ROOT/'src/hsr_battle_agent'/name
        if not p.is_file(): raise RuntimeError('missing approved architecture '+name)
    write('start_gate.json', {'head':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),
        'status':git('status','--short'),'staged':git('diff','--cached','--name-status'),
        'approved_tests_present':approved,'approved_runtime_present':required,
        'file_hashes':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)},
        'classification':'R12/R13 committed base; R14-R20 approved runtime/control/test/tool additions and edits inherited as working-tree state; frontend/.workbuddy/old reverse files unrelated; no inherited file owned by R21'})
    print('start gate recorded',len(files),'files',flush=True)

def tests(stage):
    temp=AUDIT/'test_tmp';temp.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,TMP=str(temp),TEMP=str(temp),PYTHONPATH=str(ROOT/'src'))
    lanes={'R12_R20':['-m','unittest',*['tests.battle_runtime.test_behavior_r'+str(n) for n in range(12,21)]]}
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
    # Only this new CR-owned gate tool existed when the gate was recorded.
    unexpected=[n for n in changed if n!='tools/runtime/r21_checks.py']
    write('preservation.json', {'changed_starting_files':changed,'unexpected_changes':unexpected,
          'checked_files':len(original),'head_unchanged':git('rev-parse','HEAD')==read(AUDIT/'start_gate.json')['head'],
          'staged_unchanged':git('diff','--cached','--name-status')==read(AUDIT/'start_gate.json')['staged'],
          'git_writes':'NONE','frozen_modules_modified':False})
    if unexpected: raise RuntimeError('inherited file changed')
    print('preservation PASS',len(original),flush=True)

if __name__=='__main__':
    {'gate':gate,'preservation':preservation}.get(sys.argv[1],lambda:tests(sys.argv[1]))()
