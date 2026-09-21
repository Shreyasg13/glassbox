"""Correlations, clusters, cohesion and lead-lag: right on planted structure, silent on noise."""
from __future__ import annotations

import math
import random

import pytest

from app import associations as A
from tests.test_paper_tax_committee import D, N, book_with


def prices(returns, start=100.0):
    px, out = start, []
    for r in returns:
        px *= 1 + r
        out.append(px)
    return out


def noise(seed, sigma=0.01, n=N):
    rnd = random.Random(seed)
    return [rnd.gauss(0.0003, sigma) for _ in range(n)]


def make(returns_by_sym):
    return book_with({s: {i: p for i, p in enumerate(prices(r))} for s, r in returns_by_sym.items()})


def factor_market(betas_by_regime, n_syms=8, seed=1):
    """Every symbol = shared market factor x weight (changes by regime) + its own noise."""
    rnd = random.Random(seed)
    factor = [rnd.gauss(0.0004, 0.01) for _ in range(N)]
    out = {}
    for k in range(n_syms):
        idio = [rnd.gauss(0, 0.01) for _ in range(N)]
        out[f"S{k}"] = [betas_by_regime(i) * factor[i] + idio[i] for i in range(N)]
    return out


def test_pearson_matches_the_definition_and_is_safe_on_flat_series():
    assert A._pearson([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)
    assert A._pearson([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert A._pearson([1, 1, 1, 1], [1, 2, 3, 4]) == 0.0 and A._pearson([1], [1]) == 0.0


def test_planted_correlation_is_found_and_independent_names_stay_uncorrelated():
    base = noise(1)
    book = make({"A": base, "B": [r * 1.5 + x for r, x in zip(base, noise(2, 0.002))], "C": noise(3), "D": noise(4)})
    corr = A.correlations(book, D[N - 1])
    assert corr["A"]["B"] > 0.9 and abs(corr["A"]["C"]) < 0.4 and corr["A"]["A"] == 1.0
    assert corr["A"]["B"] == corr["B"]["A"]  # symmetric
    assert A.top_peers(corr, "A", 2)[0][0] == "B"


def test_clusters_group_names_that_move_as_one_bet():
    base = noise(5)
    book = make({"A": base, "B": [r + x for r, x in zip(base, noise(6, 0.002))], "C": [r + x for r, x in zip(base, noise(7, 0.002))], "D": noise(8), "E": noise(9)})
    groups = A.clusters(A.correlations(book, D[N - 1]))
    assert groups == [["A", "B", "C"]]  # D and E are alone, so they form no group


def test_correlations_never_use_the_future():
    base = noise(10)
    i = 400
    a = make({"A": base, "B": noise(11)})
    tail = [r * 0 + 0.3 for r in base[i + 1:]]  # wildly different after day i
    b = make({"A": base[: i + 1] + tail, "B": noise(11)[: i + 1] + tail})
    assert A.correlations(a, D[i]) == A.correlations(b, D[i])


def test_cohesion_flags_a_market_moving_as_one_and_one_that_has_come_apart():
    high_late = factor_market(lambda i: 3.0 if i >= N - 70 else 0.3)  # loose for a long time, then everything moves together
    c = A.cohesion(make(high_late), D[N - 1])
    assert c["label"] == "crowded" and c["percentile"] >= 80 and c["samples"] >= 8 and c["value"] >= A.CROWDED_MIN_CORR
    low_late = factor_market(lambda i: 0.3 if i >= N - 70 else 3.0)  # tightly bound for a long time, then loose
    c2 = A.cohesion(make(low_late), D[N - 1])
    assert c2["label"] == "diversifying" and c2["percentile"] <= 20
    assert A.cohesion(make(factor_market(lambda i: 1.0)), D[100])["label"] == "n/a"  # too little history to judge


def clustered_noise(seed, n=N):
    """Fat-tailed returns with volatility clustering (calm and stormy spells), like real markets."""
    rnd, out, sigma = random.Random(seed), [], 0.008
    for _ in range(n):
        if rnd.random() < 0.03:
            sigma = rnd.choice([0.004, 0.008, 0.02, 0.035])
        out.append(rnd.gauss(0.0003, sigma) * (3.0 if rnd.random() < 0.01 else 1.0))
    return out


def test_a_planted_lead_lag_is_found_and_plain_noise_is_not():
    lead = noise(20)
    follow = [0.0] + [0.6 * lead[i - 1] + x for i, x in zip(range(1, N), noise(21, 0.004))]
    syms = {"LEAD": lead, "FOLLOW": follow, **{f"N{k}": noise(30 + k) for k in range(8)}}
    scan = A.lead_lag_scan(make(syms), D[N - 1])
    assert scan["tests"] == 10 * 9 * A.MAX_LAG
    found = [(f["leader"], f["follower"], f["lag_days"]) for f in scan["findings"]]
    assert ("LEAD", "FOLLOW", 1) in found and len(found) == 1  # the planted one, and nothing spurious
    assert A.lead_lag_scan(make({f"N{k}": noise(50 + k) for k in range(12)}), D[N - 1])["tests"] == 12 * 11 * A.MAX_LAG


def test_plain_noise_flags_about_as_often_as_the_significance_level_says_it_should():
    """At a 5% level roughly 1 dataset in 20 will flag by chance: asserting 'never' from one seed would test luck, so
    measure the RATE across many independent datasets instead."""
    flagged = sum(1 for trial in range(20) if A.lead_lag_scan(make({f"N{k}": noise(5000 + 100 * trial + k) for k in range(10)}), D[N - 1])["findings"])
    assert flagged <= 3, flagged


def test_fat_tailed_volatility_clustered_noise_does_not_produce_discoveries():
    """The regression that motivated the permutation bar: a bell-curve Bonferroni threshold 'found' a
    relationship in noise like this. At a 5% level, about 1 run in 20 may flag by design; far more means the bar is broken."""
    flagged = sum(1 for trial in range(20) if A.lead_lag_scan(make({f"N{k}": clustered_noise(1000 * trial + k) for k in range(10)}), D[N - 1])["findings"])
    assert flagged <= 3, flagged


def test_the_significance_bar_is_empirical_stricter_than_the_naive_one_and_deterministic():
    book = make({f"N{k}": noise(70 + k) for k in range(6)})
    a, b = A.lead_lag_scan(book, D[N - 1]), A.lead_lag_scan(book, D[N - 1])
    assert a == b  # same data, same answer
    assert a["threshold_r"] > 2 / math.sqrt(A.LEAD_LAG_WINDOW)  # far above the naive 5% bar for one test
    assert a["method"].startswith("max-statistic")


def test_lead_lag_declines_to_speak_without_enough_history():
    scan = A.lead_lag_scan(make({"A": noise(1), "B": noise(2)}), D[40])
    assert scan["findings"] == []


def test_peer_context_names_the_peers_their_signals_and_the_group():
    base = noise(80)
    book = make({"A": base, "B": [r + x for r, x in zip(base, noise(81, 0.002))], "C": noise(82), "D": noise(83)})
    line = A.peer_context(book, "A", D[N - 1])
    assert line.startswith("Moves most with: B (correlation +") and "engine HOLD" in line
    assert "trades as one group with B" in line and "one bet" in line
    assert A.peer_context(make({"A": noise(1), "B": noise(2)}), "A", D[N - 1]) is None  # too few names to say anything
    assert A.peer_context(book, "ZZZ", D[N - 1]) is None


def test_the_daily_report_bundles_everything():
    base = noise(90)
    book = make({"A": base, "B": [r + x for r, x in zip(base, noise(91, 0.002))], "C": noise(92), "D": noise(93)})
    r = A.association_report(book, D[N - 1])
    assert r["symbols"] == 4 and r["strongest_pairs"][0]["a"] == "A" and r["strongest_pairs"][0]["b"] == "B"
    assert r["clusters"] == [["A", "B"]] and {"cohesion", "lead_lag", "weakest_pairs"} <= set(r)
    assert r["strongest_pairs"][0]["r"] >= r["weakest_pairs"][0]["r"]


def test_a_high_percentile_alone_never_means_crowded_when_the_level_is_near_zero():
    # uncorrelated noise: whatever percentile today lands on, the average correlation is ~0, so it cannot be "crowded"
    c = A.cohesion(make({f"N{k}": noise(200 + k) for k in range(8)}), D[N - 1])
    assert abs(c["value"]) < A.CROWDED_MIN_CORR and c["label"] != "crowded"


def jumpy(seed, n=N, jumps=3):
    """Ordinary noise plus a few huge single-day moves, like earnings days."""
    rnd = random.Random(seed)
    r = [rnd.gauss(0.0003, 0.008) for _ in range(n)]
    for _ in range(jumps):
        r[rnd.randrange(60, n)] += rnd.choice([-1, 1]) * rnd.uniform(0.10, 0.18)
    return r


def test_single_day_jumps_do_not_blind_the_lead_lag_scan():
    """Regression: with plain correlation, jumps that line up in shuffled data pushed the bar to ~0.8 (blind).
    By rank the bar stays near ordinary chance, so a genuine relationship is still detectable."""
    syms = {f"J{k}": jumpy(300 + k) for k in range(12)}
    scan = A.lead_lag_scan(make(syms), D[N - 1])
    assert scan["threshold_r"] < 0.4 and scan["findings"] == []
    lead = jumpy(400)
    follow = [0.0] + [0.5 * lead[i - 1] + x for i, x in zip(range(1, N), noise(401, 0.004))]
    planted = A.lead_lag_scan(make({"LEAD": lead, "FOLLOW": follow, **{f"J{k}": jumpy(410 + k) for k in range(8)}}), D[N - 1])
    assert ("LEAD", "FOLLOW", 1) in [(f["leader"], f["follower"], f["lag_days"]) for f in planted["findings"]]
