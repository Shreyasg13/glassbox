"""The labelled matrix store: the same numbers as the dict-based code, on one aligned grid."""
from __future__ import annotations

import numpy as np
import pytest

from app import associations as A
from app import panel as P
from tests.test_associations import make, noise
from tests.test_paper_tax_committee import D, N, book_with


@pytest.fixture()
def pan():
    base = noise(1)
    book = make({"A": base, "B": [r * 1.5 + x for r, x in zip(base, noise(2, 0.002))], "C": noise(3), "D": noise(4)})
    return book, P.from_book(book)


def test_shape_labels_and_cache(pan):
    book, p = pan
    assert p.dates == book.dates and p.symbols == ["A", "B", "C", "D"]
    for name in P.FIELDS_MARKET:
        assert p.fields[name].shape == (N, 4)
    assert P.from_book(book) is p  # one build per book


def test_close_and_return_match_the_book(pan):
    book, p = pan
    d = D[300]
    assert p.at("close", d)["A"] == pytest.approx(book.close["A"][d])
    prev = book.close["A"][D[299]]
    assert p.at("ret", d)["A"] == pytest.approx(book.close["A"][d] / prev - 1)
    assert np.isnan(p.fields["ret"][0]).all()  # no return on the first day


def test_correlation_matrix_equals_the_dict_implementation(pan):
    book, p = pan
    end = D[N - 1]
    old = A.correlations(book, end, 60)
    C = p.corr(end, 60)
    for a in p.symbols:
        for b in p.symbols:
            assert C[p.col(a), p.col(b)] == pytest.approx(old[a][b], abs=1e-9)
    assert np.allclose(C, C.T) and np.allclose(np.diag(C), 1.0)


def test_path_and_cross_section_retrieval(pan):
    _, p = pan
    ds, vals = p.path("close", "C", D[10], D[20])
    assert ds == D[10:21] and len(vals) == 11
    assert p.at("close", D[20])["C"] == vals[-1]
    # a non-trading date maps to the bar before it
    assert p.row_le("2000-01-01") is None and p.row(D[5]) == 5 and p.row("1999-01-01") is None
    sub = p.slice_dates(D[100], D[199])
    assert len(sub.dates) == 100 and sub.fields["close"].shape == (100, 4)


def test_window_edge_cases(pan):
    _, p = pan
    assert p.window("ret", D[0], 60).shape == (1, 4)  # first row only, not an off-by-one wrap-around
    assert p.window("ret", "1999-01-01", 60).shape == (0, 4)
    assert p.window("ret", D[N - 1], 60).shape == (60, 4)


def test_a_data_hole_is_unknown_not_a_return():
    d_idx = list(range(N))
    book = book_with({"A": {i: 100.0 + 0.1 * i for i in d_idx}})
    # remove 8 months of bars from the middle: the step across the hole must not become one enormous daily return
    cut = set(range(200, 400))
    book.close["A"] = {d: v for d, v in book.close["A"].items() if D.index(d) not in cut}
    book._sorted_dates["A"] = sorted(book.close["A"])
    book.dates = sorted(book.close["A"])
    p = P.from_book(book)
    after = p.row(D[400])
    assert np.isnan(p.fields["ret"][after, 0])
    assert np.nanmax(np.abs(p.fields["ret"][:, 0])) < 0.01


def test_a_missing_bar_for_one_symbol_is_nan_that_day_and_multi_day_after():
    book = make({"A": noise(1), "B": noise(2)})
    gone = D[300]
    book.close["B"].pop(gone)
    book._sorted_dates["B"] = sorted(book.close["B"])
    p = P.from_book(book)
    i = p.row(gone)
    assert np.isnan(p.fields["ret"][i, p.col("B")]) and not np.isnan(p.fields["ret"][i, p.col("A")])
    assert p.fields["ret"][i + 1, p.col("B")] == pytest.approx(book.close["B"][D[301]] / book.close["B"][D[299]] - 1)


def test_portfolio_path_earns_the_NEXT_days_return_no_lookahead(pan):
    _, p = pan
    W = np.zeros((N, 4))
    W[:, p.col("A")] = 1.0
    out = p.portfolio_path(W, cost_bps=0.0)
    R = np.nan_to_num(p.fields["ret"][:, p.col("A")])
    assert out["ret"][0] == 0.0  # nothing was held before the first decision
    assert out["ret"][5] == pytest.approx(R[5])  # held since row 4, earns row 5's return
    assert out["equity"][-1] == pytest.approx(np.prod(1 + np.r_[0.0, R[1:]]))
    # peeking: a strategy holding the sign of TODAY's return (unknowable at the close before) must not be possible;
    # here, weights = sign(next day's return) is impossible to build causally, so we check the shift instead
    peek = np.zeros((N, 4))
    peek[:-1, p.col("A")] = np.sign(R[1:])
    cheat = p.portfolio_path(peek, cost_bps=0.0)
    assert cheat["total_return"] > 5  # the shift is real: knowing tomorrow is enormously profitable, and is only possible by cheating
    honest = np.zeros((N, 4))
    honest[1:, p.col("A")] = np.sign(R[:-1])  # yesterday's sign, known at yesterday's close ... applied one row late
    assert p.portfolio_path(honest, cost_bps=0.0)["total_return"] < cheat["total_return"]


def test_costs_reduce_the_result_and_scale_with_turnover(pan):
    _, p = pan
    rnd = np.random.default_rng(0)
    W = rnd.random((N, 4)) / 4
    free = p.portfolio_path(W, cost_bps=0.0)
    paid = p.portfolio_path(W, cost_bps=25.0)
    hold = np.full((N, 4), 0.25)
    assert paid["total_return"] < free["total_return"]
    assert p.portfolio_path(hold, 25.0)["turnover"].sum() == pytest.approx(1.0)  # bought once
    assert paid["turnover"].sum() > 50


def test_weights_validation(pan):
    _, p = pan
    with pytest.raises(ValueError):
        p.portfolio_path(np.zeros((N - 1, 4)))
    bad = np.zeros((N, 4))
    bad[3, 1] = np.nan
    with pytest.raises(ValueError):
        p.portfolio_path(bad)
    by_name = p.portfolio_path({"A": np.ones(N)}, cost_bps=0.0)
    assert by_name["equity"].shape == (N,)


def test_inference_fields_and_agent_cube(pan):
    _, p = pan
    runs = [
        {"date": D[300], "symbol": "A", "action": "BUY", "decision": "BUY", "quorum_ok": True, "answered": 9, "ceo": {"consensus": 0.8},
         "agents": [{"agent": "x", "ok": True, "lean": "BUY"}, {"agent": "y", "ok": True, "lean": "SELL"}, {"agent": "z", "ok": False}]},
        {"date": D[300], "symbol": "B", "action": None, "decision": "SELL", "quorum_ok": False, "answered": 3, "agents": []},
        {"date": "1999-01-04", "symbol": "A", "action": "BUY", "agents": []},  # not on the calendar: ignored
        {"date": D[301], "symbol": "ZZZ", "action": "BUY", "agents": []},  # not in the panel: ignored
    ]
    q = p.with_inference(runs)
    i = q.row(D[300])
    assert q.fields["committee_code"][i, q.col("A")] == 1.0
    assert np.isnan(q.fields["committee_code"][i, q.col("B")])  # low quorum carries no action
    assert q.fields["committee_consensus"][i, q.col("A")] == 0.8
    assert q.agents == ["x", "y", "z"] and q.agent_lean.shape == (N, 4, 3)
    assert q.agent_lean[i, q.col("A"), 0] == 1.0 and q.agent_lean[i, q.col("A"), 1] == -1.0 and np.isnan(q.agent_lean[i, q.col("A"), 2])
    assert q.slice_dates(D[300], D[300]).agent_lean.shape == (1, 4, 3)
    # the base panel is untouched
    assert "committee_code" not in p.fields


def test_payload_is_json_ready(pan):
    import json

    _, p = pan
    out = p.to_payload(["close", "ret"], symbols=["B", "A"], days=5)
    assert out["symbols"] == ["B", "A"] and len(out["dates"]) == 5 and len(out["fields"]["close"]) == 5
    json.dumps(out)  # no NaN leaks through
    with pytest.raises(KeyError):
        p.to_payload(["nope"])
