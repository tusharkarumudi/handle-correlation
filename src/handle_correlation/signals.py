"""Correlation signals over observed handles.

Every function here takes ``Observation`` records the analyst already holds --
from forum scrapes they conducted, commit logs, malware configuration, ad
network records, their own platform telemetry -- and emits ``Claim`` objects for
``attribution-graph`` to score.

Nothing in this package discovers handles. It decides whether handles you
already have belong to the same actor. That distinction is the whole design:
discovery across hundreds of sites is a profile-building operation, while
deciding whether two observed handles co-refer is the analytic question in
threat-actor attribution, and it is the one nobody has calibrated.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from itertools import combinations

from attribution_graph import Claim, Identifier, IdKind, Predicate, Reliability

from .mutation import MutationMatch, compare, normalize, root_key

# --------------------------------------------------------------------------- #
# Observations
# --------------------------------------------------------------------------- #

@dataclass
class Observation:
    """One handle, seen on one platform, at one time, in your own case data."""

    handle: str
    platform: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    #: Identifiers the *platform itself* published alongside the handle --
    #: a profile email, a PGP fingerprint, a linked site. Not inferred.
    linked: dict[str, str] = field(default_factory=dict)
    #: UTC hour histogram of activity, if you have post or commit timestamps.
    activity_hours: Counter[int] = field(default_factory=Counter)
    #: Free-text sample for stylometry. Corroborative only.
    text_sample: str = ""
    source_url: str = ""
    case_ref: str = ""

    @property
    def qualified(self) -> str:
        return f"{self.platform}:{self.handle}"

    @property
    def ident(self) -> Identifier:
        return Identifier(IdKind.HANDLE, self.qualified)


# --------------------------------------------------------------------------- #
# Handle selectivity
# --------------------------------------------------------------------------- #

class HandleCorpus:
    """Counts how many distinct people plausibly use a handle root.

    This is the single largest improvement over existing username tooling.
    Maigret and Sherlock report that ``dave`` exists on 180 sites and that
    ``kr4ken_x99`` exists on 3, with no indication that the second result is
    worth a thousand times more. Selectivity supplies exactly that.

    Seed from any large public username list -- top-username corpora, package
    registry maintainer names, public commit author names -- plus your own
    accumulated case observations. The counts do not need to be precise; they
    need to distinguish three orders of magnitude, which is easy.
    """

    def __init__(self, counts: dict[str, int] | None = None, universe: int = 50_000_000):
        self._counts: dict[str, int] = counts or {}
        self._universe = universe

    @classmethod
    def from_file(cls, path: str, universe: int = 50_000_000) -> HandleCorpus:
        counts: dict[str, int] = defaultdict(int)
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                h = line.strip()
                if not h:
                    continue
                parts = h.split("\t")
                root = normalize(parts[0]).root
                if root:
                    counts[root] += int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        return cls(dict(counts), universe)

    def observe(self, handle: str) -> None:
        r = normalize(handle).root
        if r:
            self._counts[r] = self._counts.get(r, 0) + 1

    def holders(self, ident: Identifier) -> int:
        if ident.kind is not IdKind.HANDLE:
            return 0
        return self._counts.get(normalize(ident.value).root, 1)

    def universe(self) -> int:
        return self._universe


# --------------------------------------------------------------------------- #
# Signals
# --------------------------------------------------------------------------- #

def handle_similarity_claims(
    observations: Sequence[Observation],
    corpus: HandleCorpus,
) -> list[Claim]:
    """Same-root and mutation links between observed handles.

    Blocked on root prefix so this stays tractable on large observation sets.
    """
    blocks: dict[str, list[Observation]] = defaultdict(list)
    for o in observations:
        k = root_key(o.qualified)
        if k:
            blocks[k].append(o)

    claims: list[Claim] = []
    for block in blocks.values():
        for a, b in combinations(block, 2):
            if a.platform == b.platform and a.handle == b.handle:
                continue
            m = compare(a.qualified, b.qualified)
            if not m.is_link:
                continue
            claims.append(_mutation_claim(a, b, m))
    return claims


_RELATION_RELIABILITY = {
    "identical_root": Reliability.STRONG,
    "same_root_mutated": Reliability.MODERATE,
    "near_identical": Reliability.MODERATE,
    "substring": Reliability.WEAK,
    "close_variant": Reliability.WEAK,
}


def _mutation_claim(a: Observation, b: Observation, m: MutationMatch) -> Claim:
    rel = _RELATION_RELIABILITY.get(m.relation, Reliability.WEAK)
    # Homoglyph substitution in a handle is deliberate. It raises confidence
    # that the two are one actor evading correlation, rather than a coincidence.
    if "homoglyph" in m.transforms:
        rel = Reliability.MODERATE if rel is Reliability.WEAK else rel
    return Claim(
        subject=a.ident,
        predicate=Predicate.SAME_AS,
        object=b.ident,
        collector="handle_mutation",
        source_url=a.source_url or f"observation://{a.case_ref or 'case'}",
        reliability=rel,
        observed_at=a.first_seen or a.last_seen,
        # Handle reuse is ONE naming habit, expressed once. Every pair sharing a
        # root belongs to the same group -- otherwise a handle seen on eight
        # platforms manufactures 28 "independent" observations from one fact.
        correlation_group=f"handle_root|{m.root_a}",
        raw={"relation": m.relation, "distance": m.distance,
             "transforms": list(m.transforms),
             "platforms": [a.platform, b.platform]},
    )


def linked_identifier_claims(observations: Sequence[Observation]) -> list[Claim]:
    """Platform-published identifiers attached to a handle.

    This is where an attribution actually lands. A handle is a label; an email,
    a PGP fingerprint or a wallet is a durable identifier that appears elsewhere.
    These are the highest-value claims in the module -- and they are all things
    the platform published, not things this code derived.
    """
    kind_map = {
        "email": IdKind.EMAIL,
        "pgp": IdKind.PGP_FPR,
        "ssh": IdKind.SSH_FPR,
        "domain": IdKind.DOMAIN,
        "url": IdKind.URL,
        "gravatar": IdKind.GRAVATAR_HASH,
        "name": IdKind.PERSON_NAME,
    }
    reliability = {
        "email": Reliability.STRONG,
        "pgp": Reliability.AUTHORITATIVE,
        "ssh": Reliability.AUTHORITATIVE,
        "gravatar": Reliability.STRONG,
        "domain": Reliability.MODERATE,
        "url": Reliability.MODERATE,
        "name": Reliability.WEAK,
    }

    claims: list[Claim] = []
    for o in observations:
        for key, value in o.linked.items():
            kind = kind_map.get(key.lower())
            if not kind or not value:
                continue
            claims.append(Claim(
                subject=o.ident,
                predicate=Predicate.PROFILE_BINDING,
                object=Identifier(kind, value),
                collector="handle_linked_identifier",
                source_url=o.source_url or f"observation://{o.case_ref or 'case'}",
                reliability=reliability.get(key.lower(), Reliability.WEAK),
                observed_at=o.first_seen,
                correlation_group=f"profile|{o.qualified}",
                raw={"platform": o.platform, "field": key},
            ))
    return claims


def shared_identifier_claims(observations: Sequence[Observation]) -> list[Claim]:
    """Handles that bind the *same* durable identifier co-refer.

    Without this, a shared PGP fingerprint produces two separate
    handle->key claims and no handle<->handle link, so union-find never merges
    the actors even though the evidence is conclusive. Materializing the
    transitive edge is what makes a hub identifier do its job.

    Each emitted claim inherits the correlation group of the binding that
    produced it, so two handles sharing one key via two independent platform
    profiles counts as two groups -- which is exactly what should lift it above
    the single-source cap.
    """
    by_value: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for o in observations:
        for key, value in o.linked.items():
            if key.lower() in ("pgp", "ssh", "email", "gravatar") and value:
                by_value[(key.lower(), value.strip().lower())].append(o)

    strength = {
        "pgp": Reliability.AUTHORITATIVE,
        "ssh": Reliability.AUTHORITATIVE,
        "gravatar": Reliability.STRONG,
        "email": Reliability.STRONG,
    }

    claims: list[Claim] = []
    for (key, value), group in by_value.items():
        if len(group) < 2:
            continue
        for a, b in combinations(group, 2):
            if a.qualified == b.qualified:
                continue
            claims.append(Claim(
                subject=a.ident, predicate=Predicate.SAME_AS, object=b.ident,
                collector="handle_shared_identifier",
                source_url=a.source_url or "observation://case",
                reliability=strength.get(key, Reliability.MODERATE),
                observed_at=a.first_seen,
                # Reuses the source binding's group. This claim is *derived*
                # from the profile bindings, not observed independently, so a
                # new group would count one fact twice.
                correlation_group=f"profile|{a.qualified}",
                raw={"shared": key, "platforms": [a.platform, b.platform]},
            ))
    return claims


def temporal_claims(
    observations: Sequence[Observation],
    min_events: int = 30,
) -> list[Claim]:
    """Activity-hour overlap between handles.

    Corroborative only. ``TIMEZONE_HINT`` is excluded from the independent-group
    count in the scoring model, so this can strengthen a link that already has
    support but can never create one. That is the correct weight: a shared
    timezone is shared with roughly a twelfth of the internet.
    """
    claims: list[Claim] = []
    usable = [o for o in observations if sum(o.activity_hours.values()) >= min_events]
    for a, b in combinations(usable, 2):
        oa, ob = _peak_offset(a.activity_hours), _peak_offset(b.activity_hours)
        if oa is None or ob is None:
            continue
        delta = min(abs(oa - ob), 24 - abs(oa - ob))
        if delta <= 1:
            claims.append(Claim(
                subject=a.ident, predicate=Predicate.TIMEZONE_HINT,
                object=Identifier(IdKind.HANDLE, b.qualified),
                collector="handle_temporal",
                source_url=a.source_url or "observation://case",
                reliability=Reliability.WEAK,
                correlation_group=f"tz|{a.qualified}|{b.qualified}",
                raw={"offset_a": oa, "offset_b": ob, "delta_hours": delta},
            ))
        elif delta >= 8:
            # Contradiction. Weak, but negative evidence is rarer than positive
            # and therefore disproportionately useful.
            claims.append(Claim(
                subject=a.ident, predicate=Predicate.CONTRADICTS,
                object=Identifier(IdKind.HANDLE, b.qualified),
                collector="handle_temporal",
                source_url=a.source_url or "observation://case",
                reliability=Reliability.WEAK,
                correlation_group=f"tz_conflict|{a.qualified}|{b.qualified}",
                raw={"offset_a": oa, "offset_b": ob, "delta_hours": delta},
            ))
    return claims


def _peak_offset(hours: Counter[int]) -> int | None:
    """Infer UTC offset from an activity histogram.

    Assumes the quietest contiguous six hours are local 01:00-07:00. Crude, and
    weighted accordingly.
    """
    if not hours:
        return None
    best_start, best = None, None
    for start in range(24):
        w = sum(hours.get((start + i) % 24, 0) for i in range(6))
        if best is None or w < best:
            best, best_start = w, start
    if best_start is None:
        return None
    off = (1 - best_start) % 24
    return off - 24 if off > 12 else off


def lifespan_contradiction_claims(observations: Sequence[Observation]) -> list[Claim]:
    """Non-overlapping account lifespans as weak negative evidence.

    Useful in the opposite direction too: sequential accounts where one dies
    within days of the next appearing is a classic ban-evasion pattern. That is
    left to the analyst rather than encoded, because the same shape occurs
    innocently.
    """
    claims: list[Claim] = []
    dated = [o for o in observations if o.first_seen and o.last_seen]
    for a, b in combinations(dated, 2):
        if a.last_seen < b.first_seen or b.last_seen < a.first_seen:
            gap = abs((b.first_seen - a.last_seen).days) if a.last_seen < b.first_seen \
                else abs((a.first_seen - b.last_seen).days)
            if gap > 730:
                claims.append(Claim(
                    subject=a.ident, predicate=Predicate.CONTRADICTS,
                    object=b.ident,
                    collector="handle_lifespan",
                    source_url="observation://case",
                    reliability=Reliability.WEAK,
                    correlation_group=f"lifespan|{a.qualified}|{b.qualified}",
                    raw={"gap_days": gap},
                ))
    return claims


# --------------------------------------------------------------------------- #
# Correlation-point policy
# --------------------------------------------------------------------------- #

class Confidence(StrEnum):
    INSUFFICIENT = "INSUFFICIENT"   # 0-1 points: not a lead
    LOW = "LOW"                     # 2-3 points: a lead, never a finding
    MODERATE = "MODERATE"           # 4-5 points
    HIGH = "HIGH"                   # 6+ points and a durable identifier


#: Distinct evidence types, not claim count. Eight platforms showing one handle
#: is one point, because it is one naming habit observed once.
POINT_KINDS = {
    Predicate.SAME_AS: "handle_root",
    Predicate.PROFILE_BINDING: "profile_binding",
    Predicate.COMMIT_EMAIL: "commit_email",
    Predicate.KEY_BINDING: "key_binding",
}

#: Identifier kinds that are durable and hard to fake -- what separates a real
#: attribution from a naming coincidence.
DURABLE_KINDS = {IdKind.PGP_FPR, IdKind.SSH_FPR, IdKind.GRAVATAR_HASH, IdKind.EMAIL}


@dataclass
class HandleConfidence:
    points: int
    kinds: list[str]
    has_durable_identifier: bool
    level: Confidence
    caveat: str

    def to_dict(self) -> dict:
        return {"correlation_points": self.points, "evidence_kinds": self.kinds,
                "durable_identifier": self.has_durable_identifier,
                "confidence": self.level.value, "caveat": self.caveat}


def correlation_points(claims: Sequence[Claim]) -> HandleConfidence:
    """Count distinct correlation points and apply the confidence policy.

    Handle correlation deserves a harder floor than the generic model, because
    handle reuse is both the most common signal and the weakest: people pick
    similar names independently all the time, and an adversary can adopt a
    target's handle deliberately. So two or three points is a lead worth
    following, never a finding to act on.
    """
    # A correlation point must be a RELATION connecting observations, not an
    # attribute decorating one.
    #
    # This counted each distinct identifier value as a point regardless of
    # whether it linked anything. A review built six profiles sharing a handle,
    # each with a *different* email, and got 7 points / HIGH / durable=True.
    # Six unrelated addresses do not corroborate a shared actor -- they are
    # attributes of six separate observations, and if anything they weigh
    # against a merge.
    #
    # So a durable identifier scores only when the same normalised value is
    # observed on two or more distinct profiles.
    kinds: set[str] = set()
    durable = False
    #: identifier value -> the profiles that published it
    by_value: dict[str, set[str]] = {}
    #: values that appear on a single profile, kept for the caveat
    singletons: set[str] = set()

    for c in claims:
        if c.weight <= 0:
            continue

        # Derived claims add no information. shared_identifier claims are
        # computed *from* the profile bindings below, so counting both is
        # double counting one fact.
        if c.collector == "handle_shared_identifier":
            continue

        kind = POINT_KINDS.get(c.predicate)
        if not kind:
            continue

        if kind == "handle_root":
            # One point for the whole naming habit, regardless of how many
            # platforms or pairs it spans.
            kinds.add("handle_root")
            continue

        if isinstance(c.object, Identifier):
            key = f"{c.object.kind.value}:{c.object.value}"
            # The subject of a profile binding is the profile that published it.
            profile = (c.subject.value if isinstance(c.subject, Identifier)
                       else c.correlation_group)
            by_value.setdefault(key, set()).add(profile)
        else:
            kinds.add(c.correlation_group)

    for key, profiles in by_value.items():
        if len(profiles) >= 2:
            kinds.add(key)
            kind_name = key.split(":", 1)[0]
            if any(k.value == kind_name for k in DURABLE_KINDS):
                durable = True
        else:
            singletons.add(key)

    n = len(kinds)
    if n <= 1:
        level = Confidence.INSUFFICIENT
        caveat = ("Single correlation point. This is not a lead — a shared or "
                  "similar handle alone is consistent with two unrelated people.")
    elif n <= 3:
        level = Confidence.LOW
        caveat = (f"{n} correlation points. LOW confidence: treat as a lead for "
                  "further collection, not as an attribution. Do not act on this "
                  "alone and do not report it as identifying anyone.")
    elif n <= 5:
        level = Confidence.MODERATE if durable else Confidence.LOW
        caveat = (f"{n} correlation points"
                  + ("" if durable else " but no durable identifier (key, verified "
                     "email or avatar hash) — held at LOW because handle and "
                     "profile-text similarity is imitable")
                  + ".")
    else:
        level = Confidence.HIGH if durable else Confidence.MODERATE
        caveat = (f"{n} correlation points"
                  + (" including a durable identifier." if durable else
                     " but no durable identifier; capped at MODERATE."))

    if singletons:
        caveat += (f" {len(singletons)} identifier(s) appeared on only one "
                   "profile and were not counted: an attribute of a single "
                   "observation links nothing.")

    return HandleConfidence(n, sorted(kinds), durable, level, caveat)


def all_claims(
    observations: Sequence[Observation],
    corpus: HandleCorpus | None = None,
) -> list[Claim]:
    """Every signal, ready for ``attribution_graph.assess`` or ``resolve``."""
    corpus = corpus or HandleCorpus()
    return [
        *handle_similarity_claims(observations, corpus),
        *linked_identifier_claims(observations),
        *shared_identifier_claims(observations),
        *temporal_claims(observations),
        *lifespan_contradiction_claims(observations),
    ]
