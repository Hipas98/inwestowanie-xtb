"""Position sizing with XTB costs and Polish tax. All trade arithmetic lives here, never in the LLM.

Usage:
    .venv/bin/python scripts/position.py TTWO.US --entries 200:40,192:30,185:30 --stop 178 --targets 216,234,260
    .venv/bin/python scripts/position.py XTB.PL --entries 132:100 --stop 124 --targets 142,156 --budget 3000 --account ike

--entries   price:percent_of_position, comma separated (percents sum to 100)
--stop      invalidation price (whole position exits there)
--targets   target prices
--budget    max PLN for this position (default: capital × max position % from portfel.md)
--risk-pct  max loss on this position as % of capital (default: from portfel.md)
--account   standard | ike | ikze  (ike/ikze: no 19% tax on exit)
--fractional  allow fractional shares (XTB "prawa ułamkowe", only some instruments)

Costs modelled (XTB tabela opłat z 29.05.2026):
    commission 0% up to 100 000 EUR monthly turnover (above: 0.2%, min 10 EUR -> not modelled, warning only)
    FX conversion 0.5% on buy and on sell when instrument currency != PLN account
    19% Belka tax on profit for standard account
"""
import argparse
import json
import math
import re
import sys

from common import DATA, ROOT, fx_to_pln, last_price, r, safe_name, to_yahoo, write_json

FX_FEE = 0.005
TAX = 0.19


def portfolio_params():
    text = (ROOT / "portfel.md").read_text() if (ROOT / "portfel.md").exists() else ""

    def num(label):
        m = re.search(rf"{label}[^:]*:\s*([\d\s.,]+)", text)
        if not m:
            return None
        raw = m.group(1).replace(" ", "").replace(",", ".").strip(".")
        try:
            return float(raw)
        except ValueError:
            return None

    return {
        "capital": num("Kapitał na inwestycje"),
        "risk_pct": num("Max ryzyko na jedną pozycję"),
        "max_pos_pct": num("Max udział jednej pozycji"),
    }


def parse_entries(s):
    out = []
    for part in s.split(","):
        price, w = part.split(":")
        out.append((float(price), float(w)))
    total = sum(w for _, w in out)
    if abs(total - 100) > 0.01:
        sys.exit(f"Udziały w --entries sumują się do {total}, a mają do 100.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol")
    ap.add_argument("--entries", required=True)
    ap.add_argument("--stop", type=float, required=True)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--budget", type=float)
    ap.add_argument("--risk-pct", type=float)
    ap.add_argument("--account", choices=["standard", "ike", "ikze"], default="standard")
    ap.add_argument("--fractional", action="store_true")
    a = ap.parse_args()

    symbol = a.symbol.upper()
    ysym = to_yahoo(symbol)
    price, cur, price_date, _ = last_price(ysym)
    fx = fx_to_pln(cur)
    fx_fee = FX_FEE if cur != "PLN" else 0.0
    tax = 0.0 if a.account in ("ike", "ikze") else TAX
    entries = parse_entries(a.entries)
    targets = [float(t) for t in a.targets.split(",")]
    params = portfolio_params()
    warnings = []

    if any(p <= a.stop for p, _ in entries):
        sys.exit("Stop musi być poniżej wszystkich poziomów wejścia (pozycja długa).")

    capital = params["capital"]
    risk_pct = a.risk_pct if a.risk_pct is not None else params["risk_pct"]
    budget = a.budget
    if budget is None and capital and params["max_pos_pct"]:
        budget = capital * params["max_pos_pct"] / 100
    if budget is None:
        sys.exit("Brak budżetu: podaj --budget albo uzupełnij kapitał i max udział w portfel.md.")
    max_loss = capital * risk_pct / 100 if capital and risk_pct else None
    if max_loss is None:
        warnings.append("Brak kapitału lub max ryzyka w portfel.md: wielkość liczona tylko z budżetu, bez limitu straty.")

    avg_entry = sum(p * w for p, w in entries) / 100
    # PLN loss per 1 share bought at avg entry and sold at stop, incl. FX fees both ways
    loss_per_share = (avg_entry * (1 + fx_fee) - a.stop * (1 - fx_fee)) * fx
    cost_per_share = avg_entry * (1 + fx_fee) * fx
    n_budget = budget / cost_per_share
    n_risk = max_loss / loss_per_share if max_loss else math.inf
    n_total = min(n_budget, n_risk)
    binding = "limit straty (risk %)" if n_risk < n_budget else "budżet pozycji"

    if a.fractional:
        alloc = [round(n_total * w / 100, 4) for _, w in entries]
    else:
        # Largest-remainder split of the integer share count, then trim until budget and risk limits hold.
        total = math.floor(n_total)
        raw = [total * w / 100 for _, w in entries]
        alloc = [math.floor(x) for x in raw]
        for i in sorted(range(len(raw)), key=lambda i: raw[i] - alloc[i], reverse=True)[: total - sum(alloc)]:
            alloc[i] += 1

        def over(al):
            n = sum(al)
            if n == 0:
                return False
            avg = sum(c * p for c, (p, _) in zip(al, entries)) / n
            cost = sum(c * p for c, (p, _) in zip(al, entries)) * (1 + fx_fee) * fx
            loss = n * (avg * (1 + fx_fee) - a.stop * (1 - fx_fee)) * fx
            return cost > budget or (max_loss is not None and loss > max_loss)

        while over(alloc):
            alloc[max((i for i in range(len(alloc)) if alloc[i]), key=lambda i: entries[i][0])] -= 1

    tranches = [
        {"price": p, "pct": w, "shares": n, "cost_pln": r(n * p * (1 + fx_fee) * fx)}
        for (p, w), n in zip(entries, alloc)
    ]
    shares = sum(t["shares"] for t in tranches)
    if shares == 0:
        sys.exit("Budżet/limit ryzyka za mały na choćby 1 akcję w każdej transzy. Zwiększ budżet, użyj --fractional albo mniej transz.")
    if any(t["shares"] == 0 for t in tranches):
        warnings.append("Część transz ma 0 akcji (zaokrąglenie w dół). Rozważ mniej transz albo --fractional.")
    real_avg = sum(t["shares"] * t["price"] for t in tranches) / shares
    invested = sum(t["cost_pln"] for t in tranches)
    loss_at_stop = shares * (real_avg * (1 + fx_fee) - a.stop * (1 - fx_fee)) * fx

    tgt = []
    for t in targets:
        gross = shares * (t * (1 - fx_fee) - real_avg * (1 + fx_fee)) * fx
        net = gross * (1 - tax) if gross > 0 else gross
        tgt.append({
            "price": t,
            "move_from_avg_pct": r((t / real_avg - 1) * 100),
            "profit_pln_before_tax": r(gross),
            "profit_pln_after_tax": r(net),
            "rr": r(gross / loss_at_stop) if loss_at_stop > 0 else None,
        })
    if tgt and tgt[0]["rr"] is not None and tgt[0]["rr"] < 1.5:
        warnings.append(f"R:R do pierwszego targetu = {tgt[0]['rr']} (< 1.5). Słaba asymetria.")
    if a.stop < real_avg * 0.75:
        warnings.append("Stop ponad 25% pod średnią ceną wejścia: to bardziej zakład długoterminowy niż setup.")
    if invested / 4.5 > 100_000:  # rough PLN->EUR
        warnings.append("Obrót może przekroczyć 100 000 EUR/mies.: od nadwyżki XTB pobiera 0,2% (min 10 EUR).")

    rep = {
        "symbol": symbol,
        "price_now": r(price),
        "price_date": price_date,
        "currency": cur,
        "fx_to_pln": r(fx, 4),
        "account": a.account,
        "assumptions": {
            "fx_fee_each_way": fx_fee,
            "tax_on_profit": tax,
            "commission": "0% (obrót < 100 000 EUR/mies.)",
            "stop_execution": "zakładane po cenie stopu; w praktyce luka cenowa może dać gorszą cenę",
        },
        "inputs": {"budget_pln": r(budget), "capital_pln": capital, "risk_pct": risk_pct, "max_loss_pln": r(max_loss)},
        "binding_constraint": binding,
        "tranches": tranches,
        "total_shares": shares,
        "avg_entry": r(real_avg),
        "invested_pln": r(invested),
        "stop": a.stop,
        "stop_distance_pct": r((a.stop / real_avg - 1) * 100),
        "loss_at_stop_pln": r(loss_at_stop),
        "loss_at_stop_pct_of_capital": r(loss_at_stop / capital * 100) if capital else None,
        "targets": tgt,
        "warnings": warnings,
    }
    write_json(DATA / f"{safe_name(symbol)}-position.json", rep)

    print(f"{symbol} · cena {rep['price_now']} {cur} ({price_date}) · konto {a.account} · ogranicza: {binding}")
    print("| Transza | Cena | % | Akcje | Koszt PLN |\n|---|---:|---:|---:|---:|")
    for i, t in enumerate(tranches, 1):
        print(f"| {i} | {t['price']} | {t['pct']:.0f}% | {t['shares']} | {t['cost_pln']} |")
    print(f"Średnia {rep['avg_entry']} · zainwestowane {rep['invested_pln']} PLN · stop {a.stop} ({rep['stop_distance_pct']}%) · strata na stopie {rep['loss_at_stop_pln']} PLN")
    print("| Target | Ruch | Zysk brutto PLN | Zysk netto PLN | R:R |\n|---|---:|---:|---:|---:|")
    for t in tgt:
        print(f"| {t['price']} | {t['move_from_avg_pct']}% | {t['profit_pln_before_tax']} | {t['profit_pln_after_tax']} | {t['rr']} |")
    for w in warnings:
        print("UWAGA:", w)


if __name__ == "__main__":
    main()
