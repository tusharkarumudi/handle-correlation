"""Obfuscation in handle correlation.

Handle mutation already folds leetspeak and homoglyphs for *matching*. These
test the adversarial direction: an actor deliberately varying a handle to avoid
correlation, and an actor deliberately colliding with someone else's.
"""

import pytest
from attribution_graph import Identifier, IdKind, assess

from handle_correlation import (
    Observation,
    all_claims,
    compare,
    correlation_points,
    normalize,
)


def obs(handle, platform, **kw):
    return Observation(handle=handle, platform=platform, **kw)


# ---- evasion: one actor varying a handle ---------------------------------- #

@pytest.mark.parametrize("variant", [
    "kr4ken", "KRAKEN", "kraken_x", "xXkrakenXx", "kraken.1988",
    "kr\u0430ken",              # Cyrillic а
    "kraken\u200b",             # zero-width padding
    "k r a k e n",              # spaced
])
def test_variants_recover_the_same_root(variant):
    assert normalize(variant).root == "kraken"


def test_homoglyph_use_raises_rather_than_lowers_confidence():
    """Substituting Cyrillic а is deliberate. It is evidence of evasion, so it
    must not be treated as a coincidental near-miss."""
    m = compare("github:kraken", "telegram:kr\u0430ken")
    assert m.is_link
    assert "homoglyph" in m.transforms


def test_evasion_across_platforms_still_counts_once():
    """Varying the handle per platform must not manufacture extra evidence."""
    variants = ["kr4ken", "KRAKEN", "kraken_x", "xXkrakenXx",
                "kr\u0430ken", "kraken.1988"]
    claims = all_claims([obs(v, f"p{i}") for i, v in enumerate(variants)])
    a = assess(claims, lambda i: 1)
    assert a.independent_groups <= 1
    assert a.band.value in ("WEAK", "UNSUPPORTED")


def test_correlation_points_not_inflated_by_variants():
    variants = ["kr4ken", "KRAKEN", "kraken_x", "xXkrakenXx", "kr\u0430ken"]
    hc = correlation_points(all_claims([obs(v, f"p{i}")
                                        for i, v in enumerate(variants)]))
    assert hc.points == 1
    assert hc.level.value == "INSUFFICIENT"


# ---- collision: one actor impersonating another --------------------------- #

def test_generic_and_short_handles_are_never_evidence():
    for h in ("admin", "root", "support", "abc", "user"):
        assert not compare(f"github:{h}", f"telegram:{h}").is_link, h


def test_shared_durable_identifier_is_what_actually_links():
    """Handle similarity is imitable; a key binding is not."""
    fpr = "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
    weak = correlation_points(all_claims(
        [obs("kr4ken", "github"), obs("kraken_x", "telegram")]))
    strong = correlation_points(all_claims(
        [obs("kr4ken", "github", linked={"pgp": fpr}),
         obs("kraken_x", "telegram", linked={"pgp": fpr})]))
    assert weak.points < strong.points
    assert not weak.has_durable_identifier
    assert strong.has_durable_identifier


def test_obfuscated_linked_identifiers_normalize():
    """A PGP fingerprint padded with zero-width characters is the same key."""
    a = Identifier(IdKind.PGP_FPR, "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234")
    b = Identifier(IdKind.PGP_FPR, "abcd1234abcd1234abcd1234abcd1234abcd1234\u200b")
    assert a.key == b.key


def test_impersonation_still_reports_low_without_a_binding():
    """An actor adopting a target's handle costs nothing. Two or three points
    is a lead, never a finding."""
    hc = correlation_points(all_claims(
        [obs("kr4ken", "github"), obs("kr4ken", "telegram")]))
    assert hc.level.value in ("INSUFFICIENT", "LOW")
    assert "lead" in hc.caveat.lower() or "not a lead" in hc.caveat.lower()
