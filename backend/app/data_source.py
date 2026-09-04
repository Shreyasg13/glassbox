"""Data access layer wrapping the existing engine's output files.

This is a straight port of the file-reading logic in
backend-source/dashboard/DASHBOARD_PRO.py. It does not reimplement any
trading/agent math -- it reads the same JSON/parquet artifacts the
legacy Flask dashboard read, from configurable locations so this
service is not tied to the original machine's D: drive layout.

Env vars:
  BACKEND_SOURCE_PATH  -- path to the cloned multi-agent-trading-system
                          repo (for reports/*.json). Default: ../backend-source
  TRADING_STORAGE_PATH -- path to the live data store the legacy code
                          hardcoded as D:/TradingStorage. Default: D:/TradingStorage
                          When absent, endpoints fall back to the same
                          generated/defaulted values DASHBOARD_PRO.py used.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

BACKEND_SOURCE_PATH = Path(os.environ.get("BACKEND_SOURCE_PATH", "../backend-source")).resolve()
TRADING_STORAGE_PATH = Path(os.environ.get("TRADING_STORAGE_PATH", "D:/TradingStorage"))
REPORTS_DIR = BACKEND_SOURCE_PATH / "reports"

STOCK_INFO: Dict[str, Dict[str, Any]] = {
    "SPY": {"name": "S&P 500 ETF", "sector": "ETF", "beta": 1.00},
    "QQQ": {"name": "Nasdaq 100 ETF", "sector": "ETF", "beta": 1.15},
    "IWM": {"name": "Russell 2000 ETF", "sector": "ETF", "beta": 1.20},
    "TLT": {"name": "20+ Year Treasury", "sector": "Bonds", "beta": -0.15},
    "GLD": {"name": "Gold ETF", "sector": "Commodities", "beta": 0.05},
    "AAPL": {"name": "Apple Inc.", "sector": "Technology", "beta": 1.25},
    "MSFT": {"name": "Microsoft Corp.", "sector": "Technology", "beta": 1.10},
    "GOOGL": {"name": "Alphabet Inc.", "sector": "Technology", "beta": 1.15},
    "AMZN": {"name": "Amazon.com Inc.", "sector": "Consumer", "beta": 1.30},
    "NVDA": {"name": "NVIDIA Corp.", "sector": "Technology", "beta": 1.80},
    "META": {"name": "Meta Platforms", "sector": "Technology", "beta": 1.35},
    "TSLA": {"name": "Tesla Inc.", "sector": "Consumer", "beta": 2.00},
    "JPM": {"name": "JPMorgan Chase", "sector": "Financials", "beta": 1.10},
    "JNJ": {"name": "Johnson & Johnson", "sector": "Healthcare", "beta": 0.70},
    "V": {"name": "Visa Inc.", "sector": "Financials", "beta": 0.95},
}
TARGET_WEIGHTS = {symbol: 100 / 15 for symbol in STOCK_INFO}


def live_signals_source_paths() -> List[Path]:
    """Files whose mtime should invalidate the /api/live-signals and
    /api/holdings cache entries (app/cache.py)."""
    paths = [TRADING_STORAGE_PATH / "training_results" / "trained_params.json"]
    paths += [TRADING_STORAGE_PATH / "data_parquet" / f"{s}.parquet" for s in STOCK_INFO]
    paths.append(TRADING_STORAGE_PATH / "data_parquet")  # catches a newly-added file
    return paths


def track_source_paths(track_file: str) -> List[Path]:
    return [TRADING_STORAGE_PATH / track_file, REPORTS_DIR]


def report_source_paths() -> List[Path]:
    return [REPORTS_DIR]


def load_latest_data() -> Optional[List[Dict[str, Any]]]:
    """Load the most recently modified daily_*.json report."""
    if not REPORTS_DIR.exists():
        return None
    reports = list(REPORTS_DIR.glob("daily_*.json"))
    if not reports:
        return None
    latest_report = max(reports, key=lambda p: p.stat().st_mtime)
    with open(latest_report, "r") as f:
        return json.load(f)


def get_track1_data() -> List[Dict[str, Any]]:
    track1_file = TRADING_STORAGE_PATH / "track1_performance.json"
    if track1_file.exists():
        with open(track1_file, "r") as f:
            return json.load(f)

    data = load_latest_data()
    if data is None:
        data = []
        portfolio_value = 10000.0
        for i in range(30):
            date = (datetime.now() - timedelta(days=30 - i)).strftime("%Y-%m-%d")
            daily_return = float(np.random.normal(0.003, 0.015))
            portfolio_value *= 1 + daily_return
            data.append(
                {
                    "date": date,
                    "portfolio_value": portfolio_value,
                    "daily_return": daily_return,
                    "agents_active": 3,
                    "vn_score": 0.85,
                    "track": "track1",
                }
            )
    else:
        data = [dict(d, agents_active=3, vn_score=0.85, track="track1") for d in data]
    return data


def get_track2_data() -> List[Dict[str, Any]]:
    track2_file = TRADING_STORAGE_PATH / "track2_performance.json"
    if track2_file.exists():
        with open(track2_file, "r") as f:
            return json.load(f)

    data = load_latest_data()
    if data is None:
        data = []
        portfolio_value = 100000.0
        for i in range(30):
            date = (datetime.now() - timedelta(days=30 - i)).strftime("%Y-%m-%d")
            daily_return = float(np.random.normal(0.004, 0.010))
            portfolio_value *= 1 + daily_return
            data.append(
                {
                    "date": date,
                    "portfolio_value": portfolio_value,
                    "daily_return": daily_return,
                    "agents_active": 7,
                    "vn_score": 0.92,
                    "track": "track2",
                }
            )
    else:
        scale_factor = 100000 / 10000
        data = [
            dict(d, portfolio_value=d["portfolio_value"] * scale_factor, agents_active=7, vn_score=0.92, track="track2")
            for d in data
        ]
    return data


TRACK1_AGENTS = [
    {"name": "Risk Manager", "score": 85, "win_rate": 71, "decisions": 52, "avg_impact": 0.8, "color": "#667eea"},
    {"name": "Quantitative Strategist", "score": 78, "win_rate": 62, "decisions": 45, "avg_impact": 1.2, "color": "#11998e"},
    {"name": "Value Investor", "score": 72, "win_rate": 58, "decisions": 38, "avg_impact": 1.5, "color": "#f5576c"},
]

TRACK2_AGENTS = [
    {"name": "Risk Manager", "score": 88, "win_rate": 75, "decisions": 62, "avg_impact": 0.7, "color": "#667eea"},
    {"name": "Quantitative Strategist", "score": 82, "win_rate": 68, "decisions": 55, "avg_impact": 1.1, "color": "#11998e"},
    {"name": "Value Investor", "score": 76, "win_rate": 63, "decisions": 48, "avg_impact": 1.3, "color": "#f5576c"},
    {"name": "Behavioral Coach", "score": 79, "win_rate": 65, "decisions": 42, "avg_impact": 0.9, "color": "#f093fb"},
    {"name": "Global Macro Specialist", "score": 84, "win_rate": 70, "decisions": 58, "avg_impact": 1.4, "color": "#4facfe"},
    {"name": "Tech Innovator", "score": 81, "win_rate": 67, "decisions": 51, "avg_impact": 1.2, "color": "#ffa726"},
    {"name": "Personal Context", "score": 74, "win_rate": 60, "decisions": 35, "avg_impact": 0.8, "color": "#66bb6a"},
]

def _load_trained_params() -> Dict[str, Any]:
    params_file = TRADING_STORAGE_PATH / "training_results" / "trained_params.json"
    if params_file.exists():
        with open(params_file, "r") as f:
            return json.load(f)
    return {}


def _load_parquet_row(symbol: str):
    """Return (df_or_none). Only imports pandas/pyarrow if a parquet file exists."""
    parquet_file = TRADING_STORAGE_PATH / "data_parquet" / f"{symbol}.parquet"
    if not parquet_file.exists():
        return None
    import pandas as pd  # local import: optional heavy dep, only needed with real data

    return pd.read_parquet(parquet_file)


def get_holdings() -> Dict[str, Any]:
    trained_params = _load_trained_params()
    holdings: List[Dict[str, Any]] = []
    total_win_rate = 0.0
    best_performer = {"symbol": "-", "return": -999.0}

    for symbol, info in STOCK_INFO.items():
        params = trained_params.get(symbol, {})
        df = _load_parquet_row(symbol)

        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            current_price = float(latest["Close"])
            prev_price = float(prev["Close"])
            price_change = ((current_price - prev_price) / prev_price) * 100
            current_rsi = float(latest.get("RSI", 50))
            volume = int(latest["Volume"])
            data_date = str(df.index[-1])
        else:
            current_price = 0.0
            prev_price = 0.0
            price_change = 0.0
            current_rsi = 50.0
            volume = 0
            data_date = "N/A"

        test_return = params.get("test_return", 0) * 100
        win_rate = params.get("test_win_rate", 0) * 100
        sharpe = params.get("test_sharpe", 0)

        if sharpe > 0.3 and win_rate > 25:
            signal = "BUY"
        elif sharpe < -0.3 or win_rate < 20:
            signal = "SELL"
        else:
            signal = "HOLD"

        holding = {
            "symbol": symbol,
            "name": info["name"],
            "sector": info["sector"],
            "weight": TARGET_WEIGHTS.get(symbol, 6.67),
            "signal": signal,
            "win_rate": round(win_rate, 1),
            "sharpe": round(sharpe, 2),
            "test_return": round(test_return, 2),
            "fast_ma": params.get("fast_ma", 20),
            "slow_ma": params.get("slow_ma", 50),
            "rsi_low": params.get("rsi_low", 30),
            "rsi_high": params.get("rsi_high", 70),
            "beta": info["beta"],
            "current_price": round(current_price, 2),
            "price_change": round(price_change, 2),
            "current_rsi": round(current_rsi, 1),
            "volume": volume,
            "data_date": data_date,
        }
        holdings.append(holding)
        total_win_rate += win_rate
        if test_return > best_performer["return"]:
            best_performer = {"symbol": symbol, "return": test_return}

    sectors: Dict[str, float] = {}
    for h in holdings:
        sectors[h["sector"]] = sectors.get(h["sector"], 0) + h["weight"]

    latest_dates = [h["data_date"] for h in holdings if h["data_date"] != "N/A"]
    data_freshness = max(latest_dates) if latest_dates else "N/A"

    return {
        "holdings": holdings,
        "summary": {
            "total_symbols": len(holdings),
            "avg_win_rate": round(total_win_rate / len(holdings), 1),
            "best_performer": best_performer["symbol"],
            "best_return": round(best_performer["return"], 2),
            "portfolio_beta": round(sum(h["beta"] * h["weight"] / 100 for h in holdings), 2),
            "data_source": f"Parquet Files ({TRADING_STORAGE_PATH / 'data_parquet'})",
            "data_date": data_freshness,
        },
        "sectors": sectors,
    }


def get_live_signals() -> Dict[str, Any]:
    trained_params = _load_trained_params()
    signals: List[Dict[str, Any]] = []
    buy_count = sell_count = hold_count = 0
    total_confidence = 0.0

    for symbol, info in STOCK_INFO.items():
        params = trained_params.get(symbol, {})
        df = _load_parquet_row(symbol)

        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            current_price = latest["Close"]
            current_rsi = latest.get("RSI", 50)
            fast_ma_col = f"MA_{params.get('fast_ma', 20)}"
            slow_ma_col = f"MA_{params.get('slow_ma', 50)}"
            ma_fast = latest.get(fast_ma_col, latest.get("MA_20", current_price))
            ma_slow = latest.get(slow_ma_col, latest.get("MA_50", current_price))
            volume = latest["Volume"]
            volume_ma = latest.get("Volume_MA", volume)
            volume_ratio = volume / volume_ma if volume_ma > 0 else 1.0
            if ma_fast > ma_slow:
                ma_cross = "BULLISH"
            elif ma_fast < ma_slow:
                ma_cross = "BEARISH"
            else:
                ma_cross = "NEUTRAL"
            data_date = str(df.index[-1])
        else:
            current_price = 100.0
            current_rsi = 50
            ma_cross = "NEUTRAL"
            volume_ratio = 1.0
            data_date = "N/A"

        test_sharpe = params.get("test_sharpe", 0)
        win_rate = params.get("test_win_rate", 0)
        rsi_low = params.get("rsi_low", 30)
        rsi_high = params.get("rsi_high", 70)

        if current_rsi < rsi_low and ma_cross == "BULLISH":
            signal = "BUY"
            confidence = min(90, 60 + (rsi_low - current_rsi))
            buy_count += 1
        elif current_rsi > rsi_high and ma_cross == "BEARISH":
            signal = "SELL"
            confidence = min(85, 50 + (current_rsi - rsi_high))
            sell_count += 1
        else:
            signal = "HOLD"
            confidence = 50
            hold_count += 1

        total_confidence += confidence

        base_weight = 100 / 15
        if signal == "BUY" and test_sharpe > 0:
            suggested_weight = base_weight * 1.5
        elif signal == "SELL":
            suggested_weight = base_weight * 0.5
        else:
            suggested_weight = base_weight

        signals.append(
            {
                "symbol": symbol,
                "name": info["name"],
                "sector": info["sector"],
                "current_price": round(float(current_price), 2),
                "signal": signal,
                "confidence": round(float(confidence), 0),
                "rsi": round(float(current_rsi), 1),
                "ma_cross": ma_cross,
                "volume_ratio": round(float(volume_ratio), 2),
                "suggested_weight": round(suggested_weight, 1),
                "fast_ma": params.get("fast_ma", 20),
                "slow_ma": params.get("slow_ma", 50),
                "test_sharpe": round(test_sharpe, 2),
                "win_rate": round(win_rate * 100, 1),
                "data_date": data_date,
            }
        )

    return {
        "signals": signals,
        "summary": {
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "hold_signals": hold_count,
            "avg_confidence": round(total_confidence / len(signals), 0) if signals else 0,
            "data_source": f"Parquet Files ({TRADING_STORAGE_PATH / 'data_parquet'})",
            "last_update": signals[0]["data_date"] if signals else "N/A",
        },
    }


def run_monte_carlo(days: int, simulations: int, confidence: float) -> Optional[Dict[str, Any]]:
    data = load_latest_data()
    if not data:
        return None

    returns = [d["daily_return"] for d in data]
    mu = float(np.mean(returns))
    sigma = float(np.std(returns))
    current_value = data[-1]["portfolio_value"]

    paths: List[List[float]] = []
    final_values: List[float] = []
    for _ in range(simulations):
        path = [current_value]
        value = current_value
        for _day in range(days):
            daily_return = np.random.normal(mu, sigma)
            value *= 1 + daily_return
            path.append(value)
        paths.append(path)
        final_values.append(value)

    final_values_arr = np.array(final_values)
    return {
        "mean": float(np.mean(final_values_arr)),
        "percentile_5": float(np.percentile(final_values_arr, 5)),
        "percentile_95": float(np.percentile(final_values_arr, 95)),
        "prob_profit": float((final_values_arr > current_value).sum() / simulations * 100),
        "paths": paths[:100],
        "final_values": final_values_arr.tolist(),
    }


def get_historical_reports() -> List[Dict[str, Any]]:
    if not REPORTS_DIR.exists():
        return []

    reports: List[Dict[str, Any]] = []
    for report_file in sorted(REPORTS_DIR.glob("daily_*.json"), reverse=True):
        try:
            with open(report_file, "r") as f:
                data = json.load(f)
            if not data:
                continue
            latest = data[-1]
            initial = 10000
            total_return = ((latest["portfolio_value"] - initial) / initial) * 100

            returns = [d["daily_return"] for d in data]
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe = (avg_return / std_return * (252**0.5)) if std_return > 0 else 0

            peak = initial
            max_dd = 0.0
            for d in data:
                if d["portfolio_value"] > peak:
                    peak = d["portfolio_value"]
                dd = (peak - d["portfolio_value"]) / peak
                if dd > max_dd:
                    max_dd = dd

            reports.append(
                {
                    "date": report_file.stem.replace("daily_", ""),
                    "file": report_file.name,
                    "final_value": latest["portfolio_value"],
                    "return": total_return,
                    "sharpe": sharpe,
                    "max_dd": max_dd * 100,
                }
            )
        except Exception:
            continue
    return reports


def get_daily_summary() -> Dict[str, Any]:
    data = load_latest_data()
    if not data:
        return {}

    latest = data[-1]
    initial = 10000
    returns = [d["daily_return"] for d in data]
    avg_return = sum(returns) / len(returns)
    std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
    sharpe = (avg_return / std_return * (252**0.5)) if std_return > 0 else 0

    peak = initial
    max_dd = 0.0
    for d in data:
        if d["portfolio_value"] > peak:
            peak = d["portfolio_value"]
        dd = (peak - d["portfolio_value"]) / peak
        if dd > max_dd:
            max_dd = dd

    wins = sum(1 for r in returns if r > 0)
    win_rate = (wins / len(returns)) * 100 if returns else 0
    risk_status = "LOW" if max_dd < 0.10 else "MEDIUM" if max_dd < 0.15 else "HIGH"

    alerts: List[str] = []
    if max_dd > 0.15:
        alerts.append("Drawdown exceeds 15% threshold")
    if sharpe < 1.0:
        alerts.append("Sharpe ratio below target (1.0)")
    if latest["positions"] > 3:
        alerts.append("High position count - monitor concentration")

    return {
        "status": "ACTIVE",
        "current_value": latest["portfolio_value"],
        "daily_change": latest["daily_return"] * 100,
        "vn_score": 8.5,
        "risk_status": risk_status,
        "sharpe": sharpe,
        "max_dd": max_dd * 100,
        "win_rate": win_rate,
        "position_util": (latest["positions"] / 5) * 100,
        "alerts": alerts,
        "dates": [d["date"] for d in data],
        "growth_rates": [d["daily_return"] * 100 for d in data],
    }
