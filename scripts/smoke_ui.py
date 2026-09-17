#!/usr/bin/env python3
"""离屏 UI 冒烟测试：验证详情页在多种尺寸下不重叠、控件完整、档位逻辑正确。

不弹窗、不进事件循环，纯程序化断言。用法: python scripts/smoke_ui.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

import core  # noqa: E402
import ui  # noqa: E402


def tr_probe(s: str) -> str:
    """测试里不做翻译，直接用中文字面量。"""
    return s


def main() -> int:
    app = QApplication.instance() or QApplication([])
    win = ui.MainWindow()
    fails: list[str] = []

    # 造一个假的已选游戏，直接进详情页
    g = core.Game(name="SmokeTest", exe_dir=str(Path.cwd()),
                  exe=str(Path.cwd() / "x.exe"), source="Steam",
                  resolution=(2560, 1440), dlssg=True, engine="Unreal")
    win.games = [g]
    win.current = g
    win.stack.setCurrentIndex(1)

    print("=== 档位控件存在性 ===")
    for attr in ("seg_tier", "lb_tier", "seg_mult", "cmb_runtime"):
        ok = hasattr(win, attr)
        print(f"  {'OK  ' if ok else 'FAIL'}  {attr}")
        if not ok:
            fails.append(f"缺少控件 {attr}")
    if fails:
        return 1

    print("\n=== 档位逻辑 ===")
    win.cmb_runtime.setCurrentIndex(win.cmb_runtime.findData("310.9"))
    app.processEvents()
    n3109 = len(win.seg_tier.group.buttons())
    t3109 = win._tier()
    print(f"  310.9: 档位按钮数={n3109} 当前档位={t3109} 上限={win._tier_cap()}")
    print(f"    说明文字: {win.lb_tier.text()!r}")
    if n3109 != 4:
        fails.append(f"310.9 应有 4 个档位按钮，实际 {n3109}")
    if t3109 != core.DEFAULT_TIER:
        fails.append(f"310.9 默认档位应 {core.DEFAULT_TIER}，实际 {t3109}")

    # 选到档位 3（最高）
    win.seg_tier.set_value(3)
    app.processEvents()
    print(f"    选档位 3 后: {win._tier()}  说明: {win.lb_tier.text()!r}")
    if win._tier() != 3:
        fails.append("310.9 上无法选到档位 3")

    # 切到 310.1 → 档位上限降为 1
    win.cmb_runtime.setCurrentIndex(win.cmb_runtime.findData("310.1"))
    app.processEvents()
    n3101 = len(win.seg_tier.group.buttons())
    t3101 = win._tier()
    print(f"  310.1: 档位按钮数={n3101} 当前档位={t3101} 上限={win._tier_cap()}")
    print(f"    说明文字: {win.lb_tier.text()!r}")
    if n3101 != 2:
        fails.append(f"310.1 应有 2 个档位按钮（0/1），实际 {n3101}")
    if t3101 > 1:
        fails.append(f"310.1 档位应被钳到 <=1，实际 {t3101}")

    print("\n=== 极端尺寸布局（直接驱动 FlowRow 布局算法） ===")
    # 离屏平台不会给嵌套控件派发真实 resize，几何会停在默认 640x480，
    # 直接断言窗口尺寸等于“假通过”。这里改为对档位所在那一行
    # 显式调用 setGeometry，检查换行后各控件不重叠、高度不塌陷。
    for width in (1400, 1100, 900, 820, 780, 700, 520, 400):
        # 复刻详情页里 r3 的结构：标签 + 档位段 + 说明标签
        row = ui.FlowRow(h_spacing=10, v_spacing=6)
        lb = QLabel(tr_probe("一致性档位"))
        lb.setMinimumWidth(66)
        seg = ui.Segmented(["0", "1", "2", "3"], 1)
        hint = QLabel(tr_probe("1 逐位一致（推荐）"))
        hint.setWordWrap(True)
        for w in (lb, seg, hint):
            row.add(w)

        row.setGeometry(QRect(0, 0, width, 10_000))
        row._flow.setGeometry(QRect(0, 0, width, 10_000))
        app.processEvents()

        rects = [QRect(w.geometry()) for w in (lb, seg, hint)]
        bad = []
        # 1) 每个控件都必须有正的宽高（不被压扁/不可见）
        for name, r in zip(("label", "seg_tier", "hint"), rects):
            if r.width() <= 0 or r.height() <= 0:
                bad.append(f"{name} {r.width()}x{r.height()}")
        # 2) 相邻控件不得重叠
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                if rects[i].intersects(rects[j]):
                    bad.append(f"控件 {i} 与 {j} 重叠")
        # 3) 不超出可用宽度
        for name, r in zip(("label", "seg_tier", "hint"), rects):
            if r.right() > width:
                bad.append(f"{name} 超出宽度 {r.right()} > {width}")
        # 4) 容器高度必须覆盖所有控件（FlowRow 曾因 QScrollArea 不采纳
        #    heightForWidth 而高度按单行算，导致换行后控件被裁掉）
        need = max(r.bottom() for r in rects) + 1
        got = row._flow.heightForWidth(width)
        if got < need:
            bad.append(f"容器高度不足 {got} < {need}")

        status = "OK" if not bad else f"FAIL {bad}"
        print(f"  宽 {width:>4}: 高={got:>3}  seg 位置=({rects[1].x()},{rects[1].y()})  {status}")
        if bad:
            fails.append(f"FlowRow@{width}: {'; '.join(bad)}")
        row.deleteLater()

    print("\n=== INI 生成（档位落到文件） ===")
    for rt, t in (("310.9", 0), ("310.9", 1), ("310.9", 2), ("310.9", 3), ("310.1", 2)):
        txt = core.build_ini("SM86", 4, False, 1, t, rt)
        line = [l for l in txt.splitlines() if l.startswith("Optimized=")]
        expect = min(t, core.tier_cap(rt))
        got = line[0].split("=")[1] if line else "?"
        ok = got == str(expect)
        print(f"  {rt} tier={t} -> Optimized={got} (期望 {expect})  {'OK' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"{rt} tier={t} 写出 {got}，期望 {expect}")

    print("\n=== 结果 ===")
    if fails:
        for f in fails:
            print("  FAIL:", f)
        print(f"合计 {len(fails)} 项失败")
        return 1
    print("  全部断言通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
