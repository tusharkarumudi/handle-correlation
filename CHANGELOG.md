# Changelog

### Fixed (0.6.0)
- Leet translation mangled trailing digit runs: "kraken1988" normalised to
  "krakenigbb", silently breaking every handle with a year suffix. Trailing runs
  are now treated as numeric suffixes, not leetspeak.
- Derived shared-identifier claims created a new correlation group, counting one
  fact twice. They now reuse the source binding's group.

### Added (0.6.0)
- examples/end_to_end_handles.py (which is what surfaced both bugs above)

## [Unreleased]

## [2.0.1] - 2026-09-21

- Documentation, examples and test fixtures now use only placeholder data.
  2.0.0 has been withdrawn; upgrade to 2.0.1.
- Dependencies between the four packages now require `>=2.0.1,<2.1`.

## [0.1.0] - 2026-08-17

Initial release.

### Added
- Handle root recovery under leetspeak, separators, repeated characters, wrapper
  affixes, numeric suffixes and Cyrillic/Greek homoglyphs
- Length-scaled edit-distance thresholds; generic and short handles rejected
  outright rather than scored low
- `HandleCorpus` selectivity estimation from a username frequency list
- Signals: same-root mutation, platform-published identifier bindings, shared
  durable identifiers (transitive), activity-hour overlap, timezone conflict,
  lifespan contradiction
- CSV/JSON observation ingest; `handlecorr score` CLI

### Design constraints
- No enumeration. No breach-corpus ingest. No stylometry above WEAK.
- All same-root evidence occupies one correlation group, so handle reuse across
  N platforms cannot exceed the single-source confidence cap.
