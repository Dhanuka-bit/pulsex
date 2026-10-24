"""Brand assets for the app: logo, hero artwork (SVG, generated), optional photo, CSS."""
import base64
import os
import random

_HERE = os.path.dirname(os.path.abspath(__file__))


def _b64svg(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


LOGO_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
<defs>
<linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#a78bfa'/><stop offset='1' stop-color='#22d3ee'/></linearGradient>
<linearGradient id='f' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#2e1065'/><stop offset='1' stop-color='#0b0e11'/></linearGradient>
</defs>
<path d='M32 3 58 18v28L32 61 6 46V18z' fill='url(#f)' stroke='url(#g)' stroke-width='3' stroke-linejoin='round'/>
<path d='M13 35h9l5-15 8 27 6-19 3 7h7' fill='none' stroke='url(#g)' stroke-width='3.6' stroke-linecap='round' stroke-linejoin='round'/>
<circle cx='51' cy='35' r='2.6' fill='#22d3ee'/>
</svg>"""


def logo_img(px=48):
    return f"<img src='{_b64svg(LOGO_SVG)}' width='{px}' height='{px}' style='display:block'>"


def _wordmark(name):
    n = name.upper()
    return f"{n[:-1]}<span>{n[-1]}</span>"


def sidebar_logo(name):
    return (f"<div style='display:flex;align-items:center;gap:10px;padding:4px 0 10px'>{logo_img(40)}"
            f"<div><div class='brand-sm'>{_wordmark(name)}</div>"
            f"<div style='font-size:11px;color:#848e9c;margin-top:-2px'>by Software owners</div></div></div>")


def hero_art():
    """Glowing rising candlestick chart + orbit rings + coin, drawn procedurally."""
    rnd = random.Random(11)
    W, H, n, x0 = 900, 300, 30, 330
    step = (W - x0 - 40) / n
    price, cs = 100.0, []
    for _ in range(n):
        o = price
        c = o + rnd.uniform(-9, 13) + 2.4
        cs.append((o, c, max(o, c) + rnd.uniform(2, 9), min(o, c) - rnd.uniform(2, 9)))
        price = c
    lo, hi = min(c[3] for c in cs), max(c[2] for c in cs)
    y = lambda v: 262 - (v - lo) / (hi - lo) * 205
    body, line = [], []
    for i, (o, c, h, l) in enumerate(cs):
        x = x0 + i * step + step / 2
        col = "#0ecb81" if c >= o else "#f6465d"
        body.append(f"<line x1='{x:.1f}' x2='{x:.1f}' y1='{y(h):.1f}' y2='{y(l):.1f}' stroke='{col}' stroke-width='1.6'/>")
        body.append(f"<rect x='{x - step * .3:.1f}' y='{y(max(o, c)):.1f}' width='{step * .6:.1f}' "
                    f"height='{max(abs(y(o) - y(c)), 2):.1f}' rx='1.5' fill='{col}'/>")
        line.append((x, y(c)))
    avg = []
    for i in range(len(line)):
        seg = line[max(0, i - 3): i + 1]
        avg.append((line[i][0], sum(p[1] for p in seg) / len(seg)))
    pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in avg)
    area = f"{avg[0][0]:.1f},290 {pts} {avg[-1][0]:.1f},290"
    grid = "".join(f"<line x1='300' x2='{W}' y1='{gy}' y2='{gy}' stroke='#ffffff' stroke-opacity='.05'/>" for gy in range(50, 290, 45))
    return f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}' preserveAspectRatio='xMaxYMid slice'>
<defs>
<linearGradient id='a' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#22d3ee' stop-opacity='.35'/><stop offset='1' stop-color='#22d3ee' stop-opacity='0'/></linearGradient>
<linearGradient id='l' x1='0' y1='0' x2='1' y2='0'><stop offset='0' stop-color='#7c3aed'/><stop offset='1' stop-color='#22d3ee'/></linearGradient>
<radialGradient id='r1' cx='.5' cy='.5' r='.5'><stop offset='0' stop-color='#7c3aed' stop-opacity='.55'/><stop offset='1' stop-color='#7c3aed' stop-opacity='0'/></radialGradient>
<radialGradient id='c' cx='.35' cy='.3' r='.8'><stop offset='0' stop-color='#c4b5fd'/><stop offset='1' stop-color='#4c1d95'/></radialGradient>
<filter id='b' x='-20%' y='-20%' width='140%' height='140%'><feGaussianBlur stdDeviation='5'/></filter>
</defs>
<circle cx='760' cy='60' r='170' fill='url(#r1)'/><circle cx='420' cy='300' r='150' fill='url(#r1)' opacity='.6'/>
{grid}
<ellipse cx='790' cy='78' rx='95' ry='34' fill='none' stroke='#a78bfa' stroke-opacity='.35' transform='rotate(-18 790 78)'/>
<ellipse cx='790' cy='78' rx='70' ry='24' fill='none' stroke='#22d3ee' stroke-opacity='.3' transform='rotate(24 790 78)'/>
<polygon points='{area}' fill='url(#a)'/>
{''.join(body)}
<polyline points='{pts}' fill='none' stroke='url(#l)' stroke-width='5' filter='url(#b)' opacity='.8'/>
<polyline points='{pts}' fill='none' stroke='url(#l)' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'/>
<circle cx='790' cy='78' r='27' fill='url(#c)' stroke='#e9d5ff' stroke-opacity='.6' stroke-width='1.5'/>
<polygon points='792,62 781,80 789,80 785,96 800,75 792,75 797,62' fill='#fff'/>
<circle cx='{avg[-1][0]:.1f}' cy='{avg[-1][1]:.1f}' r='5' fill='#22d3ee'/>
<circle cx='{avg[-1][0]:.1f}' cy='{avg[-1][1]:.1f}' r='11' fill='#22d3ee' opacity='.25'/>
</svg>"""


_photo_cache = {}


def _photo_uri():
    """If you add hero.jpg / hero.png / hero.webp next to app.py, it is used as the banner photo."""
    if "v" in _photo_cache:
        return _photo_cache["v"]
    uri = None
    for ext, mime in (("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("png", "image/png"), ("webp", "image/webp")):
        p = os.path.join(_HERE, f"hero.{ext}")
        if os.path.exists(p) and os.path.getsize(p) < 1_500_000:
            with open(p, "rb") as f:
                uri = f"data:{mime};base64," + base64.b64encode(f.read()).decode()
            break
    _photo_cache["v"] = uri
    return uri


def hero_html(name, tagline, badges):
    photo = _photo_uri()
    if photo:
        bg = (f"linear-gradient(90deg,rgba(11,14,17,.94) 0%,rgba(11,14,17,.7) 45%,rgba(11,14,17,.25) 100%),"
              f"url({photo}) center/cover no-repeat")
    else:
        bg = (f"url({_b64svg(hero_art())}) right center/auto 100% no-repeat,"
              "linear-gradient(120deg,#12161c 0%,#1b1740 100%)")
    chips = "".join(f"<span class='badge'>{b}</span>" for b in badges)
    return (f"<div class='hero' style='background:{bg}'>"
            f"<div class='hero-row'>{logo_img(64)}<div><div class='brand'>{_wordmark(name)}</div>"
            f"<div class='tag'>{tagline}</div></div></div><div class='badges'>{chips}</div></div>")


def css():
    return """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
.stApp{font-family:'Inter',system-ui,sans-serif}
footer{visibility:hidden}
[data-testid=stSidebar]{border-right:1px solid rgba(128,128,128,.25)}
.block-container{padding-top:2rem;max-width:1250px}
.brand-sm{font-size:21px;font-weight:800;letter-spacing:1.5px;color:inherit;line-height:1.1}
.brand-sm span,.brand span{background:linear-gradient(90deg,#a78bfa,#22d3ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero{position:relative;padding:26px 28px;border-radius:20px;margin-bottom:12px;border:1px solid rgba(128,128,128,.3);color:#fff;
 min-height:150px;box-shadow:0 10px 36px rgba(124,58,237,.2)}
.hero-row{display:flex;align-items:center;gap:16px}
.brand{font-size:44px;font-weight:800;letter-spacing:3px;color:#fff;line-height:1}
.tag{color:#c4b5fd;font-size:16px;margin-top:6px;font-weight:600}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.badge{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);border-radius:999px;
 padding:5px 12px;font-size:12.5px;color:#e5e7eb;backdrop-filter:blur(4px)}
.ticker{display:flex;gap:10px;overflow-x:auto;white-space:nowrap;padding:2px 0 12px;scrollbar-width:thin}
.chip{background:rgba(128,128,128,.12);border:1px solid rgba(128,128,128,.3);border-radius:999px;padding:6px 14px;font-size:13px}
.chip b{margin-right:6px}.chip i{font-style:normal;font-weight:700;margin-left:6px}
.up{color:#0ecb81}.dn{color:#f6465d}
[data-testid=stMetric]{background:rgba(128,128,128,.08);border:1px solid rgba(128,128,128,.25);border-radius:12px;padding:12px 14px}
[data-testid=stMetricLabel]{opacity:.7}
[data-testid=stExpander]{background:rgba(128,128,128,.06);border:1px solid rgba(128,128,128,.25);border-radius:12px}
[data-testid=stDataFrame]{border:1px solid rgba(128,128,128,.25);border-radius:12px;overflow:hidden}
[data-testid=stButtonGroup]{flex-wrap:wrap;gap:6px}
[data-testid=stButtonGroup] button{border-radius:999px !important}
button[kind=segmented_controlActive]{background:linear-gradient(90deg,#7c3aed,#4f46e5) !important;color:#fff !important;border-color:transparent !important}
.stButton>button{border-radius:10px;border:1px solid rgba(128,128,128,.3)}
.stButton>button[kind=primary]{background:linear-gradient(90deg,#7c3aed,#4f46e5);border:0;color:#fff;font-weight:700}
.mobile-hint{display:none}
@media (max-width:640px){
 .block-container{padding:3.2rem .7rem 3rem !important}
 .hero{padding:16px;border-radius:16px;min-height:0}
 .brand{font-size:30px;letter-spacing:2px}.tag{font-size:13px}
 .hero-row img{width:46px;height:46px}
 .badges{margin-top:10px}.badge{font-size:11.5px;padding:4px 9px}
 [data-testid=stMetricValue]{font-size:1.25rem}[data-testid=stMetricLabel]{font-size:.8rem}
 .stButton>button,.stDownloadButton>button{width:100%;min-height:46px}
 h2,h3{font-size:1.15rem !important}
 .mobile-hint{display:block;background:#1b1740;color:#e0e7ff;padding:8px 12px;border-radius:10px;font-size:13px;margin-bottom:10px}
}
</style>"""
