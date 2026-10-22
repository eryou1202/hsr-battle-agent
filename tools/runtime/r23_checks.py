"""R23 preservation gate and unchanged regression lanes; no Git writes."""
from __future__ import annotations
import os
import re
import subprocess
import sys
from pathlib import Path
import r21_checks as checks

ROOT = checks.ROOT
AUDIT = ROOT / 'tmp/audit/r23_real_skill_root_closure_20261012_001'
checks.AUDIT = AUDIT


def tests(stage):
    temp = AUDIT / 'test_tmp'
    temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMP=str(temp), TEMP=str(temp), PYTHONPATH=str(ROOT / 'src'))
    phases = list(range(12, 21)) + [22] + ([23] if stage == 'final' else [])
    lanes = {'R12_R23' if stage == 'final' else 'R12_R22':
             ['-m', 'unittest', *['tests.battle_runtime.test_behavior_r'+str(n) for n in phases]],
             'R21': ['-m', 'unittest', 'discover', '-s', 'tools/runtime', '-p', 'r21_specs.py']}
    lanes.update({f+'_FAST_UNIT': ['-m', 'unittest', 'discover', '-s', 'tests/'+f, '-t', '.', '-p', 'test_*.py']
                  for f in ['battle_ir', 'battle_runtime', 'battle_sandbox']})
    receipt = {}
    for name, args in lanes.items():
        result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, capture_output=True)
        output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        (AUDIT / (stage+'_'+name+'.txt')).write_text(output, encoding='utf-8')
        count = re.search(r'Ran (\d+) tests?', output)
        receipt[name] = {'returncode': result.returncode, 'tests': int(count[1]) if count else None}
        checks.write(stage+'_tests.json', receipt)
        print(stage, name, receipt[name], flush=True)
    assert all(r['returncode'] == 0 for r in receipt.values()), receipt


if __name__ == '__main__':
    if sys.argv[1] == 'gate':
        checks.gate()
    else:
        tests(sys.argv[1])
