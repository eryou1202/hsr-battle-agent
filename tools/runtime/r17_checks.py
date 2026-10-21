"""R17 start gate, preservation and test receipts; read-only Git commands."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'tmp/audit/r17_modifier_event_20261009_001'
PRODUCTION = ['src/hsr_battle_agent/battle_ir/content_catalog.py',
              'src/hsr_battle_agent/battle_runtime/behavior.py',
              'src/hsr_battle_agent/battle_runtime/behavior_state.py',
              'src/hsr_battle_agent/battle_runtime/action_scheduler.py',
              'src/hsr_battle_agent/battle_runtime/modifier_lifecycle.py']

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(name, value):
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT/name).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n', encoding='utf-8')
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def gate():
    def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8').strip()
    files = {ROOT/p for p in git('ls-files','-z').split('\0') if p and (ROOT/p).is_file()}
    for base in ['src','tests','tools/runtime','data/control','docs/agent/handoffs',
                 'tmp/audit/r14_real_combat_corpus_20261008_001',
                 'tmp/audit/r15_action_scheduler_20261008_001',
                 'tmp/audit/r16_ability_dependency_closure_20261008_001']:
        files.update(p for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    write('start_gate.json', {'head':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),
          'status':git('status','--short'),'file_hashes':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}})
    for name in PRODUCTION:
        if (ROOT/name).exists():
            target=AUDIT/'starting_files'/name; target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())

def tests(stage,reuse_passed=False):
    temp=AUDIT/'test_tmp';temp.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,TMP=str(temp),TEMP=str(temp),PYTHONPATH=str(ROOT/'src'))
    lanes={'R12_R17' if stage=='final' else 'R12_R16':['-m','unittest',*[
        'tests.battle_runtime.test_behavior_r'+str(n) for n in range(12,18 if stage=='final' else 17)]]}
    lanes.update({f+'_FAST_UNIT':['-m','unittest','discover','-s','tests/'+f,'-t','.', '-p','test_*.py']
                  for f in ['battle_ir','battle_runtime','battle_sandbox']})
    receipt={}
    previous=read(AUDIT/(stage+'_tests.json')) if reuse_passed else {}
    for name,args in lanes.items():
        if previous.get(name,{}).get('returncode')==0:
            receipt[name]=previous[name];print(stage,name,'previous PASS retained',flush=True);continue
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
    changed=[name for name,h in original.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=h]
    unexpected=[name for name in changed if name not in PRODUCTION and not name.startswith('tools/runtime/r17_')]
    write('preservation.json',{'changed_starting_files':changed,'unexpected_changes':unexpected,
          'frozen_M10_M15_modified':bool(unexpected),'checked_files':len(original)})
    if unexpected: raise RuntimeError('preservation failure: '+str(unexpected))

if __name__=='__main__':
    {'gate':gate,'preservation':preservation}.get(sys.argv[1],lambda:tests(sys.argv[1],'--reuse-passed' in sys.argv))()
