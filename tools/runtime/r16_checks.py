"""R16 preservation receipt and reproducible local test lanes (no Git writes)."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'tmp/audit/r16_ability_dependency_closure_20261008_001'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, value):
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT/name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')

def gate():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()
    names = git('ls-files', '-z').split('\0')
    # Preserve all tracked files and previous generic phase artifacts including audit.
    files = {ROOT/p for p in names if p and (ROOT/p).is_file()}
    for base in ['data/control', 'tools/runtime', 'docs/agent/handoffs', 'tests/battle_runtime',
                 'src/hsr_battle_agent/battle_runtime', 'tmp/audit/r14_real_combat_corpus_20261008_001',
                 'tmp/audit/r15_action_scheduler_20261008_001']:
        files.update(p for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    write('start_gate.json', {'head':git('rev-parse','HEAD'), 'branch':git('branch','--show-current'),
          'status':git('status','--short'), 'file_hashes':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}})

def tests(stage):
    temp = AUDIT/'test_tmp'; temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMP=str(temp), TEMP=str(temp), PYTHONPATH=str(ROOT/'src'))
    lanes = {'R12_R16' if stage=='final' else 'R12_R15': ['-m','unittest', *[
        'tests.battle_runtime.test_behavior_r'+str(n) for n in range(12, 17 if stage=='final' else 16)]]}
    lanes.update({family+'_FAST_UNIT':['-m','unittest','discover','-s','tests/'+family,'-t','.', '-p','test_*.py']
                  for family in ['battle_ir','battle_runtime','battle_sandbox']})
    receipt = {}
    for name, args in lanes.items():
        p = subprocess.run([sys.executable,*args],cwd=ROOT,env=env,capture_output=True)
        output=(p.stdout+p.stderr).decode('utf-8', errors='replace')
        (AUDIT/(stage+'_'+name+'.txt')).write_text(output,encoding='utf-8')
        count=re.search(r'Ran (\d+) tests?',output)
        receipt[name]={'returncode':p.returncode,'tests':int(count[1]) if count else None}
        print(stage,name,receipt[name],flush=True)
    write(stage+'_tests.json',receipt)
    if any(r['returncode'] for r in receipt.values()): raise RuntimeError('test gate failed')

if __name__=='__main__':
    if sys.argv[1]=='gate': gate()
    else: tests(sys.argv[1])
