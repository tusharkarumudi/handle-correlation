"""Handle correlation, start to finish, offline.

    python examples/end_to_end_handles.py

Three scenarios, chosen to show where the confidence policy bites:

  1. One handle across eight platforms      -> INSUFFICIENT
  2. Two handles, one shared PGP key        -> LOW
  3. Two handles, several durable links     -> MODERATE

The first is the one worth understanding. Most username tooling would present
eight platform hits as strong corroboration. It is one naming habit, observed
once.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta

from attribution_graph import AttributionGraph, EntityType, assess, resolve

from handle_correlation import (
    HandleCorpus,
    Observation,
    all_claims,
    compare,
    correlation_points,
    normalize,
)

NOW = datetime(2026, 8, 19, tzinfo=UTC)
FPR = "9F3A2B1C4D5E6F708192A3B4C5D6E7F8091A2B3C"


def banner(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def show(label: str, observations: list[Observation], corpus: HandleCorpus) -> None:
    claims = all_claims(observations, corpus)
    hc = correlation_points(claims)
    linking = [c for c in claims if hasattr(c.object, "kind")]
    a = assess(linking, corpus.holders, corpus.universe(), now=NOW)

    print(f"\n{label}")
    print(f"  observations      {len(observations)} across "
          f"{len({o.platform for o in observations})} platform(s)")
    print(f"  claims            {len(claims)} in "
          f"{len({c.correlation_group for c in claims})} correlation group(s)")
    print(f"  points            {hc.points}  ({', '.join(hc.kinds[:4])}"
          f"{'…' if len(hc.kinds) > 4 else ''})")
    print(f"  durable id        {hc.has_durable_identifier}")
    print(f"  CONFIDENCE        {hc.level.value}")
    print(f"  generic model     {a.band.value} (p={a.probability:.3f}, "
          f"{a.independent_groups} independent group(s))")
    print(f"  caveat            {hc.caveat}")
    if hc.level.value in ("INSUFFICIENT", "LOW") and a.band.value in (
            "MODERATE_EVIDENCE", "STRONG_EVIDENCE"):
        print("  ** the handle policy is stricter than the generic model here, "
              "and governs **")


def main() -> None:
    banner("Handle mutation: recovering the root")
    for h in ("kr4ken", "xXkraken_1988Xx", "KRAKEN.x", "kr\u0430ken"):
        n = normalize(h)
        flags = [f for f, on in (("leet", n.leet_used), ("homoglyph", n.homoglyph_used),
                                 ("affix", n.stripped_affix)) if on]
        print(f"  {h:20} -> {n.root:12} {'(' + ', '.join(flags) + ')' if flags else ''}")

    m = compare("github:kr4ken", "telegram:xXkraken_1988Xx")
    print(f"\n  relation: {m.relation}, transforms: {', '.join(m.transforms)}")

    print("\n  admin / admin -> "
          f"meaningful={compare('github:admin', 'x:admin').meaningful} "
          "(generic handles are no evidence, not weak evidence)")

    # Selectivity corpus. Without one, every handle looks unique.
    corpus = HandleCorpus({"kraken": 4, "dave": 180_000, "phoenix": 22_000})

    banner("Scenario 1 — one handle, eight platforms")
    show("same handle everywhere, nothing else",
         [Observation(handle="kr4ken", platform=p, first_seen=NOW)
          for p in ("github", "telegram", "x", "forum", "gitlab",
                    "npm", "reddit", "keybase")],
         corpus)
    print("\n  Eight platforms is ONE observation of ONE naming habit, made once.")
    print("  Every same-root claim shares a correlation group, so it cannot")
    print("  exceed the single-source cap however many platforms are added.")

    banner("Scenario 2 — two handles, one shared PGP key")
    show("shared cryptographic binding",
         [Observation(handle="kr4ken", platform="github", first_seen=NOW,
                      linked={"pgp": FPR}),
          Observation(handle="kraken_x", platform="telegram", first_seen=NOW,
                      linked={"pgp": FPR})],
         corpus)
    print("\n  A durable identifier published by two independent profiles.")
    print("  Still LOW: a lead worth pursuing, not an attribution to act on.")

    banner("Scenario 3 — multiple durable links")
    show("key, email, domain and activity overlap",
         [Observation(handle="kr4ken", platform="github", first_seen=NOW,
                      linked={"pgp": FPR, "email": "k@example.test"},
                      activity_hours=Counter({h: 12 for h in range(13, 23)})),
          Observation(handle="kraken_x", platform="telegram", first_seen=NOW,
                      linked={"pgp": FPR, "domain": "kraken.example"},
                      activity_hours=Counter({h: 11 for h in range(13, 23)}))],
         corpus)

    banner("Scenario 4 — a common handle, same evidence shape")
    show("identical structure, but the handle is 'dave'",
         [Observation(handle="dave", platform="github", first_seen=NOW),
          Observation(handle="dave_x", platform="telegram", first_seen=NOW)],
         corpus)
    print("\n  Same shape as scenario 1, far lower weight: selectivity does the")
    print("  work. 'dave' is held by ~180,000 people; 'kraken' by ~4.")

    banner("Negative evidence")
    show("non-overlapping lifespans",
         [Observation(handle="kr4ken", platform="forum",
                      first_seen=NOW - timedelta(days=3000),
                      last_seen=NOW - timedelta(days=2600)),
          Observation(handle="kraken_x", platform="telegram",
                      first_seen=NOW - timedelta(days=60), last_seen=NOW)],
         corpus)

    banner("Why two numbers")
    print("""
  The generic scoring model and the handle policy can disagree, and where they
  do, the handle policy governs. That is deliberate.

  The generic model counts independent correlation groups. The handle policy
  counts distinct evidence *types*, deduplicated by identifier value -- so two
  profiles publishing the same PGP key is one point, not two, because it is one
  key corroborated twice rather than two independent facts.

  Handle correlation earns the stricter floor because handle reuse is
  simultaneously the commonest signal and the weakest. People pick similar names
  independently all the time, and an adversary can adopt a target's handle
  deliberately at zero cost. Two or three points is a lead worth following. It is
  not something to act on, and not something to put in a report as identifying
  anyone.""")

    banner("Resolution")
    graph = AttributionGraph(case_ref="HANDLE-DEMO")
    obs = [Observation(handle="kr4ken", platform="github", first_seen=NOW,
                       linked={"pgp": FPR, "email": "k@example.test"}),
           Observation(handle="kraken_x", platform="telegram", first_seen=NOW,
                       linked={"pgp": FPR}),
           Observation(handle="phoenixfire", platform="x", first_seen=NOW)]
    for c in all_claims(obs, corpus):
        graph.add_claim(c)
    resolve(graph, {EntityType.PERSONA}, index=corpus)

    clusters = [e for e in graph.entities.values() if len(e.identifiers) > 1]
    print(f"\n  {len(clusters)} actor cluster(s) from {len(obs)} observation(s)")
    for e in clusters:
        print(f"    {', '.join(sorted(i.value for i in e.identifiers))}")
    print("\n  phoenixfire stayed separate. Nothing linked it, and nothing")
    print("  should have.")


if __name__ == "__main__":
    main()
