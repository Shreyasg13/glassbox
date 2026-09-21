# The arena: competing with TradingAgents (and anything else) on evidence

**Goal.** Keep GlassBox honestly ahead of research frameworks such as
[TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache-2.0). Nobody can promise to *stay* ahead of a project that is
free to copy from -- and it can copy from us. What can be kept is a fair, public, always-running yardstick, so that if a challenger is
better we find out first and adopt the idea, and if we are better we can prove it.

## How it works
1. A challenger's daily BUY / SELL / HOLD calls are recorded (`python -m app.scripts.record_challenger`, see below).
2. The next paper cycle creates the account **Challenger: <name>** (`external_tilt`). It trades exactly on those calls, on the same
   15 symbols, same costs, same rules as "Engine on all symbols". A stock it made no fresh call on (calls stay fresh 5 trading days)
   is **neutral**, never quietly backed by our engine.
3. Admin -> Strategy -> Research judges it with the same **live evidence gate** as our own strategies: >= 60 live trading days and a
   bootstrap confidence interval of its daily excess return over equal-weight hold (and over the placebo) above zero, corrected for the
   number of strategies compared. Until then the verdict is "insufficient" -- for everyone, us included.
4. Challengers are stored apart from our committee's decisions (they can never contaminate our scorecards) and are never shown to users.

## Recording calls
```
python -m app.scripts.record_challenger --source tradingagents --date 2026-09-21 --symbol NVDA --decision BUY
python -m app.scripts.record_challenger --source tradingagents --date 2026-09-21 --file today.json   # {"NVDA":"BUY","AAPL":"HOLD"}
python -m app.scripts.record_challenger --list
```
Other vocabularies are mapped (Overweight/Strong Buy -> BUY, Underweight/Reduce -> SELL, Neutral -> HOLD); an unreadable answer is skipped
and reported, never guessed. A call can only be recorded for a date that has already happened.

## Wiring TradingAgents in (illustrative -- not run here; check their README for the current API)
TradingAgents is a Python framework that needs its own LLM keys and makes ~11 model calls and 20+ tool calls per decision (their paper).
For 15 symbols a day that is ~165 model calls: use a paid API key, not a free tier. Run it OUTSIDE the GlassBox containers (it has its own
heavy dependencies), on a schedule after the 22:00 data sync, and feed the results in:

```python
# tradingagents_daily.py -- run after the market close, e.g. 22:30 UTC, from a separate virtualenv
import json, sys
from tradingagents.graph.trading_graph import TradingAgentsGraph      # per their README
from tradingagents.default_config import DEFAULT_CONFIG               # per their README

DATE = sys.argv[1]                                                     # e.g. 2026-09-21
SYMBOLS = ["AAPL","AMZN","GLD","GOOGL","IWM","JNJ","JPM","META","MSFT","NVDA","QQQ","SPY","TLT","TSLA","V"]
ta = TradingAgentsGraph(debug=False, config=DEFAULT_CONFIG.copy())
calls = {}
for s in SYMBOLS:
    _state, decision = ta.propagate(s, DATE)                           # returns their final decision text
    calls[s] = decision
json.dump(calls, open("today.json", "w"))
# then, on the GlassBox VM:  record_challenger --source tradingagents --date DATE --file today.json
```
Fairness checks before trusting a comparison: give it the SAME data cut-off as ours (decisions at the close of DATE, applied at the next
close, exactly as our accounts do), run it every trading day without cherry-picking, and never backfill past dates with a model whose
training data may already contain them (that is look-ahead through the model).

## Staying ahead: what we actually do
- **Adopt what works, measured.** Every idea from a challenger (debate, reflection memory, news inputs) enters as a shadow variant and
  must clear the same gate before it drives anything.
- **Information breadth, free and commercially safe.** SEC fundamentals and 8-K events, Treasury and BLS macro (docs/PROJECT_STATUS.md).
- **Integrity they do not have.** Point-in-time data, data-gap detection, a placebo, costs, wash-sale and tax, and a scoreboard that
  reports "insufficient" instead of a flattering 3-month Sharpe.
- **The product around the agents.** Stance, track record, tax-aware views, sheltered vs taxable, conversion features.
- **Where they are ahead today:** multi-round bull/bear debate, reflection memory, news/sentiment breadth, more model providers. The
  arena exists so we notice if any of that turns out to matter.
