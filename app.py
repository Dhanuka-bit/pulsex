import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
import numpy as np
import pandas as pd
import streamlit as st
import accounts
import i18n
import plotly.graph_objects as go
from plotly.subplots import make_subplots

APP_NAME, TAGLINE = "PulseX", "Catch every move."
st.set_page_config(page_title=f"{APP_NAME} · Crypto Signals", page_icon="⚡", layout="wide")
t = i18n.setup()


TF = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120,
      "4h": 240, "5h": 300, "6h": 360, "12h": 720, "1d": 1440}
LADDER = [5, 15, 60, 240, 720, 1440]  # higher-timeframe ladder for trend filters
EX = {
    "MEXC Futures": {"max": 1000, "native": {1: "Min1", 5: "Min5", 15: "Min15", 30: "Min30", 60: "Min60", 240: "Hour4", 480: "Hour8", 1440: "Day1"}},
    "Binance Futures": {"max": 1000, "native": {1: "1m", 3: "3m", 5: "5m", 15: "15m", 30: "30m", 60: "1h", 120: "2h", 240: "4h", 360: "6h", 720: "12h", 1440: "1d"}},
    "OKX Swap": {"max": 600, "native": {1: "1m", 3: "3m", 5: "5m", 15: "15m", 30: "30m", 60: "1H", 120: "2H", 240: "4H", 360: "6H", 720: "12H", 1440: "1D"}},
    "Bybit Futures": {"max": 1000, "native": {1: "1", 3: "3", 5: "5", 15: "15", 30: "30", 60: "60", 120: "120", 240: "240", 360: "360", 720: "720", 1440: "D"}},
}
CG_FIX = {"BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "SOL": "solana", "XRP": "ripple"}

# ---------------- tiny shared TTL cache (thread-safe, shared by all visitors) ----------------
_C, _L = {}, threading.Lock()


def cached(ttl):
    def deco(f):
        def w(*a):
            k, now = (f.__name__,) + a, time.time()
            with _L:
                v = _C.get(k)
                if v and now - v[0] < ttl:
                    return v[1]
            r = f(*a)
            with _L:
                _C[k] = (now, r)
                if len(_C) > 3000:
                    for kk in [kk for kk, vv in _C.items() if now - vv[0] > 600]:
                        del _C[kk]
            return r
        return w
    return deco


def J(url, **params):
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def fmt(x):
    return f"{x:,.4f}" if abs(x) >= 1 else f"{x:.8f}"


# ---------------- Exchange data: every pair, auto-updating ----------------
@cached(600)
def instruments(ex):
    if ex == "Binance Futures":
        j = J("https://fapi.binance.com/fapi/v1/exchangeInfo")["symbols"]
        rows = [(x["baseAsset"], x["symbol"], int(x.get("onboardDate") or 0)) for x in j
                if x.get("contractType") == "PERPETUAL" and x["quoteAsset"] == "USDT" and x["status"] == "TRADING"]
    elif ex == "Bybit Futures":
        j = J("https://api.bybit.com/v5/market/instruments-info", category="linear", limit=1000)["result"]["list"]
        rows = [(x["baseCoin"], x["symbol"], int(x.get("launchTime") or 0)) for x in j
                if x.get("quoteCoin") == "USDT" and x.get("status") == "Trading" and x.get("contractType") == "LinearPerpetual"]
    elif ex == "OKX Swap":
        j = J("https://www.okx.com/api/v5/public/instruments", instType="SWAP")["data"]
        rows = [(x["instId"].split("-")[0], x["instId"], int(x.get("listTime") or 0)) for x in j
                if x["instId"].endswith("-USDT-SWAP") and x.get("state") == "live"]
    else:
        j = J("https://contract.mexc.com/api/v1/contract/detail")["data"]
        rows = [(x["baseCoin"], x["symbol"], int(x.get("createTime") or 0)) for x in j
                if x.get("quoteCoin") == "USDT" and x.get("state") == 0]
    if not rows:
        raise ValueError("empty instrument list")
    return pd.DataFrame(rows, columns=["base", "sym", "listed"]).drop_duplicates("base")


@cached(30)
def tickers(ex):
    if ex == "Binance Futures":
        j = J("https://fapi.binance.com/fapi/v1/ticker/24hr")
        rows = [(x["symbol"], float(x["lastPrice"]), float(x["quoteVolume"]), float(x["priceChangePercent"])) for x in j]
    elif ex == "Bybit Futures":
        j = J("https://api.bybit.com/v5/market/tickers", category="linear")["result"]["list"]
        rows = [(x["symbol"], float(x["lastPrice"]), float(x["turnover24h"]), float(x["price24hPcnt"]) * 100) for x in j]
    elif ex == "OKX Swap":
        j = J("https://www.okx.com/api/v5/market/tickers", instType="SWAP")["data"]
        rows = []
        for x in j:
            last, o = float(x["last"]), float(x.get("open24h") or 0)
            rows.append((x["instId"], last, float(x["volCcy24h"]) * last, (last / o - 1) * 100 if o else 0.0))
    else:
        j = J("https://contract.mexc.com/api/v1/contract/ticker")["data"]
        rows = [(x["symbol"], float(x["lastPrice"]), float(x.get("amount24") or 0), float(x.get("riseFallRate") or 0) * 100) for x in j]
    return pd.DataFrame(rows, columns=["sym", "price", "vol", "chg"])


@cached(120)
def market(ex):
    inst = instruments(ex)
    try:
        tk = tickers(ex)
    except Exception:
        tk = pd.DataFrame(columns=["sym", "price", "vol", "chg"])
    m = inst.merge(tk, on="sym", how="left")
    for c in ("price", "vol", "chg"):
        m[c] = pd.to_numeric(m[c], errors="coerce").fillna(0.0)
    return m.sort_values("vol", ascending=False).reset_index(drop=True)


@cached(600)
def reachable():
    """Exchanges this server can actually reach (some block cloud servers by region)."""
    def ok(e):
        try:
            return len(market(e)) > 0
        except Exception:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        res = list(pool.map(ok, list(EX)))
    return [e for e, r in zip(EX, res) if r]


def market_any(pref):
    for e in [pref] + [x for x in EX if x != pref]:
        try:
            return e, market(e)
        except Exception:
            continue
    raise RuntimeError("No exchange reachable")


def symmap(ex):
    i = instruments(ex)
    return dict(zip(i.base, i.sym))


def raw_klines(ex, s, nat, limit):
    iv = EX[ex]["native"][nat]
    if ex == "Binance Futures":
        rows = [x[:6] for x in J("https://fapi.binance.com/fapi/v1/klines", symbol=s, interval=iv, limit=limit)]
    elif ex == "Bybit Futures":
        rows = [x[:6] for x in J("https://api.bybit.com/v5/market/kline", category="linear", symbol=s, interval=iv, limit=limit)["result"]["list"]]
    elif ex == "OKX Swap":
        rows, after = [], None
        for page in range(8):
            p = {"instId": s, "bar": iv, "limit": 300 if page == 0 else 100}
            if after:
                p["after"] = after
            data = J("https://www.okx.com/api/v5/market/candles" if page == 0 else "https://www.okx.com/api/v5/market/history-candles", **p)["data"]
            if not data:
                break
            rows += [x[:6] for x in data]
            after = data[-1][0]
            if len(rows) >= limit:
                break
    else:
        end = int(time.time())
        d = J(f"https://contract.mexc.com/api/v1/contract/kline/{s}", interval=iv, start=end - nat * 60 * limit, end=end)["data"]
        rows = [[tt * 1000, o, h, l, c, v] for tt, o, h, l, c, v in zip(d["time"], d["open"], d["high"], d["low"], d["close"], d["vol"])]
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    if df.empty:
        raise ValueError("no candles")
    df = df.astype(float)
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    return df.sort_values("time").drop_duplicates("time").reset_index(drop=True)


@cached(15)
def get_candles(ex, s, tfm, bars=1000):
    nat = [m for m in EX[ex]["native"] if tfm % m == 0]
    if not nat:
        raise ValueError("timeframe not supported")
    n = max(nat)
    k = tfm // n
    df = raw_klines(ex, s, n, min(EX[ex]["max"], bars * k))
    if k > 1:  # build custom timeframes (5h, 7m ...) from smaller candles
        df = (df.set_index("time").resample(f"{tfm}min", origin="epoch")
              .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
              .dropna().reset_index())
    return df.tail(bars).reset_index(drop=True)


def load(ex, base, tfm, bars=1000):
    errs = []
    for e in [ex] + [x for x in EX if x != ex]:  # automatic fallback if an exchange is blocked
        try:
            s = symmap(e).get(base)
            if not s:
                raise KeyError("not listed")
            return e, s, get_candles(e, s, tfm, bars)
        except Exception as x:
            errs.append(f"{e}: {type(x).__name__}")
    raise RuntimeError(" | ".join(errs))


@cached(60)
def funding(ex, s):
    try:
        if ex == "Binance Futures":
            return float(J("https://fapi.binance.com/fapi/v1/premiumIndex", symbol=s)["lastFundingRate"])
        if ex == "Bybit Futures":
            return float(J("https://api.bybit.com/v5/market/tickers", category="linear", symbol=s)["result"]["list"][0]["fundingRate"])
        if ex == "OKX Swap":
            return float(J("https://www.okx.com/api/v5/public/funding-rate", instId=s)["data"][0]["fundingRate"])
        return float(J("https://contract.mexc.com/api/v1/contract/ticker", symbol=s)["data"]["fundingRate"])
    except Exception:
        return None


@cached(10)
def obi(ex, s):
    """Order-book imbalance of the top levels: +1 = all bids, -1 = all asks."""
    try:
        if ex == "Binance Futures":
            j = J("https://fapi.binance.com/fapi/v1/depth", symbol=s, limit=50)
            b, a = j["bids"], j["asks"]
        elif ex == "Bybit Futures":
            j = J("https://api.bybit.com/v5/market/orderbook", category="linear", symbol=s, limit=50)["result"]
            b, a = j["b"], j["a"]
        elif ex == "OKX Swap":
            j = J("https://www.okx.com/api/v5/market/books", instId=s, sz=50)["data"][0]
            b, a = j["bids"], j["asks"]
        else:
            j = J(f"https://contract.mexc.com/api/v1/contract/depth/{s}", limit=50)["data"]
            b, a = j["bids"], j["asks"]
        bv, av = sum(float(x[1]) for x in b[:25]), sum(float(x[1]) for x in a[:25])
        return (bv - av) / (bv + av) if bv + av > 0 else None
    except Exception:
        return None


# ---------------- Indicators & regime-adaptive scoring ----------------
def ind(df):
    d = df.copy()
    c, h, l = d["close"], d["high"], d["low"]
    for n in (9, 21, 50, 200):
        d[f"ema{n}"] = c.ewm(span=n, adjust=False).mean()
    dl = c.diff()
    g = dl.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    ls = (-dl.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["rsi"] = 100 - 100 / (1 + g / ls.replace(0, np.nan))
    m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    d["macd_h"] = m - m.ewm(span=9, adjust=False).mean()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    up, dn = h.diff(), -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=d.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=d.index)
    d["pdi"] = 100 * pdm.ewm(alpha=1 / 14, adjust=False).mean() / d["atr"]
    d["ndi"] = 100 * ndm.ewm(alpha=1 / 14, adjust=False).mean() / d["atr"]
    dx = 100 * (d["pdi"] - d["ndi"]).abs() / (d["pdi"] + d["ndi"]).replace(0, np.nan)
    d["adx"] = dx.ewm(alpha=1 / 14, adjust=False).mean()
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    d["bb_u"], d["bb_l"] = mid + 2 * sd, mid - 2 * sd
    d["pb"] = (c - d["bb_l"]) / (d["bb_u"] - d["bb_l"])
    d["vr"] = d["volume"] / d["volume"].rolling(20).mean()
    return d


def score_df(d):
    """Trending market -> trend-following score. Ranging market -> mean-reversion score."""
    trend = (np.where(d.ema9 > d.ema21, 1, -1) + np.where(d.close > d.ema50, 1, -1)
             + np.where(d.ema50 > d.ema200, 1, -1) + np.where(d.macd_h > 0, 1, -1)
             + np.where(d.pdi > d.ndi, 1, -1)
             + np.select([(d.rsi > 50) & (d.rsi <= 70), (d.rsi < 50) & (d.rsi >= 30)], [1, -1], 0)
             + np.where(d.vr > 1.5, np.where(d.close > d.open, 0.5, -0.5), 0))
    pb = d.pb
    rng = (np.select([d.rsi < 30, d.rsi < 40, d.rsi > 70, d.rsi > 60], [2, 1, -2, -1], 0)
           + np.select([pb < 0.05, pb < 0.2, pb > 0.95, pb > 0.8], [2, 1, -2, -1], 0)
           + np.where((d.close > d.open) & (d.close.shift() < d.open.shift()) & (pb < 0.3), 1, 0)
           - np.where((d.close < d.open) & (d.close.shift() > d.open.shift()) & (pb > 0.7), 1, 0))
    return pd.Series(np.where(d.adx >= 22, trend, rng), index=d.index)


def htf_bias(df):
    l = ind(df).iloc[-1]
    if l.close > l.ema50 and l.ema21 > l.ema50:
        return 1
    if l.close < l.ema50 and l.ema21 < l.ema50:
        return -1
    return 0


def backtest(d, thr, mult, rr=2.0, maxbars=60):
    sc, cl, hi, lo, at = score_df(d).values, d.close.values, d.high.values, d.low.values, d.atr.values
    res, i, n = [], 60, len(d)
    while i < n - 1:
        if abs(sc[i]) >= thr and at[i] > 0:
            sg, r, e = (1 if sc[i] > 0 else -1), at[i] * mult, cl[i]
            sl, tp, out, j = e - sg * r, e + sg * rr * r, None, i
            for j in range(i + 1, min(n, i + 1 + maxbars)):
                if (lo[j] <= sl) if sg > 0 else (hi[j] >= sl):
                    out = -1.0
                    break
                if (hi[j] >= tp) if sg > 0 else (lo[j] <= tp):
                    out = rr
                    break
            if out is None:
                out = (cl[j] - e) * sg / r
            res.append(out)
            i = j + 1
        else:
            i += 1
    return res


def stop_distance(d, sg, price, atr, mult, smart):
    r = atr * mult
    if smart:  # place the stop beyond the latest swing high/low
        w = d.tail(20)
        swing = w.low.min() if sg > 0 else w.high.max()
        r = min(max(abs(price - swing) + 0.25 * atr, 1.0 * atr), 3.0 * atr)
    return r


def reasons(l):
    def ic(v):
        return "🟢" if v > 0 else ("🔴" if v < 0 else "🟡")
    trending = l.adx >= 22
    out = [(0, t(f"Market regime: {'TRENDING' if trending else 'RANGING'} (ADX {l.adx:.1f}) - "
                 f"{'trend-following' if trending else 'mean-reversion'} rules used",
                 f"වෙළඳපොළ තත්ත්වය: {'TREND එකක්' if trending else 'RANGE එකක්'} (ADX {l.adx:.1f})")),
           (1 if l.ema9 > l.ema21 else -1, t(f"EMA9 {'above' if l.ema9 > l.ema21 else 'below'} EMA21 (short trend)", f"EMA9 {'>' if l.ema9 > l.ema21 else '<'} EMA21 (කෙටි trend)")),
           (1 if l.close > l.ema50 else -1, t(f"Price {'above' if l.close > l.ema50 else 'below'} EMA50 (medium trend)", f"මිල {'>' if l.close > l.ema50 else '<'} EMA50 (මධ්‍ය trend)")),
           (1 if l.ema50 > l.ema200 else -1, t(f"EMA50 {'above' if l.ema50 > l.ema200 else 'below'} EMA200 (long trend)", f"EMA50 {'>' if l.ema50 > l.ema200 else '<'} EMA200 (දිගු trend)")),
           (1 if l.macd_h > 0 else -1, t(f"MACD momentum {'positive' if l.macd_h > 0 else 'negative'}", f"MACD momentum {'ධනාත්මකයි' if l.macd_h > 0 else 'සෘණාත්මකයි'}")),
           (1 if l.rsi < 30 else (-1 if l.rsi > 70 else 0), f"RSI {l.rsi:.1f}"),
           (1 if l.pb < 0.05 else (-1 if l.pb > 0.95 else 0), f"Bollinger %B {l.pb:.2f}"),
           ((1 if l.close > l.open else -1) if l.vr > 1.5 else 0, t(f"Volume {l.vr:.1f}x average", f"Volume සාමාන්‍යයෙන් {l.vr:.1f} ගුණයක්"))]
    return [f"{ic(v)} {x}" for v, x in out]


def card(side, grade, head, sub):
    bg = {"LONG": "linear-gradient(135deg,#064e3b,#0ecb81)", "SHORT": "linear-gradient(135deg,#7f1d1d,#f6465d)",
          "WAIT": "linear-gradient(135deg,#3f3f46,#a16207)"}[side]
    glow = {"LONG": "rgba(14,203,129,.35)", "SHORT": "rgba(246,70,93,.35)", "WAIT": "rgba(161,98,7,.25)"}[side]
    ico = {"LONG": "🟢", "SHORT": "🔴", "WAIT": "🟡"}[side]
    g = f" · {grade}" if grade else ""
    st.markdown(
        f"<div style='background:{bg};color:#fff;padding:clamp(14px,3.5vw,20px) clamp(14px,4vw,24px);"
        f"border-radius:18px;box-shadow:0 8px 28px {glow};border:1px solid rgba(255,255,255,.12)'>"
        f"<div style='font-size:clamp(26px,8vw,38px);font-weight:800;line-height:1.1'>{ico} {side}{g}</div>"
        f"<div style='font-size:15px;margin-top:8px;opacity:.95'>{head}</div>"
        f"<div style='font-size:14px;margin-top:6px;opacity:.85'>{sub}</div></div>", unsafe_allow_html=True)


# ---------------- Sidebar ----------------
qp = st.query_params
st.sidebar.title(f"⚡ {APP_NAME}")
st.sidebar.caption("by Software owners")
accounts.sidebar_box(t)
OK = reachable()
if not OK:
    with _L:
        _C.pop(("reachable",), None)  # don't remember a total failure
    st.error(t("No exchange could be reached from this server. Please try again in a minute.",
               "මෙම server එකෙන් කිසිදු exchange එකකට සම්බන්ධ විය නොහැක. විනාඩියකින් නැවත උත්සාහ කරන්න."))
    st.stop()
_want = qp.get("ex") if qp.get("ex") in OK else OK[0]
ex_pref = st.sidebar.selectbox(t("Exchange (futures)", "එක්ස්චේන්ජ් එක (futures)"), OK, index=OK.index(_want))
try:
    ex, mk = market_any(ex_pref)
except Exception as e:
    st.error(t("Exchange data could not be loaded.", "Exchange දත්ත load කළ නොහැක.") + f" ({e})")
    st.stop()
if len(OK) < len(EX):
    st.sidebar.caption(t("ℹ️ Only exchanges available from this server are listed.",
                         "ℹ️ මෙම server එකෙන් සම්බන්ධ විය හැකි exchanges පමණක් පෙන්වයි."))
coins = list(dict.fromkeys(mk.base))
NEW = set(mk[(mk.listed > 0) & ((time.time() * 1000 - mk.listed) < 14 * 86400000)].base)
cur = st.session_state.get("coin_sel", qp.get("coin", "BTC"))
st.session_state["coin_sel"] = cur if cur in coins else ("BTC" if "BTC" in coins else coins[0])
coin = st.sidebar.selectbox(t(f"Coin ({len(coins)} pairs - type to search)", f"කොයින් එක (pairs {len(coins)} - ටයිප් කර සොයන්න)"),
                            coins, key="coin_sel", format_func=lambda c: f"{c} 🆕" if c in NEW else c)
with st.sidebar.expander(t("⚙️ Advanced settings", "⚙️ උසස් සැකසුම්")):
    sens = st.radio(t("Sensitivity", "සංවේදීතාව"), ["Conservative", "Balanced", "Aggressive"], index=1,
                    help=t("Conservative = fewer but stronger signals", "Conservative = signals අඩුයි, නමුත් ශක්තිමත්"))
    strict = st.checkbox(t("Strict accuracy mode", "Strict accuracy mode"), True,
                         help=t("Blocks signals when higher timeframes, funding, overextension or the pair's backtest disagree.",
                                "ඉහළ කාල රාමු, funding, අධික ලෙස දුර ගිය මිල හෝ backtest විරුද්ධ නම් signal එක නවත්වයි."))
    smart = st.checkbox(t("Smart stop-loss (behind swing high/low)", "Smart stop-loss (swing high/low පිටුපස)"), True)
    atr_mult = st.slider(t("Fixed stop-loss (x ATR)", "ස්ථාවර stop-loss (x ATR)"), 1.0, 3.0, 1.5, 0.1)
    closed = st.checkbox(t("Closed candles only (no repainting)", "වැසුණු candles පමණක්"), True)
    custom_tf = st.number_input(t("Custom timeframe (minutes, 0 = off)", "අභිමත කාල රාමුව (මිනිත්තු, 0 = off)"), 0, 10080, 0)
    balance = st.number_input(t("Account balance (USDT)", "ගිණුම් ශේෂය (USDT)"), 10.0, 10_000_000.0, 1000.0)
    risk = st.slider(t("Risk per trade (%)", "එක ට්‍රේඩ් එකකට අවදානම (%)"), 0.25, 5.0, 1.0, 0.25)
    refresh = st.selectbox(t("Auto refresh", "Auto refresh"), ["Off", "15s", "30s", "60s"], index=2)
THR = {"Conservative": 5.0, "Balanced": 3.5, "Aggressive": 2.5}[sens]
if refresh != "Off":
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=int(refresh[:-1]) * 1000, key="auto")
    except ImportError:
        pass

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
.stApp{background:#0b0e11;font-family:'Inter',system-ui,sans-serif}
footer{visibility:hidden}
[data-testid=stSidebar]{background:#11151a;border-right:1px solid #2b3139}
.block-container{padding-top:2.2rem;max-width:1250px}
.hero{padding:22px 26px;border-radius:18px;margin-bottom:12px;border:1px solid #2b3139;
 background:radial-gradient(circle at 85% 0%,#4c1d95 0%,transparent 55%),linear-gradient(120deg,#12161c,#1b1740);
 box-shadow:0 8px 30px rgba(124,58,237,.18)}
.hero h1{margin:0;font-size:42px;font-weight:800;letter-spacing:.5px;
 background:linear-gradient(90deg,#fff,#c4b5fd,#67e8f9);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{margin:4px 0 0;color:#9ca3af;font-size:15px}
.ticker{display:flex;gap:10px;overflow-x:auto;white-space:nowrap;padding:2px 0 12px;scrollbar-width:thin}
.chip{background:#161a1e;border:1px solid #2b3139;border-radius:999px;padding:6px 14px;font-size:13px;color:#eaecef}
.chip b{margin-right:6px}.chip i{font-style:normal;font-weight:700;margin-left:6px}
.up{color:#0ecb81}.dn{color:#f6465d}
[data-testid=stMetric]{background:#161a1e;border:1px solid #2b3139;border-radius:12px;padding:12px 14px}
[data-testid=stMetricLabel]{color:#848e9c}
[data-testid=stExpander]{background:#161a1e;border:1px solid #2b3139;border-radius:12px}
[data-testid=stDataFrame]{border:1px solid #2b3139;border-radius:12px;overflow:hidden}
button[data-baseweb=tab]{font-weight:600;color:#848e9c}
button[data-baseweb=tab][aria-selected=true]{color:#fff}
div[data-baseweb=tab-highlight]{background:linear-gradient(90deg,#7c3aed,#67e8f9);height:3px}
.stButton>button{border-radius:10px;border:1px solid #2b3139}
.stButton>button[kind=primary]{background:linear-gradient(90deg,#7c3aed,#4f46e5);border:0;color:#fff;font-weight:700}
.mobile-hint{display:none}
@media (max-width:640px){
 .block-container{padding:3.2rem .7rem 3rem !important}
 .hero{padding:14px 16px;border-radius:14px;margin-bottom:10px}
 .hero h1{font-size:28px}.hero p{font-size:13px}
 button[data-baseweb=tab]{padding:8px 10px;font-size:14px}
 [data-testid=stMetricValue]{font-size:1.25rem}[data-testid=stMetricLabel]{font-size:.8rem}
 .stButton>button,.stDownloadButton>button{width:100%;min-height:46px}
 h2,h3{font-size:1.15rem !important}
 .mobile-hint{display:block;background:#1b1740;color:#e0e7ff;padding:8px 12px;border-radius:10px;font-size:13px;margin-bottom:10px}
}
</style>""", unsafe_allow_html=True)
st.markdown(f"<div class='hero'><h1>⚡ {APP_NAME}</h1><p>{TAGLINE} · Smart crypto futures signals</p></div>", unsafe_allow_html=True)
_chips = ""
for _, _r in mk[mk.price > 0].head(8).iterrows():
    _chips += (f"<span class='chip'><b>{_r.base}</b>{fmt(_r.price)}"
               f"<i class='{'up' if _r.chg >= 0 else 'dn'}'>{_r.chg:+.2f}%</i></span>")
if _chips:
    st.markdown(f"<div class='ticker'>{_chips}</div>", unsafe_allow_html=True)
st.markdown("<div class='mobile-hint'>" + t("📱 Tap the ☰ / arrow at the top-left to choose exchange, coin and settings.",
            "📱 exchange, coin සහ සැකසුම් තෝරන්න උඩ වම් කෙළවරේ ☰ / ඊතලය ඔබන්න.") + "</div>", unsafe_allow_html=True)
tf_default = qp.get("tf") if qp.get("tf") in TF else "5m"
if hasattr(st, "segmented_control"):
    tf_label = st.segmented_control(t("Timeframe", "කාල රාමුව"), list(TF), default=tf_default, key="tf_sel") or tf_default
else:
    tf_label = st.selectbox(t("Timeframe", "කාල රාමුව"), list(TF), index=list(TF).index(tf_default))
tfm = int(custom_tf) if custom_tf > 0 else TF[tf_label]
if custom_tf > 0:
    tf_label = f"{custom_tf}m"
try:
    st.query_params.update({"ex": ex_pref, "coin": coin, "tf": tf_label if tf_label in TF else "5m"})
except Exception:
    pass


# ---------------- Tabs ----------------
def tab_signal():
    try:
        used, s, raw = load(ex, coin, tfm)
    except Exception as e:
        st.error(t("No data for this coin/timeframe.", "මෙම coin/කාල රාමුවට දත්ත නැත.") + f" ({e})")
        return
    if used != ex:
        st.info(t(f"Using {used} data for this pair.", f"මෙම pair එකට {used} දත්ත භාවිතා කරයි."))
    d = ind(raw)
    price = float(raw.close.iloc[-1])
    if closed:
        d = d.iloc[:-1]
    if len(d) < 70:
        st.warning(t("Not enough candles yet (new coin?). Try a smaller timeframe like 1m or 5m.",
                     "candles ප්‍රමාණවත් නැත (අලුත් coin එකක්ද?). 1m හෝ 5m වැනි කුඩා කාල රාමුවක් try කරන්න."))
        return
    l, base = d.iloc[-1], float(score_df(d).iloc[-1])
    h1 = next((m for m in LADDER if m >= 3 * tfm), None)
    h2 = next((m for m in LADDER if h1 and m >= 3 * h1), None)
    hb = []
    for m in (h1, h2):
        v = 0
        if m:
            try:
                v = htf_bias(load(used, coin, m, 300)[2])
            except Exception:
                pass
        hb.append(v)
    fr, ob = funding(used, s), obi(used, s)
    fadj = 0.0 if fr is None else (-0.5 if fr > 0.0005 else (0.5 if fr < -0.0005 else 0.0))
    oadj = 0.0 if ob is None else (0.5 if ob > 0.2 else (-0.5 if ob < -0.2 else 0.0))
    total = base + hb[0] + 0.5 * hb[1] + fadj + oadj
    cand = "LONG" if total >= THR else ("SHORT" if total <= -THR else "WAIT")
    res = backtest(d, THR, atr_mult)
    n = len(res)
    wr = sum(1 for x in res if x > 0) / n if n else 0
    exp = float(np.mean(res)) if n else 0.0
    edge = None if n < 8 else exp > 0

    side, grade, fails, chk = cand, "", [], []
    if cand != "WAIT":
        sg = 1 if cand == "LONG" else -1
        ext = (price - l.ema21) / l.atr * sg
        chk = [
            (t("Higher timeframe 1 agrees", "ඉහළ කාල රාමුව 1 එකඟයි"), None if hb[0] == 0 else hb[0] * sg > 0),
            (t("Higher timeframe 2 agrees", "ඉහළ කාල රාමුව 2 එකඟයි"), None if hb[1] == 0 else hb[1] * sg > 0),
            (t("Funding not crowded against you", "Funding ඔබට විරුද්ධ නැත"), None if fr is None else not ((sg > 0 and fr > 0.0005) or (sg < 0 and fr < -0.0005))),
            (t("Order book supports", "Order book සහාය දෙයි"), None if ob is None or abs(ob) <= 0.15 else ob * sg > 0),
            (t("Price not overextended", "මිල අධික ලෙස දුර ගොස් නැත"), bool(ext < 2.5)),
            (t("Trending market (ADX 22+)", "Trend එකක් ඇත (ADX 22+)"), True if l.adx >= 22 else None),
            (t("Backtest shows an edge on this pair", "මෙම pair එකේ backtest ජයග්‍රාහී"), edge),
        ]
        fails = [a for a, v in chk if v is False]
        oks = sum(1 for _, v in chk if v is True)
        grade = "A+" if oks >= 6 else "A" if oks == 5 else "B" if oks == 4 else "C"
        if strict and (fails or oks < 3):
            side = "WAIT"
    strength = min(100, abs(total) / 9 * 100)
    head = f"{coin}/USDT · {tf_label} · {used} · {t('strength', 'ශක්තිය')} {strength:.0f}%"
    sub = {"LONG": t("Price is more likely to go UP. Consider a long (buy).", "මිල ඉහළ යාමට වැඩි ඉඩක් ඇත. Long (මිලදී ගැනීම) සලකා බලන්න."),
           "SHORT": t("Price is more likely to go DOWN. Consider a short (sell).", "මිල පහළ යාමට වැඩි ඉඩක් ඇත. Short (විකිණීම) සලකා බලන්න."),
           "WAIT": t("No clear edge right now. Waiting is also a position.", "දැනට පැහැදිලි වාසියක් නැත. බලා සිටීමත් හොඳ තීරණයක්.")}[side]
    if cand != "WAIT" and side == "WAIT":
        sub = t(f"A {cand} setup appeared but strict mode blocked it: ", f"{cand} setup එකක් ආවත් strict mode එක නැවැත්වීය: ") + (", ".join(fails) if fails else t("too few confirmations", "තහවුරු කිරීම් අඩුයි"))
    card(side, grade if side != "WAIT" else "", head, sub)
    st.progress(strength / 100, text=t(f"Signal strength {strength:.0f}% (score {total:+.1f} of ±9)", f"Signal ශක්තිය {strength:.0f}% (score {total:+.1f} / ±9)"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("Price", "මිල"), fmt(price))
    c2.metric("Higher TFs", " / ".join({1: "🟢", -1: "🔴", 0: "🟡"}[v] for v in hb))
    c3.metric("Funding", "n/a" if fr is None else f"{fr * 100:.4f}%")
    c4.metric(t("Order book", "Order book"), "n/a" if ob is None else f"{ob:+.2f}")

    plan = None
    if side != "WAIT":
        sg = 1 if side == "LONG" else -1
        r = stop_distance(d, sg, price, l.atr, atr_mult, smart)
        sl_pct = r / price
        notional = balance * risk / 100 / sl_pct
        lev = int(max(1, min(25, 0.5 / sl_pct)))
        plan = {"sl": price - sg * r, "tp1": price + sg * r, "tp2": price + sg * 2 * r, "tp3": price + sg * 3 * r}
        st.subheader(t("Trade plan", "ට්‍රේඩ් සැලැස්ම"))
        st.table(pd.DataFrame({
            t("Level", "මට්ටම"): [t("Entry", "ඇතුල් වන මිල"), "Stop-loss", "TP1 (1R)", "TP2 (2R)", "TP3 (3R)"],
            t("Price", "මිල"): [fmt(price), fmt(plan["sl"]), fmt(plan["tp1"]), fmt(plan["tp2"]), fmt(plan["tp3"])]}))
        k1, k2, k3 = st.columns(3)
        k1.metric(t("Stop distance", "Stop දුර"), f"{sl_pct * 100:.2f}%")
        k2.metric(t("Position size", "ට්‍රේඩ් ප්‍රමාණය"), f"{notional:,.0f} USDT")
        k3.metric(t("Max sensible leverage", "උපරිම සුදුසු leverage"), f"{lev}x")
        st.caption(t(f"Sized so a stop-out loses about {risk}% of your balance ({balance * risk / 100:,.2f} USDT). Move stop to entry after TP1.",
                     f"Stop එකට වැදුණොත් ශේෂයෙන් {risk}% ({balance * risk / 100:,.2f} USDT) පමණක් අහිමි වේ. TP1 ට පසු stop එක entry එකට ගෙන එන්න."))
        w = d.tail(100)
        lvl = w.high[w.high > price].min() if sg > 0 else w.low[w.low < price].max()
        if pd.notna(lvl):
            st.caption(t(f"Next {'resistance' if sg > 0 else 'support'}: {fmt(lvl)} ({abs(lvl - price) / r:.1f}R away)",
                         f"ඊළඟ {'resistance' if sg > 0 else 'support'}: {fmt(lvl)} (R {abs(lvl - price) / r:.1f} ක් දුරින්)"))

    if chk:
        with st.expander(t("Confirmation checklist", "තහවුරු කිරීමේ checklist"), expanded=True):
            for a, v in chk:
                st.write(("✅" if v is True else "❌" if v is False else "➖") + " " + a)
    with st.expander(t("Why this signal?", "මේ signal එක ඇයි?")):
        for x in reasons(l):
            st.write(x)

    dd, sc = d.tail(150), score_df(d)
    upm, dnm = (sc >= THR) & (sc.shift() < THR), (sc <= -THR) & (sc.shift() > -THR)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=dd.time, open=dd.open, high=dd.high, low=dd.low, close=dd.close, name="Price",
                                 increasing_line_color="#0ecb81", increasing_fillcolor="#0ecb81",
                                 decreasing_line_color="#f6465d", decreasing_fillcolor="#f6465d"), row=1, col=1)
    for nn, col in [(9, "#f5a623"), (21, "#4a90e2"), (50, "#9b59b6"), (200, "#7f8c8d")]:
        fig.add_trace(go.Scatter(x=dd.time, y=dd[f"ema{nn}"], name=f"EMA{nn}", line=dict(width=1, color=col)), row=1, col=1)
    fig.add_trace(go.Scatter(x=dd.time[upm[dd.index]], y=dd.low[upm[dd.index]] * 0.999, mode="markers", name="Long",
                             marker=dict(symbol="triangle-up", size=11, color="#2ecc71")), row=1, col=1)
    fig.add_trace(go.Scatter(x=dd.time[dnm[dd.index]], y=dd.high[dnm[dd.index]] * 1.001, mode="markers", name="Short",
                             marker=dict(symbol="triangle-down", size=11, color="#e74c3c")), row=1, col=1)
    if plan:
        for k, col in (("sl", "#e74c3c"), ("tp1", "#2ecc71"), ("tp2", "#27ae60"), ("tp3", "#1e8449")):
            fig.add_hline(y=plan[k], line_dash="dot", line_color=col, annotation_text=k.upper(), row=1, col=1)
    fig.add_trace(go.Scatter(x=dd.time, y=dd.rsi, name="RSI", line=dict(color="#e67e22")), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    fig.add_trace(go.Bar(x=dd.time, y=dd.macd_h, name="MACD hist", marker_color=["#0ecb81" if v >= 0 else "#f6465d" for v in dd.macd_h]), row=3, col=1)
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      height=620, xaxis_rangeslider_visible=False, margin=dict(l=5, r=5, t=5, b=5),
                      legend=dict(orientation='h', y=1.02, x=0))
    fig.update_xaxes(gridcolor="#1e2329")
    fig.update_yaxes(gridcolor="#1e2329")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(t("Reality check: this strategy on this pair's history", "Reality check: මෙම pair එකේ ඉතිහාසයේ strategy එක"))
    if n >= 3:
        b1, b2, b3, b4 = st.columns(4)
        b1.metric(t("Trades", "ට්‍රේඩ්"), n)
        b2.metric(t("Win rate", "ජය අනුපාතය"), f"{wr * 100:.0f}%")
        b3.metric(t("Avg result", "සාමාන්‍ය ප්‍රතිඵලය"), f"{exp:+.2f} R")
        b4.metric(t("Total", "එකතුව"), f"{sum(res):+.1f} R")
        st.caption(t("TP at 2R, fixed-ATR stop, no fees/slippage, base score only (no higher-TF/funding/order-book filters). Break-even win rate is ~33%. In-sample test: past results never guarantee future results.",
                     "TP 2R, ස්ථාවර ATR stop, fees/slippage නැත, base score පමණි. Break-even ජය අනුපාතය ~33%. අතීත ප්‍රතිඵල අනාගතය තහවුරු නොකරයි."))
    else:
        st.info(t("Too few historical signals to judge this pair/timeframe.", "මෙම pair/කාල රාමුව විනිශ්චය කිරීමට ඉතිහාසයේ signals ප්‍රමාණවත් නැත."))


def pick_coin(c):
    st.session_state["coin_sel"] = c


def scan_one(args):
    base, price, vol, chg = args
    try:
        _, _, raw = load(ex, base, tfm, 300)
        d = ind(raw)
        d = d.iloc[:-1] if closed else d
        if len(d) < 70:
            return None
        sc, l = float(score_df(d).iloc[-1]), d.iloc[-1]
        return {"Coin": base, "Signal": "LONG" if sc >= THR else ("SHORT" if sc <= -THR else "WAIT"),
                "Strength %": round(abs(sc) / 7 * 100), "Price": fmt(l.close), "24h %": round(chg, 2),
                "Vol (M USDT)": round(vol / 1e6, 1), "RSI": round(float(l.rsi), 1), "ADX": round(float(l.adx), 1)}
    except Exception:
        return None


def tab_scan():
    st.write(t(f"Scans the most traded USDT pairs on **{tf_label}** ({len(coins)} pairs listed on {ex}).",
               f"{ex} හි pairs {len(coins)} අතරින් වැඩියෙන්ම trade වන ඒවා **{tf_label}** මත ස්කෑන් කරයි."))
    top_n = st.select_slider(t("How many pairs (by 24h volume)", "pairs කීයක් (24h volume අනුව)"), [10, 25, 50, 100, 200], 25)
    only = st.checkbox(t("Hide WAIT", "WAIT සඟවන්න"), True)
    if st.button(t("🔎 Scan now", "🔎 දැන් ස්කෑන් කරන්න"), type="primary"):
        rows = list(mk.head(top_n)[["base", "price", "vol", "chg"]].itertuples(index=False, name=None))
        with st.spinner(t("Scanning...", "ස්කෑන් කරමින්...")):
            with ThreadPoolExecutor(max_workers=8) as pool:
                out = [x for x in pool.map(scan_one, rows) if x]
        if not out:
            st.error(t("Scan failed (exchange unreachable).", "ස්කෑන් අසාර්ථකයි (exchange එකට සම්බන්ධ විය නොහැක)."))
            return
        df = pd.DataFrame(out).sort_values("Strength %", ascending=False)
        if only:
            df = df[df.Signal != "WAIT"]
        st.session_state["scan_df"] = df
    df = st.session_state.get("scan_df")
    if df is not None:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("⬇️ CSV", df.to_csv(index=False), "signals.csv", "text/csv")
        cols = st.columns(6)
        for i, c in enumerate(df.Coin.head(6)):
            cols[i].button(f"{c}", key=f"sc_{c}", on_click=pick_coin, args=(c,), help=t("Open full analysis", "සම්පූර්ණ විශ්ලේෂණය බලන්න"))


def tab_new():
    st.write(t("Newly listed futures pairs appear here automatically (the exchange list refreshes every 10 minutes).",
               "අලුතින් list වන futures pairs මෙතනට ස්වයංක්‍රීයව එයි (exchange list එක විනාඩි 10කට වරක් යාවත්කාලීන වේ)."))
    days = st.select_slider(t("Listed within (days)", "list වී දින"), [7, 14, 30, 60, 90], 30)
    m = mk[(mk.listed > 0)].copy()
    m["Age (days)"] = ((time.time() * 1000 - m.listed) / 86400000).round(1)
    m = m[m["Age (days)"] <= days].sort_values("Age (days)")
    if m.empty:
        st.info(t("No new listings in this period.", "මෙම කාලයේ අලුත් listings නැත."))
        return
    show = m[["base", "Age (days)", "price", "chg", "vol"]].rename(columns={"base": "Coin", "price": "Price", "chg": "24h %", "vol": "24h Volume"})
    st.dataframe(show, use_container_width=True, hide_index=True)
    cols = st.columns(6)
    for i, c in enumerate(m.base.head(6)):
        cols[i].button(f"{c} 🆕", key=f"nw_{c}", on_click=pick_coin, args=(c,))
    st.caption(t("New coins have few candles and extreme volatility. Use small timeframes (1m/5m) and tiny size.",
                 "අලුත් coins වල candles අඩුයි, volatility අධිකයි. කුඩා කාල රාමු (1m/5m) සහ කුඩා ප්‍රමාණයක් භාවිතා කරන්න."))


@cached(300)
def cg(base):
    b = re.sub(r"^(1000000|10000|1000|1M)", "", base)
    cid = CG_FIX.get(b)
    if not cid:
        r = J("https://api.coingecko.com/api/v3/search", query=b)["coins"]
        cid = next(x["id"] for x in r if x["symbol"].upper() == b.upper())
    return J(f"https://api.coingecko.com/api/v3/coins/{cid}", localization="false", tickers="false", community_data="false", developer_data="true")


def tab_fund():
    try:
        j = cg(coin)
        md = j["market_data"]
    except Exception:
        st.warning(t("Fundamental data not available (very new coin or CoinGecko limit).", "මූලික දත්ත නැත (ඉතා අලුත් coin එකක් හෝ CoinGecko සීමාව)."))
        return
    mc, vol = md["market_cap"].get("usd") or 0, md["total_volume"].get("usd") or 0
    a = st.columns(4)
    a[0].metric("Rank", f"#{j.get('market_cap_rank')}")
    a[1].metric("Market cap", f"${mc:,.0f}")
    a[2].metric(t("24h volume", "24h volume"), f"${vol:,.0f}")
    a[3].metric(t("Circulating", "සංසරණ supply"), f"{(md.get('circulating_supply') or 0):,.0f}")
    b = st.columns(4)
    b[0].metric("ATH", f"${md['ath']['usd']:,.4f}")
    b[1].metric(t("From ATH", "ATH සිට"), f"{md['ath_change_percentage']['usd']:.1f}%")
    b[2].metric("30d", f"{(md.get('price_change_percentage_30d') or 0):.1f}%")
    b[3].metric("1y", f"{(md.get('price_change_percentage_1y') or 0):.1f}%")
    if mc:
        r = vol / mc
        st.write(("🟢" if r > 0.1 else "🔴" if r < 0.02 else "🟡") + t(f" Volume/market cap {r:.1%} (liquidity)", f" Volume/market cap {r:.1%} (නගුලතාව)"))
    if md.get("max_supply") and md.get("circulating_supply"):
        p = md["circulating_supply"] / md["max_supply"]
        st.write(("🟢" if p > 0.8 else "🟡") + t(f" {p:.0%} of max supply issued", f" max supply හි {p:.0%} නිකුත් වී ඇත"))
    else:
        st.write("🟡 " + t("No supply cap (inflation risk)", "supply සීමාවක් නැත (උද්ධමන අවදානම)"))
    cm = (j.get("developer_data") or {}).get("commit_count_4_weeks")
    if cm is not None:
        st.write(("🟢" if cm > 50 else "🔴" if cm == 0 else "🟡") + t(f" {cm} developer commits in 4 weeks", f" සති 4ක developer commits {cm}"))


def tab_guide():
    st.markdown(t(
        """**How to use:** pick an exchange, a coin and a timeframe. Read the colored card first, then the checklist, then the trade plan.

**Grades:** A+ / A / B / C = how many independent checks agree (higher timeframes, funding, order book, trend strength, overextension, backtest edge).

**Strict mode** blocks a signal when any check clearly disagrees. It means fewer signals, not guaranteed wins.

**Honest accuracy:** no indicator system predicts the market. The *Reality check* section shows how this exact logic performed on this pair's recent history, so you can see the real win rate instead of trusting a number.

**Risk rules:** always use the stop-loss, risk 1% or less per trade, never use the maximum leverage, avoid trading around big news.""",
        """**භාවිතය:** exchange එක, coin එක, කාල රාමුව තෝරන්න. මුලින් වර්ණ කාඩ් එක, ඊළඟට checklist එක, පසුව trade plan එක කියවන්න.

**Grades:** A+ / A / B / C = ස්වාධීන තහවුරු කිරීම් කීයක් එකඟද (ඉහළ කාල රාමු, funding, order book, trend ශක්තිය, මිල දුර, backtest).

**Strict mode** කිසියම් check එකක් පැහැදිලිව විරුද්ධ නම් signal එක නවත්වයි. ඒ කියන්නේ signals අඩුයි, ජයග්‍රහණ සහතික නැත.

**අවංක සත්‍යය:** කිසිම indicator පද්ධතියකට වෙළඳපොළ කල්තියා කියන්න බැහැ. *Reality check* කොටසින් මෙම logic එක මෙම pair එකේ ඉතිහාසයේ කොහොම වැඩ කළාද බලාගන්න පුළුවන්.

**අවදානම් නීති:** stop-loss හැමවිටම භාවිතා කරන්න, එක ට්‍රේඩ් එකකට 1% හෝ අඩුවෙන් අවදානම් වන්න, උපරිම leverage කිසිවිටක පාවිච්චි කරන්න එපා, ලොකු news වෙලාවල ට්‍රේඩ් නොකරන්න."""))


tabs = st.tabs([t("⚡ Signal", "⚡ Signal"), t("🔎 Scanner", "🔎 ස්කෑනර්"), t("🆕 New listings", "🆕 අලුත් coins"),
                t("📊 Fundamentals", "📊 මූලික දත්ත"), t("❓ Guide", "❓ මාර්ගෝපදේශය"), t("💼 Portfolio", "💼 Portfolio")])
for tb, fn in zip(tabs, (tab_signal, tab_scan, tab_new, tab_fund, tab_guide, lambda: accounts.portfolio_tab(t, mk, fmt))):
    with tb:
        fn()

st.caption("⚠️ " + t("Educational tool, not financial advice. Signals are probabilities, never guarantees. Leveraged futures can wipe out your account - always use a stop-loss.",
                      "අධ්‍යාපනික මෙවලමකි, මූල්‍ය උපදෙස් නොවේ. Signals සම්භාවිතාවන් මිස සහතික නොවේ. Leverage සහිත futures වලින් ඔබේ ගිණුම සම්පූර්ණයෙන් අහිමි විය හැක - හැමවිටම stop-loss භාවිතා කරන්න."))

st.markdown("<div style='text-align:center;opacity:.7;padding:16px 0'>© 2026 <b>Software owners</b> · Owner: Dhanushka Rathnayaka</div>", unsafe_allow_html=True)
