import json, os
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
SUPPORTED = ["en","tr","ko","pt","zh-Hans","ja","es","de","fr","hi","id","it"]

class SafeDict(dict):
    # t["missing.key"] returns "missing.key" instead of KeyError / blank
    def __missing__(self, key):
        return key
    def get(self, key, default=None):
        return dict.get(self, key, default if default is not None else key)

def _load_json(code: str) -> dict:
    path = LOCALES_DIR / f"{code}.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def load_lang(code: str) -> SafeDict:
    # English is the base
    base = _load_json("en")
    if code and code in SUPPORTED and code != "en":
        overlay = _load_json(code)
        merged = {**base, **overlay}
    else:
        merged = dict(base)
    # ensure SafeDict so missing keys are never empty/raise
    return SafeDict(merged)

def pick_lang(request) -> str:
    # cookie first, then 'en'
    try:
        cookie = request.cookies.get("lang", "en")
    except Exception:
        cookie = "en"
    return cookie if cookie in SUPPORTED else "en"
