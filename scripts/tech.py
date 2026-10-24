"""Daily price data -> technicals, levels, relative strength, liquidity, annotated chart.

Usage:
    .venv/bin/python scripts/tech.py XTB.PL
    .venv/bin/python scripts/tech.py TTWO.US --range 5y

Outputs:
    dane/<SYMBOL>.csv             raw daily bars + indicators (git-ignored)
    dane/<SYMBOL>-tech.json       metrics + metadata (the only source of market numbers for agents)
    wykresy/<SYMBOL>-<date>.png   annotated chart
"""
import argparse
import sys

from common import (
    CHARTS,
    DATA,
    benchmark_for,
    fetch_chart,
    fx_to_pln,
    now_utc,
    r,
    safe_name,
    to_yahoo,
    write_json,
)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

STALE_DAYS = 4
PIVOT_WINDOW = 5
LOW_LIQUIDITY_PLN = 100_000  # avg daily turnover below this -> wide spreads, slow exits [założenie]


def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss)


def atr(df, n=14):
    prev = df["close"].shift()
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def add_indicators(df):
    c = df["close"]
    for n in (20, 50, 200):
        df[f"sma{n}"] = c.rolling(n).mean()
    df["ema20"] = c.ewm(span=20, adjust=False).mean()
    df["rsi14"] = rsi(c)
    df["macd"] = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["atr14"] = atr(df)
    # Yahoo sometimes reports 0 volume for sessions that traded; keep zeros out of averages.
    vol = df["volume"].where(df["volume"] > 0)
    df["vol_avg20"] = vol.rolling(20, min_periods=15).mean()
    df["turnover"] = df["close"] * vol
    df["ret"] = c.pct_change()
    return df


def pivots(df, w=PIVOT_WINDOW):
    """Fractal swing points: bar is the extreme of a 2w+1 window. Last w bars can't be confirmed."""
    hi = df["high"] == df["high"].rolling(2 * w + 1, center=True).max()
    lo = df["low"] == df["low"].rolling(2 * w + 1, center=True).min()
    return (
        [(d, float(p)) for d, p in df.loc[hi, "high"].items()],
        [(d, float(p)) for d, p in df.loc[lo, "low"].items()],
    )


def cluster_levels(highs, lows, tol_pct):
    """Greedy clustering of swing prices. Zone width is capped at tol_pct from its lowest price
    (no chaining), and the tolerance is relative so it scales across price regimes."""
    points = sorted(highs + lows, key=lambda x: x[1])
    clusters = []
    for d, p in points:
        if clusters and (p / clusters[-1][0][1] - 1) <= tol_pct:
            clusters[-1].append((d, p))
        else:
            clusters.append([(d, p)])
    return [
        {
            "price": round(sum(p for _, p in cl) / len(cl), 2),
            "touches": len(cl),
            "last_touch": max(d for d, _ in cl).strftime("%Y-%m-%d"),
        }
        for cl in clusters
    ]


def nearest_levels(levels, close, side, n=3):
    """n nearest levels; if none of them is multi-touch, append the nearest multi-touch zone."""
    below = side == "support"
    key = (lambda x: -x["price"]) if below else (lambda x: x["price"])
    cand = sorted([lv for lv in levels if (lv["price"] < close) == below and lv["price"] != close], key=key)
    out = cand[:n]
    if not any(lv["touches"] >= 2 for lv in out):
        out += [lv for lv in cand[n:] if lv["touches"] >= 2][:1]
    for lv in out:
        lv["distance_pct"] = r((lv["price"] / close - 1) * 100)
    return out


def structure(highs, lows):
    out = {}
    if len(highs) >= 2:
        out["highs"] = "HH" if highs[-1][1] > highs[-2][1] else "LH"
    if len(lows) >= 2:
        out["lows"] = "HL" if lows[-1][1] > lows[-2][1] else "LL"
    out["trend"] = {("HH", "HL"): "wzrostowy", ("LH", "LL"): "spadkowy"}.get(
        (out.get("highs"), out.get("lows")), "mieszany/konsolidacja"
    )
    out["last_swing_highs"] = [{"date": d.strftime("%Y-%m-%d"), "price": round(p, 2)} for d, p in highs[-3:]]
    out["last_swing_lows"] = [{"date": d.strftime("%Y-%m-%d"), "price": round(p, 2)} for d, p in lows[-3:]]
    return out


def ret_over(series, bars):
    return r((series.iloc[-1] / series.iloc[-bars - 1] - 1) * 100) if len(series) > bars else None


def relative_strength(df, bench_symbol, rng):
    bdf, _, burl, _ = fetch_chart(bench_symbol, rng=rng)
    joined = pd.concat([df["close"], bdf["close"]], axis=1, keys=["s", "b"]).dropna()
    out = {"benchmark": bench_symbol, "source": burl}
    for label, bars in (("1m", 21), ("3m", 63), ("6m", 126), ("1y", 252)):
        s, b = ret_over(joined["s"], bars), ret_over(joined["b"], bars)
        out[label] = {"stock_pct": s, "benchmark_pct": b, "diff_pp": r(s - b) if s is not None and b is not None else None}
    corr = joined.pct_change().dropna().iloc[-252:].corr().iloc[0, 1]
    out["corr_1y_daily"] = r(corr)
    return out


def big_moves(df, n=5, days=60):
    recent = df.iloc[-days:]
    top = recent["ret"].abs().nlargest(n).index
    return [
        {
            "date": d.strftime("%Y-%m-%d"),
            "change_pct": r(df.loc[d, "ret"] * 100),
            "volume_x_avg20": r(df.loc[d, "volume"] / df.loc[d, "vol_avg20"]) if df.loc[d, "vol_avg20"] else None,
        }
        for d in sorted(top)
    ]


def slope_pct(series, bars=20):
    s = series.dropna()
    return r((s.iloc[-1] / s.iloc[-bars - 1] - 1) * 100) if len(s) > bars else None


def build_report(df, meta, url, dropped, symbol, rs):
    last = df.iloc[-1]
    last_date = df.index[-1]
    close = float(last["close"])
    a = float(last["atr14"])
    highs, lows = pivots(df)
    levels = cluster_levels(highs, lows, tol_pct=0.75 * a / close)
    y = df.iloc[-252:]
    cur = meta.get("currency")
    turnover20 = float(df["turnover"].iloc[-20:].mean())
    turnover20_pln = turnover20 * fx_to_pln(cur)

    warnings = []
    age = (pd.Timestamp.now().normalize() - last_date).days
    if age > STALE_DAYS:
        warnings.append(f"Ostatnia świeca ma {age} dni, dane mogą być nieaktualne.")
    if dropped:
        warnings.append(f"Usunięto {dropped} niepełnych świec z odpowiedzi źródła.")
    if len(df) < 200:
        warnings.append(f"Tylko {len(df)} świec, SMA200 niewiarygodna lub brak.")
    if (df["volume"].iloc[-20:] == 0).any():
        warnings.append("Zerowy wolumen w ostatnich 20 sesjach (możliwy brak danych o wolumenie).")
    if turnover20_pln < LOW_LIQUIDITY_PLN:
        warnings.append(f"Niska płynność: średni obrót 20 sesji ok. {turnover20_pln:,.0f} PLN/dzień. Szerokie spready, wolne wyjście.")

    def vs_sma(k):
        return r((close - last[k]) / a) if not pd.isna(last[k]) else None

    return {
        "symbol": symbol,
        "yahoo_symbol": meta["symbol"],
        "name": meta.get("longName") or meta.get("shortName"),
        "currency": cur,
        "exchange": meta.get("fullExchangeName"),
        "instrument_type": meta.get("instrumentType"),
        "source": url,
        "fetched_at": now_utc(),
        "last_bar": last_date.strftime("%Y-%m-%d"),
        "bars": len(df),
        "price_note": "Ceny dzienne, korygowane o splity, nie o dywidendy. Ostatnia świeca może być sesją w toku.",
        "warnings": warnings,
        "price": {
            "close": r(close),
            "change_1d_pct": r(last["ret"] * 100),
            "change_1m_pct": ret_over(df["close"], 21),
            "change_1y_pct": ret_over(df["close"], 252),
            "high_52w": r(y["high"].max()),
            "low_52w": r(y["low"].min()),
            "drawdown_from_52w_high_pct": r((close / y["high"].max() - 1) * 100),
            "high_in_range": r(df["high"].max()),
        },
        "averages": {
            **{k: r(last[k]) for k in ("sma20", "sma50", "sma200", "ema20")},
            "close_vs_sma50_atr": vs_sma("sma50"),
            "close_vs_sma200_atr": vs_sma("sma200"),
            "sma50_slope_20d_pct": slope_pct(df["sma50"]),
            "sma200_slope_20d_pct": slope_pct(df["sma200"]),
        },
        "momentum": {
            "rsi14": r(last["rsi14"], 1),
            "macd": r(last["macd"], 3),
            "macd_signal": r(last["macd_signal"], 3),
            "macd_hist": r(last["macd"] - last["macd_signal"], 3),
        },
        "volatility": {
            "atr14": r(a),
            "atr14_pct": r(a / close * 100),
            "stdev_daily_1y_pct": r(y["ret"].std() * 100),
            "max_drawdown_1y_pct": r(((y["close"] / y["close"].cummax()) - 1).min() * 100),
        },
        "volume": {
            "last": int(last["volume"]),
            "avg20": int(last["vol_avg20"]) if not pd.isna(last["vol_avg20"]) else None,
            "ratio_to_avg20": r(last["volume"] / last["vol_avg20"]) if last["vol_avg20"] else None,
            "turnover_avg20": r(turnover20, 0),
            "turnover_avg20_pln": r(turnover20_pln, 0),
            "days_above_2x_avg_last20": int((df["volume"].iloc[-20:] > 2 * df["vol_avg20"].iloc[-20:]).sum()),
        },
        "big_moves_60d": big_moves(df),
        "relative_strength": rs,
        "structure": structure(highs, lows),
        "levels": {
            "method": f"Fraktale ±{PIVOT_WINDOW} świec, klastrowane w tolerancji 0.75×ATR% ceny; touches = liczba swingów w strefie; 3 najbliższe + najbliższa strefa wielokrotna.",
            "supports": nearest_levels(levels, close, "support"),
            "resistances": nearest_levels(levels, close, "resistance"),
        },
    }


def draw(df, rep, path, bars=250):
    d = df.iloc[-bars:].reset_index()
    x = range(len(d))
    fig, (ax, axv, axr) = plt.subplots(
        3, 1, figsize=(14, 9), sharex=True, gridspec_kw={"height_ratios": [5, 1.2, 1.5]}
    )
    col = ["#2e9d5b" if u else "#d64545" for u in d["close"] >= d["open"]]
    ax.vlines(x, d["low"], d["high"], color=col, linewidth=0.8)
    ax.bar(x, (d["close"] - d["open"]).abs(), bottom=d[["open", "close"]].min(axis=1), color=col, width=0.7)
    for k, c in (("sma50", "#e09b2d"), ("sma200", "#4a6fd1")):
        ax.plot(x, d[k], color=c, linewidth=1.2, label=k.upper())
    for side, color, tag in (("supports", "#2e9d5b", "S"), ("resistances", "#d64545", "R")):
        for lv in rep["levels"][side]:
            ax.axhline(lv["price"], color=color, linestyle="--", linewidth=1, alpha=0.8)
            ax.text(len(d) + 1, lv["price"], f"{tag} {lv['price']} ({lv['touches']}x)", va="center", fontsize=8, color=color)
    ax.axhline(rep["price"]["close"], color="#333", linewidth=0.6, alpha=0.6)
    ax.set_title(f"{rep['name']} ({rep['symbol']}) · {rep['currency']} · ostatnia świeca {rep['last_bar']} · źródło: Yahoo Finance")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.2)

    axv.bar(x, d["volume"], color=col, width=0.7)
    axv.plot(x, d["vol_avg20"], color="#555", linewidth=1)
    axv.set_ylabel("Wolumen")
    axv.grid(alpha=0.2)

    axr.plot(x, d["rsi14"], color="#7a4ad1", linewidth=1)
    for lvl in (30, 70):
        axr.axhline(lvl, color="#999", linestyle=":", linewidth=1)
    axr.set_ylim(0, 100)
    axr.set_ylabel("RSI14")
    axr.grid(alpha=0.2)

    step = max(1, len(d) // 10)
    axr.set_xticks(list(x)[::step])
    axr.set_xticklabels([t.strftime("%Y-%m") for t in d["index"][::step]])
    ax.set_xlim(-1, len(d) + 14)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", help="xStation ticker (XTB.PL, TTWO.US) or Yahoo symbol")
    ap.add_argument("--range", default="2y", help="Yahoo range: 1y, 2y, 5y, 10y, max")
    args = ap.parse_args()

    symbol = args.symbol.upper()
    ysym = to_yahoo(symbol)
    df, meta, url, dropped = fetch_chart(ysym, rng=args.range)
    if len(df) < 30:
        sys.exit(f"Za mało danych dla {ysym}: {len(df)} świec.")
    df = add_indicators(df)
    rs = relative_strength(df, benchmark_for(ysym), args.range)
    rep = build_report(df, meta, url, dropped, symbol, rs)

    name = safe_name(symbol)
    CHARTS.mkdir(exist_ok=True)
    png = CHARTS / f"{name}-{rep['last_bar']}.png"
    draw(df, rep, png)
    rep["chart"] = f"wykresy/{png.name}"
    DATA.mkdir(exist_ok=True)
    df.to_csv(DATA / f"{name}.csv")
    write_json(DATA / f"{name}-tech.json", rep)
    print(f"OK: dane/{name}-tech.json, {rep['chart']}")
    for w in rep["warnings"]:
        print("UWAGA:", w)


if __name__ == "__main__":
    main()
