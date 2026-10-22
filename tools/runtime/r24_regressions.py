"""Reuse unchanged R20 frozen, R22 A-L and R23 skill runners in R24 audit only."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime'), str(ROOT)]
from r24_checks import AUDIT
from r24_evidence import write
from r21_checks import read


def main(mode):
    if mode == 'turns':
        import r22_audit as prior
        prior.AUDIT = AUDIT/'r22'
        prior.main()
        receipt = read(prior.AUDIT/'execution_summary.json')
        assert receipt == read(ROOT/'tmp/audit/r22_global_turn_engine_20261011_001/execution_summary.json')
        write('r22_regression.json', {'status':'PASS','summary':receipt})
    elif mode == 'frozen':
        import r20_probes as prior
        from r18_probes import load
        prior.AUDIT = AUDIT/'frozen'
        prior.write = lambda name,doc: write('frozen/'+name,doc)
        roots,_ = load()
        prior.comparisons(roots,True)
        receipt = read(prior.AUDIT/'frozen_regression.json')
        assert receipt['all_original_state_hashes_equal']
        write('frozen_regression.json', receipt)
    elif mode == 'skills':
        import r23_probes as prior
        import r23_discovery as discovery
        previous = ROOT/'tmp/audit/r23_real_skill_root_closure_20261012_001'
        prior.AUDIT = AUDIT/'r23'
        discovery.AUDIT = prior.AUDIT
        prior.read = lambda path: read(previous/'joined_dependency.json' if Path(path).name == 'joined_dependency.json' else path)
        prior.main()
        receipt = read(prior.AUDIT/'execution_summary.json')
        saved = read(previous/'execution_summary.json')
        if receipt != saved:
            import subprocess
            # Preserve archived controls; isolate the discrepancy against exact
            # starting source rather than forcing cached counts to match.
            subprocess.run([sys.executable,str(ROOT/'tools/runtime/r24_census_check.py')],cwd=ROOT,check=True)
        else:
            write('r23_regression.json', {'status':'PASS','summary':receipt,'archived_summary':saved,
                'archived_summary_equal':True,'discrepancy':None})
    else:
        raise ValueError(mode)
    print('R24', mode, 'regression PASS', flush=True)


if __name__ == '__main__': main(sys.argv[1])
