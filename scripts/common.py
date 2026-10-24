"""Shared helpers: paths, ticker mapping, Yahoo Finance access, FX, benchmarks."""
import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dane"
CHARTS = ROOT / "wykresy"
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))

import pandas as pd  # noqa: E402

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range}&interval={interval}"
FUND_URL = (
    "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}"
    "?type={types}&period1={p1}&period2={p2}"
)
# Yahoo has no history for Polish indices (WIG.WA returns 1 bar), so GPW uses the Beta WIG20TR ETF.
BENCHMARKS = {".WA": "ETFBW20TR.WA", "": "^GSPC"}


def to_yahoo(symbol):
    """Map xStation-style tickers (XTB.PL, TTWO.US) to Yahoo symbols (XTB.WA, TTWO)."""
    s = symbol.upper().strip()
    if s.endswith(".PL"):
        return s[:-3] + ".WA"
    if s.endswith(".US"):
        return s[:-3]
    return s


def benchmark_for(yahoo_symbol):
    return BENCHMARKS[".WA"] if yahoo_symbol.endswith(".WA") else BENCHMARKS[""]


def safe_name(symbol):
    return symbol.upper().replace("/", "_").replace("^", "")


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp)
        except Exception as e:  # network hiccups and 429s
            if attempt == 2:
                sys.exit(f"Błąd pobierania {url}: {e}")
            time.sleep(2 * (attempt + 1))


def fetch_chart(yahoo_symbol, rng="2y", interval="1d"):
    """Return (df, meta, url, dropped_rows). Index = session date (exchange timezone)."""
    url = CHART_URL.format(symbol=yahoo_symbol, range=rng, interval=interval)
    payload = get_json(url)
    err = payload["chart"].get("error")
    if err or not payload["chart"]["result"]:
        sys.exit(f"Yahoo: brak danych dla {yahoo_symbol}: {err}")
    res = payload["chart"]["result"][0]
    if "timestamp" not in res:
        sys.exit(f"Yahoo: brak notowań dla {yahoo_symbol}")
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame(
        {k: q[k] for k in ("open", "high", "low", "close", "volume")},
        index=pd.to_datetime(res["timestamp"], unit="s", utc=True)
        .tz_convert(res["meta"]["exchangeTimezoneName"])
        .normalize()
        .tz_localize(None),
    )
    raw_len = len(df)
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[~df.index.duplicated(keep="last")]
    df["volume"] = df["volume"].fillna(0)
    return df, res["meta"], url, raw_len - len(df)


def fetch_fundamentals(yahoo_symbol, types, years=6):
    """Return ({type: [(asOfDate, value, currency)]}, url). Missing types map to []."""
    p2 = int(time.time())
    p1 = p2 - int(years * 365.25 * 86400)
    url = FUND_URL.format(symbol=yahoo_symbol, types=",".join(types), p1=p1, p2=p2)
    payload = get_json(url)
    out = {t: [] for t in types}
    for r in payload.get("timeseries", {}).get("result") or []:
        t = r["meta"]["type"][0]
        out[t] = [
            (x["asOfDate"], x["reportedValue"]["raw"], x.get("currencyCode"))
            for x in (r.get(t) or [])
            if x and x.get("reportedValue")
        ]
    return out, url


def last_price(yahoo_symbol):
    df, meta, url, _ = fetch_chart(yahoo_symbol, rng="5d")
    return float(df["close"].iloc[-1]), meta.get("currency"), df.index[-1].strftime("%Y-%m-%d"), url


def fx_to_pln(currency, cache={}):
    """PLN value of 1 unit of currency (mid, from Yahoo). GBp (pence) handled."""
    if currency in (None, "PLN"):
        return 1.0
    if currency in cache:
        return cache[currency]
    pence = currency == "GBp"
    cur = "GBP" if pence else currency
    rate, _, _, _ = last_price(f"{cur}PLN=X")
    cache[currency] = rate / 100 if pence else rate
    return cache[currency]


def write_json(path, obj):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))


def r(x, nd=2):
    """Round for JSON output; None/NaN/inf -> None."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None
