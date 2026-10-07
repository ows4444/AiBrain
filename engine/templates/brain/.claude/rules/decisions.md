---
paths:
  - "cortex/decisions/**"
---

# Decision pages

A decision adds `status: open | decided | reviewed`, a `review:` date and a
`revisit_if:` event once decided, and an `outcome:` once reviewed.

Its `## Expected` is frozen once it is decided, and a decided page is never
reopened. Under its Options, Expected, Decision and Lessons each line says
what it is: `- [observation]` (cites a page, or `(owner, DATE)`),
`[interpretation]`, `[hypothesis]`, `[assumption]` or `[decision]`. A guess
may carry the owner's probability, `- [hypothesis 70%] ...`; reviews score it.
