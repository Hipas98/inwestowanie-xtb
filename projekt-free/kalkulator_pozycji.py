"""Position sizing for XTB, offline (no internet, standard library only).
Built for the Claude.ai code-execution sandbox, where market data APIs are blocked.

Usage:
    python3 kalkulator_pozycji.py --price 203.7 --currency USD --fx 3.93 \
        --entries 198:40,192:30,188:30 --stop 180 --targets 207.8,216.9,234 \
        --budget 5000 --capital 20000 --risk-pct 1 [--account ike] [--fractional]

--price     current price (from xStation screenshot or a dated source)
--fx        PLN per 1 unit of instrument currency (1 for PLN instruments)
--entries   price:percent_of_position, percents sum to 100
--budget    max PLN for this position
--capital   total investable capital in PLN (enables the risk limit)
--risk-pct  max loss on this position as % of capital

Costs (XTB fee table 29.05.2026): 0% commission below 100 000 EUR monthly turnover,
0.5% FX conversion on buy and on sell for non-PLN instruments, 19% tax outside IKE/IKZE.
"""
import argparse
import math
import sys

FX_FEE = 0.005
TAX = 0.19


def parse_entries(s):
    out = [(float(p), float(w)) for p, w in (part.split(":") for part in s.split(","))]
    total = sum(w for _, w in out)
    if abs(total - 100) > 0.01:
        sys.exit(f"Udziały w --entries sumują się do {total}, a mają do 100.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--price", type=float, required=True)
    ap.add_argument("--currency", default="PLN")
    ap.add_argument("--fx", type=float, default=1.0)
    ap.add_argument("--entries", required=True)
    ap.add_argument("--stop", type=float, required=True)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--capital", type=float)
    ap.add_argument("--risk-pct", type=float, default=1.0)
    ap.add_argument("--account", choices=["standard", "ike", "ikze"], default="standard")
    ap.add_argument("--fractional", action="store_true")
    a = ap.parse_args()

    fx_fee = 0.0 if a.currency.upper() == "PLN" else FX_FEE
    tax = 0.0 if a.account in ("ike", "ikze") else TAX
    entries = parse_entries(a.entries)
    targets = [float(t) for t in a.targets.split(",")]
    if any(p <= a.stop for p, _ in entries):
        sys.exit("Stop musi być poniżej wszystkich poziomów wejścia (pozycja długa).")
    if a.currency.upper() != "PLN" and a.fx == 1.0:
        sys.exit("Instrument nie jest w PLN: podaj --fx (kurs waluty w PLN).")

    max_loss = a.capital * a.risk_pct / 100 if a.capital else None
    avg_entry = sum(p * w for p, w in entries) / 100
    loss_per_share = (avg_entry * (1 + fx_fee) - a.stop * (1 - fx_fee)) * a.fx
    n_budget = a.budget / (avg_entry * (1 + fx_fee) * a.fx)
    n_risk = max_loss / loss_per_share if max_loss else math.inf
    n_total = min(n_budget, n_risk)
    binding = "limit straty" if n_risk < n_budget else "budżet"

    def stats(alloc):
        n = sum(alloc)
        avg = sum(c * p for c, (p, _) in zip(alloc, entries)) / n if n else 0
        cost = sum(c * p for c, (p, _) in zip(alloc, entries)) * (1 + fx_fee) * a.fx
        loss = n * (avg * (1 + fx_fee) - a.stop * (1 - fx_fee)) * a.fx
        return n, avg, cost, loss

    if a.fractional:
        alloc = [round(n_total * w / 100, 4) for _, w in entries]
    else:
        total = math.floor(n_total)
        raw = [total * w / 100 for _, w in entries]
        alloc = [math.floor(x) for x in raw]
        for i in sorted(range(len(raw)), key=lambda i: raw[i] - alloc[i], reverse=True)[: total - sum(alloc)]:
            alloc[i] += 1
        while sum(alloc) and (stats(alloc)[2] > a.budget or (max_loss is not None and stats(alloc)[3] > max_loss)):
            alloc[max((i for i in range(len(alloc)) if alloc[i]), key=lambda i: entries[i][0])] -= 1

    n, avg, invested, loss = stats(alloc)
    if n == 0:
        sys.exit("Budżet lub limit straty za mały na 1 akcję. Zwiększ budżet, użyj --fractional albo mniej transz.")

    print(f"Cena teraz {a.price} {a.currency} · konto {a.account} · ogranicza: {binding}")
    print("| Transza | Cena | Plan % | Akcje | Koszt PLN |\n|---|---:|---:|---:|---:|")
    for i, ((p, w), c) in enumerate(zip(entries, alloc), 1):
        print(f"| {i} | {p} | {w:.0f}% | {c} | {c * p * (1 + fx_fee) * a.fx:.2f} |")
    print(f"\nŚrednia {avg:.2f} · zainwestowane {invested:.2f} PLN · stop {a.stop} ({(a.stop / avg - 1) * 100:.2f}%) · strata na stopie {loss:.2f} PLN"
          + (f" ({loss / a.capital * 100:.2f}% kapitału)" if a.capital else ""))
    print("\n| Target | Ruch | Zysk brutto PLN | Zysk netto PLN | R:R |\n|---|---:|---:|---:|---:|")
    first_rr = None
    for t in targets:
        gross = n * (t * (1 - fx_fee) - avg * (1 + fx_fee)) * a.fx
        net = gross * (1 - tax) if gross > 0 else gross
        rr = gross / loss if loss > 0 else float("nan")
        first_rr = rr if first_rr is None else first_rr
        print(f"| {t} | {(t / avg - 1) * 100:.2f}% | {gross:.2f} | {net:.2f} | {rr:.2f} |")
    print(f"\nZałożenia: przewalutowanie {fx_fee * 100:.1f}% w każdą stronę, podatek {tax * 100:.0f}%, prowizja 0%, wykonanie stopu po cenie stopu (luka może dać gorszą cenę).")
    if max_loss is None:
        print("UWAGA: brak --capital, wielkość tylko z budżetu, bez limitu straty.")
    if first_rr is not None and first_rr < 1.5:
        print(f"UWAGA: R:R do pierwszego targetu {first_rr:.2f} < 1.5. Słaba asymetria.")


if __name__ == "__main__":
    main()
