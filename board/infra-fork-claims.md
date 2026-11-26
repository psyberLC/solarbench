---
id: infra-fork-claims
title: Claims from forks
track: infra
milestone: v1
priority: stretch
needs: cpu
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "tools/board.py"
  - "tests/test_board.py"
  - "board/README.md"
done_when:
  - "python tools/board.py shows an item claimed through a draft pull request from a fork as doing, with its owner"
  - "the overlap check covers such claims"
---
## Why
A claim is a branch on this repository, which needs write access. Contributors working from a fork claim by opening a draft pull request, and today a maintainer has to check those by hand.

## What
- `tools/board.py` reads open pull requests (title starting with an item id) as claims, alongside branches.
- Works without credentials on a public repository; degrades to branches only when offline.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
