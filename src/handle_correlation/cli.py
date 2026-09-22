"""CLI: score a set of observed handles.

    handlecorr score --observations case.csv --corpus usernames.txt --out ./out
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from attribution_graph import (
    AttributionGraph,
    EntityType,
    assess,
    resolve,
)

from .ingest import load
from .signals import HandleCorpus, all_claims


def _score(args: argparse.Namespace) -> int:
    obs = load(args.observations)
    if not obs:
        print("no observations loaded", file=sys.stderr)
        return 1

    corpus = HandleCorpus.from_file(args.corpus) if args.corpus else HandleCorpus()
    if not args.corpus:
        print("warning: no --corpus given. Handle selectivity defaults to 1, so "
              "every handle looks unique and scores are upper bounds.",
              file=sys.stderr)
    for o in obs:
        corpus.observe(o.qualified)

    claims = all_claims(obs, corpus)
    graph = AttributionGraph(case_ref=args.case_ref)
    for c in claims:
        graph.add_claim(c)

    print(f"{len(obs)} observations, {len(claims)} claims")

    from collections import defaultdict
    pairs = defaultdict(list)
    for c in claims:
        if hasattr(c.object, "key"):
            pairs[tuple(sorted([c.subject.key, c.object.key]))].append(c)

    rows = []
    for pair, cs in pairs.items():
        a = assess(cs, corpus.holders, corpus.universe())
        rows.append((a.probability, pair, a))
    rows.sort(key=lambda r: -r[0])

    print(f"\n{'p':>6}  {'band':<12} {'grp':>3}  pair")
    for p, (x, y), a in rows[:40]:
        if a.band.value == "UNSUPPORTED":
            continue
        print(f"{p:6.3f}  {a.band.value:<12} {a.independent_groups:>3}  {x}  <->  {y}")

    resolve(graph, {EntityType.PERSONA}, index=corpus)  # populates graph.entities
    clusters = [e for e in graph.entities.values() if len(e.identifiers) > 1]
    print(f"\n{len(clusters)} actor cluster(s)")
    for e in clusters:
        print(f"  - {', '.join(sorted(i.value for i in e.identifiers))}")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "handle_graph.json").write_text(graph.to_json())
        (out / "assessments.json").write_text(json.dumps(
            [{"a": x, "b": y, **a.to_dict()} for _, (x, y), a in rows],
            indent=2))
        print(f"\n  {out}/handle_graph.json\n  {out}/assessments.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="handlecorr")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="score observed handles for same-actor")
    s.add_argument("--observations", required=True, help="CSV or JSON of observations")
    s.add_argument("--corpus", default="", help="username frequency list")
    s.add_argument("--case-ref", default="HANDLE-CASE")
    s.add_argument("--out", default="")
    s.set_defaults(func=_score)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
