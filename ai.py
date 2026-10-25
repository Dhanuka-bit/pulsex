"""PULSEX AI assistant: chat UI + pluggable backend (Claude API if a key is set, otherwise built-in rules over live app data)."""
import re
import time

import requests
import streamlit as st

SYSTEM = (
    "You are PULSEX AI, the assistant inside the PulseX crypto signals app (Software owners). "
    "Help users understand markets, the app's signals (LONG/SHORT/WAIT, strength, grade, entry/stop-loss/take-profits), "
    "technical indicators, risk management, and how to use the app (Markets, Alpha = Signal/Scanner/New listings, Search, Portfolio, Community, Login). "
    "Use ONLY numbers from the LIVE CONTEXT block for prices and signals; if something is missing say so. "
    "Be concise (under 180 words unless asked), reply in the user's language, use short bullets when helpful. "
    "Never promise profits or certainty, never tell people to go all-in; when you discuss a trade idea, mention stop-loss and position sizing once. "
    "You are not a financial advisor.")

CHIPS = ["Analyze BTC trend", "Explain the 5m scalping signal", "How to use the Market Scanner?", "How is risk per trade calculated?"]
INDICATORS = {
    "rsi": "RSI measures momentum from 0-100. Above 70 is stretched upward, below 30 stretched downward. In strong trends it can stay extreme, so PulseX only uses it for mean reversion in ranging markets.",
    "macd": "MACD compares two moving averages; its histogram shows whether momentum is rising or fading.",
    "ema": "EMAs are moving averages that weight recent prices. PulseX checks the EMA9/21/50/200 stack to judge short, medium and long trend.",
    "supertrend": "Supertrend is an ATR-based trailing line. Price above it = bullish trend, below = bearish; it also works as a trailing stop idea.",
    "ichimoku": "Ichimoku draws a cloud. Price above the cloud is bullish, below is bearish, inside means no clear trend.",
    "adx": "ADX measures trend strength (not direction). Above ~22 PulseX treats the market as trending, below as ranging.",
    "obv": "OBV adds volume on up candles and subtracts it on down candles; rising OBV means buyers are backing the move.",
    "mfi": "MFI is a volume-weighted RSI. Above 80 / below 20 hints at exhaustion.",
    "atr": "ATR is the average candle range. PulseX sizes stop-losses in multiples of ATR so they adapt to volatility.",
    "vwap": "VWAP is the volume-weighted average price. Price above it shows buyers in control for the session.",
}
NAMES = {"BITCOIN": "BTC", "ETHEREUM": "ETH", "SOLANA": "SOL", "RIPPLE": "XRP", "DOGECOIN": "DOGE", "CARDANO": "ADA", "BINANCE": "BNB"}


def _secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def backend_name():
    return "Claude API" if _secret("ANTHROPIC_API_KEY") else "built-in assistant"


def llm_answer(history, ctx):
    key = _secret("ANTHROPIC_API_KEY")
    if not key:
        return None
    msgs = [{"role": m["role"], "content": m["content"]} for m in history[-10:] if m["role"] in ("user", "assistant")]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=45,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                          json={"model": _secret("AI_MODEL", "claude-haiku-5-5"), "max_tokens": 700,
                                "system": SYSTEM + "\n\nLIVE CONTEXT:\n" + ctx, "messages": msgs})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip() or None
    except Exception:
        return None


def _coin_in(q, coins):
    s = set(coins)
    for w in re.findall(r"[A-Za-z0-9]{2,10}", q):
        if w.upper() in NAMES:
            return NAMES[w.upper()]
        if w.upper() in s:
            return w.upper()
    return None


def local_answer(q, coins, analyze, ctx):
    ql = q.lower()
    sym = _coin_in(q, coins)
    if sym and re.search(r"analy|trend|signal|long|short|buy|sell|price|entry|stop|target|outlook|how is", ql):
        tf = 5 if re.search(r"\b(1m|3m|5m|scalp)", ql) else 15 if "15m" in ql else 240 if re.search(r"4h|swing", ql) else 60
        try:
            a = analyze(sym, tf)
        except Exception:
            return f"I could not load live data for {sym} right now. Try again in a moment or open Alpha > Signal."
        arrow = "🟢" if a["side"] == "LONG" else "🔴" if a["side"] == "SHORT" else "🟡"
        lines = [f"**{sym}/USDT · {a['tf']}** - {arrow} **{a['side']}** (strength {a['strength']:.0f}%)",
                 f"- Price {a['price']:,.6g}; regime: {'trending' if a['adx'] >= 22 else 'ranging'} (ADX {a['adx']:.0f}), RSI {a['rsi']:.0f}",
                 f"- Higher-timeframe trend: {'up' if a['htf'] > 0 else 'down' if a['htf'] < 0 else 'mixed'}; Supertrend {'bullish' if a['st'] > 0 else 'bearish'}"]
        if a["side"] != "WAIT":
            lines.append(f"- Idea: entry ~{a['price']:,.6g}, stop-loss {a['sl']:,.6g}, TP1 {a['tp1']:,.6g}, TP2 {a['tp2']:,.6g}")
            lines.append("- Always size the position so a stop-loss costs only 1% of your account.")
        else:
            lines.append("- No clear edge right now, so waiting is a valid position.")
        lines.append("_Quick analysis only. The Alpha > Signal page applies stricter filters (higher timeframes, funding, backtest)._")
        return "\n".join(lines)
    for k, v in INDICATORS.items():
        if re.search(rf"\b{k}\b", ql):
            return v
    if re.search(r"scalp|5m|1m|signal", ql):
        return ("**Scalping signals (1m-5m)** are fast and noisy. PulseX scores 10+ indicators, checks the higher timeframes, funding and order book, "
                "then shows LONG/SHORT only when most agree. Use tight stops, small size, and expect many small losses; check the 'Reality check' win rate for that pair.")
    if re.search(r"scanner|scan", ql):
        return "**Market Scanner:** Alpha > Scanner > pick a timeframe > choose how many pairs > *Scan now*. It ranks coins by signal strength; tap a coin to open its full analysis."
    if re.search(r"risk|position|size|leverage|stop", ql):
        return ("**Risk per trade:** position size = (balance x risk%) / (entry - stop-loss). Example: $1,000 account, 1% risk = $10 at stake. "
                "If the stop is 2% away, size = $500 notional. Set balance and risk in Advanced settings; the signal page then shows the exact size.")
    if re.search(r"fear|greed|market|sentiment|dominance", ql):
        return "**Market context** (live):\n" + ctx
    if re.search(r"login|account|sign ?up|portfolio|watchlist", ql):
        return "Open the sidebar menu (top-left) > *Login / Create account*. With an account you can keep your own portfolio; signals work without one. The watchlist is saved in the page link."
    return ("I can help with:\n- **Coin analysis** (e.g. *Analyze ETH trend*)\n- **Explaining indicators** (RSI, MACD, Supertrend, ADX...)\n"
            "- **Risk and position sizing**\n- **Using the app** (Scanner, Portfolio, login)\nWhat would you like to know?")


def render(t, coins, analyze, ctx_fn):
    st.markdown("<div class='aihead'><div class='aiav'>⚡</div><div><b>PULSEX AI</b><span>" + t("Crypto trading assistant") + " · " + backend_name() + "</span></div></div>",
                unsafe_allow_html=True)
    msgs = st.session_state.setdefault("ai_msgs", [{"role": "assistant", "ts": time.strftime("%H:%M"),
                                                    "content": t("Hi! I'm PULSEX AI. Ask me about a coin, an indicator, risk management, or how to use the app.")}])
    with st.container(key="aichips"):
        for i, c in enumerate(CHIPS):
            st.button(t(c), key=f"chip{i}", on_click=lambda c=c: st.session_state.__setitem__("ai_q", c))
    with st.form("aiform", clear_on_submit=True):
        a, b = st.columns([6, 1])
        q = a.text_input("q", placeholder=t("Ask PULSEX AI..."), label_visibility="collapsed")
        sent = b.form_submit_button("➤")
    pending = st.session_state.pop("ai_q", None) or (q.strip() if sent and q.strip() else None)

    def bubble(m):
        with st.chat_message(m["role"], avatar="⚡" if m["role"] == "assistant" else "🧑"):
            st.markdown(m["content"])
            st.caption(m.get("ts", "") + " UTC")
    for m in msgs:
        bubble(m)
    if pending:
        um = {"role": "user", "content": pending, "ts": time.strftime("%H:%M")}
        msgs.append(um)
        bubble(um)
        with st.chat_message("assistant", avatar="⚡"):
            ph = st.empty()
            ph.markdown("<div class='typing'><i></i><i></i><i></i> <span>" + t("PULSEX AI is thinking...") + "</span></div>", unsafe_allow_html=True)
            ctx = ctx_fn()
            ans = llm_answer(msgs, ctx) or local_answer(pending, coins, analyze, ctx)
            if st.session_state.get("lang") not in (None, "English") and backend_name() != "Claude API":
                ans = t(ans)
            ph.markdown(ans)
            st.caption(time.strftime("%H:%M") + " UTC")
        msgs.append({"role": "assistant", "content": ans, "ts": time.strftime("%H:%M")})
    st.caption(t("AI can make mistakes. Not financial advice."))


def css():
    return """<style>
.aihead{display:flex;align-items:center;gap:12px;padding:10px 4px 12px}.aihead b{font-size:18px;color:var(--text);display:block}
.aihead span{font-size:12px;color:var(--muted)}
.aiav{width:42px;height:42px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:20px;color:#fff;
 background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 0 18px color-mix(in srgb,var(--accent) 50%,transparent)}
.st-key-aichips [data-testid=stVerticalBlock]{flex-direction:row;flex-wrap:wrap;gap:8px}
.st-key-aichips button{border-radius:999px !important;font-size:13px;padding:4px 12px}
[data-testid=stChatMessage]{background:color-mix(in srgb,var(--bg2) 85%,transparent);border:1px solid var(--border);border-radius:16px;backdrop-filter:blur(8px)}
.typing{display:flex;align-items:center;gap:5px;color:var(--muted);font-size:13px}
.typing i{width:7px;height:7px;border-radius:50%;background:var(--accent2);animation:tp 1.1s infinite ease-in-out}
.typing i:nth-child(2){animation-delay:.18s}.typing i:nth-child(3){animation-delay:.36s}
@keyframes tp{0%,80%,100%{transform:scale(.5);opacity:.4}40%{transform:scale(1);opacity:1}}
</style>"""
