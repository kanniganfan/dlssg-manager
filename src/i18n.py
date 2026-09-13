"""i18n —— DLSSG Manager 多语言引擎

设计（gettext 风格，源语言即键）：
- 源语言 zh_CN：代码里的中文字面量本身就是译文，tr() 原样返回；
- 其他语言：lang/<code>.json（UTF-8），键 = 中文原文，值 = 译文；
- 加载顺序：程序目录 lang/  >  打包内置 lang/（PyInstaller _MEIPASS），
  所以用户可以直接改 JSON 调译文，也可以丢一个新 <code>.json 进去
  凭空多出一门语言，无需重新打包；
- 缺失条目一律回退中文原文，绝不显示键名或空白；
- 本模块保持零依赖（不 import core/ui），core 与 ui 都可以反过来用它。
"""
from __future__ import annotations

import ctypes
import json
import sys
from pathlib import Path

SOURCE_LANG = "zh_CN"

# 已知语言的原生显示名（发现 lang/*.json 时以此取名，没有就用代码名）
_KNOWN = {
    "zh_CN": "简体中文",
    "zh_TW": "繁體中文",
    "en_US": "English",
    "ja_JP": "日本語",
    "ko_KR": "한국어",
    "ru_RU": "Русский",
    "de_DE": "Deutsch",
    "fr_FR": "Français",
    "es_ES": "Español",
    "pt_BR": "Português (Brasil)",
}

_current = SOURCE_LANG
_catalog: dict[str, str] = {}
_names: dict[str, str] = {SOURCE_LANG: _KNOWN[SOURCE_LANG]}
_missing: set[str] = set()          # 调试用：当前语言下未命中的键


# ---------------------------------------------------------------- 目录发现

def _base_dirs() -> list[Path]:
    """lang/ 的候选目录，越靠后优先级越高（后者覆盖前者）。"""
    dirs: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(Path(meipass) / "lang")            # 打包内置
        dirs.append(Path(sys.executable).parent / "lang")  # 用户可编辑
    else:
        dirs.append(Path(__file__).parent / "lang")
    return dirs


def _reload() -> None:
    """扫描所有 lang/*.json，重建可用语言表。"""
    _names.clear()
    _names[SOURCE_LANG] = _KNOWN[SOURCE_LANG]
    found: dict[str, dict[str, str]] = {}
    for base in _base_dirs():
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            code = p.stem
            meta = data.get("_meta") if isinstance(data.get("_meta"), dict) else {}
            found[code] = data
            _names[code] = meta.get("name") or _KNOWN.get(code) or code
    # 只缓存当前语言的全量内容；切换时再取
    global _all_catalogs
    _all_catalogs = found


_all_catalogs: dict[str, dict[str, str]] = {}


# ---------------------------------------------------------------- 系统语言

def system_lang() -> str:
    """探测系统 UI 语言，映射到可用语言；认不出就回退 en_US。"""
    lid = 0
    try:
        lid = int(ctypes.windll.kernel32.GetUserDefaultUILanguage()) & 0xFFFF
    except Exception:
        pass
    if lid:
        prim = lid & 0x3FF           # 主语言
        sub = lid >> 10              # 子语言
        if prim == 0x04:             # Chinese
            return "zh_TW" if sub in (0x01, 0x03, 0x05) else "zh_CN"
        if prim == 0x09:
            return "en_US"
        if prim == 0x11:
            return "ja_JP"
        if prim == 0x12:
            return "ko_KR"
        if prim in (0x07, 0x0C):     # de / fr
            return _KNOWN.get({0x07: "de_DE", 0x0C: "fr_FR"}[prim], "en_US")
        if prim == 0x0A:
            return "es_ES"
        if prim == 0x16:
            return "pt_BR"
        if prim == 0x19:
            return "ru_RU"
    try:
        import locale
        loc = (locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        loc = ""
    if loc.startswith("zh"):
        return "zh_TW" if any(t in loc for t in ("tw", "hk", "mo", "hant")) else "zh_CN"
    if loc.startswith("ja"):
        return "ja_JP"
    if loc.startswith("ko"):
        return "ko_KR"
    return "en_US"


# ---------------------------------------------------------------- 切换与查询

def set_lang(code: str) -> str:
    """切换当前语言。未知代码做前缀匹配，再不行回退源语言。"""
    global _current, _catalog
    code = (code or "").strip()
    if code not in _names:
        hit = next((k for k in _names if k.lower().startswith(code[:2].lower())), "")
        code = hit or SOURCE_LANG
    _current = code
    cat = _all_catalogs.get(code) or {}
    _catalog = {k: v for k, v in cat.items() if not k.startswith("_") and isinstance(v, str)}
    _missing.clear()
    return _current


def get_lang() -> str:
    return _current


def available() -> dict[str, str]:
    """当前可用的全部语言 {code: 原生显示名}。"""
    return dict(_names)


def missing_report() -> list[str]:
    """当前语言下 tr() 未命中的键（用于校验翻译完整性）。"""
    return sorted(_missing)


_HAN = None  # 惰性编译，见 tr()


def tr(s: str) -> str:
    """翻译。zh_CN 原样返回；其他语言查表，未命中回退原文并记录。

    缺翻记录只收含汉字的键 —— 运行时产生的英文名（如 GPU 型号）不属于翻译范畴，
    不记入，否则 missing_report 会有大量假阳性。
    """
    if _current == SOURCE_LANG:
        return s
    v = _catalog.get(s)
    if v is None:
        global _HAN
        if _HAN is None:
            import re as _re
            _HAN = _re.compile(r"[一-鿿]")
        if _HAN.search(s):
            _missing.add(s)
        return s
    return v


_reload()
set_lang(system_lang())
