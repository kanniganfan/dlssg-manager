#!/usr/bin/env python3
"""ANR 侧载布局探针（只读官方包，不碰任何游戏目录）。

结论来自二进制证据：`nvngx_dlssg.dll` 导入 `GetModuleFileNameA/W`，并拼
`"\\path_table.json"`、`"\\size_table.json"`、`"\\programs\\fg-lite-*"`、`"pack.nrx"`
—— 也就是说**所有资源都相对 DLL 自己所在目录**解析。所以侧载时 DLL 必须和
`programs/ kernels/ kernels-portable/ adapters/` 以及三张 json/ini 待在同一层。

用法：
    python scripts/anr_layout_probe.py [--package <anr-fg-*.zip>] [--out <dir>]

产出：把官方包里的 dlssg/ 原样铺到 --out/dlssg/，并打印游戏目录应该长什么样。
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import anr_profile as anr  # noqa: E402

PKG_PREFIX = "game/OptiScaler/custom/Apex Neural Rendering FG/dlssg/"


def find_package(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            raise SystemExit(f"找不到安装包: {p}")
        return p
    downloads = ROOT / "build" / "_downloads"
    cands = sorted(downloads.glob("anr-fg-*.zip")) if downloads.exists() else []
    if not cands:
        raise SystemExit("build/_downloads 里没有 anr-fg-*.zip，用 --package 指定官方包")
    return cands[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", default=None)
    ap.add_argument("--out", default=str(ROOT / "build" / "anr_sideload"))
    args = ap.parse_args()

    package = find_package(args.package)
    out = Path(args.out) / "dlssg"
    out.mkdir(parents=True, exist_ok=True)

    written = 0
    with zipfile.ZipFile(package) as zf:
        for name in zf.namelist():
            if not name.startswith(PKG_PREFIX) or name.endswith("/"):
                continue
            rel = name[len(PKG_PREFIX):]
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(zf.read(name))
            written += 1

    missing = anr.check_layout(out)
    print(f"package : {package.name}")
    print(f"out     : {out}")
    print(f"files   : {written}")
    print(f"layout  : {'OK' if not missing else '缺失 ' + ', '.join(missing)}")

    print("\n游戏目录应该长这样（侧载，不需要 OptiScaler）：")
    print("  <游戏目录>\\nvngx_dlssg.dll          <- 转发器（PR2 第二步实现）")
    print("  <游戏目录>\\anr_fg\\dlssg\\nvngx_dlssg.dll   <- ANR 本体（本脚本产出）")
    print("  <游戏目录>\\anr_fg\\dlssg\\{path_table.json,size_table.json,nr_fg.ini}")
    print("  <游戏目录>\\anr_fg\\dlssg\\{programs,kernels,kernels-portable,adapters}\\")

    print("\n真机验证步骤（只用你机器上已装、且原生支持 DLSS 帧生成的游戏）：")
    print("  1. 复制本脚本产出的 anr_fg\\ 到游戏目录（先别放转发器）")
    print("  2. 把 anr_fg\\dlssg\\nvngx_dlssg.dll 复制到游戏目录根，文件名保持 nvngx_dlssg.dll")
    print("  3. 只保留第 2 步这一份 DLL 时会话会跑到 dlssg\\ 里找不到资源——先按第 2 步的布局")
    print("     （即 DLL 与 programs/ 等同级）做一次：把 dlssg\\ 的内容直接铺进游戏目录")
    print("  4. 进游戏打开 DLSS 帧生成，看是否出帧、有无花屏/抖动")
    print("  5. 检查游戏目录下有没有 nr_fg-*.log，里面的 path 是否等于期望的卷积路径")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
