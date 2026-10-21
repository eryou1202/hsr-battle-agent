"""Unchanged R20 frozen-corpus runner, with receipts redirected only to R22."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime'),str(ROOT)]
import r20_probes
from r18_probes import load
from r22_audit import AUDIT,write_json

if __name__=='__main__':
    r20_probes.AUDIT=AUDIT
    r20_probes.write=write_json
    roots,_=load()
    r20_probes.comparisons(roots,True)
    print('Unchanged 632 combat / 160 joined frozen regression PASS',flush=True)
