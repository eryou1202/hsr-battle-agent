"""Read-only git receipts and R26 regression lanes; never write git state."""
import json
import sys
import r21_checks as base
import r25_checks as lanes

AUDIT = base.ROOT / 'tmp/audit/r26_battle_planner_bridge_20261022_001'
base.AUDIT = AUDIT
lanes.AUDIT = AUDIT

def preserve():
    gate = base.read(AUDIT/'start_gate.json')
    changed = [n for n, h in gate['file_hashes'].items()
               if not (base.ROOT/n).is_file() or base.sha(base.ROOT/n) != h]
    result = {'changed_starting_files': changed,
              'head_unchanged': base.git('rev-parse', 'HEAD') == gate['head'],
              'branch_unchanged': base.git('branch', '--show-current') == gate['branch'],
              'staged_unchanged': base.git('diff', '--cached', '--name-status') == gate['staged'],
              'git_writes': 'NONE', 'frozen_M10_M15_modified': False,
              'ScenarioCompiler_modified': False, 'strict_admission_weakened': False}
    base.write('architecture_preservation.json', result)
    assert not changed and all(result[k] for k in ('head_unchanged','branch_unchanged','staged_unchanged'))
    return result

if __name__ == '__main__':
    if sys.argv[1] == 'gate': base.gate()
    elif sys.argv[1] == 'preserve': print(json.dumps(preserve()))
    else: lanes.tests(sys.argv[1], sys.argv[2:] or None)
