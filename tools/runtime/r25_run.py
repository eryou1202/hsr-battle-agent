"""Run an authored victory/defeat or replay a retained public-command trace."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'tools/runtime')]
from r25_reference_fixtures import setup, complete
from r25_checks import AUDIT
from r21_checks import read
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--outcome', choices=['VICTORY', 'DEFEAT'], default='VICTORY')
    parser.add_argument('--replay', help='E01, E02, E04, E15 or E16 retained trace')
    args = parser.parse_args()
    if args.replay:
        folder = AUDIT/args.replay
        r = BehaviorRuntime.from_snapshot(read(folder/'initial_runtime.json'))
        r, _ = r.replay_encounter_commands(read(folder/'commands.json'))
        assert r.snapshot() == read(folder/'final_runtime.json')
    else:
        options = {'waves': 2} if args.outcome == 'VICTORY' else {'waves': 1, 'player_damage': 1, 'enemy_damage': 100}
        r, _, _ = setup(**options)
        b = complete(r)
        assert b.kind == 'BATTLE_TERMINAL' and r.encounter_result()['result'] == args.outcome, b
    print(json.dumps({'boundary': 'BATTLE_TERMINAL', 'receipt': r.encounter_result(), 'runtime_hash': r.stable_hash()},
                     indent=2, sort_keys=True), flush=True)

if __name__ == '__main__': main()
