"""Execute unchanged historical cohorts with output confined to R26 audit."""
import sys
from r26_checks import AUDIT
import r25_checks
import r25_regressions
import r25_scenarios

r25_checks.AUDIT = AUDIT
r25_regressions.AUDIT = AUDIT
r25_regressions.write = r25_checks.write
r25_scenarios.write = r25_checks.write

if __name__ == '__main__':
    for mode in sys.argv[1:] or ['frozen','turns','skills','defense','encounters']:
        if mode == 'encounters':
            r25_checks.AUDIT = AUDIT/'r25'
            r25_scenarios.main()
        else: r25_regressions.main(mode)
