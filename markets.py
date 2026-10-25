"""Markets home screen (CoinMarketCap-style mobile layout): stat card, filter tabs, coin list with sparklines."""
import math

import streamlit as st

import brand
import funda
import ui
from ui import esc

CG = "https://api.coingecko.com/api/v3"
CURRENCIES = {"USD": "$", "EUR": "€", "GBP": "£", "LKR": "Rs ", "INR": "₹", "AED": "AED ", "JPY": "¥"}
CATEGORIES = {"All": None, "Layer 1": "layer-1", "Layer 2": "layer-2", "DeFi": "decentralized-finance-defi", "Meme": "meme-token",
              "AI": "artificial-intelligence", "Gaming": "gaming", "RWA": "real-world-assets-rwa", "Stablecoins": "stablecoins"}
RANKS = [20, 50, 100, 200]
SORTS = ["Rank", "24h % (high to low)", "24h % (low to high)", "Volume", "Price"]
STABLES = {"usdt", "usdc", "dai", "usde", "fdusd", "tusd", "usds", "usdd", "pyusd", "usdy", "busd", "usd1", "usdt0", "wbtc", "steth",
           "wsteth", "weth", "wbeth", "cbbtc", "weeth", "reth"}


# ---------------- data ----------------
def top_coins(n=100, category=None, symbols=None):
    q = "sparkline=true&price_change_percentage=1h,24h,7d,30d"
    url = f"{CG}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={min(n, 250)}&page=1&{q}"
    if category:
        url += f"&category={category}"
    if symbols:
        url = (f"{CG}/coins/markets?vs_currency=usd&symbols={','.join(s.lower() for s in symbols)}&include_tokens=top"
               f"&order=market_cap_desc&per_page=250&{q}")
    data = funda._get(url, ttl=60)
    return data if isinstance(data, list) else None


def trending_symbols():
    j = funda._get(f"{CG}/search/trending", ttl=300) or {}
    return [c["item"]["symbol"].upper() for c in (j.get("coins") or [])][:15]


def fx(cur):
    if cur == "USD":
        return 1.0
    rates = (funda._get("https://open.er-api.com/v6/latest/USD", ttl=3600) or {}).get("rates") or {}
    return float(rates.get(cur) or 1.0)


def altcoin_index(coins):
    """Share (0-100) of the top-100 coins that beat Bitcoin over 30 days (similar idea to an 'altcoin season' index)."""
    k = "price_change_percentage_30d_in_currency"
    btc = next((c for c in coins if c.get("symbol") == "btc"), None)
    pool = [c for c in coins[:100] if c.get("symbol") not in STABLES and c.get("symbol") != "btc" and c.get(k) is not None]
    if not btc or btc.get(k) is None or len(pool) < 10:
        return None
    return round(sum(1 for c in pool if c[k] > btc[k]) / len(pool) * 100)


def px20(coins):
    """Our own top-20 index: market-cap weighted, rebased to 100 seven days ago."""
    top = [c for c in coins[:20] if (c.get("sparkline_in_7d") or {}).get("price") and c.get("market_cap")]
    if len(top) < 5:
        return None
    n = min(len(c["sparkline_in_7d"]["price"]) for c in top)
    cap = sum(c["market_cap"] for c in top)
    series = [0.0] * n
    for c in top:
        p = c["sparkline_in_7d"]["price"][-n:]
        base, w = (p[0] or 1), c["market_cap"] / cap
        for i, v in enumerate(p):
            series[i] += w * (v / base) * 100
    chg = sum((c.get("price_change_percentage_24h") or 0) * c["market_cap"] for c in top) / cap
    return {"level": series[-1], "series": series, "chg": chg, "cap": cap}


def context_text():
    g = (funda._get(f"{CG}/global") or {}).get("data") or {}
    fg = ((funda._get("https://api.alternative.me/fng/?limit=1") or {}).get("data") or [None])[0]
    bits = []
    if g:
        bits.append(f"Total crypto market cap {ui.compact((g.get('total_market_cap') or {}).get('usd'))} ({g.get('market_cap_change_percentage_24h_usd', 0):+.2f}% 24h), "
                    f"BTC dominance {(g.get('market_cap_percentage') or {}).get('btc', 0):.1f}%")
    if fg:
        bits.append(f"Fear & Greed index {fg.get('value')} ({fg.get('value_classification')})")
    return "; ".join(bits) or "Market data unavailable right now."


# ---------------- html pieces ----------------
def _arc(cx, cy, r, a0, a1):
    p = lambda a: (cx + r * math.cos(math.radians(a)), cy - r * math.sin(math.radians(a)))
    (x0, y0), (x1, y1) = p(a0), p(a1)
    return f"M{x0:.1f} {y0:.1f} A{r} {r} 0 0 1 {x1:.1f} {y1:.1f}"


def ring_gauge(v):
    """270-degree Fear & Greed ring with a marker dot; the number is overlaid in HTML so it follows the theme."""
    import base64
    segs = [(0, 25, "#f6465d"), (25, 45, "#f97316"), (45, 55, "#f0b90b"), (55, 75, "#84cc16"), (75, 100, "#0ecb81")]
    ang = lambda x: 225 - 2.7 * x
    arcs = "".join(f"<path d='{_arc(50, 50, 38, ang(a + (1 if a else 0)), ang(b - 1))}' stroke='{c}' stroke-width='9' fill='none' stroke-linecap='round'/>"
                   for a, b, c in segs)
    mx, my = 50 + 38 * math.cos(math.radians(ang(v))), 50 - 38 * math.sin(math.radians(ang(v)))
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>{arcs}<circle cx='{mx:.1f}' cy='{my:.1f}' r='6' fill='#1b2230' "
           f"stroke='#e5e7eb' stroke-width='3'/></svg>")
    return (f"<div class='ring'><img src='data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}'>"
            f"<div class='v num'>{v}</div></div>")


def money(v, sym, rate):
    if v is None:
        return "—"
    x = v * rate
    d = 2 if x >= 10 else 3 if x >= 1 else 4 if x >= 0.01 else 6
    return f"{sym}{x:,.{d}f}"


def pct(v):
    if v is None:
        return "<div class='pct'>—</div>"
    cls = "up" if v >= 0 else "dn"
    return f"<div class='pct {cls}'>{'▲' if v >= 0 else '▼'} {abs(v):.2f}%</div>"


def stat_card(t, coins, g, fg):
    mc = (g.get("total_market_cap") or {}).get("usd")
    mcc = g.get("market_cap_change_percentage_24h_usd")
    ix = px20(coins)
    alt = altcoin_index(coins)
    cells = [f"<div class='sc'><div class='lbl'>{esc(t('Market Cap'))}</div><div class='big num'>{ui.compact(mc)}</div>{pct(mcc)}</div>"]
    if ix:
        cells.append(f"<div class='sc'><div class='lbl'>PX20</div><div class='big num'>{ix['level']:.2f}</div>{pct(ix['chg'])}</div>")
    if alt is not None:
        cells.append(f"<div class='sc'><div class='lbl'>{esc(t('Altcoin Index'))}</div><div class='big num'>{alt}<small> /100</small></div>"
                     f"<div class='alt'><i style='left:{alt}%'></i></div></div>")
    if fg:
        cells.append(f"<div class='sc fg'><div class='lbl'>{esc(t('Fear & Greed'))}</div>{ring_gauge(int(fg.get('value', 0)))}</div>")
    return f"<div class='statcard'>{''.join(cells)}</div>"


def row(rank, ico, name, sub, price_txt, change, spark_html, pin=False):
    return (f"<div class='mrow2{' pin' if pin else ''}'><div class='rk'>{rank}</div>{ico}"
            f"<div class='nm'><b>{name}</b><span>{sub}</span></div><div class='pr num'>{price_txt}</div>"
            f"<div class='ch'>{spark_html}{pct(change)}</div></div>")


def rows_html(t, coins, sym, rate, with_index=False):
    out = ["<div class='mhead'><span>#&nbsp;▾&nbsp;&nbsp;" + esc(t("Market Cap")) + "</span><span>" + esc(t("Price"))
           + "</span><span>24h %</span></div>"]
    if with_index:
        ix = px20(coins)
        if ix:
            out.append(row("<span class='pinic'>" + brand.logo_img(22) + "</span>", f"<span class='ico brandico'>{brand.logo_img(30)}</span>",
                           "PX20", ui.compact(ix["cap"] * rate, sym), f"{ix['level']:.2f}", ix["chg"],
                           ui.sparkline(ix["series"], ix["chg"] >= 0, 78, 30), pin=True))
    for i, c in enumerate(coins, 1):
        img = c.get("image") or ""
        ico = (f"<img class='ico' src='{esc(img)}' loading='lazy'>" if img.startswith("https://")
               else f"<span class='ico ph'>{esc((c.get('symbol') or '?')[:1].upper())}</span>")
        ch = c.get("price_change_percentage_24h")
        spark = ui.sparkline((c.get("sparkline_in_7d") or {}).get("price"), (ch or 0) >= 0, 78, 30)
        out.append(row(c.get("market_cap_rank") or i, ico, esc((c.get("symbol") or "").upper()),
                       ui.compact((c.get("market_cap") or 0) * rate, sym), money(c.get("current_price"), sym, rate), ch, spark))
    return f"<div class='mlist'>{''.join(out)}</div>"


def mini_list(title, coins, sym, rate):
    rows = "".join(f"<div class='mini'><b>{esc((c.get('symbol') or '').upper())}</b><span class='num'>{money(c.get('current_price'), sym, rate)}</span>"
                   f"{pct(c.get('price_change_percentage_24h'))}</div>" for c in coins)
    return f"<div class='mcol'><div class='sec'>{esc(title)}</div>{rows}</div>"


# ---------------- page ----------------
def render(t, preds_html=None):
    ss = st.session_state
    ss.setdefault("mk_rank", 100)
    ss.setdefault("mk_cat", "All")
    ss.setdefault("mk_sort", "Rank")
    sym, rate = CURRENCIES.get(ss.get("mk_cur", "USD"), "$"), fx(ss.get("mk_cur", "USD"))
    rank_n, cat, sort = ss["mk_rank"], ss["mk_cat"], ss["mk_sort"]

    coins = top_coins(max(rank_n, 100), CATEGORIES.get(cat))
    if coins is None:
        st.warning(t("Market data is temporarily unavailable (rate limit). Please try again in a minute."))
        return
    base = top_coins(100) if cat != "All" else coins
    g = (funda._get(f"{CG}/global") or {}).get("data") or {}
    fg = ((funda._get("https://api.alternative.me/fng/?limit=1") or {}).get("data") or [None])[0]
    st.markdown(stat_card(t, base or coins, g, fg), unsafe_allow_html=True)

    with st.container(key="mkpills"):
        st.button(t("Ask PULSEX AI"), key="pill_ai", icon=":material/smart_toy:", on_click=lambda: ss.update(_ai=True))
        st.button(t("Top signals"), key="pill_sig", icon=":material/bolt:", on_click=lambda: ss.update(nav="alpha", alpha_sub="scan", _ai=False))

    tabs = ["top", "trending", "watch", "overview", "pred"]
    labels = {"top": t("Top"), "trending": t("Trending"), "watch": t("Watchlists"), "overview": t("Overview"), "pred": t("Predictions")}
    with st.container(key="mktabs"):
        sel = st.segmented_control("mk_tab", tabs, format_func=lambda k: labels[k], key="mk_tab", label_visibility="collapsed",
                                   **({} if "mk_tab" in ss else {"default": "top"})) or "top"

    with st.container(key="mkfilters"):
        st.selectbox("rank", RANKS, key="mk_rank", label_visibility="collapsed", format_func=lambda n: f"{t('Rank')}  Top {n}")
        st.selectbox("cat", list(CATEGORIES), key="mk_cat", label_visibility="collapsed", format_func=lambda c: t(c) if c != "All" else t("Categories"))
        st.selectbox("sort", SORTS, key="mk_sort", label_visibility="collapsed", format_func=lambda s_: "⇅  " + t(s_))

    shown = coins[:rank_n]
    if sel == "trending":
        want = trending_symbols()
        known = {c["symbol"].upper(): c for c in coins}
        shown = [known[s_] for s_ in want if s_ in known] or (top_coins(15, symbols=want) or [])
    elif sel == "watch":
        wl = [s_ for s_ in (st.query_params.get("wl") or "BTC,ETH,SOL").split(",") if s_]
        universe = sorted({c["symbol"].upper() for c in coins} | set(wl))
        pick = st.multiselect(t("Your watchlist"), universe, default=[s_ for s_ in wl if s_ in universe], key="mk_wl")
        try:
            st.query_params["wl"] = ",".join(pick)
        except Exception:
            pass
        known = {c["symbol"].upper(): c for c in coins}
        shown = [known[s_] for s_ in pick if s_ in known]
        missing = [s_ for s_ in pick if s_ not in known]
        if missing:
            shown += [c for c in (top_coins(len(missing) * 2, symbols=missing) or []) if c["symbol"].upper() in missing]
        if not shown:
            st.info(t("Pick coins above to build your watchlist. It is saved in the page link, so bookmark it."))
            return
    elif sel == "overview":
        by = lambda k, rev: sorted(coins, key=lambda c: (c.get(k) or 0), reverse=rev)[:5]
        st.markdown(f"<div class='mcols'>{mini_list(t('Top gainers (24h)'), by('price_change_percentage_24h', True), sym, rate)}"
                    f"{mini_list(t('Top losers (24h)'), by('price_change_percentage_24h', False), sym, rate)}"
                    f"{mini_list(t('Highest volume'), by('total_volume', True), sym, rate)}</div>", unsafe_allow_html=True)
        shown = coins[:20]
    elif sel == "pred":
        html = preds_html() if preds_html else ""
        if html:
            st.markdown(html, unsafe_allow_html=True)
        st.caption(t("Predictions are the app's own technical signals (not guarantees). Open Alpha for the full analysis."))
        return

    key = {"Rank": None, "24h % (high to low)": ("price_change_percentage_24h", True), "24h % (low to high)": ("price_change_percentage_24h", False),
           "Volume": ("total_volume", True), "Price": ("current_price", True)}[sort]
    if key and sel in ("top", "trending", "watch"):
        shown = sorted(shown, key=lambda c: (c.get(key[0]) or 0), reverse=key[1])
    st.markdown(rows_html(t, shown, sym, rate, with_index=(sel == "top" and sort == "Rank" and cat == "All")), unsafe_allow_html=True)
    st.caption(t("Data: CoinGecko, refreshed about every minute."))


def css():
    return """
.statcard{display:flex;overflow-x:auto;border:1px solid var(--border);border-radius:20px;background:var(--bg2);margin:2px 0 12px;scrollbar-width:none}
.statcard::-webkit-scrollbar{display:none}
.sc{flex:1 0 auto;min-width:118px;padding:14px 16px;border-right:1px solid var(--border)}.sc:last-child{border-right:0}
.sc .lbl{font-size:13px;color:var(--muted);margin-bottom:6px;white-space:nowrap}
.sc .big{font-size:23px;font-weight:700;color:var(--text);line-height:1.1;margin-bottom:6px;white-space:nowrap}
.sc .big small{font-size:15px;font-weight:500;color:var(--muted)}
.pct{font-size:13.5px;font-weight:600;white-space:nowrap;color:var(--muted)}.pct.up{color:var(--up)}.pct.dn{color:var(--down)}
.alt{position:relative;height:7px;border-radius:7px;margin-top:12px;background:linear-gradient(90deg,#f59e0b 0%,#e8d5b0 50%,#6d7cff 75%,#3b4cf0 100%)}
.alt i{position:absolute;top:-4px;width:15px;height:15px;border-radius:50%;background:#6b7280;border:3px solid #e5e7eb;transform:translateX(-7px)}
.sc.fg{min-width:112px}.ring{position:relative;width:78px;height:78px;margin:-4px auto 0}.ring img{width:100%;display:block}
.ring .v{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;color:var(--text)}

.st-key-mkpills [data-testid=stVerticalBlock]{flex-direction:row !important;flex-wrap:wrap;gap:8px !important;margin-bottom:6px}
.st-key-mkpills [data-testid=stElementContainer]{width:auto !important}
.st-key-mkpills button{border-radius:999px !important;padding:6px 16px !important;font-weight:600;border:1px solid var(--border) !important;background:var(--bg2) !important}
.st-key-mkpills [data-testid=stElementContainer]:first-child button{border-color:var(--accent) !important;color:var(--text) !important;
 background:color-mix(in srgb,var(--accent) 16%,transparent) !important}
.st-key-mktabs [data-testid=stButtonGroup]{flex-wrap:nowrap !important;overflow-x:auto;gap:22px;border-bottom:1px solid var(--border);margin-bottom:10px;scrollbar-width:none}
.st-key-mktabs button{background:transparent !important;border:0 !important;border-radius:0 !important;box-shadow:none !important;padding:10px 0 !important;
 font-size:18px;color:var(--muted) !important;white-space:nowrap;transform:none !important}
.st-key-mktabs button p{font-size:18px}
.st-key-mktabs button[kind=segmented_controlActive],.st-key-mktabs [data-testid=stBaseButton-segmented_controlActive]{
 color:var(--text) !important;font-weight:700;background:transparent !important;border-bottom:3px solid var(--accent) !important}
.st-key-mkfilters [data-testid=stVerticalBlock]{flex-direction:row !important;gap:8px !important;overflow-x:auto;scrollbar-width:none;margin-bottom:6px}
.st-key-mkfilters [data-testid=stElementContainer]{flex:0 0 auto !important;width:auto !important;min-width:150px}
.st-key-mkfilters [data-baseweb=select]>div{border-radius:14px !important;min-height:42px}

.mhead{display:flex;align-items:center;padding:12px 14px;font-size:14px;color:var(--muted);border-bottom:1px solid var(--border)}
.mhead span:first-child{flex:1}.mhead span:nth-child(2){width:104px;text-align:right}.mhead span:nth-child(3){width:96px;text-align:right}
.mlist{background:transparent}
.mrow2{display:flex;align-items:center;gap:10px;padding:13px 14px;border-bottom:1px solid color-mix(in srgb,var(--border) 60%,transparent)}
.mrow2.pin{background:var(--bg3);border-top:1px solid var(--border)}.mrow2:hover{background:var(--bg3)}
.mrow2 .rk{width:22px;text-align:center;font-size:14px;color:var(--muted);flex:0 0 22px}.pinic{display:inline-flex;opacity:.8}
.ico{width:36px;height:36px;border-radius:50%;background:var(--bg3);flex:0 0 36px;object-fit:cover}
.ico.ph{display:flex;align-items:center;justify-content:center;font-weight:700;color:var(--text)}.ico.brandico{background:transparent}
.mrow2 .nm{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}.mrow2 .nm b{font-size:17px;color:var(--text)}
.mrow2 .nm span{font-size:14px;color:var(--muted)}
.mrow2 .pr{width:104px;text-align:right;font-size:17px;font-weight:600;color:var(--text);flex:0 0 auto}
.mrow2 .ch{width:96px;flex:0 0 auto;display:flex;flex-direction:column;align-items:flex-end;gap:2px}.mrow2 .ch .spark{width:78px;height:30px}
.mcols{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-bottom:12px}
.mcol{background:var(--bg2);border:1px solid var(--border);border-radius:16px;padding:6px 14px 10px}
.mini{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 0;border-bottom:1px solid var(--border);font-size:14.5px;color:var(--text)}
.mini:last-child{border-bottom:0}
.appbar{display:flex;align-items:center;justify-content:space-between;padding:2px 2px 12px}
.appbar .ttl{font-family:'Space Grotesk','Inter',sans-serif;font-size:32px;font-weight:700;color:var(--text);line-height:1.1}
.appbar .acts{display:flex;gap:14px;align-items:center}
.appbar .ib{font-size:24px;line-height:1;opacity:.9}
.appbar .av{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:18px;color:#fff;
 background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 0 0 2px var(--border)}
@media (max-width:640px){.mrow2{padding:12px 10px;gap:8px}.mhead{padding:12px 10px}.mrow2 .pr{width:92px;font-size:16px}.mhead span:nth-child(2){width:92px}
 .mrow2 .ch{width:84px}.mrow2 .ch .spark{width:68px}.mhead span:nth-child(3){width:84px}.sc{padding:12px 13px}.sc .big{font-size:21px}.appbar .ttl{font-size:28px}}
"""
