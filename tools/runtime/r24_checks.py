"""R24 read-only repository gate and regression receipts."""
import sys
import r21_checks as base

AUDIT = base.ROOT / 'tmp/audit/r24_defense_break_shield_20261021_001'
base.AUDIT = AUDIT

def tests(stage, only=None):
    import os, re, subprocess
    temp = AUDIT / 'test_tmp'
    temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMP=str(temp), TEMP=str(temp), PYTHONPATH=str(base.ROOT/'src'))
    phases = list(range(12,21)) + [22,23] + ([24] if stage == 'final' else [])
    lanes = {'R12_R24' if stage == 'final' else 'R12_R23':
             ['-m','unittest',*['tests.battle_runtime.test_behavior_r'+str(n) for n in phases]],
             'R21':['-m','unittest','discover','-s','tools/runtime','-p','r21_specs.py']}
    lanes.update({f+'_FAST_UNIT':['-m','unittest','discover','-s','tests/'+f,'-t','.','-p','test_*.py']
                  for f in ['battle_ir','battle_runtime','battle_sandbox']})
    receipt = base.read(AUDIT/(stage+'_tests.json')) if only else {}
    if only:
        assert set(only) <= set(lanes)
        lanes = {name:args for name,args in lanes.items() if name in only}
    for name,args in lanes.items():
        p = subprocess.run([sys.executable,*args],cwd=base.ROOT,env=env,capture_output=True)
        output = (p.stdout+p.stderr).decode('utf-8',errors='replace')
        (AUDIT/(stage+'_'+name+'.txt')).write_text(output,encoding='utf-8')
        count = re.search(r'Ran (\d+) tests?',output)
        receipt[name] = {'returncode':p.returncode,'tests':int(count[1]) if count else None}
        base.write(stage+'_tests.json',receipt)
        print(stage,name,receipt[name],flush=True)
    assert all(r['returncode']==0 for r in receipt.values()), receipt

if __name__ == '__main__':
    base.gate() if sys.argv[1]=='gate' else tests(sys.argv[1])
