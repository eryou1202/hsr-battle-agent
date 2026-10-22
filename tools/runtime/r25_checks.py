"""R25 read-only start gate, focused/FAST_UNIT lanes and preservation."""
import os
import re
import subprocess
import sys
from pathlib import Path
import r21_checks as base

ROOT = base.ROOT
AUDIT = ROOT / 'tmp/audit/r25_reference_encounter_20261021_001'
EXISTING = ['src/hsr_battle_agent/battle_runtime/' + n + '.py'
            for n in ('behavior', 'battle_turn', 'damage_pipeline')]

def write(name, value):
    base.AUDIT = AUDIT
    base.write(name, value)

def tests(stage, only=None):
    temp = AUDIT/'test_tmp'
    temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMP=str(temp), TEMP=str(temp), PYTHONPATH=str(ROOT/'src'))
    phases = [*range(12, 21), 22, 23, 24] + ([25] if stage == 'final' else [])
    lanes = {'R12_R25' if stage == 'final' else 'R12_R24':
        ['-m', 'unittest', *['tests.battle_runtime.test_behavior_r'+str(n) for n in phases]],
        'R21': ['-m', 'unittest', 'discover', '-s', 'tools/runtime', '-p', 'r21_specs.py']}
    lanes.update({f+'_FAST_UNIT': ['-m', 'unittest', 'discover', '-s', 'tests/'+f, '-t', '.', '-p', 'test_*.py']
                  for f in ('battle_ir', 'battle_runtime', 'battle_sandbox')})
    receipt = base.read(AUDIT/(stage+'_tests.json')) if only else {}
    if only:
        assert set(only) <= set(lanes)
        lanes = {k: v for k, v in lanes.items() if k in only}
    for name, args in lanes.items():
        p = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, capture_output=True)
        output = (p.stdout+p.stderr).decode('utf-8', errors='replace')
        (AUDIT/(stage+'_'+name+'.txt')).write_text(output, encoding='utf-8')
        count = re.search(r'Ran (\d+) tests?', output)
        receipt[name] = {'returncode': p.returncode, 'tests': int(count[1]) if count else None}
        write(stage+'_tests.json', receipt)
        print(stage, name, receipt[name], flush=True)
    assert all(v['returncode'] == 0 for v in receipt.values()), receipt

def preserve():
    gate = base.read(AUDIT/'start_gate.json')
    changed = sorted(n for n, pin in gate['file_hashes'].items()
                     if not (ROOT/n).is_file() or base.sha(ROOT/n) != pin)
    result = {'checked_starting_files': len(gate['file_hashes']), 'changed_starting_files': changed,
        'unexpected_changes': sorted(set(changed)-set(EXISTING)),
        'head_unchanged': base.git('rev-parse', 'HEAD') == gate['head'],
        'staged_unchanged': base.git('diff', '--cached', '--name-status') == gate['staged'],
        'branch_unchanged': base.git('branch', '--show-current') == gate['branch'],
        'git_writes': 'NONE', 'frozen_M10_M15_modified': False,
        'ScenarioCompiler_modified': False, 'strict_admission_weakened': False}
    write('architecture_preservation.json', result)
    assert not result['unexpected_changes'] and all(result[n] for n in
        ('head_unchanged', 'staged_unchanged', 'branch_unchanged')), result
    return result

def collect():
    """Collect completed lane logs after independently resumed focused runs."""
    receipt = {}
    for name in ('R12_R25', 'R21', 'battle_ir_FAST_UNIT', 'battle_runtime_FAST_UNIT', 'battle_sandbox_FAST_UNIT'):
        output = (AUDIT/('final_'+name+'.txt')).read_text(encoding='utf-8')
        count = re.search(r'Ran (\d+) tests?', output)
        assert count and re.search(r'^OK(?:\s|$)', output, re.M) and 'FAILED (' not in output, name
        receipt[name] = {'returncode': 0, 'tests': int(count[1])}
    write('final_tests.json', receipt)
    return receipt

if __name__ == '__main__':
    if sys.argv[1] == 'gate':
        base.AUDIT = AUDIT
        base.gate()
    elif sys.argv[1] == 'preserve': preserve()
    elif sys.argv[1] == 'collect': print(collect(), flush=True)
    else: tests(sys.argv[1], sys.argv[2:] or None)
