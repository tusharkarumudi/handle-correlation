"""Handle mutation analysis.

The core observation: people do not pick unrelated handles. They mutate one
root. ``kr4ken``, ``kraken_x``, ``kraken1988``, ``krakenn``, ``xXkrakenXx`` and
``кraken`` (Cyrillic е) are one naming habit expressed six ways, and recovering
the root is what makes them comparable.

This module answers "how far apart are these two handles under plausible
transformation", not "does this handle exist somewhere". It is pure string
analysis over handles the analyst has already collected. No network calls.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #

LEET = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
    "8": "b", "9": "g", "$": "s", "@": "a", "!": "i", "+": "t",
})

#: Cyrillic and Greek characters visually identical to Latin. Homoglyph
#: substitution is deliberate evasion when it appears in handles, so folding it
#: is a signal in itself, tracked separately in ``homoglyph_used``.
HOMOGLYPH = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "і": "i", "ѕ": "s", "ԁ": "d", "һ": "h", "ӏ": "l", "ν": "v", "ο": "o",
    "α": "a", "ε": "e", "ρ": "p", "τ": "t", "κ": "k", "μ": "m", "ι": "i",
})

SEPARATORS = re.compile(r"[._\-\s]+")
AFFIX = re.compile(
    r"^(?:x{1,3}|the|mr|ms|real|official|its|im|i_?am)[._\-]?|"
    r"[._\-]?(?:x{1,3}|official|real|hq|yt|tv|ttv|dev|prod|bot|"
    r"\d{1,4}|1337|420|69|420_?69)$",
    re.IGNORECASE,
)
REPEAT = re.compile(r"(.)\1{2,}")

#: Handles below this length collide across unrelated people at rates that make
#: any similarity signal meaningless.
MIN_MEANINGFUL_LENGTH = 4

#: Handles that are words, roles or extremely common. Never evidence.
GENERIC = frozenset({
    "admin", "administrator", "root", "user", "test", "guest", "info", "mail",
    "support", "contact", "hello", "team", "official", "news", "media", "shop",
    "store", "blog", "home", "main", "public", "private", "anonymous", "anon",
    "unknown", "null", "none", "default", "system", "service", "bot", "api",
    "dev", "developer", "owner", "master", "staff", "mod", "moderator",
})


@dataclass(frozen=True)
class Normalized:
    original: str
    root: str
    stripped_affix: bool
    leet_used: bool
    homoglyph_used: bool
    separators_removed: int
    trailing_digits: str

    @property
    def is_generic(self) -> bool:
        return self.root in GENERIC or len(self.root) < MIN_MEANINGFUL_LENGTH


@lru_cache(maxsize=8192)
def normalize(handle: str) -> Normalized:
    """Reduce a handle to its probable root."""
    raw = handle.split(":", 1)[-1].strip()
    s = unicodedata.normalize("NFKC", raw).lower()

    homo = s.translate(HOMOGLYPH)
    homoglyph_used = homo != s
    s = homo

    trailing = ""
    m = re.search(r"(\d{2,4})$", s)
    if m:
        trailing = m.group(1)

    before = s
    s = AFFIX.sub("", s)
    stripped_affix = s != before and bool(s)
    if not s:
        s = before

    seps = len(SEPARATORS.findall(s))
    s = SEPARATORS.sub("", s)

    # Strip a trailing digit run before leet translation. Leet substitutions
    # are embedded in a word ("kr4ken"); a trailing run is a numeric suffix,
    # and translating it turns "kraken1988" into "krakenigbb".
    body, suffix = s, ""
    m_suffix = re.search(r"\d+$", s)
    if m_suffix and len(m_suffix.group(0)) >= 2:
        body, suffix = s[:m_suffix.start()], m_suffix.group(0)
        if not trailing:
            trailing = suffix

    leeted = body.translate(LEET)
    leet_used = leeted != body
    s = leeted

    s = REPEAT.sub(r"\1\1", s)
    s = re.sub(r"[^a-z0-9]", "", s)

    return Normalized(raw, s, stripped_affix, leet_used, homoglyph_used, seps, trailing)


# --------------------------------------------------------------------------- #
# Distance
# --------------------------------------------------------------------------- #

def _levenshtein(a: str, b: str, cap: int = 6) -> int:
    if a == b:
        return 0
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            best = min(best, cur[-1])
        if best > cap:
            return cap + 1
        prev = cur
    return prev[-1]


@dataclass(frozen=True)
class MutationMatch:
    a: str
    b: str
    root_a: str
    root_b: str
    distance: int
    relation: str
    transforms: tuple[str, ...]
    meaningful: bool
    note: str = ""

    @property
    def is_link(self) -> bool:
        return self.meaningful and self.relation != "unrelated"


def compare(handle_a: str, handle_b: str) -> MutationMatch:
    """Classify the relationship between two handles."""
    na, nb = normalize(handle_a), normalize(handle_b)
    ra, rb = na.root, nb.root

    transforms = []
    for flag, label in (
        (na.leet_used or nb.leet_used, "leetspeak"),
        (na.homoglyph_used or nb.homoglyph_used, "homoglyph"),
        (na.stripped_affix or nb.stripped_affix, "affix"),
        (na.separators_removed or nb.separators_removed, "separator"),
    ):
        if flag:
            transforms.append(label)

    if na.is_generic or nb.is_generic:
        return MutationMatch(
            handle_a, handle_b, ra, rb, 0, "unrelated", tuple(transforms), False,
            note="generic or too short to discriminate",
        )

    if ra == rb:
        relation = "identical_root" if handle_a.split(":")[-1] == handle_b.split(":")[-1] \
            else "same_root_mutated"
        return MutationMatch(handle_a, handle_b, ra, rb, 0, relation,
                             tuple(transforms), True)

    dist = _levenshtein(ra, rb)
    longer = max(len(ra), len(rb))

    # Containment on short roots is coincidence: "ana" in "banana".
    if (ra in rb or rb in ra) and min(len(ra), len(rb)) >= 5:
        return MutationMatch(handle_a, handle_b, ra, rb, dist, "substring",
                             tuple(transforms), True)

    if dist <= 1 and longer >= 6:
        return MutationMatch(handle_a, handle_b, ra, rb, dist, "near_identical",
                             tuple(transforms), True)
    if dist == 2 and longer >= 9:
        return MutationMatch(handle_a, handle_b, ra, rb, dist, "close_variant",
                             tuple(transforms), True)

    return MutationMatch(handle_a, handle_b, ra, rb, dist, "unrelated",
                         tuple(transforms), True)


def root_key(handle: str) -> str:
    """Blocking key for candidate generation over large handle sets."""
    return normalize(handle).root[:8]


# --------------------------------------------------------------------------- #
# Candidates from a real name
# --------------------------------------------------------------------------- #

#: Minimum length for a generated candidate. Shorter forms collide with
#: unrelated real people at rates that make any later match meaningless.
MIN_CANDIDATE_LENGTH = 4


def candidates_from_name(name: str) -> list[str]:
    """Handles a person plausibly registered from their own name.

    Leads for collection, never evidence. A generated candidate that later
    matches an observed handle contributes through the ordinary scoring path,
    where handle similarity alone is capped at INSUFFICIENT -- precisely because
    name-derived guesses collide with real people who happen to share a name.

    This lives here rather than in a collector package because handle formation
    is this module's subject, and a second implementation elsewhere would drift.
    """
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    tokens = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in folded.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return []

    out = {"".join(tokens)}
    if len(tokens) >= 2:
        first, last = tokens[0], tokens[-1]
        out |= {
            f"{first}{last}", f"{first}.{last}", f"{first}_{last}",
            f"{first[0]}{last}", f"{last}{first}", f"{last}{first[0]}",
        }
    return sorted(
        h for h in out
        if len(h) >= MIN_CANDIDATE_LENGTH and h not in GENERIC
    )
