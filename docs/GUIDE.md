# handle-correlation — method guide

In-depth reference for the method. The [README](../README.md) covers
what the package does and how to start.

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
