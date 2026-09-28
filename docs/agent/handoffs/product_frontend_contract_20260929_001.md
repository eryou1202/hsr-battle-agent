# P5A product frontend contract

CR-P5A-PRODUCT-FRONTEND-CONTRACT-20260929-001 adds static product exports and an independent FE3 import/client namespace. Starting HEAD: `b1faed71fdc2770d9000b439a3d2162ba319e46e`, branch `terra/implementation`. Every pre-existing inventoried file was preserved byte for byte. No Git writes or visual changes were made.

The backend renderer is `hsr_battle_agent.frontend_adapter.product_render`. Its four catalog functions wrap the existing P2/P3 summary rows verbatim. Its four detail functions return unchanged P2/P3 product documents. `emit_product_catalog` produces `hsr_battle_agent.fe3_product_catalog/1`. Every export requires explicit `4.4.54` and a matching product service/database. Unknown products raise `LookupError`; there is no version fallback. The frozen frontend adapter exports and CLI were not extended or edited.

`emit_scenario_support_report(version, database, scenario_package, *, registry)` requires an already valid `hsr_battle_agent.scenario_package/2` and an explicit version-matched M14 registry. P4 validates the package and owns aggregation. P5A returns its result untouched. P5A does not compile packages or add an interactive transport.

## Static transport

The versioned root is `frontend/public/data/product/4.4.54/catalog.json`. It carries counts, available collections, backend schema identities, relative catalog/detail-index locations, key fields, starting HEAD, pinned authority SHA-256 values, explicit version and disconnected dynamic status. Root size is **3,112 bytes**. The root and all four browse catalogs total **1,724,648 bytes**; clients load each collection only when requested.

| Collection | Browse rows | Browse bytes | Backend detail bytes¹ | Chunk transport bytes | Detail chunks |
| --- | ---: | ---: | ---: | ---: | ---: |
| Character | 97 | 32,992 | 4,073,056 | 4,073,780 | 4 |
| Monster | 628 | 273,278 | 5,766,409 | 5,767,471 | 6 |
| Stage | 1,459 | 527,318 | 13,145,244 | 13,147,493 | 13 |
| Encounter | 1,543 | 887,948 | 6,514,373 | 6,515,640 | 7 |

¹ Sum of canonical compact UTF-8 backend documents, each with one trailing newline. Chunk transport totals also include transport envelopes. Detail indexes are separate: Character 4,789 bytes, Monster 25,974 bytes, Stage 57,924 bytes, Encounter 102,173 bytes.

Thirty deterministic chunks contain all 3,727 catalog entity details. The byte ceiling is **1,048,576 bytes**; the largest actual chunk is **1,048,302 bytes**. Documents remain intact. A future single oversized document gets one explicitly marked chunk instead of losing fields. The index maps canonical keys to chunk locations and records exact byte lengths, document counts and SHA-256 digests. Aggregate families were measured first and exceed the ceiling, so they were chunked; no per-entity file explosion was used.

Character rows contain localized names, rarity, path and element. Monster rows contain names, rank, camp identifiers and variant counts. Stage rows keep raw stage classification and encounter source modes separate and preserve the static name metadata; expensive package counts remain null. Encounter rows preserve source mode and static display metadata. No browse row contains full skills, traces or waves. All original summary schema identities and values are retained.

Monster detail indexes cover the **628 canonical browse entities**. Their backend documents contain variant descriptors. The Python renderer also supports explicit variant-only IDs through the existing P2 service. Individual variant-only IDs are not additional static detail keys; the static client returns null for any unindexed key and never silently substitutes its parent.

Full offline generation took **43.677174 seconds**. Stage browse took 1.848388 seconds; Stage detail generation and packing took 36.464888 seconds. No frontend startup call enumerates or decodes full Stage products. All 42 static transport files total 31,530,228 bytes; they are assets served on demand and are absent from the initial application JavaScript imports.

Three copied P4 reports are explicitly listed as development examples: `A_free`, `B_stage_backed`, `C_m14_missing`. Each remains byte-identical to its P4 example authority and matches the report/package hashes pinned in the P4 control artifact. Example labels live in the root index so no FE-only envelope changes the report. They have `examples_only=true` and `production_default=false`. Temporary census files are not included.

## FE3 imports and clients

`frontend/src/fe3/productContract.ts` mirrors the backend schemas. `productImportRules.ts` defines structural guards; `productDecode.ts` exposes the six requested document imports and collection/index/chunk imports. Guards reject unknown schemas, mismatched versions, absent required fields, malformed structures, unknown closed M14/M15 vocabularies, positive eligibility/admission claims and runtime scope promotion. Nullable fields remain null; backend optional fields remain absent. Decoders return the original validated document without synthesizing defaults or a semantic view.

Raw static source records, provenance payloads, statistics tables and family-artifact metadata remain opaque backend values. Structural import checking does not interpret their gameplay meaning. The accepted M15 outcome stays exactly `REJECTED`, even if authority vocabulary metadata later lists another outcome. Permissions stay false and all M15 non-effect counters stay zero.

Backend Stage metadata includes integer IDs above JavaScript's safe-integer range. `productJson.ts` parses the original numeric JSON tokens into a `LosslessInteger` presentation wrapper whose `decimal` property is the exact original spelling. Backend JSON is unchanged. Unsafe integers already rounded by native `JSON.parse` are rejected. Callers should import via `parseProductJson` or the text-based source interfaces rather than `Response.json`. Duplicate object keys and malformed JSON are rejected. The wrapper supplies no numeric calculation or gameplay meaning.

`productClients.ts` supplies `ProductCatalogSource`, `CharacterProductSource`, `MonsterProductSource`, `StageProductSource`, `EncounterProductSource` and `ScenarioSupportReportSource`. `StaticProductClient(version, loadText)` performs no constructor I/O; the first catalog call loads only the root. Browse calls load their own catalog. Details load their own index and one requested chunk, verify byte size/digest and key correspondence, and cache at most one detail chunk per family. Importing a support report from text needs no catalog or network. Loading an example requires its explicit key and validates its root-index digest.

For Vite assets, later UI code can call `createFetchProductClient('4.4.54', '/data/product/4.4.54/')`. This is a static JSON source, with no HTTP server added by P5A. Connection status is `NOT_CONNECTED`; no `compileScenario` callback, ScenarioCompiler port, admission request transport, battle execution or planner operation exists.

The report contract preserves `static_resolution`, `avatar_content_support`, `real_content_execution_admission`, `loadout_static_support`, `monster_static_support`, `monster_runtime_support`, `stage_static_support`, `stage_runtime_support`, `unresolved_content`, `unsupported_runtime_mechanisms` and `non_claims` independently. Both runtime scopes remain `FAMILY_LEVEL_ONLY`. No supported boolean, score, execution state, legal actions or battle results are inferred.

## Regeneration and verification

The additive offline command is:

```powershell
python -m hsr_battle_agent.frontend_adapter.product_generate `
  --content-version 4.4.54 `
  --database data/db/hsr_content_4.4.54.sqlite `
  --output <empty-output-directory> `
  --starting-head b1faed71fdc2770d9000b439a3d2162ba319e46e `
  --authority-root data/control `
  --p4-examples <directory-containing-verified-p4_example_A_free.json-and-B-and-C> `
  --measurements <measurement-json-path>
```

Use Python 3.11+ with `src` and the repository root on the module path. The original P4 example input directory on this workstation is `tmp/audit`; only the three verified report documents are consumed. The generator refuses a nonempty output directory to preserve existing assets. Measurement timings are outside hashed product documents. The verified interpreter used here was the local embedded Python **3.13.14** at `D:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable\python_embeded\python.exe`; no interpreter or dependency was installed.

The combined backend suite passed **349 tests**, including **12 new P5A tests**, the **5 existing adapter tests**, P2/P3/P4, ScenarioCompiler/conformance/parity, ContentDatabase, M14 and M15 regressions. Tests prove exact schemas, deterministic output, explicit version, no raw registry reads or semantic re-derivation, all four counts, unchanged P4 reports, chunk integrity and missing/null preservation.

Frontend `npm test` passed **132 tests in 12 files**, including **31 FE3 tests** decoding every generated detail document and all three reports, fail-closed mutations and lazy clients. `npm run typecheck`, `npm run lint` and `npm run build` passed. The build retains existing UI; no UI source was edited to accommodate the contract.

Control evidence is `data/control/product_frontend_contract_20260929_001.json`. The handoff ZIP contains only the 53 CR-owned new files and an internal manifest with SHA-256 values. Existing FE1/FE2/HY4 dirt, old public documents, dependencies, build output and temporary census artifacts are excluded.
