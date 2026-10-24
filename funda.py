"""Fundamentals page (coin overview in a market-data-site style) and the global market bar."""
import re
import threading
import time
from urllib.parse import urlparse

import requests
import streamlit as st

import ui
from ui import esc

_C, _L = {}, threading.Lock()


def _get(url, ttl=300):
    with _L:
        hit = _C.get(url)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    with _L:
        _C[url] = (time.time(), data)
    return data


def global_bar(t):
    """One-line market overview (total market cap, volume, dominance, fear & greed). Returns '' if unavailable."""
    g = (_get("https://api.coingecko.com/api/v3/global") or {}).get("data")
    fg = ((_get("https://api.alternative.me/fng/?limit=1") or {}).get("data") or [None])[0]
    if not g and not fg:
        return ""
    parts = []
    if g:
        mc = (g.get("total_market_cap") or {}).get("usd")
        vol = (g.get("total_volume") or {}).get("usd")
        dom = g.get("market_cap_percentage") or {}
        parts.append(f"<span>{esc(t('Market cap'))}<b>{ui.compact(mc)}</b>{ui.pill(g.get('market_cap_change_percentage_24h_usd'))}</span>")
        parts.append(f"<span>{esc(t('24h volume'))}<b>{ui.compact(vol)}</b></span>")
        parts.append(f"<span>BTC<b>{dom.get('btc', 0):.1f}%</b> ETH<b>{dom.get('eth', 0):.1f}%</b></span>")
    if fg:
        v = int(fg.get("value", 0))
        col = "var(--down)" if v < 40 else ("#f0b90b" if v < 60 else "var(--up)")
        parts.append(f"<span>{esc(t('Fear & Greed'))}<b style='color:{col}'>{v}</b>{esc(fg.get('value_classification', ''))}</span>")
    return f"<div class='gbar'>{''.join(parts)}</div>"


def _num(x, d=0):
    return "—" if x is None else f"{x:,.{d}f}"


def _link(url, label):
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return f"<a class='lnk' href='{esc(url)}' target='_blank' rel='noopener noreferrer'>{esc(label)}</a>"
    return ""


def render(j, t):
    md = j["market_data"]
    usd = lambda k: (md.get(k) or {}).get("usd")
    p, mc, vol, fdv = usd("current_price"), usd("market_cap"), usd("total_volume"), usd("fully_diluted_valuation")
    circ, tot, mx = md.get("circulating_supply"), md.get("total_supply"), md.get("max_supply")
    ch24 = md.get("price_change_percentage_24h")
    sym = (j.get("symbol") or "").upper()

    # ---- header: logo, name, rank, categories | price, 24h change, range, 7d sparkline
    img = (j.get("image") or {}).get("small") or ""
    cats = "".join(f"<span class='tag'>{esc(c)}</span>" for c in [c for c in (j.get("categories") or []) if c][:4])
    logo = f"<img class='logo' src='{esc(img)}'>" if img.startswith("https://") else ""
    rank = f"<span class='rank'>#{j['market_cap_rank']}</span>" if j.get("market_cap_rank") else ""
    spark = ui.sparkline(((md.get("sparkline_7d") or {}).get("price")), (md.get("price_change_percentage_7d") or 0) >= 0)
    lo, hi = usd("low_24h"), usd("high_24h")
    rng = ""
    if lo and hi:
        rng = (f"<div style='min-width:220px;margin-top:10px'>{ui.range_bar(lo, hi, p)}"
               f"<div class='rl'><span>{ui.price(lo)}</span><span>{esc(t('24h range'))}</span><span>{ui.price(hi)}</span></div></div>")
    st.markdown(
        f"<div class='cmc'><div class='left'>{logo}<div><div class='nm'>{esc(j.get('name', ''))}<span class='sym'>{esc(sym)}</span>{rank}</div>"
        f"<div>{cats}</div></div></div><div class='right'><div class='bigp num'>{ui.price(p)} {ui.pill(ch24)}</div>{rng}</div>"
        f"<div>{spark}<div class='rl'><span>{esc(t('7d price'))}</span></div></div></div>", unsafe_allow_html=True)

    # ---- key statistics
    st.markdown(ui.title(t("Key statistics")), unsafe_allow_html=True)
    ratio = (vol / mc) if mc and vol else None
    liq = ("🟢 " + t("High liquidity") if ratio > 0.1 else "🔴 " + t("Low liquidity") if ratio < 0.02 else "🟡 " + t("Normal liquidity")) if ratio else ""
    issued = (circ / mx * 100) if circ and mx else None
    cards = [
        ui.card(t("Market cap"), ui.compact(mc), ui.pill(md.get("market_cap_change_percentage_24h"))),
        ui.card(t("Fully diluted value"), ui.compact(fdv), (f"{fdv / mc:.1f}x " + t("market cap")) if fdv and mc else ""),
        ui.card(t("24h volume"), ui.compact(vol)),
        ui.card(t("Volume / market cap"), f"{ratio:.2%}" if ratio else "—", esc(liq)),
        ui.card(t("Circulating supply"), f"{_num(circ)} <small>{esc(sym)}</small>", ui.progress(issued) if issued else ""),
        ui.card(t("Total supply"), _num(tot)),
        ui.card(t("Max supply"), _num(mx) if mx else "∞", f"{issued:.0f}% " + t("issued") if issued else esc(t("No hard cap"))),
    ]
    st.markdown(ui.grid(cards), unsafe_allow_html=True)

    # ---- price performance
    st.markdown(ui.title(t("Price performance")), unsafe_allow_html=True)
    per = [("1h", (md.get("price_change_percentage_1h_in_currency") or {}).get("usd")), ("24h", ch24),
           ("7d", md.get("price_change_percentage_7d")), ("14d", md.get("price_change_percentage_14d")),
           ("30d", md.get("price_change_percentage_30d")), ("60d", md.get("price_change_percentage_60d")),
           ("200d", md.get("price_change_percentage_200d")), ("1y", md.get("price_change_percentage_1y"))]
    st.markdown(ui.grid([ui.card(k, ui.pill(v, 1)) for k, v in per], 105), unsafe_allow_html=True)

    # ---- all-time high / low
    ath, atl = usd("ath"), usd("atl")
    if ath and atl:
        d = lambda key: ((md.get(key) or {}).get("usd") or "")[:10]
        pos = ui.range_bar(atl, ath, p)
        st.markdown(ui.grid([
            ui.card(t("All-time high"), ui.price(ath), f"{d('ath_date')} · {ui.pill((md.get('ath_change_percentage') or {}).get('usd'), 1)}"),
            ui.card(t("All-time low"), ui.price(atl), f"{d('atl_date')} · {ui.pill((md.get('atl_change_percentage') or {}).get('usd'), 0)}"),
            ui.card(t("Position between ATL and ATH"), "", pos + f"<div class='rl'><span>ATL</span><span>ATH</span></div>"),
        ], 230), unsafe_allow_html=True)

    # ---- quick health check
    st.markdown(ui.title(t("Quick health check")), unsafe_allow_html=True)
    checks = []
    if ratio is not None:
        checks.append(("g" if ratio > 0.1 else "r" if ratio < 0.02 else "y", t(f"Volume / market cap is {ratio:.1%} (liquidity)")))
    if issued is not None:
        checks.append(("g" if issued > 80 else "y", t(f"{issued:.0f}% of the max supply is already issued")))
    else:
        checks.append(("y", t("No supply cap, so inflation is possible")))
    if fdv and mc and fdv / mc > 2:
        checks.append(("r" if fdv / mc > 4 else "y", t(f"Fully diluted value is {fdv / mc:.1f}x the market cap, so future unlocks can add selling pressure")))
    dev = j.get("developer_data") or {}
    cm = dev.get("commit_count_4_weeks")
    if cm is not None:
        checks.append(("g" if cm > 50 else "r" if cm == 0 else "y", t(f"{cm} developer commits in the last 4 weeks")))
    if ath and p and p < ath * 0.2:
        checks.append(("y", t("Price is more than 80% below its all-time high")))
    st.markdown("".join(f"<div class='chk {c}'>{esc(x)}</div>" for c, x in checks), unsafe_allow_html=True)

    # ---- sentiment, community, developers
    st.markdown(ui.title(t("Community and development")), unsafe_allow_html=True)
    up = j.get("sentiment_votes_up_percentage")
    com = j.get("community_data") or {}
    cc = []
    if up is not None:
        cc.append(ui.card(t("Community sentiment"), f"{up:.0f}% 👍", ui.progress(up, "g")))
    for key, lbl in (("twitter_followers", "X / Twitter " + t("followers")), ("reddit_subscribers", "Reddit " + t("members")),
                     ("telegram_channel_user_count", "Telegram " + t("members"))):
        if com.get(key):
            cc.append(ui.card(lbl, _num(com[key])))
    for key, lbl in (("stars", "GitHub ⭐"), ("forks", "GitHub forks"), ("commit_count_4_weeks", t("Commits (4 weeks)")),
                     ("pull_requests_merged", t("Merged pull requests"))):
        if dev.get(key) is not None:
            cc.append(ui.card(lbl, _num(dev[key])))
    if cc:
        st.markdown(ui.grid(cc, 150), unsafe_allow_html=True)

    # ---- about + links
    desc = re.sub(r"<[^>]+>", "", (j.get("description") or {}).get("en") or "").strip()
    meta = []
    if j.get("genesis_date"):
        meta.append(f"{esc(t('Launched'))}: <b>{esc(j['genesis_date'])}</b>")
    if j.get("hashing_algorithm"):
        meta.append(f"{esc(t('Algorithm'))}: <b>{esc(j['hashing_algorithm'])}</b>")
    if desc or meta:
        st.markdown(ui.title(t("About")), unsafe_allow_html=True)
        text = esc(desc[:700] + ("…" if len(desc) > 700 else ""))
        st.markdown(f"<div class='about'>{text}<div style='margin-top:10px;color:var(--muted)'>{' · '.join(meta)}</div></div>", unsafe_allow_html=True)
    lk = j.get("links") or {}
    links = [_link((lk.get("homepage") or [""])[0], t("Website"))]
    wp = lk.get("whitepaper")
    links.append(_link(wp, t("Whitepaper")) if isinstance(wp, str) else "")
    for u in [x for x in (lk.get("blockchain_site") or []) if x][:3]:
        links.append(_link(u, urlparse(u).netloc.replace("www.", "")[:24] or "Explorer"))
    if lk.get("twitter_screen_name"):
        links.append(_link("https://x.com/" + lk["twitter_screen_name"], "X / Twitter"))
    links.append(_link(lk.get("subreddit_url"), "Reddit"))
    links.append(_link(((lk.get("repos_url") or {}).get("github") or [""])[0], "GitHub"))
    if any(links):
        st.markdown(ui.title(t("Links")) + "".join(links), unsafe_allow_html=True)
    st.caption(t("Data: CoinGecko. Not financial advice."))
