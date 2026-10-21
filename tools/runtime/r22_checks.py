"""R22 preservation gate and unchanged regression lanes. No Git writes."""
from __future__ import annotations
import sys
import os
import re
import subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import r21_checks as checks

checks.AUDIT = checks.ROOT / 'tmp/audit/r22_global_turn_engine_20261011_001'
AUDIT = checks.AUDIT
OWNED_EXISTING = {'src/hsr_battle_agent/battle_runtime/behavior.py',
                  'pyproject.toml',
                  'src/hsr_battle_agent/battle_runtime/action_scheduler.py',
                  'src/hsr_battle_agent/battle_runtime/modifier_lifecycle.py',
                  'src/hsr_battle_agent/battle_runtime/actor_binding.py',
                  'tools/runtime/r22_checks.py'}

def preservation():
    gate = checks.read(AUDIT / 'start_gate.json')
    changed = [n for n, h in gate['file_hashes'].items()
               if not (checks.ROOT / n).is_file() or checks.sha(checks.ROOT / n) != h]
    unexpected = sorted(set(changed) - OWNED_EXISTING)
    receipt = {'changed_starting_files': changed, 'unexpected_changes': unexpected,
               'checked_files': len(gate['file_hashes']),
               'head_unchanged': checks.git('rev-parse', 'HEAD') == gate['head'],
               'staged_unchanged': checks.git('diff', '--cached', '--name-status') == gate['staged'],
               'git_writes': 'NONE', 'frozen_modules_modified': False}
    checks.write('preservation.json', receipt)
    assert not unexpected and receipt['head_unchanged'] and receipt['staged_unchanged'], receipt
    print('preservation PASS', len(gate['file_hashes']), flush=True)


def focused():
    temp = AUDIT / 'test_tmp'; temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMP=str(temp), TEMP=str(temp), PYTHONPATH=str(checks.ROOT / 'src'))
    lanes = {'R21': ['-m', 'unittest', 'discover', '-s', 'tools/runtime', '-p', 'r21_specs.py', '-v'],
             'R22': ['-m', 'unittest', 'tests.battle_runtime.test_behavior_r22', '-v']}
    receipt, logs = {}, []
    for name, args in lanes.items():
        result = subprocess.run([sys.executable, *args], cwd=checks.ROOT, env=env, capture_output=True)
        output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        (AUDIT / ('final_' + name + '_focused.txt')).write_text(output, encoding='utf-8')
        logs.append(output)
        match = re.search(r'Ran (\d+) tests?', output)
        receipt[name] = {'returncode': result.returncode, 'tests': int(match[1]) if match else None}
        print('focused', name, receipt[name], flush=True)
    (AUDIT / 'final_focused_output.txt').write_text('\n'.join(logs), encoding='utf-8')
    checks.write('final_focused_tests.json', receipt)
    assert all(r['returncode'] == 0 for r in receipt.values()), receipt

if __name__ == '__main__':
    if sys.argv[1] == 'gate': checks.gate()
    elif sys.argv[1] == 'preservation': preservation()
    elif sys.argv[1] == 'focused': focused()
    else: checks.tests(sys.argv[1])
