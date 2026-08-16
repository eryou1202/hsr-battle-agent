# -*- coding: utf-8 -*-
"""Cross-version expected invariants from the CONFIRMED reverse sessions.

These constants are test-time expectations only.  The pipeline itself never
branches on game version; counts are always recomputed from assets.
"""
from __future__ import annotations

KNOWN_INVARIANTS = {
    "4.4.54": {
        "type_count": 80880,
        "method_count": 732328,
        "field_count": 555259,
        "method_code_non_null": 700198,
        "method_code_null": 32130,
    },
    "4.4.0": {
        "type_count": 76921,
        "method_count": 703008,
        "field_count": 526693,
        "method_code_non_null": 676842,
        "method_code_null": 26166,
    },
}
