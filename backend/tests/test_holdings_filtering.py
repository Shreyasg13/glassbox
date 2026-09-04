"""get_holdings(tickers=...) correctness -- added so /api/holdings can
personalize to an authenticated user's own watchlist (routers/data.py)
while staying the full shared universe for anonymous/demo requests and
any account with no watchlist set. No real trading-storage parquet data
exists in this test environment, which is fine: _load_parquet_row
returns None when a file is absent and get_holdings falls back to
zeroed price fields -- these tests are about the filtering/weight math,
not the price data itself.
"""
from __future__ import annotations

import pytest

from app import data_source as ds


def test_no_tickers_returns_full_universe():
    result = ds.get_holdings()
    assert len(result["holdings"]) == len(ds.STOCK_INFO)


def test_tickers_filters_to_subset():
    result = ds.get_holdings(tickers=["AAPL", "MSFT", "NVDA"])
    symbols = {h["symbol"] for h in result["holdings"]}
    assert symbols == {"AAPL", "MSFT", "NVDA"}
    assert result["summary"]["total_symbols"] == 3


def test_tickers_case_insensitive():
    result = ds.get_holdings(tickers=["aapl", "msft"])
    symbols = {h["symbol"] for h in result["holdings"]}
    assert symbols == {"AAPL", "MSFT"}


def test_weights_renormalize_to_subset_not_global_split():
    """A 3-symbol personal watchlist should show each holding at ~33%,
    not the global 15-symbol split (~6.7%) -- weights must be relative
    to what's actually being shown, not a leftover global constant."""
    result = ds.get_holdings(tickers=["AAPL", "MSFT", "NVDA"])
    for h in result["holdings"]:
        assert h["weight"] == pytest.approx(100 / 3)
    assert sum(h["weight"] for h in result["holdings"]) == pytest.approx(100)


def test_unknown_tickers_ignored_not_crashed():
    result = ds.get_holdings(tickers=["AAPL", "NOTASYMBOL"])
    symbols = {h["symbol"] for h in result["holdings"]}
    assert symbols == {"AAPL"}


def test_all_unknown_tickers_returns_empty_not_crash():
    """Regression test: an empty filtered universe must not raise
    ZeroDivisionError computing avg_win_rate."""
    result = ds.get_holdings(tickers=["NOTASYMBOL", "ALSOFAKE"])
    assert result["holdings"] == []
    assert result["summary"]["total_symbols"] == 0
    assert result["summary"]["avg_win_rate"] == 0.0


def test_empty_tickers_list_treated_as_no_filter():
    """An empty list is falsy -- same as tickers=None, since a user with
    no watchlist configured (every real signup today) has tickers
    absent entirely, not an empty list, but both should behave the same
    (full universe) rather than the empty-list case being confused with
    'filter to nothing'."""
    result = ds.get_holdings(tickers=[])
    assert len(result["holdings"]) == len(ds.STOCK_INFO)
