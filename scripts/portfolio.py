"""Portfolio review from portfel.md: values in PLN, weights, P&L, exposures, concentration,
correlations and thesis flags (invalidation hit, near invalidation, target reached, overweight).

Usage:
    .venv/bin/python scripts/portfolio.py
    .venv/bin/python scripts/portfolio.py --file inny-portfel.md

Output:
    dane/portfel.json + markdown summary on stdout
"""
import argparse
import re
from datetime import date
from itertools import combinations

import pandas as pd

from common import DATA, ROOT, fetch_chart, fx_to_pln, now_utc, r, to_yahoo, write_json
from position import portfolio_params

NEAR_INVALIDATION_PCT = 3.0


def num(s):
    s = (s or "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_positions(text):
    lines = [l for l in text.splitlines() if l.strip().startswith("|")]
    header = None
    rows = []
    for l in lines:
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if header is None:
            if cells and cells[0].lower() == "ticker":
                header = [c.lower() for c in cells]
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(header, cells))
        if row.get("ticker"):
            rows.append(row)
    return rows


def parse_cash(text):
    m = re.search(r"Wolna gotówka[^:]*:\s*([\d\s.,]+)", text)
    return num(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / "portfel.md"))
    a = ap.parse_args()
    text = open(a.file).read()
    rows = parse_positions(text)
    cash = parse_cash(text) or 0.0
    params = portfolio_params()
    if not rows:
        raise SystemExit("Brak pozycji w tabeli portfela.")

    positions, closes = [], {}
    for row in rows:
        sym = row["ticker"].upper()
        ysym = to_yahoo(sym)
        df, meta, url, _ = fetch_chart(ysym, rng="1y")
        cur = meta.get("currency")
        price = float(df["close"].iloc[-1])
        closes[sym] = df["close"]
        qty = num(row.get("ilość")) or 0
        avg = num(row.get("śr. cena"))
        inval = num(row.get("invalidation"))
        targets = [num(t) for t in re.split(r"[;/]", row.get("targety") or "") if num(t)]
        fx = fx_to_pln(cur)
        value = qty * price * fx
        flags = []
        if inval and price <= inval:
            flags.append("THESIS INVALIDATED: cena ≤ invalidation")
        elif inval and (price / inval - 1) * 100 <= NEAR_INVALIDATION_PCT:
            flags.append(f"Blisko invalidation (< {NEAR_INVALIDATION_PCT}%)")
        if targets and price >= targets[0]:
            flags.append(f"Osiągnięty target 1 ({targets[0]})")
        if not inval:
            flags.append("Brak poziomu invalidation")
        review = row.get("przegląd")
        if review and re.match(r"\d{4}-\d{2}-\d{2}", review) and date.fromisoformat(review[:10]) <= date.today():
            flags.append(f"Termin przeglądu tezy minął ({review[:10]})")
        positions.append({
            "ticker": sym,
            "account": row.get("konto") or "standard",
            "qty": qty,
            "avg_price": avg,
            "price": r(price),
            "currency": cur,
            "price_date": df.index[-1].strftime("%Y-%m-%d"),
            "value_pln": r(value),
            "pnl_pct_in_instrument_ccy": r((price / avg - 1) * 100) if avg else None,
            "sector": row.get("sektor") or "?",
            "thesis": row.get("teza (1 zdanie)") or row.get("teza"),
            "invalidation": inval,
            "distance_to_invalidation_pct": r((inval / price - 1) * 100) if inval else None,
            "targets": targets,
            "flags": flags,
            "source": url,
        })

    total = sum(p["value_pln"] for p in positions) + cash
    for p in positions:
        p["weight_pct"] = r(p["value_pln"] / total * 100)
        if params["max_pos_pct"] and p["weight_pct"] > params["max_pos_pct"]:
            p["flags"].append(f"Przeważona: {p['weight_pct']}% > limit {params['max_pos_pct']}%")

    def exposure(key):
        out = {}
        for p in positions:
            out[p[key]] = out.get(p[key], 0) + p["value_pln"]
        if key == "currency":
            out["PLN (gotówka)"] = out.get("PLN (gotówka)", 0) + cash
        return {k: r(v / total * 100) for k, v in sorted(out.items(), key=lambda x: -x[1])}

    weights = [p["value_pln"] / total for p in positions]
    hhi = sum(w * w for w in weights)
    rets = pd.concat(closes, axis=1).pct_change(fill_method=None).dropna(how="all")
    pairs = []
    for x, y in combinations(rets.columns, 2):
        both = rets[[x, y]].dropna()
        if len(both) > 60:
            pairs.append({"pair": f"{x}/{y}", "corr_1y": r(both.corr().iloc[0, 1])})
    pairs.sort(key=lambda p: -(p["corr_1y"] or 0))

    rep = {
        "fetched_at": now_utc(),
        "total_pln": r(total),
        "cash_pln": r(cash),
        "cash_pct": r(cash / total * 100),
        "positions": sorted(positions, key=lambda p: -p["value_pln"]),
        "exposure_currency_pct": exposure("currency"),
        "exposure_sector_pct": exposure("sector"),
        "exposure_account_pct": exposure("account"),
        "concentration": {
            "top_position_pct": r(max(weights) * 100),
            "top3_pct": r(sum(sorted(weights, reverse=True)[:3]) * 100),
            "hhi": r(hhi, 3),
            "effective_positions": r(1 / hhi, 1) if hhi else None,
        },
        "correlations_top": pairs[:5],
        "note": "Wartości w PLN po bieżącym kursie walut z Yahoo (mid), nie po kursie XTB. Wynik % w walucie instrumentu, bez efektu walutowego i kosztów.",
    }
    write_json(DATA / "portfel.json", rep)

    print(f"Portfel: {rep['total_pln']} PLN · gotówka {rep['cash_pct']}% · efektywna liczba pozycji {rep['concentration']['effective_positions']}")
    print("| Ticker | Wartość PLN | Udział | Wynik % | Do invalidation | Flagi |\n|---|---:|---:|---:|---:|---|")
    for p in rep["positions"]:
        print(f"| {p['ticker']} | {p['value_pln']} | {p['weight_pct']}% | {p['pnl_pct_in_instrument_ccy']} | {p['distance_to_invalidation_pct']} | {'; '.join(p['flags'])} |")
    print("Waluty:", rep["exposure_currency_pct"])
    print("Sektory:", rep["exposure_sector_pct"])
    if pairs:
        print("Najwyżej skorelowane:", pairs[:3])


if __name__ == "__main__":
    main()
