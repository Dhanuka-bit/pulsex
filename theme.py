"""Colour themes. Applied with CSS variables so the user can pick any palette (and a custom accent) inside the app."""

PALETTES = {
    "Dark":     dict(bg="#0b0e14", bg2="#121824", bg3="#1a2233", text="#eaecef", muted="#8792a8", border="#25304a",
                     accent="#7c3aed", accent2="#22d3ee", up="#0ecb81", down="#f6465d", scheme="dark"),
    "Midnight": dict(bg="#070b1a", bg2="#0c1330", bg3="#141d45", text="#e6ecff", muted="#8a97c7", border="#25306b",
                     accent="#3b82f6", accent2="#22d3ee", up="#34d399", down="#fb7185", scheme="dark"),
    "Emerald":  dict(bg="#06100d", bg2="#0b1a15", bg3="#12261f", text="#e6f4ee", muted="#85a898", border="#1f3d32",
                     accent="#10b981", accent2="#a3e635", up="#34d399", down="#f87171", scheme="dark"),
    "Sunset":   dict(bg="#140c0f", bg2="#1d1217", bg3="#2a1a21", text="#fbeaee", muted="#b08a95", border="#43262f",
                     accent="#f97316", accent2="#f43f5e", up="#4ade80", down="#fb7185", scheme="dark"),
    "Light":    dict(bg="#f4f6fa", bg2="#ffffff", bg3="#eef1f6", text="#1b2330", muted="#667085", border="#d9dee7",
                     accent="#6d28d9", accent2="#0891b2", up="#059669", down="#dc2626", scheme="light"),
}


def css(name, accent=None):
    p = dict(PALETTES.get(name, PALETTES["Dark"]))
    if accent:
        p["accent"] = accent
    root = (":root{" + "".join(f"--{k}:{v};" for k, v in p.items() if k != "scheme")
            + f"color-scheme:{p['scheme']}" + "}")
    return "<style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&family=Space+Grotesk:wght@500;600;700&family=Noto+Sans+Sinhala:wght@400;600&display=swap');" + root + _STATIC + "</style>"


_STATIC = """
html,body,.stApp,[data-testid=stAppViewContainer],[data-testid=stMain]{background:var(--bg) !important;color:var(--text);
 font-family:'Inter','Noto Sans Sinhala',system-ui,sans-serif}
[data-testid=stHeader],[data-testid=stToolbar]{background:transparent !important}
[data-testid=stSidebar],[data-testid=stSidebar]>div:first-child{background:var(--bg2) !important}
[data-testid=stSidebar]{border-right:1px solid var(--border)}
.stApp :is(h1,h2,h3,h4,h5,h6){color:var(--text) !important;font-family:'Space Grotesk','Inter','Noto Sans Sinhala',sans-serif}
[data-testid=stMarkdownContainer] :is(p,li,strong,em,td,th,code){color:var(--text)}
[data-testid=stCaptionContainer],[data-testid=stCaptionContainer] *{color:var(--muted) !important}
[data-testid=stWidgetLabel],[data-testid=stWidgetLabel] *,.stApp label,[data-testid=stCheckbox] span,
[data-testid=stRadio] label *{color:var(--text) !important}
[data-testid=stMetric]{background:var(--bg2) !important;border:1px solid var(--border) !important}
[data-testid=stMetricLabel],[data-testid=stMetricLabel] *{color:var(--muted) !important}
[data-testid=stMetricValue],[data-testid=stMetricValue] *{color:var(--text) !important;font-family:'Space Grotesk','Inter',sans-serif}
input,textarea,[data-baseweb=select]>div,[data-baseweb=base-input],[data-baseweb=input]{background:var(--bg3) !important;
 color:var(--text) !important;border-color:var(--border) !important}
[data-baseweb=select] *,[data-baseweb=input] *{color:var(--text)}
[data-baseweb=select] svg,[data-baseweb=input] svg{fill:var(--muted) !important}
[data-baseweb=popover],[data-baseweb=popover]>div,[data-baseweb=menu],[role=listbox]{background:var(--bg2) !important;color:var(--text) !important}
[role=option]{color:var(--text) !important}[role=option]:hover,[aria-selected=true][role=option]{background:var(--bg3) !important}
.stButton>button,.stDownloadButton>button,[data-testid^=stBaseButton-secondary],[data-testid^=stBaseButton-segmented_control]{
 background:var(--bg3) !important;color:var(--text) !important;border:1px solid var(--border) !important}
.stButton>button[kind=primary],[data-testid=stBaseButton-primary]{background:linear-gradient(90deg,var(--accent),var(--accent2)) !important;
 color:#fff !important;border:0 !important;font-weight:700}
button[kind=segmented_controlActive],[data-testid=stBaseButton-segmented_controlActive]{
 background:linear-gradient(90deg,var(--accent),var(--accent2)) !important;color:#fff !important;border-color:transparent !important;
 box-shadow:0 0 14px color-mix(in srgb,var(--accent) 55%,transparent)}
[data-testid=stButtonGroup] button{padding:6px 14px;font-weight:600;transition:all .15s}
[data-testid=stButtonGroup] button:hover{transform:translateY(-1px)}
[data-testid=stExpander],[data-testid=stExpander] details{background:var(--bg2) !important;border-color:var(--border) !important}
[data-testid=stExpander] summary,[data-testid=stExpander] summary *{color:var(--text) !important}
[data-testid=stAlert]{border:1px solid var(--border)}
hr{border-color:var(--border) !important}
::-webkit-scrollbar{width:8px;height:8px}::-webkit-scrollbar-thumb{background:var(--border);border-radius:8px}
.num{font-family:'Space Grotesk','Inter',sans-serif;font-variant-numeric:tabular-nums}
"""
