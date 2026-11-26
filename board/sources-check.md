---
id: sources-check
title: Check that every cited source still says what is cited
track: assets
milestone: ongoing
priority: core
needs: none
size: small
repeat: monthly
status: todo
owner: ""
depends_on: []
touches:
  - "docs/sources.md"
done_when:
  - "every link in sections C and D of docs/sources.md was opened; dead or changed ones are listed in this item's log"
  - "no number in solarbench/specs was changed by this item"
---
## Why
Datasheets move and get revised. A citation that no longer resolves, or now gives a different number, is worse than none.

## What
- Open each link in sections C (robots) and D (solar hardware) of `docs/sources.md`. Where the document has moved, update the link and the retrieval date.
- Where a number has changed, do not edit the spec. Record the value and both readings in this item's log, and open an item for it in a separate pull request.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
