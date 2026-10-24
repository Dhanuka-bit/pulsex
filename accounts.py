"""Optional accounts + personal portfolio (Supabase). Signals work without login."""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone


def _cfg():
    try:
        return st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    except Exception:
        return None


def enabled():
    return _cfg() is not None


def _client():
    if "sb" not in st.session_state:
        from supabase import create_client
        url, key = _cfg()
        st.session_state["sb"] = create_client(url, key)
    return st.session_state["sb"]


def user():
    return st.session_state.get("user")


def sidebar_box(t):
    if not enabled():
        return
    u = user()
    if u:
        st.sidebar.success("👤 " + u["email"])
        if st.sidebar.button(t("Log out", "ලොග් අවුට්")):
            try:
                _client().auth.sign_out()
            except Exception:
                pass
            for k in ("user", "sb"):
                st.session_state.pop(k, None)
            st.rerun()
        return
    with st.sidebar.expander(t("👤 Login / Create account (optional)", "👤 ලොගින් / ගිණුමක් හදන්න (අනිවාර්ය නැත)")):
        mode = st.radio("", [t("Login", "ලොගින්"), t("Sign up", "ගිණුම හදන්න")], horizontal=True, label_visibility="collapsed")
        email = st.text_input("Email")
        pw = st.text_input(t("Password (min 6)", "මුරපදය (අවම 6)"), type="password")
        if st.button(t("Continue", "ඉදිරියට"), type="primary"):
            try:
                sb = _client()
                if mode == t("Login", "ලොගින්"):
                    res = sb.auth.sign_in_with_password({"email": email.strip(), "password": pw})
                    st.session_state["user"] = {"id": res.user.id, "email": res.user.email}
                    st.rerun()
                else:
                    res = sb.auth.sign_up({"email": email.strip(), "password": pw})
                    if res.session:
                        st.session_state["user"] = {"id": res.user.id, "email": res.user.email}
                        st.rerun()
                    else:
                        st.success(t("Account created. Check your email and click the confirmation link, then log in.",
                                     "ගිණුම හැදුවා. ඊමේල් එක බලලා confirmation link එක click කරලා ඉන්පස්සේ ලොගින් වෙන්න."))
            except Exception as e:
                st.error(t("Failed: ", "අසාර්ථකයි: ") + str(e))


def portfolio_tab(t, mk, fmt):
    if not enabled():
        st.info(t("Portfolio is not enabled on this server.", "Portfolio මෙම server එකේ සක්‍රීය කර නැත."))
        return
    u = user()
    if not u:
        st.info(t("Signals are free for everyone. Log in (sidebar) to keep your own portfolio.",
                  "Signals හැමෝටම නොමිලේ. ඔබේම portfolio එකක් තියාගන්න sidebar එකෙන් ලොගින් වෙන්න."))
        return
    sb = _client()
    price = dict(zip(mk.base, mk.price))

    with st.expander(t("➕ Add a position", "➕ position එකක් එකතු කරන්න")):
        with st.form("addpos", clear_on_submit=True):
            a, b, c = st.columns(3)
            coin = a.selectbox("Coin", list(dict.fromkeys(mk.base)))
            side = b.selectbox("Side", ["LONG", "SHORT"])
            entry = c.number_input(t("Entry price", "Entry මිල"), min_value=0.0, format="%.8f")
            d, e, f = st.columns(3)
            size = d.number_input(t("Position size (USDT)", "Position ප්‍රමාණය (USDT)"), min_value=1.0, value=100.0)
            stop = e.number_input("Stop-loss (0 = none)", min_value=0.0, format="%.8f")
            tp = f.number_input("Take-profit (0 = none)", min_value=0.0, format="%.8f")
            note = st.text_input(t("Note", "සටහන"))
            if st.form_submit_button(t("Save", "සුරකින්න"), type="primary"):
                if entry <= 0:
                    st.error(t("Enter the entry price.", "Entry මිල ඇතුල් කරන්න."))
                else:
                    try:
                        sb.table("positions").insert({"coin": coin, "side": side, "entry": entry, "size": size,
                                                      "stop": stop or None, "tp": tp or None, "note": note}).execute()
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))
    try:
        rows = sb.table("positions").select("*").order("opened_at", desc=True).execute().data
    except Exception as ex:
        st.error(t("Could not load portfolio (try logging in again): ", "Portfolio load කළ නොහැක (නැවත ලොගින් වන්න): ") + str(ex))
        return
    if not rows:
        st.info(t("No positions yet.", "තවම positions නැත."))
        return
    df = pd.DataFrame(rows)

    def pnl(r, p):
        d = 1 if r["side"] == "LONG" else -1
        return (p - r["entry"]) / r["entry"] * r["size"] * d

    op = df[df.status == "open"].copy()
    cl = df[df.status == "closed"].copy()
    op["now"] = op.coin.map(price)
    op["pnl"] = [pnl(r, r["now"]) if r["now"] else 0.0 for _, r in op.iterrows()]
    cl["pnl"] = [pnl(r, r["close_price"]) for _, r in cl.iterrows()]
    m = st.columns(4)
    m[0].metric(t("Open PnL (USDT)", "විවෘත PnL (USDT)"), f"{op.pnl.sum():+,.2f}")
    m[1].metric(t("Realized PnL (USDT)", "ලැබූ PnL (USDT)"), f"{cl.pnl.sum():+,.2f}")
    m[2].metric(t("Closed trades", "වසා දැමූ trades"), len(cl))
    m[3].metric(t("Win rate", "ජය අනුපාතය"), f"{(cl.pnl > 0).mean():.0%}" if len(cl) else "-")

    st.subheader(t("Open positions", "විවෘත positions"))
    if op.empty:
        st.caption("-")
    else:
        st.dataframe(op[["id", "coin", "side", "entry", "now", "size", "pnl", "stop", "tp", "note"]],
                     use_container_width=True, hide_index=True)
        a, b, c = st.columns([2, 2, 1])
        pid = a.selectbox("ID", list(op.id), key="pid")
        cp = b.number_input(t("Close price", "වසන මිල"), min_value=0.0, format="%.8f",
                            value=float(price.get(op[op.id == pid].coin.iloc[0], 0.0)), key=f"cp{pid}")
        if c.button(t("Close", "වසන්න"), type="primary") and cp > 0:
            sb.table("positions").update({"status": "closed", "close_price": cp,
                                          "closed_at": datetime.now(timezone.utc).isoformat()}).eq("id", int(pid)).execute()
            st.rerun()
    st.subheader(t("History", "ඉතිහාසය"))
    if not cl.empty:
        st.dataframe(cl[["id", "coin", "side", "entry", "close_price", "size", "pnl", "note"]],
                     use_container_width=True, hide_index=True)
    dl = st.selectbox(t("Delete a position (ID)", "position එකක් මකන්න (ID)"), [None] + list(df.id), key="del")
    if dl is not None and st.button(t("Delete", "මකන්න")):
        sb.table("positions").delete().eq("id", int(dl)).execute()
        st.rerun()
