"""Languages: English + Sinhala are hand-written; others are auto-translated (cached)."""
import time
import threading
import streamlit as st

LANGS = {"English": "en", "සිංහල": "si", "தமிழ்": "ta", "हिन्दी": "hi", "বাংলা": "bn", "اردو": "ur",
         "العربية": "ar", "Español": "es", "Français": "fr", "Deutsch": "de", "Português": "pt",
         "Русский": "ru", "中文": "zh-CN", "日本語": "ja", "한국어": "ko", "Türkçe": "tr",
         "Bahasa Indonesia": "id", "Tiếng Việt": "vi"}
RTL = {"ar", "ur"}
_cache, _lock = {}, threading.Lock()
_fail = {"n": 0, "until": 0.0}


def _tr(text, code):
    if not any(ch.isalpha() for ch in text):
        return text
    k = (code, text)
    with _lock:
        if k in _cache:
            return _cache[k]
        if time.time() < _fail["until"]:
            return text
    try:
        from deep_translator import GoogleTranslator
        out = GoogleTranslator(source="en", target=code).translate(text) or text
        _fail["n"] = 0
    except Exception:
        _fail["n"] += 1
        if _fail["n"] >= 3:
            _fail["until"], _fail["n"] = time.time() + 60, 0
        return text
    with _lock:
        _cache[k] = out
    return out


def setup():
    """Draw the language picker and return the t(en, si) function."""
    name = st.sidebar.selectbox("🌐 Language / භාෂාව", list(LANGS), key="lang")
    code = LANGS[name]
    if code in RTL:
        st.markdown("<style>.stApp{direction:rtl}</style>", unsafe_allow_html=True)

    def t(en, si):
        if code == "en":
            return en
        if code == "si":
            return si
        return _tr(en, code)
    return t
