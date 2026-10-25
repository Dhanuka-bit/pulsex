"""CSS injection helper + app-shell styling (bottom navigation, floating button, drawer, header fixes)."""
import json
import re

import streamlit as st

NAV_ICONS = {"markets": "candlestick_chart", "alpha": "sensors", "search": "search", "port": "pie_chart", "community": "forum"}


def inject(*blocks):
    """Inject CSS without letting the markdown parser touch it (st.html), minified into one stylesheet."""
    css = " ".join(blocks)
    css = re.sub(r"</?style>", " ", css)
    imports = []

    def grab(m):
        if m.group(0) not in imports:
            imports.append(m.group(0))
        return ""
    css = re.sub(r"@import\s+url\([^)]*\)\s*;", grab, css)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s*\n\s*", " ", css).strip()
    html = "<style>" + "".join(imports) + css + "</style>"
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def icon_label_css(key, label, active=False):
    """Label text under a material icon button, generated from Python so it can be translated."""
    out = (f".st-key-{key} button p::after{{content:{json.dumps(label, ensure_ascii=False)};display:block;font-size:10.5px;"
           f"font-weight:600;margin-top:3px;line-height:1.1;white-space:nowrap}}")
    if active:
        out += f".st-key-{key} button{{color:var(--accent) !important}}"
    return out


def shell_css(active, labels, tile_labels):
    css = _SHELL
    for k, lab in labels.items():
        css += icon_label_css(f"nav_{k}", lab, k == active)
    for k, lab in tile_labels.items():
        css += icon_label_css(f"tile_{k}", lab)
    return css


_SHELL = """
[data-testid=stElementContainer]:has(> [data-testid=stHtml]),.stHtml{display:none !important}
[data-testid=stToolbar],[data-testid=stDecoration],[class*="viewerBadge"],[class*="_profileContainer"],[data-testid=manage-app-button],
[data-testid=stStatusWidget]{display:none !important}
[data-testid=stHeader]{background:transparent !important;height:2.6rem}
.block-container{padding-top:3.2rem !important;padding-bottom:104px !important;max-width:980px}
[data-testid=stSidebarCollapsedControl] button,[data-testid=stExpandSidebarButton],[data-testid=stSidebarCollapseButton] button{
 background:var(--bg3) !important;border:1px solid var(--border) !important;border-radius:12px !important;color:var(--text) !important}

.st-key-bottomnav{position:fixed !important;left:0 !important;right:0 !important;bottom:0 !important;top:auto !important;width:100% !important;z-index:1001;
 padding:4px 4px calc(4px + env(safe-area-inset-bottom));background:color-mix(in srgb,var(--bg2) 92%,transparent);
 backdrop-filter:blur(16px);border-top:1px solid var(--border)}
.st-key-bottomnav [data-testid=stVerticalBlock]{flex-direction:row !important;gap:0 !important;width:100%}
.st-key-bottomnav [data-testid=stElementContainer]{flex:1 1 0 !important;min-width:0 !important;width:auto !important}
.st-key-bottomnav button,.st-key-tiles button{width:100% !important;height:auto !important;min-height:54px;padding:5px 0 !important;border:0 !important;
 background:transparent !important;box-shadow:none !important;color:var(--muted) !important}
.st-key-bottomnav button p,.st-key-tiles button p{display:flex;flex-direction:column;align-items:center;margin:0;font-size:10px}
.st-key-bottomnav [data-testid=stIconMaterial],.st-key-tiles [data-testid=stIconMaterial]{font-size:26px !important}

.st-key-fabwrap{position:fixed !important;right:14px !important;left:auto !important;bottom:86px !important;top:auto !important;
 width:56px !important;z-index:1002}
.st-key-fabwrap [data-testid=stElementContainer]{width:56px !important}
.st-key-fabwrap button{width:56px !important;height:56px !important;min-height:0;padding:0 !important;border-radius:50% !important;border:0 !important;
 color:#fff !important;background:linear-gradient(135deg,var(--accent),var(--accent2)) !important;box-shadow:0 8px 24px rgba(0,0,0,.45)}
.st-key-fabwrap [data-testid=stIconMaterial]{font-size:28px !important}

[data-testid=stSidebar]>div:first-child{padding-top:.4rem}
[data-testid=stSidebarContent]{padding:.2rem .9rem 2rem}
.acct{display:flex;align-items:center;gap:14px;padding:6px 2px 12px}
.acct .av{width:58px;height:58px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:700;color:#fff;
 background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 35%,transparent)}
.acct b{display:block;font-size:20px;color:var(--text);font-family:'Space Grotesk','Inter',sans-serif}
.acct span{font-size:12.5px;color:var(--muted);overflow-wrap:anywhere}
.st-key-tiles [data-testid=stVerticalBlock]{flex-direction:row !important;gap:4px !important}
.st-key-tiles [data-testid=stElementContainer]{flex:1 1 0 !important;min-width:0 !important;width:auto !important}
.st-key-drawerset,.st-key-drawertrade:has(.dh){background:var(--bg3);border:1px solid var(--border);border-radius:18px;padding:12px 14px;margin:10px 0}
.dh{font-size:12px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);margin:2px 0 6px}
.st-key-drawerfoot{margin-top:10px}
.st-key-logout button{width:100%;justify-content:flex-start;border-radius:16px !important;padding:14px 16px !important;font-weight:600}
.dfoot{text-align:center;color:var(--muted);font-size:12px;padding:12px 0}

@media (min-width:900px){
 .st-key-bottomnav{position:static !important;border:1px solid var(--border);border-radius:16px;margin-bottom:12px;width:auto !important}
 .block-container{padding-bottom:3rem !important}.st-key-fabwrap{bottom:24px !important}
}
"""
