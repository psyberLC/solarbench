---
id: specs-keys
title: Make every source name in the specs resolvable
track: assets
milestone: v1
priority: core
needs: none
size: medium
status: todo
owner: ""
depends_on: []
touches:
  - "docs/sources.md"
  - "ASSUMPTIONS.md"
done_when:
  - "every source name used in solarbench/specs (the SRC_ constants, and any name given inline) appears verbatim in docs/sources.md next to its link"
  - "every ASSUMPTIONS.md entry that covers a spec value names that value as it is spelled in the code"
  - "no number in solarbench/specs was changed"
---
## Why
Each value in `solarbench/specs` names its source, and `docs/sources.md` holds the links, but the two are joined only by a person reading both. Nothing can check the join.

## What
- In `docs/sources.md`, put each source name from the specs, spelled exactly as in the code, beside the document and link it stands for.
- In `ASSUMPTIONS.md`, add to each entry the names of the spec values it covers.
- Where a name has no document behind it, say so in the log. Do not invent a link.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
