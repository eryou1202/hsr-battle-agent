"""Execute the required 18 cases and retain asserted observations independently."""
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'tools/runtime')]
from r24_evidence import write
from tests.battle_runtime.test_behavior_r24 import R24Scenarios


def main():
    rows = []
    for name in unittest.defaultTestLoader.getTestCaseNames(R24Scenarios):
        case = R24Scenarios(name)
        result = unittest.TestResult()
        case.run(result)
        row = {'id':int(name.split('_')[2]), 'name':name, 'PASS':result.wasSuccessful(),
               'observation':getattr(case,'observation',None),
               'failures':[trace for _,trace in result.failures+result.errors]}
        rows.append(row)
        write('functional_scenarios.json', {'required':18,'passed':sum(r['PASS'] for r in rows), 'scenarios':rows})
        print(name, 'PASS' if row['PASS'] else 'FAIL', flush=True)
    assert len(rows) == 18 and all(r['PASS'] for r in rows)
    assert sum(r['observation']['cohort']=='REAL_DAMAGE_PLUS_REFERENCE_DEFENSE' for r in rows) == 1
    write('scenario_summary.json', {'required':18,'passed':18, 'A_PURE_REFERENCE_MECHANIC':17,
        'B_REAL_DAMAGE_PLUS_REFERENCE_DEFENSE':1, 'C_SOURCE_BACKED_DEFENSE_CONTENT':0,
        'count_basis':'Core functional scenarios only; additional edge tests do not inflate these cohorts',
        'original_source_defense_completeness_proven':False,'native_correctness':'NOT_CLAIMED'})


if __name__ == '__main__': main()
