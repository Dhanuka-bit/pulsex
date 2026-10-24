"""Small HTML building blocks (cards, pills, bars, tables) styled by the theme variables."""
import base64
import html


def esc(x):
    return html.escape(str(x))


def compact(x, prefix="$"):
    if x is None:
        return "—"
    for lim, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= lim:
            return f"{prefix}{x / lim:,.2f}{suf}"
    return f"{prefix}{x:,.2f}"


def price(x):
    if x is None:
        return "—"
    a = abs(x)
    if a >= 1000:
        return f"${x:,.2f}"
    if a >= 1:
        return f"${x:,.3f}"
    if a >= 0.01:
        return f"${x:,.4f}"
    return f"${x:.8f}"


def pill(v, digits=2):
    if v is None:
        return "<span class='pill nu'>—</span>"
    cls, arr = ("up", "▲") if v >= 0 else ("dn", "▼")
    return f"<span class='pill {cls}'>{arr} {abs(v):.{digits}f}%</span>"


def progress(pct, cls=""):
    pct = max(0, min(100, pct))
    return f"<div class='prog {cls}'><i style='width:{pct:.1f}%'></i></div>"


def range_bar(lo, hi, cur):
    if lo is None or hi is None or cur is None or hi <= lo:
        return ""
    pos = max(0, min(100, (cur - lo) / (hi - lo) * 100))
    return f"<div class='rng'><i style='left:{pos:.1f}%'></i></div>"


def sparkline(prices, up=True, w=150, h=44):
    if not prices or len(prices) < 5:
        return ""
    step = max(1, len(prices) // 60)
    p = [x for x in prices[::step] if x is not None]
    lo, hi = min(p), max(p)
    if hi <= lo:
        return ""
    col = "#0ecb81" if up else "#f6465d"
    pts = [(i / (len(p) - 1) * w, h - 4 - (v - lo) / (hi - lo) * (h - 8)) for i, v in enumerate(p)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}'><defs><linearGradient id='a' x1='0' y1='0' x2='0' y2='1'>"
           f"<stop offset='0' stop-color='{col}' stop-opacity='.35'/><stop offset='1' stop-color='{col}' stop-opacity='0'/></linearGradient></defs>"
           f"<polygon points='0,{h} {line} {w},{h}' fill='url(#a)'/>"
           f"<polyline points='{line}' fill='none' stroke='{col}' stroke-width='2' stroke-linejoin='round' stroke-linecap='round'/></svg>")
    return f"<img class='spark' src='data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}'>"


def card(label, value, sub=""):
    return f"<div class='card'><div class='lbl'>{esc(label)}</div><div class='val num'>{value}</div><div class='sub'>{sub}</div></div>"


def grid(cards, min_px=170):
    return f"<div class='grid' style='--min:{min_px}px'>{''.join(cards)}</div>"


def title(text):
    return f"<div class='sec'>{esc(text)}</div>"


def table(headers, rows, right=()):
    th = "".join(f"<th class='{'r' if i in right else ''}'>{esc(h)}</th>" for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f"<td class='{'r' if i in right else ''}'>{c}</td>" for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f"<div class='tbl-wrap'><table class='tbl'><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>"


def css():
    return """<style>
.pill{display:inline-block;padding:3px 10px;border-radius:999px;font-weight:700;font-size:13px;font-family:'Space Grotesk','Inter',sans-serif;white-space:nowrap}
.pill.up{color:var(--up);background:color-mix(in srgb,var(--up) 15%,transparent)}
.pill.dn{color:var(--down);background:color-mix(in srgb,var(--down) 15%,transparent)}
.pill.nu{color:var(--muted);background:var(--bg3)}
.pill.long{color:#fff;background:var(--up)}.pill.short{color:#fff;background:var(--down)}.pill.wait{color:var(--muted);background:var(--bg3)}
.up{color:var(--up)}.dn{color:var(--down)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(var(--min),1fr));gap:10px;margin:8px 0 14px}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:14px;padding:14px 16px;min-width:0}
.card .lbl{font-size:12.5px;color:var(--muted);margin-bottom:4px}
.card .val{font-size:22px;font-weight:700;color:var(--text);overflow-wrap:anywhere;line-height:1.2}
.card .sub{font-size:12.5px;color:var(--muted);margin-top:6px;min-height:8px}
.sec{font-family:'Space Grotesk','Inter',sans-serif;font-size:18px;font-weight:700;color:var(--text);margin:18px 0 6px;display:flex;align-items:center;gap:8px}
.sec:before{content:'';width:4px;height:18px;border-radius:4px;background:linear-gradient(var(--accent),var(--accent2))}
.prog{height:7px;border-radius:7px;background:var(--bg3);overflow:hidden}
.prog i{display:block;height:100%;border-radius:7px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
.prog.g i{background:var(--up)}.prog.r i{background:var(--down)}
.rng{position:relative;height:7px;border-radius:7px;background:linear-gradient(90deg,var(--down),#f0b90b,var(--up));margin:8px 0 4px}
.rng i{position:absolute;top:-4px;width:4px;height:15px;border-radius:3px;background:var(--text);transform:translateX(-2px);box-shadow:0 0 0 2px var(--bg2)}
.rl{display:flex;justify-content:space-between;font-size:12.5px;color:var(--muted)}
.spark{width:150px;height:44px}
.tag{display:inline-block;padding:2px 10px;margin:4px 6px 0 0;border-radius:999px;font-size:12px;color:var(--muted);border:1px solid var(--border);background:var(--bg3)}
.cmc{background:var(--bg2);border:1px solid var(--border);border-radius:18px;padding:18px 20px;margin-bottom:12px;
 display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between}
.cmc .nm{font-family:'Space Grotesk','Inter',sans-serif;font-size:26px;font-weight:700;color:var(--text);display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.cmc .sym{font-size:13px;font-weight:600;color:var(--muted);background:var(--bg3);padding:3px 10px;border-radius:8px}
.cmc .rank{font-size:13px;font-weight:700;color:#fff;background:linear-gradient(90deg,var(--accent),var(--accent2));padding:3px 10px;border-radius:8px}
.cmc .logo{width:46px;height:46px;border-radius:50%;background:var(--bg3)}
.cmc .left{display:flex;align-items:center;gap:14px}
.cmc .bigp{font-size:34px;font-weight:700;color:var(--text);line-height:1.1}
.cmc .right{text-align:right}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.chk{background:var(--bg2);border:1px solid var(--border);border-left:4px solid var(--muted);border-radius:10px;padding:9px 12px;font-size:14px;color:var(--text);margin:6px 0}
.chk.g{border-left-color:var(--up)}.chk.r{border-left-color:var(--down)}.chk.y{border-left-color:#f0b90b}
.about{background:var(--bg2);border:1px solid var(--border);border-radius:14px;padding:14px 16px;color:var(--text);font-size:14px;line-height:1.6}
.lnk{display:inline-block;padding:6px 12px;margin:4px 6px 0 0;border-radius:10px;font-size:13px;font-weight:600;text-decoration:none !important;
 color:var(--text) !important;background:var(--bg3);border:1px solid var(--border)}
.lnk:hover{border-color:var(--accent)}
.gbar{display:flex;gap:18px;overflow-x:auto;white-space:nowrap;padding:8px 2px 10px;font-size:13px;color:var(--muted);scrollbar-width:thin}
.gbar b{color:var(--text);margin:0 4px;font-family:'Space Grotesk','Inter',sans-serif}
.tbl-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:14px;background:var(--bg2);margin:8px 0}
.tbl{width:100%;border-collapse:collapse;font-size:14px}
.tbl th{position:sticky;top:0;text-align:left;font-size:12px;font-weight:600;color:var(--muted);padding:11px 14px;border-bottom:1px solid var(--border);white-space:nowrap;background:var(--bg2)}
.tbl td{padding:11px 14px;border-bottom:1px solid var(--border);color:var(--text);white-space:nowrap}
.tbl tr:last-child td{border-bottom:0}.tbl tr:hover td{background:var(--bg3)}
.tbl .r{text-align:right}.tbl td.r{font-family:'Space Grotesk','Inter',sans-serif;font-variant-numeric:tabular-nums}
.tbl .coin{font-weight:700}
.strength{display:flex;align-items:center;gap:8px;min-width:120px}.strength .prog{flex:1}
.tfinfo{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;background:var(--bg2);border:1px solid var(--border);border-radius:14px;padding:10px 14px;margin:8px 0 12px;font-size:13.5px;color:var(--muted)}
.tfinfo b{color:var(--text);font-size:15px}
@media (max-width:640px){.cmc .bigp{font-size:28px}.cmc .right{text-align:left}.card .val{font-size:19px}.tbl th,.tbl td{padding:9px 10px}}
</style>"""
