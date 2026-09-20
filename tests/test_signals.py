"""Correlation signal behaviour and, critically, its limits."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from attribution_graph import Band, Identifier, IdKind, Predicate, assess

from handle_correlation import HandleCorpus, Observation, all_claims, correlation_points

NOW = datetime(2026, 8, 17, tzinfo=UTC)


def obs(handle, platform, **kw):
    return Observation(handle=handle, platform=platform,
                       first_seen=kw.pop("first_seen", NOW), **kw)


def test_same_root_across_platforms_is_one_correlation_group():
    """A handle on eight platforms is ONE naming habit, not 28 observations."""
    o = [obs("kr4ken", p) for p in
         ("github", "telegram", "x", "forum", "gitlab", "npm", "reddit", "keybase")]
    claims = all_claims(o)
    groups = {c.correlation_group for c in claims if c.predicate is Predicate.SAME_AS}
    assert len(groups) == 1


def test_handle_reuse_alone_cannot_attribute():
    """The headline property. Eight platforms, same handle, still not a finding."""
    o = [obs("kr4ken", p) for p in
         ("github", "telegram", "x", "forum", "gitlab", "npm", "reddit", "keybase")]
    claims = [c for c in all_claims(o) if c.predicate is Predicate.SAME_AS]
    a = assess(claims, lambda i: 1, now=NOW)
    assert a.independent_groups == 1
    assert a.band in (Band.WEAK, Band.UNSUPPORTED)


def test_shared_pgp_key_plus_handle_reaches_a_finding():
    """A cryptographic binding is what turns reuse into attribution."""
    fpr = "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
    o = [
        obs("kr4ken", "github", linked={"pgp": fpr}),
        obs("kraken_x", "telegram", linked={"pgp": fpr}),
    ]
    claims = all_claims(o)
    key = Identifier(IdKind.PGP_FPR, fpr)
    binding = [c for c in claims if c.object == key]
    a = assess(binding, lambda i: 1, now=NOW)
    assert a.independent_groups == 2
    assert a.band in (Band.MODERATE_EVIDENCE, Band.STRONG_EVIDENCE)


def test_common_handle_scores_far_below_rare_one():
    corpus = HandleCorpus({"dave": 180_000, "kraken": 3})
    rare = assess(all_claims([obs("kr4ken", "github"), obs("kraken_x", "x")]),
                  corpus.holders, corpus.universe(), now=NOW)
    common = assess(all_claims([obs("dave", "github"), obs("dave_x", "x")]),
                    corpus.holders, corpus.universe(), now=NOW)
    assert rare.log_odds > common.log_odds


def test_timezone_agreement_is_corroborative_only():
    hours = Counter({h: 10 for h in range(8, 20)})
    o = [obs("kr4ken", "github", activity_hours=hours),
         obs("kraken_x", "telegram", activity_hours=hours)]
    claims = all_claims(o)
    tz = [c for c in claims if c.predicate is Predicate.TIMEZONE_HINT]
    assert tz
    a = assess(tz, lambda i: 1, now=NOW)
    assert a.independent_groups == 0
    assert a.band in (Band.WEAK, Band.UNSUPPORTED)


def test_timezone_conflict_produces_negative_evidence():
    o = [obs("kr4ken", "github", activity_hours=Counter({h: 10 for h in range(2, 14)})),
         obs("kraken_x", "telegram", activity_hours=Counter({h: 10 for h in range(14, 24)}))]
    claims = all_claims(o)
    assert any(c.predicate is Predicate.CONTRADICTS for c in claims)


def test_nonoverlapping_lifespans_contradict():
    o = [Observation("kr4ken", "forum", first_seen=NOW - timedelta(days=3000),
                     last_seen=NOW - timedelta(days=2500)),
         Observation("kraken_x", "telegram", first_seen=NOW - timedelta(days=100),
                     last_seen=NOW)]
    assert any(c.predicate is Predicate.CONTRADICTS for c in all_claims(o))


def test_generic_handles_emit_nothing():
    o = [obs("admin", "github"), obs("admin", "telegram"), obs("support", "x")]
    assert not [c for c in all_claims(o) if c.predicate is Predicate.SAME_AS]


def test_module_emits_no_claims_without_observations():
    """No discovery: given nothing, it finds nothing."""
    assert all_claims([]) == []


def test_shared_key_materializes_handle_to_handle_link():
    """Two handles binding one key must produce a direct edge, or union-find
    never merges them and the evidence is wasted."""
    from attribution_graph import Predicate as P
    fpr = "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
    o = [obs("kr4ken", "github", linked={"pgp": fpr}),
         obs("kraken_x", "telegram", linked={"pgp": fpr})]
    direct = [c for c in all_claims(o)
              if c.predicate is P.SAME_AS and c.collector == "handle_shared_identifier"]
    assert len(direct) == 1
    a = assess(direct + [c for c in all_claims(o)
                         if c.predicate is P.SAME_AS
                         and c.collector == "handle_mutation"],
               lambda i: 1, now=NOW)
    assert a.independent_groups >= 2
    assert a.band in (Band.MODERATE_EVIDENCE, Band.STRONG_EVIDENCE)


def test_unique_binding_does_not_link_by_itself():
    fpr = "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
    o = [obs("kr4ken", "github", linked={"pgp": fpr})]
    assert not [c for c in all_claims(o) if c.collector == "handle_shared_identifier"]


def test_two_to_three_points_is_capped_at_low():
    """Explicit policy: 2-3 correlation points is a lead, never a finding."""
    from handle_correlation import Confidence, correlation_points
    fpr = "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
    o = [obs("kr4ken", "github", linked={"pgp": fpr}),
         obs("kraken_x", "telegram", linked={"pgp": fpr})]
    hc = correlation_points(all_claims(o))
    assert 2 <= hc.points <= 3
    assert hc.level is Confidence.LOW
    assert "lead" in hc.caveat.lower()


def test_single_point_is_insufficient():
    from handle_correlation import Confidence, correlation_points
    o = [obs("kr4ken", p) for p in ("github", "telegram", "x", "forum", "npm")]
    hc = correlation_points(all_claims(o))
    assert hc.points == 1
    assert hc.level is Confidence.INSUFFICIENT
    assert "not a lead" in hc.caveat


def test_many_points_without_durable_identifier_capped_at_moderate():
    """Several SHARED but non-durable identifiers must not reach HIGH.

    This previously used five profiles each with a *different* name and domain,
    which the corrected point logic rightly scores as no correlation at all --
    the test was encoding the bug. It now shares the non-durable identifiers, so
    it tests the cap it was written for.
    """
    from handle_correlation import Confidence, correlation_points

    shared = {"name": "K R", "domain": "shared.example"}
    o = [obs("kr4ken", f"p{i}", linked=shared) for i in range(5)]
    hc = correlation_points(all_claims(o))
    assert not hc.has_durable_identifier
    assert hc.level in (Confidence.LOW, Confidence.MODERATE)
    assert hc.level is not Confidence.HIGH



def test_derived_claims_do_not_create_new_correlation_groups():
    """shared_identifier_claims is computed FROM the profile bindings. Giving it
    its own group counted one fact twice and inflated the model's group count."""
    fpr = "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
    o = [obs("kr4ken", "github", linked={"pgp": fpr}),
         obs("kraken_x", "telegram", linked={"pgp": fpr})]
    claims = all_claims(o)
    derived = {c.correlation_group for c in claims
               if c.collector == "handle_shared_identifier"}
    bindings = {c.correlation_group for c in claims
                if c.collector == "handle_linked_identifier"}
    assert derived <= bindings, "derived claims must reuse a source group"


# ---- EA-05: a correlation point must connect observations ------------------ #

def test_unique_non_shared_identifiers_do_not_corroborate():
    """The exact adversarial case an external audit reproduced.

    Six profiles sharing a handle, each with a DIFFERENT email, previously
    scored 7 points / HIGH / durable=True. Six unrelated addresses do not
    corroborate a shared actor: they are attributes of six separate
    observations, and if anything they weigh against a merge.
    """
    obs = [Observation(handle="kr4ken", platform=f"p{i}",
                       linked={"email": f"unrelated{i}@example.test"})
           for i in range(6)]
    hc = correlation_points(all_claims(obs))

    assert hc.points == 1, "only the shared handle root links these profiles"
    assert not hc.has_durable_identifier
    assert hc.level.value == "INSUFFICIENT"
    assert "appeared on only one profile" in hc.caveat


def test_a_shared_identifier_across_two_profiles_does_corroborate():
    """The fix must not suppress the case the module exists for."""
    fpr = "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
    hc = correlation_points(all_claims([
        obs("kr4ken", "github", linked={"pgp": fpr}),
        obs("kraken_x", "telegram", linked={"pgp": fpr}),
    ]))
    assert hc.points >= 2
    assert hc.has_durable_identifier


def test_two_shared_identifiers_count_separately():
    fpr = "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
    shared = {"pgp": fpr, "email": "same@example.test"}
    hc = correlation_points(all_claims([
        obs("kr4ken", "github", linked=shared),
        obs("kraken_x", "telegram", linked=shared),
    ]))
    assert hc.points >= 3


def test_one_profile_alone_yields_no_correlation():
    hc = correlation_points(all_claims([
        obs("kr4ken", "github", linked={"pgp": "A" * 40, "email": "a@b.test"})]))
    assert hc.points <= 1
    assert hc.level.value == "INSUFFICIENT"


def test_singletons_are_reported_not_silently_dropped():
    """An analyst must see what was excluded and why."""
    fpr = "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
    hc = correlation_points(all_claims([
        obs("kr4ken", "github", linked={"pgp": fpr, "email": "one@x.test"}),
        obs("kraken_x", "telegram", linked={"pgp": fpr, "email": "two@x.test"}),
    ]))
    assert "appeared on only one profile" in hc.caveat
    assert hc.has_durable_identifier, "the shared key still counts"
