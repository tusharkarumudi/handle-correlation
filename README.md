# handle-correlation

[![CI](https://github.com/tusharkarumudi/handle-correlation/actions/workflows/ci.yml/badge.svg)](https://github.com/tusharkarumudi/handle-correlation/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/handle-correlation.svg)](https://pypi.org/project/handle-correlation/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Decides which observed usernames belong to the same actor, with a probability
you can defend.

**Scores handles. Does not discover them.** Input is observations you already
collected.

```bash
pip install handle-correlation
handlecorr score --observations case.csv --corpus usernames.txt
```

---

## Quickstart

`case.csv`:

```csv
handle,platform,first_seen,last_seen,source_url,link_email,link_pgp,case_ref
kr4ken,github,2019-03-01,2024-11-02,https://...,,ABCD1234...,CASE-1
kraken_x,telegram,2021-06-14,2026-01-20,https://...,k@example.com,ABCD1234...,CASE-1
```

Only `handle` and `platform` are required. The `link_*` columns are what turn
leads into findings.

```bash
handlecorr score --observations case.csv --corpus top-usernames.txt --out ./out
```

```
     p  band          grp  pair
 0.961  STRONG_EVIDENCE 2  handle:github:kr4ken  <->  handle:telegram:kraken_x
 0.029  WEAK            1  handle:x:kraken1988   <->  handle:npm:krakendev

1 actor cluster(s)
  - github:kr4ken, telegram:kraken_x
```

Runnable: `python examples/end_to_end_handles.py`

---

## The headline property

Handle reuse across eight platforms **cannot** produce an attribution.

```python
o = [Observation("kr4ken", p) for p in
     ("github","telegram","x","forum","gitlab","npm","reddit","keybase")]
assess(all_claims(o), corpus.holders).band     # Band.WEAK
```

Eight platforms is **one observation of one naming habit**, made once. All
same-root claims share a correlation group. Treating them as eight independent
confirmations is how a confident false accusation gets built.

Add one cryptographic binding and it resolves:

```python
o = [Observation("kr4ken",   "github",   linked={"pgp": FPR}),
     Observation("kraken_x", "telegram", linked={"pgp": FPR})]
# independent_groups = 2
```

---

## Confidence policy

Stricter than the generic model, and it governs when they disagree.

| Points | Level | Meaning |
|---:|---|---|
| 0–1 | INSUFFICIENT | Not a lead. Consistent with unrelated people. |
| 2–3 | **LOW** | A lead for further collection. Never an attribution. Do not report it as identifying anyone. |
| 4–5 | MODERATE | Only with a durable identifier; otherwise LOW. |
| 6+ | HIGH | Requires a durable identifier. |

Points count **distinct evidence types, not claims**. Eight platforms with one
handle is one point. Two profiles publishing the same PGP key is one point — one
identifier corroborated twice.

```python
hc = correlation_points(all_claims(observations))
hc.points, hc.level.value, hc.caveat     # caveat is written to paste into a report
```

Handle reuse earns the harder floor because it is simultaneously the commonest
signal and the weakest: people pick similar names independently, and an
adversary can adopt a target's handle at zero cost.

---

## Signals

| Signal | Weight |
|---|---|
| Same root after mutation | MODERATE–STRONG |
| Homoglyph substitution (Cyrillic `а`) | MODERATE — deliberate, so it *raises* confidence |
| PGP / SSH fingerprint | AUTHORITATIVE |
| Platform-published email | STRONG |
| Gravatar hash | STRONG |
| Linked domain | MODERATE |
| Display name | WEAK |
| Activity-hour overlap | WEAK, corroborative-only — cannot create a link |
| Timezone conflict ≥8h | negative |
| Non-overlapping lifespans | negative |

---

## Selectivity

Supply a username frequency corpus and `dave` becomes worth almost nothing while
`kr4ken_x99` becomes worth a great deal — automatically.

> Without `--corpus`, every handle looks unique and the CLI warns. **Scores from
> a corpus-less run are upper bounds.**

This is the gap in existing tooling: maigret reports that `dave` exists on 180
sites and `kr4ken_x99` on 3, with no indication the second is worth a thousand
times more.

---

## Mutation handling

```python
>>> normalize("xXkr4ken_1988Xx").root
'kraken'
>>> compare("github:kr4ken", "telegram:kraken_x").relation
'same_root_mutated'
>>> compare("github:admin", "telegram:admin").meaningful
False
```

Leetspeak, separators, repeated characters, wrapper affixes, numeric suffixes,
Cyrillic/Greek homoglyphs. Edit-distance thresholds scale with root length.
Generic and short handles are rejected outright — `admin` on two platforms is
not weak evidence, it is no evidence.

---

## Why no enumeration

Enumeration is solved — maigret and Sherlock do it well. What none of them do is
tell you what a match is *worth*.

Requiring you to supply observations keeps the collection decision, and its legal
basis, with the person who has authority to make it. If you need enumeration for
an authorized case, run maigret and feed its output in. The interface is a CSV.

---

## Dark web sources

`paytrace.to_handle_observations()` converts a
[Robin](https://github.com/apurvsinghgautam/robin) investigation into observation
rows, carrying durable identifiers found on the same page as each handle — which
is what lifts two forum accounts above the correlation-point floor.

Anything Robin's LLM *concluded* arrives capped at UNCERTAIN in one correlation
group. It corroborates; it cannot establish.

**Breach corpora are denied.** Correlating handles you observed *on* a forum is
what this is for. Ingesting a credential dump to resolve a handle to an email is
unlawfully obtained in most jurisdictions, has unmeasured accuracy, and taints
the investigation that touches it.

---

## Deploying

[DEPLOYMENT.md](DEPLOYMENT.md). Observation files contain real handles from real
cases — keep them outside the repo. `.gitignore`, `scripts/pre-commit` and an
`artifact-guard` CI job enforce this.

```bash
ln -sf ../../scripts/pre-commit .git/hooks/pre-commit
```

## Known limitations

`METHODOLOGY_AUDIT.md` is an adversarial read of this toolkit, written as if by
a reviewer with no stake in it. Read it before relying on a number.

The governing limitation: **calibration is unvalidated.** Every probability is a
defensible ordering, not a measured frequency. And of nine identified failure
modes, **four bias toward overconfidence and none bias low** — an asymmetry that
is a direct consequence of having nothing fitted to catch it.

## Status

See `CHANGELOG.md`. Pre-release; API unstable. Calibration not validated against ground truth — bands
are principled, not fitted. Stylometry is deliberately stubbed: the literature
does not support the accuracy commercial tools claim at short text lengths.

---

## Author

**Tushar Karumudi** — [github.com/tusharkarumudi](https://github.com/tusharkarumudi)

## License

Copyright 2026 Tushar Karumudi.

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).

Cite via [CITATION.cff](CITATION.cff).
