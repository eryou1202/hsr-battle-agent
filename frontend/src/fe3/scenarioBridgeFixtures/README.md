# P5B test documents

Explicit 4.4.54 fixtures produced by `tests/frontend_bridge/generate_fixtures.py`
using one public authority stack. Package documents are verbatim
`ScenarioCompiler.compile` output encoded with backend `stable_bytes`; the free
report is verbatim `ScenarioSupportReporter.build` output. The stage fixture uses
420101 with template waves. The overlay retains variant 100401401 and the unknown
caller rule reference. They contain no battle result or production default.

Only the Vitest module imports these fixtures. Runtime bridge/client modules do
not eagerly load them. Keep original package JSON text: reserializing parsed
JavaScript numbers can change Python float spellings and invalidate P4 hashes.
