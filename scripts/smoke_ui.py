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

from PySide6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PySide6.QtGui import QFontMetrics  # noqa: E402
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton, QStyleOptionViewItem,
                               QWidget)  # noqa: E402

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
    for attr in ("seg_tier", "lb_tier", "seg_mult", "cmb_runtime",
                 "cmb_engine", "cmb_preset", "cmb_sr"):
        ok = hasattr(win, attr)
        print(f"  {'OK  ' if ok else 'FAIL'}  {attr}")
        if not ok:
            fails.append(f"缺少控件 {attr}")
    if fails:
        return 1

    print("\n=== 引擎倍率与一致性档位 ===")
    win.cmb_engine.setCurrentIndex(win.cmb_engine.findData("DLSS"))
    app.processEvents()

    print("\n=== 预设与超分选项说明 ===")
    for combo, values, label in (
        (win.cmb_preset, ("A", "B", "C"), "preset"),
        (win.cmb_sr, ("Off", "M-INT8", "L-INT8", "M-FP16", "L-FP16"), "super-resolution"),
    ):
        for value in values:
            index = combo.findData(value)
            tip = combo.itemData(index, Qt.ToolTipRole) if index >= 0 else None
            if not tip or len(str(tip).strip()) < 8:
                fails.append(f"{label}/{value} 缺少选项说明")
        delegate = combo.view().itemDelegate()
        if not hasattr(delegate, "help_map") or len(delegate.help_map) != len(values):
            fails.append(f"{label} 下拉弹层未启用说明委托")
        else:
            opt = QStyleOptionViewItem()
            opt.font = combo.font()
            opt.fontMetrics = QFontMetrics(opt.font)
            row_h = delegate.sizeHint(opt, combo.model().index(0, 0)).height()
            if row_h < opt.fontMetrics.height() * 2 + 6:
                fails.append(f"{label} 下拉项高度不足，说明会被裁切")
            if delegate.popup_width < 400:
                fails.append(f"{label} 下拉弹层宽度不足，说明会挤成多行")
    win.cmb_preset.setCurrentIndex(win.cmb_preset.findData("B"))
    if "HUD" not in win.cmb_preset.toolTip():
        fails.append("当前预设 B 的提示未更新")
    if "HUD" not in win.lb_option_hint.text():
        fails.append("预设 B 的常驻说明未更新")
    win.cmb_sr.setCurrentIndex(win.cmb_sr.findData("M-INT8"))
    if "INT8" not in win.cmb_sr.toolTip():
        fails.append("当前超分 M-INT8 的提示未更新")
    if "INT8" not in win.lb_option_hint.text():
        fails.append("超分 M-INT8 的常驻说明未更新")
    win.cmb_preset.setCurrentIndex(win.cmb_preset.findData("A"))
    win.cmb_sr.setCurrentIndex(win.cmb_sr.findData("Off"))
    app.processEvents()
    hint = win.lb_option_hint.text()
    print(f"  常驻说明: {hint!r}")
    if "预设 A" not in hint or "超分 Off" not in hint:
        fails.append("常驻说明未同时显示预设与超分")
    if win.lb_option_hint.isHidden() or win.lb_option_hint.parentWidget() is None:
        fails.append("常驻说明已隐藏或未加入界面")
    print("  A/B/C、Off 与四种 INT8/FP16 选项均有 tooltip，当前项提示与常驻说明随选择更新")
    ndlss = len(win.seg_mult.group.buttons())
    tdlss = win._tier()
    print(f"  DLSS-G: 倍率按钮数={ndlss} 当前档位={tdlss} 上限={core.runtime_mult_cap(win._runtime(), 'DLSS')}")
    print(f"    说明文字: {win.lb_tier.text()!r}")
    if ndlss != 5:
        fails.append(f"DLSS-G 应有 5 个倍率按钮，实际 {ndlss}")
    if tdlss != core.DEFAULT_TIER:
        fails.append(f"DLSS-G 默认档位应 {core.DEFAULT_TIER}，实际 {tdlss}")
    if win._mult() != 4:
        fails.append(f"默认倍率应为 4X，实际 {win._mult()}X")

    # 选到档位 3（最高）
    win.seg_tier.set_value(3)
    app.processEvents()
    print(f"    选档位 3 后: {win._tier()}  说明: {win.lb_tier.text()!r}")
    if win._tier() != 3:
        fails.append("DLSS-G 下无法选到档位 3")

    win.cmb_engine.setCurrentIndex(win.cmb_engine.findData("XeSS"))
    app.processEvents()
    nxess = len(win.seg_mult.group.buttons())
    print(f"  XeSS-FG: 倍率按钮数={nxess} 上限={core.runtime_mult_cap(win._runtime(), 'XeSS')}")
    if nxess != 3 or core.runtime_mult_cap(win._runtime(), "XeSS") != 4:
        fails.append(f"XeSS-FG 应限于 2X–4X，实际按钮数 {nxess}")
    if win.cmb_preset.isEnabled():
        fails.append("XeSS-FG 下 DLSS-G 预设应停用")
    win.cmb_engine.setCurrentIndex(win.cmb_engine.findData("DLSS"))
    app.processEvents()

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
    from PySide6.QtGui import QFont
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
    for engine, preset, sr_mode, t in (
        ("DLSS", "A", "Off", 0), ("DLSS", "B", "M-INT8", 1),
        ("DLSS", "C", "L-FP16", 2), ("XeSS", "A", "Off", 3),
    ):
        txt = core.build_ini("SM86", 4, False, 1, t, core.DEFAULT_RUNTIME,
                             engine=engine, preset=preset, sr_mode=sr_mode)
        line = [l for l in txt.splitlines() if l.startswith("Optimized=")]
        expect = t
        got = line[0].split("=")[1] if line else "?"
        ok = got == str(expect)
        engine_line = [l for l in txt.splitlines() if l.startswith("Engine=")]
        print(f"  {engine}/{preset}/{sr_mode} tier={t} -> Optimized={got}  {'OK' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"{engine} tier={t} 写出 {got}，期望 {expect}")
        if not engine_line or engine_line[0] != f"Engine={engine}":
            fails.append(f"{engine}: Engine 配置未写入正确值")

    print("\n=== 0.3.5 兼容运行库的界面联动 ===")
    if win.cmb_runtime.count() != len(core.RUNTIMES):
        fails.append(f"运行库下拉项数 {win.cmb_runtime.count()} != {len(core.RUNTIMES)}")
    for rt in core.LEGACY_RUNTIMES:
        idx = win.cmb_runtime.findData(rt)
        if idx < 0:
            fails.append(f"运行库下拉缺少 {rt}")
            continue
        win.cmb_runtime.setCurrentIndex(idx)
        app.processEvents()
        editable = [w for w in (win.cmb_engine, win.cmb_preset, win.cmb_sr) if w.isEnabled()]
        if editable:
            fails.append(f"{rt}: 0.4.x 独占选项仍可编辑（{len(editable)} 个）")
        if (win._engine(), win._preset(), win._sr_mode()) != ("DLSS", "Auto", "Off"):
            fails.append(f"{rt}: 引擎/预设/超分未强制为 DLSS/Auto/Off")
        if win._tier_cap() != core.tier_cap(rt):
            fails.append(f"{rt}: 档位上限 {win._tier_cap()} != {core.tier_cap(rt)}")
        if win.seg_mult.group.buttons() and win._mult() > core.runtime_mult_cap(rt, "DLSS"):
            fails.append(f"{rt}: 倍率 {win._mult()} 超过上限")
        txt = core.build_ini("SM86", 6, False, 1, 3, rt)
        for token in ("[Compatibility]", "Preset=Auto", "Mode=Bundled"):
            if token not in txt:
                fails.append(f"{rt}: 旧格式 INI 缺少 {token}")
        cap = core.runtime_mult_cap(rt, "DLSS")
        if f"MaxGeneratedFrames={cap - 1}" not in txt:
            fails.append(f"{rt}: MaxGeneratedFrames 未按上限 {cap} 写入")
        print(f"  {rt}: 选项已收起、倍率上限 {core.runtime_mult_cap(rt, 'DLSS')}X、"
              f"档位上限 {core.tier_cap(rt)}、INI 旧格式 OK")
    back = win.cmb_runtime.findData(core.DEFAULT_RUNTIME)
    win.cmb_runtime.setCurrentIndex(back)
    app.processEvents()
    if not (win.cmb_engine.isEnabled() and win.cmb_sr.isEnabled()):
        fails.append("切回 310.9.16 后选项未恢复可编辑")

    print("\n=== 启动动画缓存与缩放 ===")
    splash = ui.Splash(embedded=True)
    for width, height in ((1160, 840), (780, 520), (1440, 900)):
        splash.resize(width, height)
        splash._set_fade(0.85)
        frames_ok = True
        for progress in (0.0, 0.15, 0.6, 1.0):
            splash._on_value(progress)
            frame = splash.grab()
            frames_ok = frames_ok and not frame.isNull()
        cache_key = splash._cache_key
        ok = (frames_ok and cache_key is not None
              and cache_key[:2] == (width, height)
              and not splash._dynamic_rect.isEmpty())
        print(f"  {width}x{height}: cached={splash._background_cache is not None} "
              f"frames={frames_ok} {'OK' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"启动动画缓存/渲染失败于 {width}x{height}")
    splash.hide()
    splash.deleteLater()
    app.processEvents()

    print("\n=== 扫描项右键移除（仅状态，不删目录） ===")
    target = core.Game(gid=core.game_key(str(Path.cwd() / "SyntheticGame")),
                       name="SyntheticGame", install_dir=str(Path.cwd() / "SyntheticGame"),
                       exe_dir=str(Path.cwd() / "SyntheticGame" / "Binaries"), source="Smoke")
    card = ui.GameCard(target)
    card_actions = []
    card.removeRequested.connect(card_actions.append)

    class FakeAction:
        def __init__(self, text):
            self.text = text
            self.enabled = True

        def setToolTip(self, _text):
            pass

        def setEnabled(self, enabled):
            self.enabled = enabled

    class FakeMenu:
        def __init__(self, *_args):
            self.action = None

        def addAction(self, text):
            self.action = FakeAction(text)
            return self.action

        def exec(self, _pos):
            return self.action if self.action and self.action.enabled else None

    old_menu = ui.QMenu
    deployed_card = None
    ui.QMenu = FakeMenu
    try:
        card._show_context_menu(QPoint(0, 0))
        deployed_card = ui.GameCard(core.Game(gid="deployed-smoke", name="Deployed",
                                              deployed=True))
        deployed_card.removeRequested.connect(card_actions.append)
        deployed_card._show_context_menu(QPoint(0, 0))
    finally:
        ui.QMenu = old_menu
    if card_actions != [target.gid]:
        fails.append(f"右键菜单移除信号异常：{card_actions}")

    state = {"games": {}, "roots": [], "ignored_games": [], "settings": {}}
    old_load_state, old_save_state, old_message_box = core.load_state, core.save_state, ui.QMessageBox

    class ConfirmRemove:
        StandardButton = old_message_box.StandardButton

        @staticmethod
        def question(*_args, **_kwargs):
            return old_message_box.StandardButton.Yes

    try:
        core.load_state = lambda: state
        core.save_state = lambda _state: None
        ui.QMessageBox = ConfirmRemove
        win.games = [target]
        win.current = target
        win._rebuild_list()
        win.cards[target.gid].removeRequested.emit(target.gid)
        if win.games or not core.is_game_ignored(target, state):
            fails.append("确认移除后未从列表隐藏或忽略游戏")
        if win.stack.currentIndex() != 0:
            fails.append("移除当前游戏后详情页未回到空状态")
        restored = core.unignore_game(state, target.gid)
        if not restored or core.is_game_ignored(target, state):
            fails.append("忽略项无法通过状态接口恢复")
    finally:
        core.load_state, core.save_state, ui.QMessageBox = old_load_state, old_save_state, old_message_box
        win.toast.hide()
        app.processEvents()

    card.deleteLater()
    if deployed_card is not None:
        deployed_card.deleteLater()

    # MainWindow's startup worker must finish before the test destroys its owner.
    # This smoke test does not start a game scan (shot_mode remains false).
    if win._boot_worker is not None and win._boot_worker.isRunning():
        if not win._boot_worker.wait(10_000):
            fails.append("启动校验线程未能在 10 秒内结束")
            win._boot_worker.wait()
        app.processEvents()

    print("\n=== 界面缩放与反作弊提示 ===")
    if not hasattr(win, "scale_sel"):
        fails.append("缺少界面缩放选择框")
    else:
        values = [float(win.scale_sel.itemData(i)) for i in range(win.scale_sel.count())]
        print(f"  缩放选项: {values} 当前={win.scale_sel.currentData()}")
        if values != list(core.UI_SCALES):
            fails.append(f"缩放选项异常: {values}")
        if abs(float(win.scale_sel.currentData() or 0) - core.saved_ui_scale()) > 0.001:
            fails.append("缩放选择框未反映已保存的值")

    saved = {"games": {}, "roots": [], "ignored_games": [], "settings": {}}
    try:
        core.load_state = lambda: saved
        core.save_state = lambda _state: None
        idx = win.scale_sel.findData(1.25)
        win.scale_sel.setCurrentIndex(idx)
        app.processEvents()
        if abs(float(saved["settings"].get("ui_scale", 0)) - 1.25) > 0.001:
            fails.append("界面缩放未写入状态")
        if "125%" not in win.toast.text():
            fails.append(f"缩放提示未说明生效值: {win.toast.text()!r}")
        win.toast.hide()
        win.scale_sel.setCurrentIndex(win.scale_sel.findData(1.0))
        win.toast.hide()
    finally:
        core.load_state, core.save_state = old_load_state, old_save_state

    for raw, expected in ((0.1, core.UI_SCALE_DEFAULT), (3.0, core.UI_SCALE_DEFAULT),
                          ("1.25", 1.25), ("abc", core.UI_SCALE_DEFAULT)):
        got = core.saved_ui_scale({"settings": {"ui_scale": raw}})
        if abs(got - expected) > 0.001:
            fails.append(f"saved_ui_scale({raw!r})={got} 期望 {expected}")
    print("  缩放持久化与越界回退: OK")

    ui_src = Path(ui.__file__).read_text(encoding="utf-8")
    if "请只在单机" in ui_src or "反作弊的游戏请只在" in ui_src:
        fails.append("界面仍保留限制联机使用的措辞")
    if "仅提示，不影响部署" not in ui_src:
        fails.append("反作弊提示未说明不影响部署")
    if "反作弊" not in win.hint.text():
        print("  反作弊提示: 仅日志/徽标提示，部署说明不再限制使用场景 OK")
    else:
        fails.append("部署说明仍包含反作弊限制")

    print("\n=== 显卡设备待重启状态与重启路径 ===")
    info = core.detect_gpu_mask(force=True)
    inst = info.enum_key.split("Enum\\", 1)[-1] if info.enum_key else ""
    status = core._devnode_status(inst)
    needs = core.gpu_device_needs_reboot()
    if status is None:
        print("  未取到设备节点状态，跳过（非 Windows 或无 NVIDIA 设备）")
    else:
        if needs != bool(status[0] & core.DN_NEED_RESTART):
            fails.append("gpu_device_needs_reboot 与设备节点状态不一致")
        print(f"  设备节点 status=0x{status[0]:08X} problem={status[1]} 待重启={needs}")
        if not hasattr(win, "btn_mask_reboot"):
            fails.append("缺少「重启电脑」按钮")
        else:
            if (not win.btn_mask_reboot.isHidden()) != needs:
                fails.append("「重启电脑」按钮可见性与待重启状态不一致")
            if win.btn_mask_restart.isEnabled() == needs:
                fails.append("待重启时「重启显卡」应停用")
            if needs and core.is_admin() and "重启电脑" not in win.mask_desc.text():
                fails.append("待重启时伪装说明未提示重启电脑")

    if not core.is_admin():
        ok, msg = core.restart_gpu_device()
        print(f"  非管理员调用 restart_gpu_device -> ok={ok} msg={msg!r}")
        if ok:
            fails.append("非管理员时重启显卡不应返回成功")
        ok, msg = core.schedule_reboot(60)
        if ok:
            fails.append("非管理员时不应能安排重启")
        print(f"  非管理员调用 schedule_reboot -> ok={ok}")

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
