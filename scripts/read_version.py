#!/usr/bin/env python3
"""打印 src/core.py 里的 APP_VERSION —— 版本号的唯一来源。

构建脚本（build_windows.bat / build_release.py）都从这里取版本，
避免「改了 core.py 忘了改 bat」这种发布事故。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "core.py"
PATTERN = re.compile(r"^APP_VERSION\s*=\s*[\'\"]([^\'\"]+)[\'\"]", re.MULTILINE)


def read_version() -> str:
    match = PATTERN.search(CORE.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"未在 {CORE} 找到 APP_VERSION")
    return match.group(1)


if __name__ == "__main__":
    print(read_version())
