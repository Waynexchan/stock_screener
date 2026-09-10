# Risk Model

For a long position:

```text
initial_risk_dollars = max(0, entry_price - initial_stop) * shares
initial_risk_r = initial_risk_dollars / standard_r_dollars_at_entry
unrealised_pnl_dollars = (current_price - entry_price) * shares
unrealised_pnl_r = unrealised_pnl_dollars / standard_r_dollars_at_entry
pnl_at_stop_dollars = (current_stop - entry_price) * shares
pnl_at_stop_r = pnl_at_stop_dollars / standard_r_dollars_at_entry
current_open_risk_dollars = max(0, current_price - current_stop) * shares
current_open_risk_r = current_open_risk_dollars / standard_r_dollars_at_entry
effective_open_risk_r = max(current_open_risk_r, overnight_gap_risk_floor_r)
portfolio_heat_r = sum(effective_open_risk_r)
remaining_heat_r = max(0, maximum_heat_r - portfolio_heat_r)
```

Example: entry 100, initial stop 95, current price 110, active stop 105, 100 shares, and standard R of $500 gives Initial Risk $500/1R, unrealised P&L $1,000/2R, P&L at Stop $500/1R, and Current Open Risk $500/1R.

Initial Risk is fixed trade risk for realised R and expectancy. Current Open Risk is the market value that can be given back to the active stop. P&L at Stop is the expected final P&L at an exact stop fill; it can be positive while Current Open Risk remains positive. A take-profit plan does not reduce open risk.

Effective risk applies the configurable overnight gap floor because stops cannot guarantee their price through overnight gaps. Portfolio, industry, sector, and theme heat are sums of Effective Open Risk. Default market heat is Strong 3R, Constructive 2R, Neutral 1R, Caution 0.5R, and Risk Off 0R. Actual gap losses may exceed stop-based estimates.

Drawdown is `(high-water mark equity - current equity) / 587`. NORMAL is below
2R; REDUCED begins at 2R; DEFENSIVE at 4R; STOP_NEW_RISK at 6R. Effective
Maximum Heat is the minimum of the market heat limit, drawdown heat limit, and
any explicit portfolio override. NORMAL drawdown mode uses a 3R drawdown heat
ceiling, so the report never exposes an artificial sentinel value. A separate
hard cap allows at most four unique open positions. FULL budgets 1R/$587; HALF
budgets 0.5R/$293.50; WATCH and NO TRADE always budget 0R and zero shares.

## Position-file inputs

The daily file requires ticker, entry date, entry price, initial stop, current
stop, shares, and status. Current price, sector, industry, and snapshot time are
derived from validated daily market data. Theme and setup type are optional; an
unspecified theme is conservatively grouped with its industry. Missing derived
data invalidates the portfolio calculation and never becomes zero risk.
