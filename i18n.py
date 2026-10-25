"""Languages: English + Sinhala are hand-written; every other language is auto-translated (and cached)."""
import ast
import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import streamlit as st

LANGS = {"English": "en", "සිංහල": "si", "தமிழ்": "ta", "हिन्दी": "hi", "বাংলা": "bn", "नेपाली": "ne", "اردو": "ur",
         "العربية": "ar", "فارسی": "fa", "עברית": "iw", "Türkçe": "tr", "Español": "es", "Français": "fr",
         "Deutsch": "de", "Italiano": "it", "Português": "pt", "Nederlands": "nl", "Polski": "pl",
         "Русский": "ru", "Українська": "uk", "中文": "zh-CN", "日本語": "ja", "한국어": "ko",
         "ไทย": "th", "Tiếng Việt": "vi", "Bahasa Indonesia": "id", "Bahasa Melayu": "ms", "Filipino": "tl"}
RTL = {"ar", "ur", "fa", "iw"}
_HERE = os.path.dirname(os.path.abspath(__file__))
_cache, _lock = {}, threading.Lock()
_fail = {"n": 0, "until": 0.0}
_warmed = set()
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _call(text, code):
    """One translation request (cached). Returns None if the service is unavailable."""
    k = (code, text)
    with _lock:
        if k in _cache:
            return _cache[k]
        if time.time() < _fail["until"]:
            return None
    try:
        from deep_translator import GoogleTranslator
        out = GoogleTranslator(source="en", target=code).translate(text) or text
        _fail["n"] = 0
    except Exception:
        _fail["n"] += 1
        if _fail["n"] >= 4:
            _fail["until"], _fail["n"] = time.time() + 60, 0
        return None
    with _lock:
        _cache[k] = out
    return out


def _tr(text, code):
    if not any(ch.isalpha() for ch in text):
        return text
    nums = _NUM.findall(text)
    if 0 < len(nums) <= 8:  # translate "Price is {0}" once instead of every new number
        i = [0]

        def rep(_m):
            s = "{%d}" % i[0]
            i[0] += 1
            return s
        out = _call(_NUM.sub(rep, text), code)
        if out and all("{%d}" % j in out for j in range(len(nums))):
            for j, v in enumerate(nums):
                out = out.replace("{%d}" % j, v)
            return out
    return _call(text, code) or text


def _literals():
    found = set()
    for fn in ("app.py", "accounts.py", "funda.py", "markets.py", "ai.py"):
        try:
            with open(os.path.join(_HERE, fn), encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except Exception:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "t" and n.args:
                a = n.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    found.add(a.value)
    return sorted(found)[:700]


def _guess():
    try:
        loc = (st.context.locale or "").lower()
    except Exception:
        return "English"
    base = {"he": "iw", "fil": "tl"}.get(loc.split("-")[0], loc.split("-")[0])
    if loc in ("zh-tw", "zh-hk"):
        base = "zh-cn"
    for name, c in LANGS.items():
        if c.lower() == base or c.lower().split("-")[0] == base:
            return name
    return "English"


def setup(container=None):
    """Draw the language picker and return t(en, si=None)."""
    if "lang" not in st.session_state:
        st.session_state["lang"] = _guess()
    name = (container or st.sidebar).selectbox("🌐 Language", list(LANGS), key="lang")
    code = LANGS[name]
    if code in RTL:
        st.markdown("<style>.stApp{direction:rtl}</style>", unsafe_allow_html=True)
    if code not in ("en", "si") and code not in _warmed:
        with st.spinner("🌐 Translating the app to " + name + " (first time only)..."):
            with ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(lambda s: _tr(s, code), _literals()))
        _warmed.add(code)

    def t(en, si=None):
        if code == "en":
            return en
        if code == "si" and si:
            return si
        return _tr(en, code)
    return t
