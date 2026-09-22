"""Load observations from analyst-collected case data.

Deliberately file-based. This package does not fetch handles from platforms --
it reasons about handles you already collected under your own authority, which
keeps the collection decision (and its legal basis) with the analyst rather than
buried in a library.

CSV columns: handle, platform, first_seen, last_seen, source_url,
             link_email, link_pgp, link_domain, link_name, hours, text
JSON: a list of objects with the same keys.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from .signals import Observation


def _dt(v: str | None) -> datetime | None:
    if not v:
        return None
    for f in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(v.strip()[:19], f).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _hours(v) -> Counter:
    if not v:
        return Counter()
    if isinstance(v, dict):
        return Counter({int(k): int(n) for k, n in v.items()})
    try:
        return Counter({int(k): int(n) for k, n in json.loads(v).items()})
    except (ValueError, TypeError):
        return Counter()


def _row_to_observation(row: dict) -> Observation | None:
    handle = (row.get("handle") or "").strip()
    platform = (row.get("platform") or "unknown").strip().lower()
    if not handle:
        return None
    linked = {
        k[5:]: v.strip() for k, v in row.items()
        if k.startswith("link_") and isinstance(v, str) and v.strip()
    }
    return Observation(
        handle=handle,
        platform=platform,
        first_seen=_dt(row.get("first_seen")),
        last_seen=_dt(row.get("last_seen")),
        linked=linked,
        activity_hours=_hours(row.get("hours")),
        text_sample=(row.get("text") or "")[:5000],
        source_url=(row.get("source_url") or "").strip(),
        case_ref=(row.get("case_ref") or "").strip(),
    )


def load(path: str | Path) -> list[Observation]:
    p = Path(path)
    if p.suffix.lower() == ".json":
        rows = json.loads(p.read_text())
    else:
        with p.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    return [o for r in rows if (o := _row_to_observation(r))]
