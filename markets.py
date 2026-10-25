"""Markets home screen: stat cards, Fear & Greed gauge, filter pills, coin list with sparklines (CoinGecko data)."""
import base64
import math

import streamlit as st

import funda
import ui
from ui import esc

CG = "https://api.coingecko.com/api/v3"
CURRENCIES = {"USD": "$", "EUR": "€", "GBP": "£", "LKR": "Rs ", "INR": "₹", "AED": "AED ", "JPY": "¥"}
CATEGORIES = {"All": None, "Layer 1": "layer-1", "Layer 2": "layer-2", "DeFi": "decentralized-finance-defi", "Meme": "meme-token",
              "AI": "artificial-intelligence", "Gaming": "gaming", "RWA": "real-world-assets-rwa", "Stablecoins": "stablecoins"}
RANKS = [20, 50, 100, 200]
SORTS = ["Rank", "24h % (high to low)", "24h % (low to high)", "Volume", "Price"]


def top_coins(n=100, category=None, symbols=None):
    url = (f"{CG}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={min(n, 250)}&page=1"
           f"&sparkline=true&price_change_percentage=1h,24h,7d")
    if category:
        url += f"&category={category}"
    if symbols:
        url = (f"{CG}/coins/markets?vs_currency=usd&symbols={','.join(s.lower() for s in symbols)}&include_tokens=top"
               f"&order=market_cap_desc&per_page=250&sparkline=true&price_change_percentage=1h,24h,7d")
    data = funda._get(url, ttl=60)
    return data if isinstance(data, list) else None


def trending_ids():
    j = funda._get(f"{CG}/search/trending", ttl=300) or {}
    return [c["item"]["symbol"].upper() for c in (j.get("coins") or [])][:15]


def fx(cur):
    if cur == "USD":
        return 1.0
    rates = (funda._get("https://open.er-api.com/v6/latest/USD", ttl=3600) or {}).get("rates") or {}
    return float(rates.get(cur) or 1.0)


def _arc(cx, cy, r, a0, a1):
    p = lambda a: (cx + r * math.cos(math.radians(a)), cy - r * math.sin(math.radians(a)))
    (x0, y0), (x1, y1) = p(a0), p(a1)
    return f"M{x0:.1f} {y0:.1f} A{r} {r} 0 0 1 {x1:.1f} {y1:.1f}"


def gauge(v):
    """Semicircle Fear & Greed gauge as an image (returns <img>)."""
    segs = [(0, 25, "#f6465d"), (25, 45, "#f97316"), (45, 55, "#f0b90b"), (55, 75, "#84cc16"), (75, 100, "#0ecb81")]
    arcs = "".join(f"<path d='{_arc(100, 100, 80, 180 - a * 1.8, 180 - b * 1.8 + (0 if b == 100 else 1))}' stroke='{c}' stroke-width='14' fill='none'/>"
                   for a, b, c in segs)
    ang = math.radians(180 - v * 1.8)
    nx, ny = 100 + 62 * math.cos(ang), 100 - 62 * math.sin(ang)
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 118'>{arcs}"
           f"<line x1='100' y1='100' x2='{nx:.1f}' y2='{ny:.1f}' stroke='#eaecef' stroke-width='4' stroke-linecap='round'/>"
           f"<circle cx='100' cy='100' r='7' fill='#eaecef'/></svg>")
    return f"<img class='gauge' src='data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}'>"


def stat_cards(t, coins):
    g = (funda._get(f"{CG}/global") or {}).get("data") or {}
    fg = ((funda._get("https://api.alternative.me/fng/?limit=1") or {}).get("data") or [None])[0]
    mc = (g.get("total_market_cap") or {}).get("usd")
    top20 = (coins or [])[:20]
    capsum = sum((c.get("market_cap") or 0) for c in top20) or 1
    px20 = sum((c.get("price_change_percentage_24h") or 0) * (c.get("market_cap") or 0) for c in top20) / capsum if top20 else None
    ups = [1 for c in (coins or []) if (c.get("price_change_percentage_24h") or 0) > 0]
    share = (len(ups) / len(coins) * 100) if coins else None
    senti = None if share is None else (t("Bullish") if share > 60 else t("Bearish") if share < 40 else t("Neutral"))
    cards = [
        f"<div class='scard'><div class='lbl'>{esc(t('Market cap'))}</div><div class='big num'>{ui.compact(mc)}</div>{ui.pill(g.get('market_cap_change_percentage_24h_usd'))}</div>",
        f"<div class='scard'><div class='lbl'>PX20 {esc(t('index'))}</div><div class='big num'>{('%+.2f%%' % px20) if px20 is not None else '—'}</div>"
        f"<div class='sub'>{esc(t('Top 20 by market cap, weighted'))}</div></div>",
        f"<div class='scard'><div class='lbl'>{esc(t('Sentiment'))}</div><div class='big'>{esc(senti or '—')}</div>"
        f"<div class='sub'>{('%.0f%% ' % share) + esc(t('of top coins are up 24h')) if share is not None else ''}</div></div>",
    ]
    if fg:
        v = int(fg.get("value", 0))
        cards.append(f"<div class='scard fg'>{gauge(v)}<div class='fgv num'>{v}</div><div class='sub'>{esc(t('Fear & Greed'))} · {esc(fg.get('value_classification', ''))}</div></div>")
    return f"<div class='srow'>{''.join(cards)}</div>"


def _spark(c):
    prices = (c.get("sparkline_in_7d") or {}).get("price")
    return ui.sparkline(prices, (c.get("price_change_percentage_7d_in_currency") or c.get("price_change_percentage_24h") or 0) >= 0, 96, 34)


def rows_html(coins, sym, rate):
    out = []
    for i, c in enumerate(coins, 1):
        img = c.get("image") or ""
        ico = f"<img class='ico' src='{esc(img)}'>" if img.startswith("https://") else f"<span class='ico ph'>{esc((c.get('symbol') or '?')[:1].upper())}</span>"
        pr = c.get("current_price")
        pr_txt = "—" if pr is None else (f"{sym}{pr * rate:,.2f}" if pr * rate >= 1 else f"{sym}{pr * rate:.6f}".rstrip("0"))
        out.append(
            f"<div class='mrow'><div class='rk'>{c.get('market_cap_rank') or i}</div>{ico}"
            f"<div class='nm'><b>{esc((c.get('symbol') or '').upper())}</b><span>{esc(c.get('name') or '')} · {ui.compact((c.get('market_cap') or 0) * rate, sym)}</span></div>"
            f"<div class='sp'>{_spark(c)}</div>"
            f"<div class='pr'><b class='num'>{pr_txt}</b>{ui.pill(c.get('price_change_percentage_24h'))}</div></div>")
    return f"<div class='mlist'>{''.join(out)}</div>"


def mini_list(title, coins, sym, rate):
    rows = "".join(
        f"<div class='mini'><b>{esc((c.get('symbol') or '').upper())}</b><span class='num'>{sym}{(c.get('current_price') or 0) * rate:,.4g}</span>{ui.pill(c.get('price_change_percentage_24h'))}</div>"
        for c in coins)
    return f"<div class='mcol'><div class='sec'>{esc(title)}</div>{rows}</div>"


def render(t, preds_html=None):
    """The Markets page. preds_html: callable returning HTML for the 'Predictions' pill (app signals)."""
    tabs = ["top", "trending", "watch", "overview", "pred"]
    labels = {"top": t("Top"), "trending": t("Trending"), "watch": t("Watchlists"), "overview": t("Overview"), "pred": t("Predictions")}
    sel = st.segmented_control("mk_tab", tabs, format_func=lambda k: labels[k], key="mk_tab", label_visibility="collapsed",
                               **({} if "mk_tab" in st.session_state else {"default": "top"})) or "top"

    cur = st.session_state.get("mk_cur", "USD")
    rank_n = st.session_state.get("mk_rank", 100)
    cat = st.session_state.get("mk_cat", "All")
    sort = st.session_state.get("mk_sort", "Rank")
    with st.popover(f"{CURRENCIES.get(cur, '$').strip()} · Top {rank_n} · {cat} ⚙️", use_container_width=True):
        st.selectbox(t("Currency"), list(CURRENCIES), key="mk_cur", index=list(CURRENCIES).index(cur))
        st.selectbox(t("Rank"), RANKS, key="mk_rank", index=RANKS.index(rank_n) if rank_n in RANKS else 2, format_func=lambda n: f"Top {n}")
        st.selectbox(t("Categories"), list(CATEGORIES), key="mk_cat", index=list(CATEGORIES).index(cat))
        st.selectbox(t("Sort by"), SORTS, key="mk_sort", index=SORTS.index(sort), format_func=lambda s_: t(s_))
    sym, rate = CURRENCIES.get(cur, "$"), fx(cur)

    coins = top_coins(max(rank_n, 100), CATEGORIES.get(cat))
    if coins is None:
        st.warning(t("Market data is temporarily unavailable (rate limit). Please try again in a minute."))
        return
    st.markdown(stat_cards(t, top_coins(100) if cat != "All" else coins), unsafe_allow_html=True)

    shown = coins[:rank_n]
    if sel == "trending":
        want = trending_ids()
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
    st.markdown(rows_html(shown, sym, rate), unsafe_allow_html=True)
    st.caption(t("Data: CoinGecko, refreshed about every minute."))


def css():
    return """<style>
.srow{display:flex;gap:10px;overflow-x:auto;padding:2px 2px 12px;scrollbar-width:none}.srow::-webkit-scrollbar{display:none}
.scard{flex:0 0 auto;min-width:150px;background:linear-gradient(145deg,color-mix(in srgb,var(--bg2) 92%,transparent),color-mix(in srgb,var(--bg3) 70%,transparent));
 border:1px solid var(--border);border-radius:16px;padding:12px 14px;backdrop-filter:blur(10px)}
.scard .lbl{font-size:12px;color:var(--muted)}.scard .big{font-size:21px;font-weight:700;color:var(--text);margin:3px 0 5px;line-height:1.15}
.scard .sub{font-size:11.5px;color:var(--muted)}.scard.fg{min-width:170px;text-align:center;position:relative}
.gauge{width:128px;display:block;margin:0 auto}.fgv{font-size:24px;font-weight:700;color:var(--text);margin-top:-14px}
.mlist{background:color-mix(in srgb,var(--bg2) 88%,transparent);border:1px solid var(--border);border-radius:18px;overflow:hidden;backdrop-filter:blur(10px)}
.mrow{display:flex;align-items:center;gap:10px;padding:11px 14px;border-bottom:1px solid var(--border)}
.mrow:last-child{border-bottom:0}.mrow:hover{background:var(--bg3)}
.mrow .rk{width:24px;font-size:12px;color:var(--muted);text-align:center}
.ico{width:32px;height:32px;border-radius:50%;background:var(--bg3);flex:0 0 32px}.ico.ph{display:flex;align-items:center;justify-content:center;font-weight:700;color:var(--text)}
.mrow .nm{flex:1;min-width:0;display:flex;flex-direction:column}.mrow .nm b{font-size:15px;color:var(--text)}
.mrow .nm span{font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mrow .sp{flex:0 0 auto}.mrow .sp .spark{width:84px;height:30px}
.mrow .pr{flex:0 0 auto;text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:3px;min-width:96px}
.mrow .pr b{font-size:14.5px;color:var(--text)}.mrow .pr .pill{font-size:11.5px;padding:2px 8px}
.mcols{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-bottom:12px}
.mcol{background:var(--bg2);border:1px solid var(--border);border-radius:16px;padding:6px 14px 10px}
.mini{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid var(--border);font-size:14px;color:var(--text)}
.mini:last-child{border-bottom:0}
.appbar{display:flex;align-items:center;justify-content:space-between;padding:2px 2px 10px 46px;min-height:44px}
.appbar .ttl{font-family:'Space Grotesk','Inter',sans-serif;font-size:24px;font-weight:700;color:var(--text)}
.appbar .acts{display:flex;gap:8px;align-items:center}
.appbar .ib{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--bg3);border:1px solid var(--border);font-size:15px}
.appbar .av{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;
 background:linear-gradient(135deg,var(--accent),var(--accent2))}
@media (max-width:640px){.mrow{padding:10px 10px;gap:8px}.mrow .sp .spark{width:64px}.mrow .pr{min-width:84px}.scard{min-width:138px}}
</style>"""


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
