"""Doradca XTB, offline toolkit for the Claude.ai code-execution sandbox (no market-data internet).

Commands:
  tech     price file (stooq CSV or Yahoo chart JSON) -> indicators, trend, support/resistance,
           relative strength vs benchmark file, liquidity, big moves, annotated chart PNG
  pozycja  position sizing with XTB costs and Polish tax (tranches, loss at stop, net profit, R:R)
  portfel  portfolio review from portfel.md with current prices given by the user

Examples:
  python3 doradca.py tech cdr_d.csv --ticker CDR.PL --benchmark wig20_d.csv
  python3 doradca.py pozycja --price 265 --entries 262:60,255:40 --stop 248 --targets 280,300 \
      --budget 3000 --capital 20000 --risk-pct 1 --account ike
  python3 doradca.py pozycja --price 203.7 --currency USD --fx 3.93 --entries 198:100 --stop 185 --targets 216 --budget 4000
  python3 doradca.py portfel portfel.md --ceny CDR.PL=265,TTWO.US=203.7 --fx USD=3.93

Price files on a phone: stooq.pl/q/d/l/?s=cdr&i=d (GPW), s=ttwo.us (USA), s=wig20 or s=^spx (benchmark).
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

FX_FEE = 0.005   # XTB FX conversion, each way (fee table 29.05.2026)
TAX = 0.19       # Belka, outside IKE/IKZE
PIVOT_WINDOW = 5
LOW_LIQUIDITY_PLN = 100_000

COLS = {
    "date": ["data", "date"],
    "open": ["otwarcie", "open"],
    "high": ["najwyzszy", "najwyższy", "high"],
    "low": ["najnizszy", "najniższy", "low"],
    "close": ["zamkniecie", "zamknięcie", "close"],
    "volume": ["wolumen", "volume"],
}


def rnd(x, nd=2):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None


# ---------- tech ----------

def load_prices(path):
    import pandas as pd
    p = Path(path)
    text = p.read_text(errors="ignore").lstrip()
    if text.startswith("{"):
        res = json.loads(text)["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        tz = res["meta"].get("exchangeTimezoneName", "UTC")
        idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(tz).normalize().tz_localize(None)
        df = pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close", "volume")}, index=idx)
        meta = {"source": "Yahoo Finance JSON", "currency": res["meta"].get("currency"), "name": res["meta"].get("longName")}
    else:
        if "<html" in text[:500].lower():
            sys.exit("Plik to strona HTML, nie CSV (limit stooq albo test przeglądarki). Pobierz ponownie w przeglądarce.")
        raw = pd.read_csv(p, sep=None, engine="python")
        lower = {c.lower().strip(): c for c in raw.columns}
        pick = {}
        for k, names in COLS.items():
            col = next((lower[n] for n in names if n in lower), None)
            if col is None and k != "volume":
                sys.exit(f"Brak kolumny {k} w pliku. Kolumny: {list(raw.columns)}")
            pick[k] = col
        df = pd.DataFrame({k: raw[c] if c else 0 for k, c in pick.items() if k != "date"})
        df.index = pd.to_datetime(raw[pick["date"]])
        meta = {"source": f"CSV ({p.name})", "currency": None, "name": None}
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["open", "high", "low", "close"]).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df["volume"] = df["volume"].fillna(0)
    return df, meta


def indicators(df):
    import pandas as pd
    c = df["close"]
    for n in (20, 50, 200):
        df[f"sma{n}"] = c.rolling(n).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["rsi14"] = 100 - 100 / (1 + gain / loss)
    df["macd"] = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    prev = c.shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    df["atr14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    vol = df["volume"].where(df["volume"] > 0)
    df["vol_avg20"] = vol.rolling(20, min_periods=15).mean()
    df["turnover"] = c * vol
    df["ret"] = c.pct_change()
    return df


def pivots(df, w=PIVOT_WINDOW):
    hi = df["high"] == df["high"].rolling(2 * w + 1, center=True).max()
    lo = df["low"] == df["low"].rolling(2 * w + 1, center=True).min()
    return ([(d, float(v)) for d, v in df.loc[hi, "high"].items()],
            [(d, float(v)) for d, v in df.loc[lo, "low"].items()])


def levels(highs, lows, close, tol_pct, n=3):
    """Zones capped at tol_pct width (no chaining); n nearest per side + nearest multi-touch zone."""
    clusters = []
    for d, p in sorted(highs + lows, key=lambda x: x[1]):
        if clusters and p / clusters[-1][0][1] - 1 <= tol_pct:
            clusters[-1].append((d, p))
        else:
            clusters.append([(d, p)])
    zones = [{"price": round(sum(p for _, p in cl) / len(cl), 2), "touches": len(cl),
              "last_touch": max(d for d, _ in cl).strftime("%Y-%m-%d")} for cl in clusters]
    out = {}
    for side, below in (("supports", True), ("resistances", False)):
        cand = sorted([z for z in zones if (z["price"] < close) == below and z["price"] != close],
                      key=lambda z: -z["price"] if below else z["price"])
        pick = cand[:n]
        if not any(z["touches"] >= 2 for z in pick):
            pick += [z for z in cand[n:] if z["touches"] >= 2][:1]
        for z in pick:
            z["distance_pct"] = rnd((z["price"] / close - 1) * 100)
        out[side] = pick
    return out


def ret_over(s, bars):
    return rnd((s.iloc[-1] / s.iloc[-bars - 1] - 1) * 100) if len(s) > bars else None


def cmd_tech(a):
    import pandas as pd
    df, meta = load_prices(a.file)
    if len(df) < 60:
        sys.exit(f"Za mało świec ({len(df)}). Pobierz dłuższą historię (min. 1 rok).")
    df = indicators(df)
    last, close = df.iloc[-1], float(df["close"].iloc[-1])
    atr = float(last["atr14"])
    highs, lows = pivots(df)
    y = df.iloc[-252:]
    ticker = (a.ticker or Path(a.file).stem).upper()
    currency = a.currency or meta["currency"] or ("USD" if ticker.endswith(".US") else "PLN")
    turnover_pln = float(df["turnover"].iloc[-20:].mean()) * a.fx

    warnings = []
    age = (pd.Timestamp.now().normalize() - df.index[-1]).days
    if age > 4:
        warnings.append(f"Ostatnia świeca ma {age} dni. Dane mogą być nieaktualne: porównaj cenę z xStation.")
    if (df["volume"].iloc[-20:] == 0).any():
        warnings.append("Zerowy wolumen w ostatnich 20 sesjach (brak danych o wolumenie w pliku?).")
    if currency != "PLN" and a.fx == 1.0:
        warnings.append("Instrument nie w PLN, brak --fx: obrót w PLN niepoliczony poprawnie.")
    elif turnover_pln < LOW_LIQUIDITY_PLN:
        warnings.append(f"Niska płynność: średni obrót ok. {turnover_pln:,.0f} PLN/dzień. Szerokie spready.")
    if len(df) < 200:
        warnings.append("Mniej niż 200 świec: SMA200 niedostępna.")

    struct = {}
    if len(highs) >= 2:
        struct["highs"] = "HH" if highs[-1][1] > highs[-2][1] else "LH"
    if len(lows) >= 2:
        struct["lows"] = "HL" if lows[-1][1] > lows[-2][1] else "LL"
    struct["trend"] = {("HH", "HL"): "wzrostowy", ("LH", "LL"): "spadkowy"}.get(
        (struct.get("highs"), struct.get("lows")), "mieszany/konsolidacja")

    rs = None
    if a.benchmark:
        bdf, _ = load_prices(a.benchmark)
        j = pd.concat([df["close"], bdf["close"]], axis=1, keys=["s", "b"]).dropna()
        rs = {"benchmark": Path(a.benchmark).name}
        for label, bars in (("1m", 21), ("3m", 63), ("6m", 126), ("1y", 252)):
            s, b = ret_over(j["s"], bars), ret_over(j["b"], bars)
            rs[label] = {"spolka_pct": s, "benchmark_pct": b, "roznica_pp": rnd(s - b) if s is not None and b is not None else None}

    recent = df.iloc[-60:]
    moves = [{"date": d.strftime("%Y-%m-%d"), "change_pct": rnd(df.loc[d, "ret"] * 100),
              "volume_x_avg20": rnd(df.loc[d, "volume"] / df.loc[d, "vol_avg20"]) if df.loc[d, "vol_avg20"] else None}
             for d in sorted(recent["ret"].abs().nlargest(5).index)]

    def slope(col):
        s = df[col].dropna()
        return rnd((s.iloc[-1] / s.iloc[-21] - 1) * 100) if len(s) > 21 else None

    rep = {
        "ticker": ticker, "source": meta["source"], "currency": currency,
        "last_bar": df.index[-1].strftime("%Y-%m-%d"), "bars": len(df), "warnings": warnings,
        "price": {"close": rnd(close), "change_1d_pct": rnd(last["ret"] * 100), "change_1m_pct": ret_over(df["close"], 21),
                  "change_1y_pct": ret_over(df["close"], 252), "high_52w": rnd(y["high"].max()), "low_52w": rnd(y["low"].min()),
                  "drawdown_from_52w_high_pct": rnd((close / y["high"].max() - 1) * 100)},
        "averages": {"sma20": rnd(last["sma20"]), "sma50": rnd(last["sma50"]), "sma200": rnd(last["sma200"]),
                     "sma50_slope_20d_pct": slope("sma50"), "sma200_slope_20d_pct": slope("sma200")},
        "momentum": {"rsi14": rnd(last["rsi14"], 1), "macd_hist": rnd(last["macd"] - last["macd_signal"], 3)},
        "volatility": {"atr14": rnd(atr), "atr14_pct": rnd(atr / close * 100),
                       "max_drawdown_1y_pct": rnd(((y["close"] / y["close"].cummax()) - 1).min() * 100)},
        "volume": {"ratio_to_avg20": rnd(last["volume"] / last["vol_avg20"]) if last["vol_avg20"] else None,
                   "turnover_avg20_pln": rnd(turnover_pln, 0)},
        "structure": struct,
        "last_swings": {"highs": [(d.strftime("%Y-%m-%d"), round(p, 2)) for d, p in highs[-3:]],
                        "lows": [(d.strftime("%Y-%m-%d"), round(p, 2)) for d, p in lows[-3:]]},
        "levels": levels(highs, lows, close, 0.75 * atr / close),
        "big_moves_60d": moves,
        "relative_strength": rs,
    }

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.-]", "_", ticker)
    (out / f"{safe}-tech.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2))
    chart = draw(df, rep, out / f"{safe}-{rep['last_bar']}.png")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    print(f"\nWykres: {chart}" if chart else "\nWykres: brak (matplotlib niedostępny)")


def draw(df, rep, path, bars=250):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    d = df.iloc[-bars:].reset_index()
    x = range(len(d))
    fig, (ax, axv, axr) = plt.subplots(3, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [5, 1.2, 1.5]})
    col = ["#2e9d5b" if u else "#d64545" for u in d["close"] >= d["open"]]
    ax.vlines(x, d["low"], d["high"], color=col, linewidth=0.8)
    ax.bar(x, (d["close"] - d["open"]).abs(), bottom=d[["open", "close"]].min(axis=1), color=col, width=0.7)
    for k, c in (("sma50", "#e09b2d"), ("sma200", "#4a6fd1")):
        ax.plot(x, d[k], color=c, linewidth=1.2, label=k.upper())
    for side, color, tag in (("supports", "#2e9d5b", "S"), ("resistances", "#d64545", "R")):
        for z in rep["levels"][side]:
            ax.axhline(z["price"], color=color, linestyle="--", linewidth=1)
            ax.text(len(d) + 1, z["price"], f"{tag} {z['price']} ({z['touches']}x)", va="center", fontsize=8, color=color)
    ax.set_title(f"{rep['ticker']} · ostatnia świeca {rep['last_bar']} · {rep['source']}")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.2)
    axv.bar(x, d["volume"], color=col, width=0.7)
    axv.set_ylabel("Wolumen")
    axr.plot(x, d["rsi14"], color="#7a4ad1", linewidth=1)
    for lvl in (30, 70):
        axr.axhline(lvl, color="#999", linestyle=":", linewidth=1)
    axr.set_ylim(0, 100)
    axr.set_ylabel("RSI14")
    step = max(1, len(d) // 8)
    axr.set_xticks(list(x)[::step])
    axr.set_xticklabels([t.strftime("%Y-%m") for t in d.iloc[:, 0][::step]])
    ax.set_xlim(-1, len(d) + 14)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return str(path)


# ---------- pozycja ----------

def cmd_pozycja(a):
    entries = [(float(p), float(w)) for p, w in (part.split(":") for part in a.entries.split(","))]
    if abs(sum(w for _, w in entries) - 100) > 0.01:
        sys.exit("Udziały w --entries muszą sumować się do 100.")
    if any(p <= a.stop for p, _ in entries):
        sys.exit("Stop musi być poniżej wszystkich poziomów wejścia (pozycja długa).")
    if a.currency.upper() != "PLN" and a.fx == 1.0:
        sys.exit("Instrument nie jest w PLN: podaj --fx (kurs waluty w PLN).")
    fx_fee = 0.0 if a.currency.upper() == "PLN" else FX_FEE
    tax = 0.0 if a.account in ("ike", "ikze") else TAX
    targets = [float(t) for t in a.targets.split(",")]
    max_loss = a.capital * a.risk_pct / 100 if a.capital else None

    avg0 = sum(p * w for p, w in entries) / 100
    n_budget = a.budget / (avg0 * (1 + fx_fee) * a.fx)
    n_risk = max_loss / ((avg0 * (1 + fx_fee) - a.stop * (1 - fx_fee)) * a.fx) if max_loss else math.inf
    n_total = min(n_budget, n_risk)

    def stats(al):
        n = sum(al)
        cost_ccy = sum(c * p for c, (p, _) in zip(al, entries))
        avg = cost_ccy / n if n else 0
        return n, avg, cost_ccy * (1 + fx_fee) * a.fx, n * (avg * (1 + fx_fee) - a.stop * (1 - fx_fee)) * a.fx

    if a.fractional:
        alloc = [round(n_total * w / 100, 4) for _, w in entries]
    else:
        total = math.floor(n_total)
        raw = [total * w / 100 for _, w in entries]
        alloc = [math.floor(v) for v in raw]
        for i in sorted(range(len(raw)), key=lambda i: raw[i] - alloc[i], reverse=True)[: total - sum(alloc)]:
            alloc[i] += 1
        while sum(alloc) and (stats(alloc)[2] > a.budget or (max_loss is not None and stats(alloc)[3] > max_loss)):
            alloc[max((i for i in range(len(alloc)) if alloc[i]), key=lambda i: entries[i][0])] -= 1
    n, avg, invested, loss = stats(alloc)
    if n == 0:
        sys.exit("Budżet lub limit straty za mały na 1 akcję. Zwiększ budżet, mniej transz albo --fractional.")

    print(f"Cena teraz {a.price} {a.currency} · konto {a.account} · ogranicza: {'limit straty' if n_risk < n_budget else 'budżet'}")
    print("| Transza | Cena | Plan % | Akcje | Koszt PLN |\n|---|---:|---:|---:|---:|")
    for i, ((p, w), c) in enumerate(zip(entries, alloc), 1):
        print(f"| {i} | {p} | {w:.0f}% | {c} | {c * p * (1 + fx_fee) * a.fx:.2f} |")
    print(f"\nŚrednia {avg:.2f} · zainwestowane {invested:.2f} PLN · stop {a.stop} ({(a.stop / avg - 1) * 100:.2f}%) · "
          f"strata na stopie {loss:.2f} PLN" + (f" ({loss / a.capital * 100:.2f}% kapitału)" if a.capital else ""))
    print("\n| Target | Ruch | Zysk brutto PLN | Zysk netto PLN | R:R |\n|---|---:|---:|---:|---:|")
    rrs = []
    for t in targets:
        gross = n * (t * (1 - fx_fee) - avg * (1 + fx_fee)) * a.fx
        rr = gross / loss if loss > 0 else float("nan")
        rrs.append(rr)
        print(f"| {t} | {(t / avg - 1) * 100:.2f}% | {gross:.2f} | {gross * (1 - tax) if gross > 0 else gross:.2f} | {rr:.2f} |")
    print(f"\nZałożenia: przewalutowanie {fx_fee * 100:.1f}% w każdą stronę, podatek {tax * 100:.0f}%, prowizja 0% "
          "(do 100 000 EUR obrotu/mies.), stop wykonany po cenie stopu (luka cenowa może dać gorszą).")
    if max_loss is None:
        print("UWAGA: brak --capital: wielkość tylko z budżetu, bez limitu straty.")
    if rrs and rrs[0] < 1.5:
        print(f"UWAGA: R:R do pierwszego targetu {rrs[0]:.2f} < 1.5. Słaba asymetria.")


# ---------- portfel ----------

def num(s):
    try:
        return float(str(s).replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def cmd_portfel(a):
    text = Path(a.file).read_text()
    prices = {k.strip().upper(): float(v) for k, v in (p.split("=") for p in a.ceny.split(","))} if a.ceny else {}
    fx = {"PLN": 1.0}
    if a.fx:
        fx.update({k.strip().upper(): float(v) for k, v in (p.split("=") for p in a.fx.split(","))})

    def param(label):
        m = re.search(rf"{label}[^:]*:\s*([\d\s.,]+)", text)
        return num(m.group(1)) if m else None

    cash = param("Wolna gotówka") or 0.0
    max_pos = param("Max udział jednej pozycji")
    header, rows = None, []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            if cells and cells[0].lower() == "ticker":
                header = [c.lower() for c in cells]
            continue
        if set("".join(cells)) <= set("-: ") or not cells[0]:
            continue
        rows.append(dict(zip(header, cells)))
    if not rows:
        sys.exit("Brak pozycji w tabeli portfel.md.")

    pos, missing = [], []
    for r in rows:
        t = r["ticker"].upper()
        cur = (r.get("waluta") or ("USD" if t.endswith(".US") else "PLN")).upper()
        if t not in prices:
            missing.append(t)
            continue
        if cur not in fx:
            sys.exit(f"Brak kursu {cur}: dodaj --fx {cur}=...")
        price, qty, avg, inval = prices[t], num(r.get("ilość")) or 0, num(r.get("śr. cena")), num(r.get("invalidation"))
        targets = [num(x) for x in re.split(r"[;/]", r.get("targety") or "") if num(x)]
        flags = []
        if inval and price <= inval:
            flags.append("THESIS INVALIDATED")
        elif inval and (price / inval - 1) * 100 <= 3:
            flags.append("blisko invalidation (<3%)")
        if not inval:
            flags.append("brak invalidation")
        if targets and price >= targets[0]:
            flags.append(f"target 1 osiągnięty ({targets[0]})")
        pos.append({"ticker": t, "konto": r.get("konto") or "standard", "waluta": cur, "value": qty * price * fx[cur],
                    "pnl": rnd((price / avg - 1) * 100) if avg else None,
                    "to_inval": rnd((inval / price - 1) * 100) if inval else None, "flags": flags})
    total = sum(p["value"] for p in pos) + cash
    for p in pos:
        p["weight"] = p["value"] / total * 100
        if max_pos and p["weight"] > max_pos:
            p["flags"].append(f"przeważona ({p['weight']:.1f}% > {max_pos:.0f}%)")
    w = [p["value"] / total for p in pos]
    hhi = sum(x * x for x in w)

    print(f"Wartość: {total:.2f} PLN · gotówka {cash / total * 100:.1f}% · efektywna liczba pozycji {1 / hhi:.1f}" if hhi else "")
    print("| Ticker | Konto | Wartość PLN | Udział | Wynik % | Do invalidation | Flagi |\n|---|---|---:|---:|---:|---:|---|")
    for p in sorted(pos, key=lambda p: -p["value"]):
        print(f"| {p['ticker']} | {p['konto']} | {p['value']:.2f} | {p['weight']:.1f}% | {p['pnl']} | {p['to_inval']} | {'; '.join(p['flags'])} |")
    by_ccy = {}
    for p in pos:
        by_ccy[p["waluta"]] = by_ccy.get(p["waluta"], 0) + p["value"]
    by_ccy["PLN (gotówka)"] = cash
    print("Waluty: " + ", ".join(f"{k} {v / total * 100:.1f}%" for k, v in by_ccy.items()))
    print("Wynik % w walucie instrumentu, bez efektu walutowego i kosztów.")
    if missing:
        print("UWAGA: brak ceny dla: " + ", ".join(missing) + " (pominięte, podaj w --ceny).")


def main():
    ap = argparse.ArgumentParser(description="Doradca XTB, offline toolkit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tech")
    t.add_argument("file")
    t.add_argument("--ticker")
    t.add_argument("--benchmark")
    t.add_argument("--currency")
    t.add_argument("--fx", type=float, default=1.0, help="PLN per 1 unit of instrument currency (liquidity in PLN)")
    t.add_argument("--out", default=".")
    t.set_defaults(func=cmd_tech)

    p = sub.add_parser("pozycja")
    p.add_argument("--price", type=float, required=True)
    p.add_argument("--currency", default="PLN")
    p.add_argument("--fx", type=float, default=1.0)
    p.add_argument("--entries", required=True)
    p.add_argument("--stop", type=float, required=True)
    p.add_argument("--targets", required=True)
    p.add_argument("--budget", type=float, required=True)
    p.add_argument("--capital", type=float)
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--account", choices=["standard", "ike", "ikze"], default="standard")
    p.add_argument("--fractional", action="store_true")
    p.set_defaults(func=cmd_pozycja)

    f = sub.add_parser("portfel")
    f.add_argument("file")
    f.add_argument("--ceny", help="TICKER=cena,... (aktualne ceny z xStation)")
    f.add_argument("--fx", help="USD=3.93,EUR=4.30")
    f.set_defaults(func=cmd_portfel)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
