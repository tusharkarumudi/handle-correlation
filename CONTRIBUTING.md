# Contributing

## What belongs here

Signals that compare handles the analyst **already has**. Mutation patterns,
selectivity estimation, temporal analysis, negative evidence.

New mutation patterns are especially welcome — the current set is Latin-script
biased and will miss transliteration conventions in Cyrillic, Arabic, Devanagari
and CJK handle formation. If you know how handles mutate in a script this misses,
that is the most useful PR available.

## What does not belong here

**Enumeration.** No PR adding "check whether this handle exists on N platforms",
however convenient. That capability exists in maigret and Sherlock; feed their
output in as a CSV. The value here is the scoring, and adding discovery converts
a scoring library into an assembled tracking tool. This is a design boundary, not
a TODO.

**Breach corpora.** No credential dumps, combolists, or "email for handle"
lookups against leaked data. Unlawfully obtained in most jurisdictions, unmeasured
accuracy, and it taints every conclusion downstream.

**Confident stylometry.** Author attribution at short text lengths does not
support the accuracy commercial tools claim. If you add stylometric signals they
must be `Reliability.WEAK` and corroborative-only, with a citation for the
accuracy claim.

## Correlation groups are the review bar

Every claim declares one, and getting it wrong is the failure mode this project
exists to prevent. All same-root claims share one group. All bindings from one
platform profile share one group. If your PR emits N claims from one underlying
fact in N groups, it will be declined regardless of how good the signal is.

## Development

```bash
pip install -e ".[dev]"
pytest -q && ruff check .
```

Tests are written as properties — "handle reuse alone cannot attribute", "generic
handles emit nothing" — not assertions about specific floats. Follow that style.
