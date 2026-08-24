# External Reference License and Use Audit

This audit covers only the four fixed sources used by the external
reconstruction layer.  It is not a license statement for HSR assets.

| Source | Pin | Repository license observed | Repository use in this project | Practical rule |
| --- | --- | --- | --- | --- |
| TurnBasedGameData | `b11066beacc4de454b625fafc7ea3dd540c5bbf3` | `NOASSERTION` (no repository LICENSE found) | client-dump static reference | Do not vendor its source/data tree. Keep only minimal local cache, hashes, provenance, and independently written adapter output. |
| StarRailRes | `02bdd75e1e3cf4272cea94165275c98a17ff1719` | `AGPL-3.0-only` | schema and numeric cross-check reference | Do not copy/link its implementation or data tree. This repository contains only independent code and factual audit results. |
| HSR-Mapping-DATA | `245f286185f5274609be264b6ef6dbc15e8a27ad` | `NOASSERTION` (no repository LICENSE found) | mapping/schema reference | Preserve source-path/symbol provenance; independently implement every adapter transformation. |
| hsr-optimizer | `47ae66d8abac80b1f485a06fc11fe5e54c349c60` | `MIT` | narrow numeric algorithm reference | Independent implementation only; retain source attribution and scope limits in the rule pack. |

## Repository policy

- `.external_refs/` is an ignored local cache, not committed third-party
  source distribution.
- Generated Canonical data is also ignored; committed artifacts contain only
  counts, source pins, hashes, mapping paths, classifications, and gap lists.
- No upstream source file, raw table, code block, or full repository is copied
  into project source or documentation.
- An external source is evidence of a static fact or algorithmic reference.
  It is never evidence that the local client has proved an event order or
  runtime behavior.

If redistribution, packaging, or public release becomes a goal, rerun this
audit with a qualified license review before shipping any generated content or
downstream derivative database.
