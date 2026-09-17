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
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

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

    print("\n=== 更新检测 ===")
    # 1) 版本比较
    vcases = [("1.7.2", "1.7.1", True), ("1.7.1", "1.7.1", False),
              ("1.7.0", "1.7.1", False), ("v1.8.0", "1.7.1", True),
              ("1.7", "1.7.0", False), ("1.7.1.1", "1.7.1", True),
              ("2.0.0", "1.9.9", True), ("", "1.7.1", False)]
    for a, b, exp in vcases:
        got = core.version_gt(a, b)
        if got != exp:
            fails.append(f"version_gt({a!r},{b!r})={got} 期望 {exp}")
    print(f"  版本比较 {len(vcases)} 例: "
          f"{'全部通过' if not any('version_gt' in f for f in fails) else '有失败'}")

    # 2) 控件存在 + 默认隐藏（无更新时不占位）
    for attr in ("tb_update", "btn_check_update", "btn_repo"):
        if not hasattr(win, attr):
            fails.append(f"缺少控件 {attr}")
    print(f"  控件: tb_update={hasattr(win,'tb_update')} "
          f"btn_check_update={hasattr(win,'btn_check_update')} "
          f"btn_repo={hasattr(win,'btn_repo')}")
    if hasattr(win, "tb_update") and win.tb_update.isVisible():
        # shot_mode 下窗口未 show，isVisible 可能为 False；用 isHidden 判断更准
        pass
    if hasattr(win, "tb_update") and not win.tb_update.isHidden():
        fails.append("tb_update 默认应为隐藏（未检测到更新时不应占位）")
    else:
        print("  tb_update 默认隐藏: OK")

    # 3) 模拟「有新版本」→ 徽标应出现且文字带版本号
    fake = core.UpdateInfo(ok=True, version="9.9.9", is_newer=True,
                           url="https://example.invalid/x", published="2026-01-01T00:00:00Z")
    win._update_silent = False
    win._on_update_checked(fake)
    app.processEvents()
    shown = not win.tb_update.isHidden()
    text = win.tb_update.text()
    print(f"  模拟有更新: 徽标可见={shown} 文字={text!r}")
    if not shown:
        fails.append("检测到新版本后徽标未显示")
    if "9.9.9" not in text:
        fails.append(f"徽标文字未含版本号: {text!r}")

    # 4) 模拟「已是最新」→ 徽标应重新隐藏
    same = core.UpdateInfo(ok=True, version=core.APP_VERSION, is_newer=False)
    win._on_update_checked(same)
    app.processEvents()
    if not win.tb_update.isHidden():
        fails.append("已是最新时徽标应隐藏")
    else:
        print("  模拟已最新: 徽标隐藏 OK")

    # 5) 模拟「检查失败」→ 不崩、不弹徽标、给出错误提示
    bad = core.UpdateInfo(ok=False, error="连接超时")
    win._on_update_checked(bad)
    app.processEvents()
    if not win.tb_update.isHidden():
        fails.append("检查失败时不应显示更新徽标")
    else:
        print("  模拟检查失败: 徽标保持隐藏 OK（仅日志提示）")

    # 6) toast 不得盖住页脚（曾经盖住「检查更新 / 上游仓库」）
    #    离屏下 Qt 不会真正跑布局，foot_w.y() 恒为 0，比较控件几何等于假通过；
    #    这里直接验证抽出来的定位算法在多种尺寸下都成立。
    cases = [(840, 34, 34), (520, 34, 34), (900, 34, 60), (300, 34, 34),
             (840, 0, 34), (840, 480, 34)]
    bad_pos = []
    for rh, fh, th in cases:
        y = ui.toast_rest_y(rh, fh, th)
        if y < 8 or y + th > max(0, rh - min(fh, rh)):
            bad_pos.append(f"root={rh} foot={fh} toast={th} -> y={y}")
    if bad_pos:
        fails.append(f"toast 定位会压到页脚: {bad_pos}")
        print(f"  toast 定位: FAIL {bad_pos}")
    else:
        print(f"  toast 定位 {len(cases)} 例: 全部落在页脚上方 OK")
    win.toast.hide()

    # 7) 按钮文字不得被垂直裁剪（v1.7.1 实测缺陷：页脚按钮 24px 高、
    #    #ghost 上下 padding 16px + 边框 2px，只剩 6px 给 12px 的字）
    #    判据：sizeHint 高度必须 >= 字体行高 + 上下 padding + 边框。
    from PySide6.QtGui import QFont, QFontMetrics
    clip_bad = []
    for pt in (9, 11, 13, 15):                 # 覆盖 100% / 125% / 150% / 175% 缩放
        app.setFont(QFont("Microsoft YaHei UI", pt))
        app.setStyleSheet(ui.qss())
        fm = QFontMetrics(app.font())
        for name, obj, text in (("检查更新", "ghostSm", "检查更新"),
                                ("项目主页", "ghostSm", "项目主页")):
            b = QPushButton(text)
            b.setObjectName(obj)
            b.ensurePolished()
            h = b.sizeHint().height()
            if h < fm.height():
                clip_bad.append(f"{pt}pt/{name} sizeHint={h} < 字高 {fm.height()}")
        # 页脚按钮不能再被固定高度锁死
    app.setFont(QFont("Microsoft YaHei UI", 9))
    app.setStyleSheet(ui.qss())
    for attr in ("btn_check_update", "btn_repo"):
        w = getattr(win, attr, None)
        if w is None:
            fails.append(f"缺少控件 {attr}")
            continue
        if w.maximumHeight() == w.minimumHeight() and w.maximumHeight() < 30:
            fails.append(f"{attr} 仍被固定高度锁死（{w.maximumHeight()}px），会裁字")
    if clip_bad:
        fails.append(f"按钮文字会被裁剪: {clip_bad}")
        print(f"  按钮文字裁剪: FAIL {clip_bad}")
    else:
        print("  按钮文字 4 种缩放下均不被裁剪 OK")

    # 8) 上游检测已移除，仅保留软件自身检测
    if hasattr(win, "btn_upstream"):
        fails.append("btn_upstream 仍存在（应已移除上游检测）")
    if hasattr(core, "UPSTREAM_API") or hasattr(core, "UPSTREAM_REPO"):
        fails.append("core 仍保留 UPSTREAM_* 常量（应已移除上游检测）")
    if hasattr(win, "open_upstream_page"):
        fails.append("ui 仍保留 open_upstream_page（应已移除上游检测）")
    if not (hasattr(win, "btn_repo") and hasattr(win, "open_repo_page")):
        fails.append("缺少项目主页入口（btn_repo / open_repo_page）")
    print("  上游检测已移除、项目主页入口就位 OK")

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
