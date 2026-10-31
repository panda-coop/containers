# NNNN — Short imperative title of the decision

- Status: draft | proposed | accepted | rejected | superseded by [NNNN](NNNN-slug.md)
- Date: YYYY-MM-DD
- Decision makers: <owner>

## Context

What forces this decision, in 3-6 sentences. State facts with their source (research
date, doc URL, repo evidence) — no ungrounded claims. Neutral engineering language; no
personal attribution in prose.

## Options considered

| Option | Rejected because |
|--------|------------------|
| Option A | one-line concrete reason |
| **Option chosen** | — chosen |

Every rejected option carries the *why*; a decision without alternatives is a note, not
a decision.

## Decision

The decision itself, in imperative present tense. Tables for facts, prose for reasoning.
Only what was decided — implementation detail lives in the implementing skill/code.

## Consequences

What becomes easier, what becomes harder, what must change elsewhere (files, CI,
conventions), and any follow-up decisions this forces.

## Open questions (optional)

Explicitly unresolved points, each with its candidate answers. An open question here is
the trigger for a future decision record — not silently resolved in implementation.

---

Rules for this directory: MADR-style, one decision per file, `NNNN-kebab-slug.md`,
numbered sequentially. A record is immutable once `accepted` — corrections before
acceptance are amendments; after acceptance, write a superseding record and link both
ways. Nothing is `accepted` without explicit sign-off from the decision makers. Keep
records under ~80 lines; move bulk evidence to `docs/specs/` and link it.
