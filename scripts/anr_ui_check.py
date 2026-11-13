#!/usr/bin/env python3
"""ANR 设置区块的离屏 UI 检查：装了 ANR 的游戏显示并能写回 nr_fg.ini。

不碰真实游戏目录，也不碰真实 state.json（LOCALAPPDATA 指到 build/ 沙箱）。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
BUILD.mkdir(exist_ok=True)
_SANDBOX = Path(tempfile.mkdtemp(prefix="anr_ui_", dir=BUILD))
os.environ["LOCALAPPDATA"] = str(_SANDBOX)

sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

import anr_profile  # noqa: E402
import core  # noqa: E402
import ui  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication([])
    core.scan_steam = core.scan_epic = core.scan_gog = core.scan_ubisoft = lambda: []
    fails: list[str] = []

    exe_dir = _SANDBOX / "WithAnr" / "Binaries" / "Win64"
    exe_dir.mkdir(parents=True)
    exe = exe_dir / "WithAnr-Win64-Shipping.exe"
    exe.write_bytes(b"MZ" + b"\0" * 4096)
    ini = exe_dir / anr_profile.INI_RELPATH
    ini.parent.mkdir(parents=True)
    ini.write_text("build = user\npath = coopmat\nmodel_size = large\n"
                   "nits_per_unit = 120\nmax_generated = 2\nscene_cut = 0\n", encoding="utf-8")

    plain_dir = _SANDBOX / "Plain" / "Binaries" / "Win64"
    plain_dir.mkdir(parents=True)
    plain_exe = plain_dir / "Plain-Win64-Shipping.exe"
    plain_exe.write_bytes(b"MZ" + b"\0" * 4096)

    win = ui.MainWindow()
    win.show()          # 离屏平台也要 show，否则 grab() 拿到的是未绘制的内容
    g_anr = core.Game(gid="anr", name="WithAnr", exe_dir=str(exe_dir), exe=str(exe),
                      source="Steam", install_dir=str(exe_dir.parent.parent))
    g_plain = core.Game(gid="plain", name="Plain", exe_dir=str(plain_dir), exe=str(plain_exe),
                        source="Steam", install_dir=str(plain_dir.parent.parent))
    win.games = [g_anr, g_plain]
    win.cards = {}
    win.stack.setCurrentIndex(1)

    # 装了 ANR → 区块可见且回显正确
    win.select("anr")
    if not win.row_anr.isVisibleTo(win):
        fails.append("装了 ANR 但区块没显示")
    if win.cmb_anr_path.currentData() != "coopmat":
        fails.append(f"路径没回显: {win.cmb_anr_path.currentData()}")
    if win.seg_anr_mult.value() != 1:            # max_generated=2 → 3X → 段索引 1
        fails.append(f"倍率没回显: seg={win.seg_anr_mult.value()}")
    if win.sw_anr_cut.isChecked():
        fails.append("scene_cut=0 应回显为关")
    if win.ed_anr_nits.text() != "120":
        fails.append(f"HDR 亮度没回显: {win.ed_anr_nits.text()}")

    # 改一改再写回
    idx = win.cmb_anr_path.findData("dp4a")
    win.cmb_anr_path.setCurrentIndex(idx)
    win.seg_anr_mult.set_value(4)                 # 6X
    win.sw_anr_cut.setChecked(True)
    win.ed_anr_nits.setText("203")
    win.apply_anr()
    saved = anr_profile.load_profile(ini)
    if saved.path != "dp4a" or saved.max_generated != 5 or not saved.scene_cut or saved.nits_per_unit != 203:
        fails.append(f"写回内容不对: {saved}")
    if not ini.with_suffix(".ini.bak").exists():
        fails.append("写回时没留 .bak")

    # 没装 ANR 的游戏 → 区块隐藏
    win.select("plain")
    if win.row_anr.isVisibleTo(win):
        fails.append("没装 ANR 的游戏不该显示区块")

    # 截图（回到有 ANR 的那个游戏）
    win.select("anr")
    win.resize(1280, 900)
    # 等开屏动画撤掉，否则抓到的是加载页
    import time
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and getattr(win, "splash", None) is not None:
        app.processEvents()
        time.sleep(0.02)
    splash = getattr(win, "splash", None)
    if splash is not None:
        splash.hide()
        win.splash = None
    win.stack.setCurrentIndex(1)
    win.select("anr")
    for _ in range(80):
        app.processEvents()
    print("route:", win.stack.currentIndex(), "row_anr_visible:", win.row_anr.isVisibleTo(win),
          "geom:", win.width(), "x", win.height())
    shot = BUILD / "_shot_anr_block.png"
    win.grab().save(str(shot))

    if fails:
        for line in fails:
            print("FAIL:", line)
        return 1
    print(f"PASS: anr ui block; shot={shot.name}")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
