"""Handle mutation analysis."""

import pytest

from handle_correlation import compare, normalize


@pytest.mark.parametrize("handle,root", [
    ("kr4ken", "kraken"), ("Kraken_X", "kraken"), ("xXkrakenXx", "kraken"),
    ("kraken.1988", "kraken"), ("KRAKEN", "kraken"), ("k.r.a.k.e.n", "kraken"),
    ("krakennnn", "krakenn"),
])
def test_root_recovery(handle, root):
    assert normalize(handle).root == root


def test_homoglyph_folding_is_detected():
    n = normalize("kr\u0430ken")   # Cyrillic а
    assert n.root == "kraken"
    assert n.homoglyph_used


def test_platform_prefix_ignored():
    assert normalize("github:kraken").root == normalize("telegram:kraken").root


@pytest.mark.parametrize("a,b", [
    ("github:kr4ken", "telegram:kraken_x"),
    ("x:xXkrakenXx", "forum:kraken1988"),
    ("gitlab:d4rkw0lf", "telegram:darkwolf"),
])
def test_mutations_of_one_root_link(a, b):
    assert compare(a, b).is_link


@pytest.mark.parametrize("h", ["admin", "root", "support", "official", "abc"])
def test_generic_handles_are_never_evidence(h):
    m = compare(f"github:{h}", f"telegram:{h}")
    assert not m.meaningful and not m.is_link


def test_short_handles_rejected():
    assert not compare("x:joe", "github:joe").meaningful


def test_unrelated_handles_do_not_link():
    assert not compare("github:kraken", "telegram:phoenixfire").is_link


def test_short_substring_is_not_containment():
    """'ana' in 'banana' must not link."""
    m = compare("github:banana_split", "x:anaconda")
    assert m.relation != "substring" or not m.is_link


def test_distance_threshold_scales_with_length():
    # 2 edits on a short root is coincidence; on a long one it is a variant
    assert not compare("x:kraken", "x:krokan").is_link
    assert compare("x:krakenmaster", "x:krokenmaster").is_link


@pytest.mark.parametrize("handle,root", [
    ("kraken1988", "kraken"), ("xXkraken_1988Xx", "kraken"), ("kr4ken99", "kraken"),
])
def test_trailing_digits_are_a_suffix_not_leetspeak(handle, root):
    """Leet substitutions are embedded in a word ("kr4ken"). A trailing digit
    run is a numeric suffix, and translating it turned "kraken1988" into
    "krakenigbb" -- silently breaking every handle with a year on the end."""
    n = normalize(handle)
    assert n.root == root
    assert n.trailing_digits


def test_embedded_leet_still_translates():
    assert normalize("kr4ken").root == "kraken"
    assert normalize("l33t").root == "leet"


# ---- candidates from a real name ------------------------------------------- #

def test_candidates_generated_from_a_person_name():
    from handle_correlation import candidates_from_name

    h = candidates_from_name("HOÀNG PHÚ LINH")
    assert "hoanglinh" in h and "hoang.linh" in h and "hlinh" in h


def test_candidates_fold_diacritics():
    from handle_correlation import candidates_from_name

    assert candidates_from_name("Müller Schmidt") == candidates_from_name(
        "Muller Schmidt")


def test_candidates_reject_generic_and_short_forms():
    from handle_correlation import candidates_from_name

    assert all(len(h) >= 4 for h in candidates_from_name("Li Wu"))
    assert "admin" not in candidates_from_name("Admin User")


def test_empty_name_yields_no_candidates():
    from handle_correlation import candidates_from_name

    assert candidates_from_name("") == []
