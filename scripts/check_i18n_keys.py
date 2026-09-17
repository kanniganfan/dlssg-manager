#!/usr/bin/env python3
"""对比 src/ 里 tr() 的字面量键与 gen_i18n_catalog.py 的词典，列出缺失项。

只是自检工具，不修改任何文件。
"""
import ast
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def code_keys() -> set[str]:
    keys: set[str] = set()
    for f in ("core.py", "ui.py"):
        tree = ast.parse((SRC / f).read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "tr":
                a = n.args[0] if n.args else None
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    keys.add(a.value)
    return keys


def catalog_dicts() -> tuple[dict, dict]:
    """把 gen_i18n_catalog.py 当模块加载，直接拿 EN / ZH_TW 两个字典。"""
    spec = importlib.util.spec_from_file_location(
        "_gen", ROOT / "scripts" / "gen_i18n_catalog.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    # 该模块在 import 时会执行 build() 并写 lang/*.json，这里规避副作用：
    real_write = pathlib.Path.write_text
    pathlib.Path.write_text = lambda *a, **k: None       # type: ignore[assignment]
    try:
        spec.loader.exec_module(mod)                      # type: ignore[union-attr]
    finally:
        pathlib.Path.write_text = real_write             # type: ignore[assignment]
    return mod.EN, mod.ZH_TW


def main() -> int:
    ck = code_keys()
    en, tw = catalog_dicts()
    rc = 0
    for name, cat in (("en_US", en), ("zh_TW", tw)):
        missing = sorted(k for k in ck if k not in cat)
        orphan = sorted(k for k in cat if k not in ck)
        print(f"[{name}] 代码键 {len(ck)} / 词典 {len(cat)} / 缺 {len(missing)} / 多 {len(orphan)}")
        for k in missing:
            print(f"   缺翻译: {k!r}")
        for k in orphan:
            print(f"   词典多余（会写入但代码未用）: {k!r}")
        if missing:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
