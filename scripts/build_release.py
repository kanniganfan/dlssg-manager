#!/usr/bin/env python3
"""DLSSG Manager 发行构建：组装暂存目录 → 便携包 → NSIS 安装器。

用法: python build_release.py [--version 1.9.3] [--portable-only]

关键点（踩过的坑）:
- LICENSE 转 UTF-16LE **带 BOM** 给 NSIS 许可证页 —— 无 BOM 的 UTF-8 会被
  按系统 ANSI(GBK) 解析，中文全是乱码。
- installer.nsi 必须存成 UTF-8 **带 BOM**，否则 Unicode makensis 报
  "Bad text encoding"。
- makensis 的 File/LicenseData 是相对当前工作目录解析的，必须在 _stage 里执行。
- --add-data 与 --icon 用绝对路径（--specpath build 下相对路径基于 workpath 解析）。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "1.9.3"
STAGE = ROOT / "build" / "release-stage" / "1.9.3"
NSIS = ROOT / "_tools" / "nsis-3.10" / "makensis.exe"
PUB = ROOT


def build_stage(version: str) -> None:
    """组装安装/便携共用的暂存目录。"""
    if STAGE.exists():
        sys.exit(f"暂存目录已存在，为保护其中内容而停止: {STAGE}")
    if not (DIST / "DLSSG Manager.exe").is_file():
        sys.exit(f"未找到构建好的程序: {DIST / 'DLSSG Manager.exe'}")
    if not (PUB / "payload" / "version.dll").is_file():
        sys.exit(f"未找到已校验的上游 payload: {PUB / 'payload'}")
    if not (ROOT / "src" / "upstream_payload.py").is_file():
        sys.exit("程序内置的上游文件校验清单缺失")
    STAGE.mkdir(parents=True)

    shutil.copy(DIST / "DLSSG Manager.exe", STAGE / "DLSSG Manager.exe")
    shutil.copy(ROOT / "assets" / "icon.ico", STAGE / "icon.ico")
    shutil.copy(PUB / "docs" / "使用说明.txt", STAGE / "使用说明.txt")
    shutil.copytree(PUB / "payload", STAGE / "payload")
    shutil.copytree(ROOT / "lang", STAGE / "lang")

    # LICENSE → UTF-16LE BOM（NSIS 许可证页必须能识别编码，否则中文乱码）
    lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
    (STAGE / "license.txt").write_bytes(b"\xff\xfe" + lic.encode("utf-16-le"))

    # installer.nsi → UTF-8 BOM（Unicode makensis 要求）。
    # 源文件本身已带 BOM，读取必须用 utf-8-sig 剥掉，否则会写成双 BOM
    # （makensis 报 Invalid command: "?;"）。
    nsi = (ROOT / "scripts" / "installer.nsi").read_text(encoding="utf-8-sig")
    (STAGE / "installer.nsi").write_text(nsi, encoding="utf-8-sig")
    print(f"[stage] {version} 暂存目录就绪（license.txt = UTF-16LE BOM）")


def build_portable(version: str) -> Path:
    out = DIST / f"DLSSG_Manager_{version}_portable_x64.zip"
    if out.exists():
        sys.exit(f"发行包已存在，为保护它而停止: {out}")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(STAGE.rglob("*")):
            if f.name == "installer.nsi":      # 构建脚本不进发行包
                continue
            z.write(f, f"{STAGE.name}/{f.relative_to(STAGE)}")
    print(f"[portable] {out.name}  {out.stat().st_size/1048576:.1f} MB")
    return out


def build_installer(version: str) -> Path:
    if not NSIS.exists():
        sys.exit(f"未找到 makensis: {NSIS}（解压 NSIS 到 _tools/nsis-3.10）")
    # 版本号注入（读 utf-8-sig 已剥 BOM，写回也只用 utf-8-sig，勿重复加）
    import re
    nsi_path = STAGE / "installer.nsi"
    nsi = nsi_path.read_text(encoding="utf-8-sig")
    nsi = re.sub(r'!define VERSION "[^"]*"', f'!define VERSION "{version}"', nsi)
    nsi = re.sub(r'OutFile "DLSSG_Manager_[^"]*"',
                 f'OutFile "DLSSG_Manager_{version}_setup_x64.exe"', nsi)
    nsi_path.write_text(nsi, encoding="utf-8-sig")

    # 必须在 _stage 内执行：File / LicenseData 相对 cwd 解析
    r = subprocess.run([str(NSIS), "installer.nsi"], cwd=STAGE,
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        sys.exit(f"makensis 失败:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    made = STAGE / f"DLSSG_Manager_{version}_setup_x64.exe"
    if not made.exists():
        cands = list(STAGE.glob("*setup*.exe"))
        if not cands:
            sys.exit("makensis 未产出安装器")
        made = cands[0]
    out = DIST / made.name
    if out.exists():
        sys.exit(f"安装包已存在，为保护它而停止: {out}")
    shutil.move(str(made), str(out))
    print(f"[installer] {out.name}  {out.stat().st_size/1048576:.1f} MB")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.9.3")
    ap.add_argument("--keep-stage", action="store_true")
    ap.add_argument("--portable-only", action="store_true",
                    help="只生成便携 ZIP，不需要 NSIS")
    args = ap.parse_args()

    build_stage(args.version)
    p = build_portable(args.version)
    i = None if args.portable_only else build_installer(args.version)
    if not args.keep_stage:
        shutil.rmtree(STAGE, ignore_errors=True)

    print("\n发行产物:")
    print(f"  {p}")
    if i:
        print(f"  {i}")


if __name__ == "__main__":
    main()
