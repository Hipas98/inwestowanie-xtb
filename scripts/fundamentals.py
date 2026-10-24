"""Fundamentals from Yahoo fundamentals-timeseries: quarterly/annual results, growth, margins,
balance sheet, valuation computed from the current price, and historical year-end valuation.

Usage:
    .venv/bin/python scripts/fundamentals.py XTB.PL

Output:
    dane/<SYMBOL>-fund.json

Yahoo is an aggregator, not a primary source: the latest quarter must be confirmed
against the company's own report before it goes into a final report (see CLAUDE.md).
"""
import argparse
from datetime import date

from common import DATA, fetch_chart, fetch_fundamentals, fx_to_pln, now_utc, r, safe_name, to_yahoo, write_json

FLOW = ["TotalRevenue", "GrossProfit", "OperatingIncome", "EBITDA", "NetIncome",
        "OperatingCashFlow", "CapitalExpenditure", "FreeCashFlow", "DilutedEPS"]
STOCK = ["TotalDebt", "CashAndCashEquivalents", "StockholdersEquity", "OrdinarySharesNumber"]
STALE_REPORT_DAYS = 135


def series(data, prefix, item):
    return [(d, v) for d, v, _ in data.get(prefix + item, [])]


def latest(data, prefix, item):
    s = series(data, prefix, item)
    return s[-1] if s else (None, None)


def ttm(data, item):
    """Sum of the last 4 quarters if they span ~1 year, else None."""
    s = series(data, "quarterly", item)[-4:]
    if len(s) < 4:
        return None
    span = (date.fromisoformat(s[-1][0]) - date.fromisoformat(s[0][0])).days
    return sum(v for _, v in s) if 250 <= span <= 300 else None


def pct(a, b):
    return r((a / b - 1) * 100) if a is not None and b not in (None, 0) and b > 0 else None


def ratio(a, b, nd=2):
    return r(a / b, nd) if a is not None and b not in (None, 0) else None


def quarter_table(data):
    rows = {}
    for item in ("TotalRevenue", "OperatingIncome", "NetIncome", "FreeCashFlow"):
        for d, v in series(data, "quarterly", item):
            rows.setdefault(d, {})[item] = v
    out = []
    for d in sorted(rows):
        row = rows[d]
        rev = row.get("TotalRevenue")
        out.append({
            "period_end": d,
            "revenue": r(rev, 0),
            "operating_income": r(row.get("OperatingIncome"), 0),
            "net_income": r(row.get("NetIncome"), 0),
            "fcf": r(row.get("FreeCashFlow"), 0),
            "net_margin_pct": r(row["NetIncome"] / rev * 100) if rev and row.get("NetIncome") is not None else None,
        })
    return out


def yoy_last_quarter(data, item):
    s = series(data, "quarterly", item)
    if len(s) < 5:
        return None
    gap = (date.fromisoformat(s[-1][0]) - date.fromisoformat(s[-5][0])).days
    return pct(s[-1][1], s[-5][1]) if 350 <= gap <= 380 else None


def annual_history(data, prices, price_to_fin):
    """Per fiscal year: results and valuation at fiscal-year-end price."""
    out = []
    shares_s = dict(series(data, "annual", "OrdinarySharesNumber"))
    for d, rev in series(data, "annual", "TotalRevenue") or [(d, None) for d, _ in series(data, "annual", "NetIncome")]:
        ni = dict(series(data, "annual", "NetIncome")).get(d)
        ebitda = dict(series(data, "annual", "EBITDA")).get(d)
        debt = dict(series(data, "annual", "TotalDebt")).get(d)
        cash = dict(series(data, "annual", "CashAndCashEquivalents")).get(d)
        shares = shares_s.get(d)
        px = prices[prices.index <= d]
        mcap = float(px.iloc[-1]) * price_to_fin * shares if len(px) and shares else None
        ev = mcap + (debt or 0) - (cash or 0) if mcap is not None else None
        out.append({
            "fiscal_year_end": d,
            "revenue": r(rev, 0),
            "net_income": r(ni, 0),
            "net_margin_pct": r(ni / rev * 100) if rev and ni is not None else None,
            "price_at_year_end": r(px.iloc[-1]) if len(px) else None,
            "pe": ratio(mcap, ni) if ni and ni > 0 else None,
            "ps": ratio(mcap, rev),
            "ev_ebitda": ratio(ev, ebitda) if ebitda and ebitda > 0 else None,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol")
    args = ap.parse_args()
    symbol = args.symbol.upper()
    ysym = to_yahoo(symbol)

    types = [p + i for p in ("quarterly", "annual") for i in FLOW + STOCK]
    data, url = fetch_fundamentals(ysym, types)
    prices_df, meta, price_url, _ = fetch_chart(ysym, rng="5y")
    price = float(prices_df["close"].iloc[-1])
    price_cur = meta.get("currency")

    fin_cur = next((c for t in types for _, _, c in data[t] if c), None)
    warnings = []
    if not any(data[t] for t in types):
        warnings.append("Yahoo nie zwróciło żadnych danych fundamentalnych (ETF, fundusz albo brak pokrycia).")
    price_to_fin = 1.0
    if fin_cur and price_cur and fin_cur != price_cur:
        price_to_fin = fx_to_pln(price_cur) / fx_to_pln(fin_cur)
        warnings.append(f"Waluta raportów ({fin_cur}) różni się od waluty notowań ({price_cur}); kapitalizację przeliczono po bieżącym kursie.")

    last_q_date, _ = latest(data, "quarterly", "NetIncome")
    if last_q_date and (date.today() - date.fromisoformat(last_q_date)).days > STALE_REPORT_DAYS:
        warnings.append(f"Ostatni kwartał w danych kończy się {last_q_date}; możliwy nowszy raport, którego Yahoo jeszcze nie ma.")
    if not series(data, "quarterly", "EBITDA") and series(data, "quarterly", "NetIncome"):
        warnings.append("Brak EBITDA (typowe dla banków i ubezpieczycieli): oceniaj przez P/E, P/BV, ROE.")

    shares = latest(data, "quarterly", "OrdinarySharesNumber")[1] or latest(data, "annual", "OrdinarySharesNumber")[1]
    debt = latest(data, "quarterly", "TotalDebt")[1]
    cash = latest(data, "quarterly", "CashAndCashEquivalents")[1]
    equity = latest(data, "quarterly", "StockholdersEquity")[1]
    t = {k: ttm(data, k) for k in ("TotalRevenue", "EBITDA", "NetIncome", "FreeCashFlow", "OperatingCashFlow")}
    mcap = price * price_to_fin * shares if shares else None
    ev = mcap + (debt or 0) - (cash or 0) if mcap is not None else None
    net_debt = (debt or 0) - (cash or 0) if debt is not None or cash is not None else None

    sh = series(data, "quarterly", "OrdinarySharesNumber")
    dilution = pct(sh[-1][1], sh[0][1]) if len(sh) >= 2 else None

    rep = {
        "symbol": symbol,
        "yahoo_symbol": ysym,
        "source": url,
        "source_note": "Yahoo Finance (agregator). Ostatni kwartał potwierdź w raporcie spółki.",
        "price_source": price_url,
        "fetched_at": now_utc(),
        "financial_currency": fin_cur,
        "price": r(price),
        "price_currency": price_cur,
        "warnings": warnings,
        "last_quarter_end": last_q_date,
        "quarters": quarter_table(data),
        "growth": {
            "revenue_yoy_last_q_pct": yoy_last_quarter(data, "TotalRevenue"),
            "net_income_yoy_last_q_pct": yoy_last_quarter(data, "NetIncome"),
        },
        "ttm": {k: r(v, 0) for k, v in t.items()},
        "balance": {
            "total_debt": r(debt, 0),
            "cash": r(cash, 0),
            "net_debt": r(net_debt, 0),
            "equity": r(equity, 0),
            "shares": r(shares, 0),
            "net_debt_to_ebitda": ratio(net_debt, t["EBITDA"]) if t["EBITDA"] and t["EBITDA"] > 0 else None,
            "share_count_change_pct": dilution,
            "share_count_change_period": f"{sh[0][0]} → {sh[-1][0]}" if len(sh) >= 2 else None,
        },
        "valuation_now": {
            "market_cap": r(mcap, 0),
            "enterprise_value": r(ev, 0),
            "pe_ttm": ratio(mcap, t["NetIncome"]) if t["NetIncome"] and t["NetIncome"] > 0 else None,
            "ps_ttm": ratio(mcap, t["TotalRevenue"]),
            "pbv": ratio(mcap, equity) if equity and equity > 0 else None,
            "ev_ebitda_ttm": ratio(ev, t["EBITDA"]) if t["EBITDA"] and t["EBITDA"] > 0 else None,
            "fcf_yield_pct": r(t["FreeCashFlow"] / mcap * 100) if t["FreeCashFlow"] is not None and mcap else None,
            "roe_ttm_pct": r(t["NetIncome"] / equity * 100) if t["NetIncome"] is not None and equity and equity > 0 else None,
            "note": "Wycena liczona: bieżąca cena × ostatnia liczba akcji, suma 4 ostatnich kwartałów (TTM). Ujemny zysk → P/E = null.",
        },
        "annual_history": annual_history(data, prices_df["close"], price_to_fin),
    }
    if t["NetIncome"] is None:
        warnings.append("Brak 4 kolejnych kwartałów: wskaźniki TTM niedostępne, użyj danych rocznych.")

    out = DATA / f"{safe_name(symbol)}-fund.json"
    write_json(out, rep)
    print(f"OK: dane/{out.name}")
    for w in warnings:
        print("UWAGA:", w)


if __name__ == "__main__":
    main()
