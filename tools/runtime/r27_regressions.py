"""Unchanged frozen R20, R22, stable R23, R24 and R25 regression runners."""
import sys
from r27_checks import AUDIT,write
import r25_checks
import r25_regressions
import r25_scenarios
r25_checks.AUDIT=AUDIT/'regressions'
r25_regressions.AUDIT=r25_checks.AUDIT
r25_regressions.write=r25_checks.write
r25_scenarios.write=r25_checks.write
if __name__=='__main__':
    for mode in sys.argv[1:] or ('frozen','turns','skills','defense','encounters'):
        if mode=='encounters':
            r25_checks.AUDIT=AUDIT/'regressions/r25'
            r25_scenarios.main()
        else:r25_regressions.main(mode)
