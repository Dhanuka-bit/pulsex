"""Signal engine: many independent indicator families -> regime-adaptive confluence score (about -9 .. +9)."""
import numpy as np
import pandas as pd


def _supertrend(h, l, c, atr, mult=3.0):
    hl2 = ((h + l) / 2).values
    ub, lb, cv, a = hl2 + mult * atr.values, hl2 - mult * atr.values, c.values, atr.values
    n = len(cv)
    fu, fl, dr, line = ub.copy(), lb.copy(), np.ones(n), np.zeros(n)
    for i in range(1, n):
        fu[i] = ub[i] if (ub[i] < fu[i - 1] or cv[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lb[i] if (lb[i] > fl[i - 1] or cv[i - 1] < fl[i - 1]) else fl[i - 1]
        if dr[i - 1] == 1 and cv[i] < fl[i]:
            dr[i] = -1
        elif dr[i - 1] == -1 and cv[i] > fu[i]:
            dr[i] = 1
        else:
            dr[i] = dr[i - 1]
    line = np.where(dr == 1, fl, fu)
    return pd.Series(dr, index=c.index), pd.Series(line, index=c.index)


def ind(df):
    d = df.copy()
    o, c, h, l, v = d["open"], d["close"], d["high"], d["low"], d["volume"]
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
    d["vr"] = v / v.rolling(20).mean()
    # --- volatility regime: Bollinger squeeze and dead-market detector
    bw = (d["bb_u"] - d["bb_l"]) / mid
    d["squeeze"] = bw.rolling(100, min_periods=30).rank(pct=True) < 0.15
    d["atr_rank"] = (d["atr"] / c).rolling(100, min_periods=30).rank(pct=True)
    # --- trend family: Supertrend + Ichimoku cloud
    d["st_dir"], d["st_line"] = _supertrend(h, l, c, tr.ewm(alpha=1 / 10, adjust=False).mean(), 3.0)
    tenkan = (h.rolling(9).max() + l.rolling(9).min()) / 2
    kijun = (h.rolling(26).max() + l.rolling(26).min()) / 2
    spa = ((tenkan + kijun) / 2).shift(26)
    spb = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
    d["ich_top"], d["ich_bot"] = np.maximum(spa, spb), np.minimum(spa, spb)
    # --- momentum family: Stochastic RSI, CCI
    r = d["rsi"]
    sr = (r - r.rolling(14).min()) / (r.rolling(14).max() - r.rolling(14).min()).replace(0, np.nan)
    d["stoch_k"] = sr.rolling(3).mean()
    d["stoch_d"] = d["stoch_k"].rolling(3).mean()
    tp = (h + l + c) / 3
    mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    d["cci"] = (tp - tp.rolling(20).mean()) / (0.015 * mad.replace(0, np.nan))
    # --- volume / money-flow family: OBV, MFI, rolling VWAP
    d["obv"] = (np.sign(c.diff().fillna(0)) * v).cumsum()
    d["obv_ema"] = d["obv"].ewm(span=20, adjust=False).mean()
    rmf = tp * v
    pos = rmf.where(tp > tp.shift(), 0.0).rolling(14).sum()
    neg = rmf.where(tp < tp.shift(), 0.0).rolling(14).sum()
    d["mfi"] = 100 - 100 / (1 + pos / neg.replace(0, np.nan))
    d["vwap"] = (tp * v).rolling(48).sum() / v.rolling(48).sum().replace(0, np.nan)
    # --- structure family: Donchian breakout, higher-high/higher-low
    d["dh20"], d["dl20"] = h.rolling(20).max().shift(), l.rolling(20).min().shift()
    hi10, lo10 = h.rolling(10).max(), l.rolling(10).min()
    d["struct"] = np.where((hi10 > hi10.shift(10)) & (lo10 > lo10.shift(10)), 1,
                           np.where((hi10 < hi10.shift(10)) & (lo10 < lo10.shift(10)), -1, 0))
    # --- candle patterns
    body = (c - o).abs()
    lw, uw = np.minimum(o, c) - l, h - np.maximum(o, c)
    bull_e = (c > o) & (c.shift() < o.shift()) & (c >= o.shift()) & (o <= c.shift())
    bear_e = (c < o) & (c.shift() > o.shift()) & (c <= o.shift()) & (o >= c.shift())
    d["bull_pat"] = bull_e | ((lw > 2 * body) & (uw <= body) & (h > l))
    d["bear_pat"] = bear_e | ((uw > 2 * body) & (lw <= body) & (h > l))
    # --- RSI divergence (price makes a new extreme, RSI does not confirm)
    bd = (c <= c.rolling(20).min()) & (r > r.rolling(20).min().shift() + 2)
    sd_ = (c >= c.rolling(20).max()) & (r < r.rolling(20).max().shift() - 2)
    d["bull_div"] = bd.rolling(3).max().fillna(0).astype(bool)
    d["bear_div"] = sd_.rolling(3).max().fillna(0).astype(bool)
    return d


def _s(up, dn):
    return np.where(up, 1.0, np.where(dn, -1.0, 0.0))


def score_df(d):
    """Trending market -> trend-following confluence. Ranging market -> mean-reversion confluence."""
    pm = lambda cond: np.where(cond, 1.0, -1.0)
    trend = (0.5 * (pm(d.ema9 > d.ema21) + pm(d.close > d.ema50) + pm(d.ema50 > d.ema200))   # EMA stack  +-1.5
             + 1.0 * d.st_dir.values                                                         # Supertrend +-1
             + 0.5 * _s(d.close > d.ich_top, d.close < d.ich_bot)                            # Ichimoku   +-0.5
             + 0.5 * pm(d.macd_h > 0) + 0.25 * pm(d.macd_h > d.macd_h.shift())               # MACD       +-0.75
             + 0.5 * pm(d.pdi > d.ndi)                                                       # DI         +-0.5
             + np.select([(d.rsi > 50) & (d.rsi <= 72), (d.rsi < 50) & (d.rsi >= 28)], [0.5, -0.5], 0.0)
             + 0.5 * _s((d.stoch_k > d.stoch_d) & (d.stoch_k < 0.85), (d.stoch_k < d.stoch_d) & (d.stoch_k > 0.15))
             + 0.4 * pm(d.obv > d.obv_ema)                                                   # money flow +-1.6
             + 0.4 * np.select([(d.mfi > 50) & (d.mfi < 80), (d.mfi < 50) & (d.mfi > 20)], [1.0, -1.0], 0.0)
             + 0.4 * pm(d.close > d.vwap)
             + 0.4 * np.where(d.vr > 1.5, pm(d.close > d.open), 0.0)
             + 1.0 * _s(d.close > d.dh20, d.close < d.dl20)                                  # breakout   +-1
             + 0.5 * d.struct.values                                                         # HH/HL      +-0.5
             + 0.5 * (np.where(d.bull_pat & (d.close > d.ema50), 1.0, 0.0)
                      - np.where(d.bear_pat & (d.close < d.ema50), 1.0, 0.0)))
    pb = d.pb
    rng = (np.select([d.rsi < 30, d.rsi < 40, d.rsi > 70, d.rsi > 60], [2.0, 1.0, -2.0, -1.0], 0.0)
           + np.select([pb < 0.05, pb < 0.2, pb > 0.95, pb > 0.8], [2.0, 1.0, -2.0, -1.0], 0.0)
           + np.select([d.stoch_k < 0.1, d.stoch_k > 0.9], [1.0, -1.0], 0.0)
           + np.select([d.cci < -150, d.cci > 150], [1.0, -1.0], 0.0)
           + np.select([d.mfi < 20, d.mfi > 80], [1.0, -1.0], 0.0)
           + np.where(d.bull_pat & (pb < 0.35), 1.0, 0.0) - np.where(d.bear_pat & (pb > 0.65), 1.0, 0.0)
           + np.where(d.bull_div, 1.0, 0.0) - np.where(d.bear_div, 1.0, 0.0))
    rng = rng * np.where(d.squeeze, 0.4, 1.0)            # a squeeze usually ends in a breakout, not a bounce
    raw = np.where(d.adx >= 22, trend, np.clip(rng, -9, 9))
    quality = np.where(d.atr_rank < 0.10, 0.6, 1.0)      # dead, low-volatility market: signals are unreliable
    return pd.Series(np.nan_to_num(raw * quality), index=d.index)


def backtest_ix(d, thr, mult, rr=2.0, maxbars=60, cost=0.001):
    """Returns [(entry_index, result_in_R)] net of fees+slippage (cost = round-trip fraction of price)."""
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
            res.append((i, out - cost * e / r))
            i = j + 1
        else:
            i += 1
    return res


def backtest(d, thr, mult, rr=2.0, maxbars=60):
    return [r for _, r in backtest_ix(d, thr, mult, rr, maxbars)]
