"""DLSSG Manager - 界面层（PySide6，暗色卡片风格）"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QBuffer, QEvent, QIODevice, QPoint, QPointF,
                            QPropertyAnimation, QRect, QRectF, QSize, Qt, QThread, QTimer,
                            QVariantAnimation, Property, Signal)
from PySide6.QtGui import (QAction, QBrush, QColor, QCursor, QFont, QFontDatabase,
                           QFontMetrics, QFontMetricsF, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QButtonGroup, QComboBox,
                               QFileDialog, QFrame, QGraphicsDropShadowEffect, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMenu, QPlainTextEdit,
                               QPushButton, QScrollArea, QSizeGrip, QSizePolicy, QStackedWidget,
                               QVBoxLayout, QWidget)

import core
import i18n
from i18n import tr

C = {
    "bg": "#0D0F14",
    "panel": "#131722",
    "card": "#191E2A",
    "card2": "#222839",
    "line": "#252C3B",
    "line2": "#333D52",
    "text": "#EAEDF3",
    "muted": "#8E96A6",
    "dim": "#5B6474",
    "accent": "#5B8CFF",
    "accent2": "#7FA3FF",
    "ok": "#3DD68C",
    "warn": "#FFB020",
    "bad": "#FF5F6D",
    "purple": "#9B7BFF",
}

QSS = """
* { outline: none; }
QWidget { color: TEXT; font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; font-size: 13px; }
#root { background: transparent; border: none; }
#titlebar { background: transparent; }
#appTitle { font-size: 15px; font-weight: 600; letter-spacing: 0.2px; }
#appSub { font-size: 11px; color: MUTED; }

#side { background: PANEL; border: 1px solid LINE; border-radius: 14px; }
#search { background: CARD; border: 1px solid LINE; border-radius: 10px; padding: 8px 12px;
          color: TEXT; font-size: 12px; }
#search:focus { border: 1px solid ACCENT; background: CARD2; }
#gpuCard { background: PANEL; border: 1px solid LINE; border-radius: 14px; }
#gpuName { font-size: 14px; font-weight: 600; }
#gpuSub { font-size: 11px; color: MUTED; }

#card { background: CARD; border: 1px solid LINE; border-radius: 14px; }
#cardTitle { font-size: 13px; font-weight: 600; color: TEXT; }
#hero { background: PANEL; border: 1px solid LINE; border-radius: 14px; }
#heroTitle { font-size: 20px; font-weight: 600; letter-spacing: 0.2px; }
#heroSub { font-size: 11px; color: MUTED; }
#kv { font-size: 12px; color: MUTED; }
#kvVal { font-size: 12px; color: TEXT; }

QPushButton#ghost { background: CARD2; border: 1px solid LINE2; border-radius: 10px;
                    padding: 8px 15px; color: TEXT; font-size: 12px; font-weight: 500; }
QPushButton#ghost:hover { background: LINE2; border: 1px solid MUTED; }
QPushButton#ghost:pressed { background: CARD; }
QPushButton#ghost:disabled { color: DIM; background: CARD; border: 1px solid LINE; }

QComboBox#langSel { background: CARD2; border: 1px solid LINE2; border-radius: 10px;
                    padding: 4px 26px 4px 12px; color: TEXT; font-size: 12px; }
QComboBox#langSel:hover { background: LINE2; border: 1px solid MUTED; }
QComboBox#langSel QAbstractItemView { background: PANEL; border: 1px solid LINE2;
                                      border-radius: 8px; color: TEXT;
                                      selection-background-color: ACCENT;
                                      selection-color: #FFFFFF; outline: none; padding: 4px; }

QPushButton#primary { background: ACCENT; border: none; border-radius: 11px; padding: 12px 22px;
                      color: #FFFFFF; font-size: 14px; font-weight: 600; letter-spacing: 0.2px; }
QPushButton#primary:hover { background: ACCENT2; }
QPushButton#primary:pressed { background: #4A78E0; }
QPushButton#primary:disabled { background: CARD2; color: DIM; }

QPushButton#danger { background: transparent; border: 1px solid #4A2A31; border-radius: 11px;
                     padding: 12px 19px; color: BAD; font-size: 13px; font-weight: 500; }
QPushButton#danger:hover { background: #2A1720; border: 1px solid BAD; }
QPushButton#danger:disabled { color: DIM; border: 1px solid LINE; }

QComboBox { background: CARD2; border: 1px solid LINE2; border-radius: 10px; padding: 7px 11px;
            color: TEXT; font-size: 12px; min-height: 18px; }
QComboBox:hover { border: 1px solid MUTED; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: none; width: 0; height: 0; border: none; }
QComboBox QAbstractItemView { background: CARD2; border: 1px solid LINE2; color: TEXT;
                              selection-background-color: ACCENT; outline: none; padding: 5px; }

#segContainer { background: CARD2; border: 1px solid LINE; border-radius: 10px; }
QPushButton#seg { background: transparent; border: none; border-radius: 8px; padding: 7px 13px;
                  color: MUTED; font-size: 12px; font-weight: 500; }
QPushButton#seg:hover { color: TEXT; }
QPushButton#seg:checked { background: ACCENT; color: #FFFFFF; }

#console { background: #090C11; border: 1px solid LINE; border-radius: 12px; color: #C8CEDA;
           font-family: "Cascadia Mono", "Consolas", monospace; font-size: 11px; padding: 9px; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: LINE2; border-radius: 5px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: MUTED; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

#toast { background: CARD2; border: 1px solid LINE2; border-radius: 11px; padding: 11px 19px;
         font-size: 12px; font-weight: 500; }
#emptyWrap { background: transparent; }
#emptyTitle { font-size: 15px; font-weight: 500; color: MUTED; }
#emptySub { font-size: 12px; color: DIM; }
#sectionLabel { font-size: 11px; color: DIM; }
#hagsCard { background: CARD; border: 1px solid LINE; border-radius: 12px; }
"""


def qss() -> str:
    s = QSS
    for k in sorted(C, key=len, reverse=True):
        s = s.replace(k.upper(), C[k])
    return s


# ---------------------------------------------------------------- 小部件

def shadow(widget: QWidget, blur: int = 46, alpha: int = 170, dy: int = 10) -> None:
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setColor(QColor(0, 0, 0, alpha))
    eff.setOffset(0, dy)
    widget.setGraphicsEffect(eff)


class Pill(QLabel):
    """状态胶囊标签。"""

    def __init__(self, text: str = "", kind: str = "muted"):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        self.set_kind(text, kind)

    def set_kind(self, text: str, kind: str = "muted"):
        colors = {
            "ok": (C["ok"], "rgba(57,217,138,0.13)", "rgba(57,217,138,0.32)"),
            "info": (C["accent"], "rgba(91,140,255,0.14)", "rgba(91,140,255,0.34)"),
            "warn": (C["warn"], "rgba(255,176,32,0.13)", "rgba(255,176,32,0.32)"),
            "bad": (C["bad"], "rgba(255,95,109,0.13)", "rgba(255,95,109,0.32)"),
            "purple": (C["purple"], "rgba(155,123,255,0.14)", "rgba(155,123,255,0.34)"),
            "muted": (C["muted"], "rgba(139,147,163,0.10)", "rgba(139,147,163,0.24)"),
        }
        fg, bg, br = colors.get(kind, colors["muted"])
        self.setText(text)
        self.setStyleSheet(
            f"color:{fg}; background:{bg}; border:1px solid {br}; border-radius:9px;"
            "padding:2px 9px; font-size:11px;")


class Switch(QAbstractButton):
    """带滑动的开关。"""

    def __init__(self, checked: bool = False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._on_toggle)

    def get_offset(self) -> float:
        return self._pos

    def set_offset(self, v: float) -> None:
        self._pos = v
        self.update()

    offset = Property(float, get_offset, set_offset)

    def _on_toggle(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self._pos
        track = QColor(C["accent"])
        off = QColor(C["line2"])
        col = QColor(int(off.red() + (track.red() - off.red()) * on),
                     int(off.green() + (track.green() - off.green()) * on),
                     int(off.blue() + (track.blue() - off.blue()) * on))
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(0, 0, 40, 22), 11, 11)
        x = 3 + on * (40 - 22)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, 3, 16, 16))


class Combo(QComboBox):
    """自绘白色箭头的下拉框（Qt 的 QSS 画不出 CSS 三角）。"""

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(C["muted"]), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        x = self.width() - 15
        y = self.height() / 2.0 - 1
        path = QPainterPath()
        path.moveTo(x - 3.6, y - 1.6)
        path.lineTo(x, y + 1.8)
        path.lineTo(x + 3.6, y - 1.6)
        p.drawPath(path)
        p.end()


class Segmented(QWidget):
    """分段选择控件。"""

    changed = Signal(int)

    def __init__(self, options: list[str], current: int = 0):
        super().__init__()
        self.setObjectName("segContainer")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(3)
        self.group = QButtonGroup(self)
        for i, opt in enumerate(options):
            b = QPushButton(opt)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(i == current)
            self.group.addButton(b, i)
            lay.addWidget(b)
        self.group.idClicked.connect(self.changed.emit)

    def value(self) -> int:
        return self.group.checkedId()

    def set_value(self, i: int) -> None:
        b = self.group.button(i)
        if b and not b.isChecked():
            b.setChecked(True)
            self.changed.emit(i)


class ElidedLabel(QLabel):
    """按【像素宽度】中段省略的标签。

    字符数预算对 CJK 双宽字符失效：一条 37 字符的中文游戏路径
    （如 永劫无间极速版 的 NarakaBladepoint.exe）比 54 个英文字符宽得多，
    按字符数截断等于没截。必须用 QFontMetrics 按实际像素省略，语言无关。
    tooltip 始终是完整文本。
    """

    def __init__(self, text: str = "", wrap: bool = False):
        super().__init__(text)
        self._raw = text
        self._wrap = wrap
        self.setWordWrap(wrap)
        self.setToolTip(text)
        # 允许被布局压缩；省略由 _apply 按实际宽度重算
        self.setMinimumWidth(0)

    def setRaw(self, text: str) -> None:
        self._raw = text
        self.setToolTip(text)
        self._apply()

    def raw(self) -> str:
        return self._raw

    def _apply(self) -> None:
        if self._wrap or self.width() < 40:   # 未完成布局时先原样显示
            if self.text() != self._raw:
                self.setText(self._raw)
            return
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(self._raw, Qt.ElideMiddle, max(30, self.width() - 2))
        if elided != self.text():
            self.setText(elided)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._apply()


class KV(QWidget):
    """键值行。"""

    def __init__(self, key: str, value: str = "", wrap: bool = False):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        k = QLabel(key)
        k.setObjectName("kv")
        # 最小宽取文字实际渲染宽度：中文四字约 52px，英文如 Install directory
        # 约 100px。用 sizeHint 而不是写死，任何语言都不会被裁。
        k.setMinimumWidth(max(66, k.sizeHint().width()))
        # 高度锁到字型实际需要：布局在竖向紧张时会把 QLabel 压到 10-11px，
        # 12px 字体的下缘（g/y/p 的降部）被裁 —— 用户反馈的「文字底部遮挡」。
        k.setMinimumHeight(k.sizeHint().height())
        self.v = ElidedLabel(value, wrap=wrap)
        self.v.setObjectName("kvVal")
        self.v.setMinimumHeight(self.v.sizeHint().height())
        # 注意：不要给该标签开 TextSelectableByMouse —— 可选中会让 QLabel 改走
        # QTextControl 渲染，其字体回退在 CJK 相邻的「…」上会渲染成宽空白
        #（本机实测，中英文都中招）。完整文本有 tooltip，选择功能舍弃。
        lay.addWidget(k, 0, Qt.AlignTop)
        lay.addWidget(self.v, 1)

    def set(self, text: str) -> None:
        self.v.setRaw(text)


def mid(s: str, n: int) -> str:
    """把长路径中间省略，保留头尾。"""
    if not s or len(s) <= n:
        return s
    head = max(8, n // 2 - 4)
    tail = max(8, n - head - 1)
    return s[:head] + "…" + s[-tail:]


class GameCard(QFrame):
    """左侧游戏列表项。"""

    clicked = Signal(str)

    def __init__(self, game: core.Game):
        super().__init__()
        self.game = game
        self._selected = False
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(100 if game.anticheat else 80)
        self.setAttribute(Qt.WA_Hover, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(7)

        top = QHBoxLayout()
        top.setSpacing(8)
        title = game.name if len(game.name) <= 17 else game.name[:16] + "…"
        self.name = QLabel(title)
        self.name.setStyleSheet("font-size:13px; font-weight:600;")
        self.name.setMinimumWidth(10)
        self.name.setToolTip(game.name)
        top.addWidget(self.name, 1)
        self.pill = Pill()
        self._apply_pill()
        top.addWidget(self.pill, 0, Qt.AlignTop)
        lay.addLayout(top)

        self.path = QLabel(self._short_path())
        self.path.setStyleSheet(f"font-size:11px; color:{C['dim']};")
        self.path.setToolTip(game.exe_dir or game.install_dir)
        lay.addWidget(self.path)

        if game.anticheat:
            chips = QHBoxLayout()
            chips.setSpacing(6)
            # 产品决策：只提示「有反作弊」，不显示具体类型，也不做任何限制
            chips.addWidget(Pill(tr('反作弊'), "warn"))
            chips.addStretch(1)
            lay.addLayout(chips)
        else:
            lay.addStretch(1)

        self._apply_style()

    def _short_path(self) -> str:
        p = self.game.exe_dir or self.game.install_dir
        if len(p) > 44:
            p = p[:18] + " … " + p[-22:]
        return p

    def _apply_pill(self) -> None:
        g = self.game
        if g.deployed:
            self.pill.set_kind(tr('已启用'), "ok")
        elif g.dlssg:
            self.pill.set_kind(tr('可启用'), "info")
        elif g.dlss:
            self.pill.set_kind(tr('仅超分'), "purple")
        else:
            self.pill.set_kind(tr('无帧生成'), "muted")

    def _apply_style(self) -> None:
        # 左侧强调条：选中时点亮，给出清晰的定位感
        bar = C["accent"] if self._selected else "transparent"
        if self._selected:
            bg, bd = C["card2"], C["accent"]
        else:
            bg, bd = C["card"], C["line"]
        self.setStyleSheet(
            f"#card {{ background:{bg}; border:1px solid {bd};"
            f"border-left:3px solid {bar}; border-radius:12px; }}"
            + ("" if self._selected else
               f"#card:hover {{ background:{C['card2']}; border:1px solid {C['line2']};"
               f"border-left:3px solid {C['line2']}; }}"))

    def set_selected(self, on: bool) -> None:
        self._selected = on
        self._apply_style()

    def refresh(self) -> None:
        self._apply_pill()
        self.name.setText(self.game.name)
        self.path.setText(self._short_path())

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.game.gid)


# ---------------------------------------------------------------- 工作线程

class ScanWorker(QThread):
    progress = Signal(str)
    done = Signal(list, list, str)

    def __init__(self, deep: bool = False, roots: list[str] | None = None):
        super().__init__()
        self.deep = deep
        self.roots = roots or []

    def run(self) -> None:
        try:
            st = core.load_state()
            warns = core.verify_payload()
            games = core.collect_games(st, progress=self.progress.emit,
                                       deep_roots=self.roots,
                                       deep_budget=60.0 if self.roots else 0.0)
            self.done.emit(games, warns, "")
        except Exception as e:
            self.done.emit([], [], f"{type(e).__name__}: {e}")


class ActionWorker(QThread):
    done = Signal(bool, list, str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs

    def run(self) -> None:
        try:
            ok, logs = self.fn(*self.args, **self.kwargs)
            self.done.emit(bool(ok), logs, "")
        except Exception as e:
            self.done.emit(False, [], f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- 主窗口

class TrafficLights(QWidget):
    """macOS 风格三色按钮（红=关闭 / 黄=最小化 / 绿=最大化）。"""

    close_clicked = Signal()
    min_clicked = Signal()
    max_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(66, 20)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = -1
        self._maximized = False
        self._colors = [("#FF5F57", "#BF4942"),   # close
                        ("#FEBC2E", "#BF8E22"),   # min
                        ("#28C840", "#1F9B32")]   # max
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)

    def set_maximized(self, on: bool) -> None:
        self._maximized = on
        self.update()

    def _idx_at(self, x: float) -> int:
        for i in range(3):
            if 2 + i * 21 <= x <= 2 + i * 21 + 13:
                return i
        return -1

    def _glyph(self, p: QPainter, i: int, cx: float, cy: float) -> None:
        p.setBrush(Qt.NoBrush)
        if i == 0:      # ✕
            p.setPen(QPen(QColor("#5A0E0C"), 1.4))
            p.drawLine(QPoint(int(cx - 2.6), int(cy - 2.6)), QPoint(int(cx + 2.6), int(cy + 2.6)))
            p.drawLine(QPoint(int(cx + 2.6), int(cy - 2.6)), QPoint(int(cx - 2.6), int(cy + 2.6)))
        elif i == 1:    # −
            p.setPen(QPen(QColor("#603D08"), 1.4))
            p.drawLine(QPoint(int(cx - 3), int(cy)), QPoint(int(cx + 3), int(cy)))
        else:           # + / 双箭头
            p.setPen(QPen(QColor("#0B4C16"), 1.4))
            if self._maximized:
                p.drawLine(QPoint(int(cx - 3), int(cy)), QPoint(int(cx + 3), int(cy)))
                p.drawLine(QPoint(int(cx), int(cy - 3)), QPoint(int(cx), int(cy + 3)))
            else:
                p.drawLine(QPoint(int(cx - 2.6), int(cy - 2.6)), QPoint(int(cx + 2.6), int(cy + 2.6)))
                p.drawLine(QPoint(int(cx - 2.6), int(cy + 2.6)), QPoint(int(cx + 2.6), int(cy - 2.6)))

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["line2"]))
            for i in range(3):
                p.drawEllipse(QRectF(2 + i * 21, 3.5, 13, 13))
            p.end()
            return
        # 始终彩色（比 macOS 的失焦灰化更适合单窗口工具，避免看着像禁用）
        for i, (base, dark) in enumerate(self._colors):
            x = 2 + i * 21
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(base))
            p.drawEllipse(QRectF(x, 3.5, 13, 13))
            if self._hover == i:
                p.setBrush(QColor(dark))
                p.drawEllipse(QRectF(x + 2, 5.5, 9, 9))
                self._glyph(p, i, x + 6.5, 10)
        p.end()

    def mouseMoveEvent(self, e) -> None:
        i = self._idx_at(e.position().x())
        if i != self._hover:
            self._hover = i
            self.update()

    def leaveEvent(self, _e) -> None:
        self._hover = -1
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.LeftButton:
            return
        i = self._idx_at(e.position().x())
        if i == 0:
            self.close_clicked.emit()
        elif i == 1:
            self.min_clicked.emit()
        elif i == 2:
            self.max_clicked.emit()


class Splash(QWidget):
    """启动载入动画：KANNI 字符逐个渐显并循环，同时做真实初始化。"""

    finished = Signal()

    WORD = "KANNI"
    SUB = "DLSSG MANAGER"
    MIN_MS = 2600      # 至少停留这么久
    MAX_MS = 4200      # 最长等待这么久

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("splash")
        # 不透明窗口 + 纯自绘（无半透明）：DWM 不用做逐帧合成，
        # 从根上避免「卡住 / 局部空白 / 要鼠标划过才刷新」这类重绘残缺。
        # 圆角改由 paintEvent 把四角涂成与主界面同色近似的方式处理。
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._progress = 0.0        # 0..1 字符渐显推进度
        self._fade = 0.0            # 整体
        self._phase = 0             # 0=显示 1=淡出
        self._done = False
        self._tick = 0

        self._fade_in = QPropertyAnimation(self, b"fade", self)
        self._fade_in.setDuration(420)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(1500)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)
        self._anim.valueChanged.connect(self._on_value)
        self._anim.finished.connect(self._loop)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick_loop)

    # 属性（供 QPropertyAnimation 使用）
    def _get_fade(self) -> float:
        return self._fade

    def _set_fade(self, v: float) -> None:
        self._fade = v
        self.update()

    fade = Property(float, _get_fade, _set_fade, notify=None)

    def start(self) -> None:
        self._timer.start()
        self._fade_in.start()
        self._anim.start()

    def _on_value(self, v) -> None:
        self._progress = float(v)
        self.update()

    def _loop(self) -> None:
        """一轮走完，反向再来，形成循环等待。"""
        self._anim.setDirection(
            QVariantAnimation.Backward if self._anim.direction() == QVariantAnimation.Forward
            else QVariantAnimation.Forward)
        self._anim.start()

    def _tick_loop(self) -> None:
        self._tick += 1

    def finish(self) -> None:
        """初始化完成，播放淡出。"""
        if self._phase:
            return
        self._phase = 1
        self._timer.stop()
        self._anim.stop()
        self._out = QPropertyAnimation(self, b"fade", self)
        self._out.setDuration(320)
        self._out.setStartValue(1.0)      # 从当前不透明度起淡出，避免跳变
        self._out.setEndValue(0.0)
        self._out.setEasingCurve(QEasingCurve.InCubic)
        self._out.finished.connect(self._on_faded_out)
        self._out.start()

    def _on_faded_out(self) -> None:
        # 先彻底隐藏，再通知外部销毁，保证父窗口能立刻重绘底下内容
        self.hide()
        self.finished.emit()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        w, h = self.width(), self.height()

        # 不透明窗口：先整块铺满（避免残留），再用圆角路径画背景
        p.fillRect(self.rect(), QColor("#05070B"))
        radius = 16.0
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)

        # 渐变底
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#0B0E15"))
        grad.setColorAt(1.0, QColor("#12161F"))
        p.save()
        p.setClipPath(path)
        p.fillRect(self.rect(), QBrush(grad))
        p.restore()
        # 圆角描边
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(C["line"]), 1))
        p.drawPath(path)

        a = max(0.0, min(1.0, self._fade))
        if a <= 0.01:
            p.end()
            return

        p.setOpacity(a)
        cx, cy = w / 2, h / 2 - 8

        # 中心光晕
        radial = QRadialGradient(cx, cy, max(w, h) * 0.34)
        radial.setColorAt(0.0, QColor(91, 140, 255, 34))
        radial.setColorAt(1.0, QColor(91, 140, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(radial))
        p.drawEllipse(QRectF(cx - w * 0.34, cy - h * 0.34, w * 0.68, h * 0.68))

        # KANNI 逐字渐显：每个字符有自己的 [起, 起+0.4] 窗口
        f = QFont("Segoe UI", 46)
        f.setWeight(QFont.Black)
        f.setLetterSpacing(QFont.PercentageSpacing, 116)
        p.setFont(f)
        fm = QFontMetricsF(f)
        n = len(self.WORD)
        span = 0.42
        step = (1.0 - span) / max(1, n - 1)
        adv = [fm.horizontalAdvance(ch) for ch in self.WORD]
        total = sum(adv)
        x = cx - total / 2
        baseline = cy + fm.capHeight() / 2 + 2
        for i, ch in enumerate(self.WORD):
            t0 = i * step
            raw = (self._progress - t0) / span
            k = max(0.0, min(1.0, raw))
            k = 1 - (1 - k) ** 3                      # easeOutCubic
            if k <= 0.001:
                x += adv[i]
                continue
            # 未完成的字符带一点上浮与光晕
            rise = (1 - k) * 16
            glow = 26 * (k ** 1.6) * (1 if self._progress < 1 else 0.6)
            col = QColor("#7FA3FF")
            col.setAlphaF(min(1.0, k * 0.42))
            p.setPen(QColor(0, 0, 0, 0))
            gpen = QPen(QColor("#5B8CFF"))
            gpen.setWidthF(1.4)
            gpen.setJoinStyle(Qt.RoundJoin)
            # 描边发光（用同一字符多次描边近似）
            if glow > 1:
                gp = QPainterPath()
                gp.addText(x, baseline - rise, f, ch)
                p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(glow * 2.2)), 2.0))
                p.setBrush(Qt.NoBrush)
                p.drawPath(gp)
            p.setPen(QColor(233, 236, 241, int(255 * k)))
            p.drawText(QPointF(x, baseline - rise), ch)
            x += adv[i]

        # 副标题与进度点
        f2 = QFont("Segoe UI", 9)
        f2.setLetterSpacing(QFont.PercentageSpacing, 300)
        p.setFont(f2)
        p.setPen(QColor(139, 147, 163, int(150 * a)))
        sub = self.SUB
        fm2 = QFontMetricsF(f2)
        p.drawText(QPointF(cx - fm2.horizontalAdvance(sub) / 2, baseline + 34), sub)

        # 载入点：三个点依次呼吸
        dot_y = baseline + 58
        for i in range(3):
            ph = (self._tick * 0.42 + i * 0.28) % 1.0
            breathe = 0.35 + 0.65 * (1 - abs(ph * 2 - 1))
            r = 2.6 + 1.6 * breathe
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(91, 140, 255, int(210 * breathe * a)))
            p.drawEllipse(QRectF(cx - 16 + i * 16 - r, dot_y - r, r * 2, r * 2))
        p.end()


def _blend(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(int(c1.red() + (c2.red() - c1.red()) * t),
                  int(c1.green() + (c2.green() - c1.green()) * t),
                  int(c1.blue() + (c2.blue() - c1.blue()) * t))


class RootFrame(QFrame):
    """主容器。显式绘制圆角背景；最大化铺满屏幕时改直角。"""

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        radius = 0 if (self.window() is not None and self.window().isMaximized()) else 16
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), radius, radius)
        p.fillPath(path, QColor(C["bg"]))
        p.setPen(QPen(QColor(C["line"]), 1))
        p.drawPath(path)
        p.end()


class MainWindow(QWidget):
    def __init__(self, shot_mode: bool = False):
        super().__init__()
        self.shot_mode = shot_mode
        self.gpu = core.detect_gpu()
        self.games: list[core.Game] = []
        self.current: core.Game | None = None
        self.cards: dict[str, GameCard] = {}
        self.worker = None
        self._resize_edge = None
        self._drag_origin = None
        self._normal_geo = None

        self.setWindowTitle(core.APP_TITLE)
        self.setWindowIcon(make_icon())
        self.setMinimumSize(940, 620)
        self.resize(1120, 720)
        if not shot_mode:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            # 根因性修复：WA_TranslucentBackground 的分层窗口在本机驱动/DWM
            # 组合下会残留陈旧瓦片 —— 表现为「文字被遮挡/显示不完整，
            # 移动或点击后才恢复」。改为不透明窗口后不再走逐像素合成，
            # 这一类问题从根上消失。外圈 20px 由 paintEvent 画成深色背板，
            # root 仍是圆角卡片，观感不变。
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            self.setAutoFillBackground(True)
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor("#05070B"))
            self.setPalette(pal)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0 if shot_mode else 20, 0 if shot_mode else 20,
                                 0 if shot_mode else 20, 0 if shot_mode else 20)
        self.root = RootFrame()
        self.root.setObjectName("root")
        outer.addWidget(self.root)
        # 注意：这里刻意不加 QGraphicsDropShadowEffect。
        # 在 WA_TranslucentBackground 的无边框窗口上，阴影效果会让 Qt 只重绘
        # 变化区域而非整窗，配合子控件遮挡会出现大块空白与残影，故改用圆角+描边表现层次。
        root_lay = QVBoxLayout(self.root)
        root_lay.setContentsMargins(16, 14, 16, 12)
        root_lay.setSpacing(12)

        root_lay.addWidget(self._build_titlebar())
        root_lay.addWidget(self._build_gpu_bar())

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self._build_side(), 0)
        body.addWidget(self._build_detail(), 1)
        root_lay.addLayout(body, 1)

        foot = QHBoxLayout()
        self.status = QLabel(tr('就绪'))
        self.status.setStyleSheet(f"font-size:11px; color:{C['dim']};")
        foot.addWidget(self.status)
        foot.addStretch(1)
        hint = QLabel(tr('{0} · 仅供单机 / 非反作弊线上环境使用').format(core.MOD_NAME))
        hint.setStyleSheet(f"font-size:11px; color:{C['dim']};")
        foot.addWidget(hint)
        grip = QSizeGrip(self.root)
        grip.setFixedSize(14, 14)
        foot.addWidget(grip, 0, Qt.AlignBottom)
        root_lay.addLayout(foot)

        self.toast = QLabel("", self.root)
        self.toast.setObjectName("toast")
        self.toast.hide()
        self._toast_anim = QPropertyAnimation(self.toast, b"pos", self)
        self._toast_anim.setDuration(220)
        self._toast_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._init_ready = False
        self._splash_elapsed = False
        self._boot()
        if not shot_mode:
            # 先让主窗口完成一次完整布局与首次绘制，再挂 splash 盖上去，
            # 避免「底下还没画好就被遮住 → 移开 splash 后一片空白」。
            QTimer.singleShot(0, self._mount_splash)
        else:
            QTimer.singleShot(150, self.start_scan)

    def _boot(self) -> None:
        """真实初始化：显卡探测、运行包校验。供载入动画期间完成。"""
        self._log(tr('欢迎使用，点击“扫描游戏”开始识别本机已安装的游戏。'))
        self._log(tr('显卡：{0}（驱动 {1}）→ 路由 {2}').format(self.gpu.name, self.gpu.driver or '未知', self.gpu.route))
        if self.gpu.vram_mb:
            self._log(tr('显存：{0} MiB。开启帧生成会额外占用显存，请留出余量。').format(self.gpu.vram_mb))
        pd = core.payload_dir()
        if pd is None:
            self._log(tr('[错误] 未找到 payload 目录，请把 payload 文件夹放在程序同级目录后重启'))
            self.toast_msg(tr('缺少 payload 运行包文件夹'), "bad")
        else:
            warns = core.verify_payload()
            if warns:
                self._log(tr('[警告] 运行包校验异常 {0} 项：{1}').format(len(warns), tr('；').join(warns)))
            else:
                self._log(tr('[提示] 运行包校验通过（{0}）').format(pd))
        core.detect_hags(force=True)
        self._init_ready = True

    def _mount_splash(self) -> None:
        # 关键：splash 做成独立的顶层无边框窗口，盖在主窗口之上。
        # 早期把它挂成 root 的子控件，会出现「主界面不重绘 / 卡住 / 要鼠标划过才显示」
        # 的问题——子控件大范围遮挡时父级不会自动补绘，且 deleteLater 会留下残影。
        #
        # 现在进一步：splash 是【不透明】顶层窗口，不再依赖 WA_TranslucentBackground
        # 的逐帧合成，重绘残缺问题从根上消失。
        self.splash = Splash()
        self.splash.setWindowFlags(Qt.FramelessWindowHint | Qt.Window
                                   | Qt.WindowStaysOnTopHint | Qt.Tool
                                   | Qt.NoDropShadowWindowHint)
        self.splash.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.splash.finished.connect(self._splash_gone)
        self._place_splash()
        self.splash.show()
        self.splash.raise_()
        self.splash.start()

        # 无边框顶层窗口在主窗口 move()/resize() 时不一定收到事件，
        # 用「主窗口事件过滤器 + 轻量跟随定时器」双保险，保证 splash 始终贴住主窗口。
        self.installEventFilter(self)
        self._follow = QTimer(self)
        self._follow.setInterval(16)
        self._follow.timeout.connect(self._place_splash)
        self._follow.start()

        QTimer.singleShot(Splash.MIN_MS, self._splash_min_elapsed)
        QTimer.singleShot(Splash.MAX_MS, self._splash_min_elapsed)

    def eventFilter(self, obj, ev):
        if obj is self and getattr(self, "splash", None) is not None:
            if ev.type() in (QEvent.Move, QEvent.Resize, QEvent.WindowStateChange,
                             QEvent.Show, QEvent.LayoutRequest):
                self._place_splash()
        return super().eventFilter(obj, ev)

    def _place_splash(self) -> None:
        s = getattr(self, "splash", None)
        if s is None:
            return
        # 盖满【整个窗口】而不是只盖 root：主窗口有 20px 半透明边距，
        # 若只盖 root，加载期间四周会露出一圈主窗口的透明区，观感很脏。
        top_left = self.mapToGlobal(QPoint(0, 0))
        geo = QRect(top_left.x(), top_left.y(), self.width(), self.height())
        if s.geometry() != geo:
            s.setGeometry(geo)

    def _splash_min_elapsed(self) -> None:
        self._splash_elapsed = True
        self._try_end_splash()

    def _try_end_splash(self) -> None:
        if self._splash_elapsed and self._init_ready and getattr(self, "splash", None):
            self.splash.finish()

    def _splash_gone(self) -> None:
        s = getattr(self, "splash", None)
        if s is not None:
            s.close()
            s.deleteLater()
            self.splash = None
        # 停掉跟随定时器，避免空转
        f = getattr(self, "_follow", None)
        if f is not None:
            f.stop()
        # 让底层主窗口强制整屏重绘一次，确保立刻显示而不是等鼠标移入
        self._repaint_all()
        QTimer.singleShot(60, self.start_scan)
        QTimer.singleShot(260, self._repaint_all)

    def _repaint_all(self) -> None:
        """强制整窗递归重绘一次，压掉半透明无边框窗口的残影/空白。

        半透明无边框窗口在部分驱动/DPI 组合下，Qt 只重绘「变化区域」，
        于是出现大块旧内容残留，必须靠鼠标移动触发的局部重绘才补上。
        这里对整个控件树逐个 repaint()，一次性把整窗刷干净。
        """
        self.update()
        self.root.update()
        self.root.repaint()
        for w in self.findChildren(QWidget):
            if w.isVisible():
                w.update()
        self.repaint()

    def paintEvent(self, e) -> None:
        """不透明窗口的外圈背板（root 之外的 20px 边距区）。"""
        super().paintEvent(e)
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#05070B"))
        p.end()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        # 窗口首次显示时排一次重绘，避免开场大片空白要鼠标划过才出现
        QTimer.singleShot(30, self._repaint_all)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._place_splash()

    # ------------------------------------------------- 顶栏

    def _on_lang_changed(self, idx: int) -> None:
        """切换语言：立即持久化，重启后整套界面换语言。"""
        code = self.lang_sel.itemData(idx)
        if not code or code == i18n.get_lang():
            return
        try:
            st = core.load_state()
            st["lang"] = code
            core.save_state(st)
        except Exception:
            pass
        self.toast_msg(tr('语言已切换为 {0}，重启程序后生效').format(
            self.lang_sel.itemText(idx)), "info")

    def _build_titlebar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("titlebar")
        bar.setFixedHeight(40)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(13)

        if self.shot_mode:
            lay.addSpacing(4)
        else:
            self.lights = TrafficLights()
            self.lights.setToolTip(tr('关闭 / 最小化 / 最大化'))
            self.lights.close_clicked.connect(self.close)
            self.lights.min_clicked.connect(self.showMinimized)
            self.lights.max_clicked.connect(self.toggle_max)
            lay.addWidget(self.lights, 0, Qt.AlignVCenter)
            lay.addSpacing(1)

        logo = QLabel()
        logo.setPixmap(make_icon().pixmap(30, 30))
        logo.setFixedSize(30, 30)
        logo.setScaledContents(True)
        logo.setToolTip(core.APP_TITLE)
        lay.addWidget(logo, 0, Qt.AlignVCenter)

        ttl = QVBoxLayout()
        ttl.setSpacing(1)
        ttl.setContentsMargins(0, 0, 0, 0)
        t = QLabel(core.APP_TITLE)
        t.setObjectName("appTitle")
        s = QLabel(tr('为 RTX 20 / 30 系解锁 DLSS 帧生成'))
        s.setObjectName("appSub")
        ttl.addWidget(t)
        ttl.addWidget(s)
        lay.addLayout(ttl)
        lay.addStretch(1)

        # 语言切换：选项永远用各自语言的原生名字显示（英语就写 English）
        self.lang_sel = Combo()
        self.lang_sel.setObjectName("langSel")
        self.lang_sel.setCursor(Qt.PointingHandCursor)
        self._langs = i18n.available()
        for _code, _name in self._langs.items():
            self.lang_sel.addItem(_name, _code)
        _cur = i18n.get_lang()
        self.lang_sel.setCurrentIndex(list(self._langs).index(_cur)
                                      if _cur in self._langs else 0)
        self.lang_sel.setToolTip(tr('界面语言（切换后重启程序生效）'))
        self.lang_sel.currentIndexChanged.connect(self._on_lang_changed)
        lay.addWidget(self.lang_sel, 0, Qt.AlignVCenter)

        # 右侧状态点：显示是否已开启 HAGS，呼应左侧系统准备卡片
        self.tb_hags = Pill(tr('HAGS 检测中'), "muted")
        self.tb_hags.setToolTip(tr('硬件加速 GPU 计划状态'))
        lay.addWidget(self.tb_hags, 0, Qt.AlignVCenter)

        bar.mousePressEvent = self._tb_press
        bar.mouseMoveEvent = self._tb_move
        bar.mouseDoubleClickEvent = lambda e: self.toggle_max()
        return bar

    def toggle_max(self) -> None:
        """最大化 / 还原（无边框窗口需手动处理，并留出阴影边距）。"""
        if self.isMaximized() or self._normal_geo is not None:
            self._normal_geo = None
            lay = self.layout()
            if lay:
                lay.setContentsMargins(20, 20, 20, 20)
            self.showNormal()
            if hasattr(self, "lights"):
                self.lights.set_maximized(False)
        else:
            self._normal_geo = self.geometry()
            lay = self.layout()
            if lay:
                lay.setContentsMargins(0, 0, 0, 0)
            scr = self.screen().availableGeometry()
            self.setGeometry(scr)
            if hasattr(self, "lights"):
                self.lights.set_maximized(True)

    def _tb_press(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_origin = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _tb_move(self, e):
        if self._drag_origin is not None and e.buttons() & Qt.LeftButton:
            if self._normal_geo is not None:      # 拖动即还原
                self.toggle_max()
                self._drag_origin = (e.globalPosition().toPoint()
                                     - self.frameGeometry().topLeft())
            self.move(e.globalPosition().toPoint() - self._drag_origin)

    def mouseReleaseEvent(self, e):
        self._drag_origin = None
        self._resize_edge = None

    # 边缘拉伸
    _EDGE = 8

    def _edge_at(self, pos: QPoint):
        w, h = self.width(), self.height()
        e = []
        if pos.x() <= self._EDGE:
            e.append("l")
        elif pos.x() >= w - self._EDGE:
            e.append("r")
        if pos.y() <= self._EDGE:
            e.append("t")
        elif pos.y() >= h - self._EDGE:
            e.append("b")
        return "".join(e)

    def mouseMoveEvent(self, e):
        if self.shot_mode:
            return
        pos = e.position().toPoint()
        if e.buttons() & Qt.LeftButton and self._resize_edge:
            g = e.globalPosition().toPoint()
            geo = self.geometry()
            if "r" in self._resize_edge:
                geo.setRight(g.x())
            if "b" in self._resize_edge:
                geo.setBottom(g.y())
            if "l" in self._resize_edge:
                geo.setLeft(g.x())
            if "t" in self._resize_edge:
                geo.setTop(g.y())
            if geo.width() >= self.minimumWidth() and geo.height() >= self.minimumHeight():
                self.setGeometry(geo)
            return
        edge = self._edge_at(pos)
        cursors = {"l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor, "t": Qt.SizeVerCursor,
                   "b": Qt.SizeVerCursor, "lt": Qt.SizeFDiagCursor, "rb": Qt.SizeFDiagCursor,
                   "rt": Qt.SizeBDiagCursor, "lb": Qt.SizeBDiagCursor}
        self.setCursor(cursors.get(edge, Qt.ArrowCursor))

    def mousePressEvent(self, e):
        if self.shot_mode:
            return
        if e.button() == Qt.LeftButton:
            self._resize_edge = self._edge_at(e.position().toPoint()) or None

    # ------------------------------------------------- 显卡条

    def _build_gpu_bar(self) -> QWidget:
        w = QFrame()
        w.setObjectName("gpuCard")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 11, 14, 11)
        lay.setSpacing(14)

        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(tr(self.gpu.name))  # 未检测到时是中文兜底名
        name.setObjectName("gpuName")
        sub = QLabel(tr('驱动 {0}').format(self.gpu.driver or '未知')
                     + (tr(' · 显存 {0} MiB').format(self.gpu.vram_mb) if self.gpu.vram_mb else ""))
        sub.setObjectName("gpuSub")
        col.addWidget(name)
        col.addWidget(sub)
        lay.addLayout(col, 1)

        self.gpu_pill = Pill(tr('路由 {0}').format(self.gpu.route), "info" if self.gpu.supported else "warn")
        lay.addWidget(self.gpu_pill)
        lay.addWidget(Pill(tr('SM86 / SM75 内核'), "purple"))
        return w

    # ------------------------------------------------- 左侧列表

    def _build_side(self) -> QWidget:
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(348)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText(tr('搜索游戏…'))
        self.search.textChanged.connect(self._filter)
        row.addWidget(self.search, 1)

        self.btn_scan = QPushButton(tr('扫描游戏'))
        self.btn_scan.setObjectName("ghost")
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.clicked.connect(lambda: self.start_scan(False))
        row.addWidget(self.btn_scan)

        self.btn_deep = QPushButton(tr('深度扫描'))
        self.btn_deep.setObjectName("ghost")
        self.btn_deep.setCursor(Qt.PointingHandCursor)
        self.btn_deep.setToolTip(tr('按盘符全盘反查 DLSS 运行库，可发现免安装 / 非平台游戏'))
        self.btn_deep.clicked.connect(self._deep_menu)
        row.addWidget(self.btn_deep)
        lay.addLayout(row)

        self.count = QLabel(tr('尚未扫描'))
        self.count.setObjectName("sectionLabel")
        lay.addWidget(self.count)

        lay.addWidget(self._build_hags_card())

        self.list_area = QScrollArea()
        self.list_area.setWidgetResizable(True)
        holder = QWidget()
        self.list_lay = QVBoxLayout(holder)
        self.list_lay.setContentsMargins(0, 0, 6, 0)
        self.list_lay.setSpacing(8)
        self.list_lay.addStretch(1)
        self.list_area.setWidget(holder)
        lay.addWidget(self.list_area, 1)

        self.btn_add = QPushButton(tr('手动添加游戏目录…'))
        self.btn_add.setObjectName("ghost")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self.add_root)
        lay.addWidget(self.btn_add)
        return side

    def _deep_menu(self) -> None:
        m = QMenu(self)
        m.setStyleSheet(f"QMenu {{ background:{C['card2']}; border:1px solid {C['line2']};"
                        f"border-radius:8px; padding:6px; }}"
                        f"QMenu::item {{ padding:6px 18px; border-radius:6px; color:{C['text']}; }}"
                        f"QMenu::item:selected {{ background:{C['accent']}; color:#FFF; }}")
        for d in core.list_drives():
            m.addAction(d).setData(d)
        act = m.exec(QCursor.pos())
        if act:
            self.start_scan(True, [act.data()])

    # ------------------------------------------------- 系统准备（HAGS）

    def _build_hags_card(self) -> QWidget:
        self.hags_info = core.detect_hags(force=True)
        card = QFrame()
        card.setObjectName("hagsCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 11)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)
        t = QLabel(tr('系统准备'))
        t.setObjectName("cardTitle")
        t.setStyleSheet("font-size:12px; font-weight:500;")
        top.addWidget(t, 0)
        top.addStretch(1)
        self.hags_pill = Pill(tr('检测中'), "muted")
        top.addWidget(self.hags_pill, 0)
        lay.addLayout(top)

        name = QLabel(tr('硬件加速 GPU 计划（HAGS）'))
        name.setStyleSheet(f"font-size:12px; color:{C['text']};")
        lay.addWidget(name)

        self.hags_desc = QLabel("")
        self.hags_desc.setWordWrap(True)
        self.hags_desc.setStyleSheet(f"font-size:11px; color:{C['dim']};")
        lay.addWidget(self.hags_desc)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_hags = QPushButton(tr('一键开启'))
        self.btn_hags.setObjectName("ghost")
        self.btn_hags.setCursor(Qt.PointingHandCursor)
        self.btn_hags.clicked.connect(self.toggle_hags)
        row.addWidget(self.btn_hags, 1)
        self.btn_hags_manual = QPushButton(tr('手动设置'))
        self.btn_hags_manual.setObjectName("ghost")
        self.btn_hags_manual.setCursor(Qt.PointingHandCursor)
        self.btn_hags_manual.setToolTip(tr('打开「设置 → 系统 → 屏幕 → 图形设置」页面，手动切换开关'))
        self.btn_hags_manual.clicked.connect(self.open_hags_settings)
        row.addWidget(self.btn_hags_manual, 0)
        lay.addLayout(row)

        self.hags_tip = QLabel("")
        self.hags_tip.setWordWrap(True)
        self.hags_tip.setStyleSheet(f"font-size:11px; color:{C['warn']};")
        self.hags_tip.setVisible(False)
        lay.addWidget(self.hags_tip)

        self._refresh_hags()
        return card

    def _refresh_hags(self) -> None:
        info = core.detect_hags(force=True)
        self.hags_info = info
        if hasattr(self, "tb_hags"):
            if not info.supported:
                self.tb_hags.set_kind(tr('HAGS 不可用'), "muted")
            elif info.enabled:
                self.tb_hags.set_kind(tr('HAGS 已开启'), "ok")
            else:
                self.tb_hags.set_kind(tr('HAGS 未开启'), "warn")
        if not info.supported:
            self.hags_pill.set_kind(tr('不可用'), "muted")
            self.hags_desc.setText(tr('本机不满足条件：{0}。').format(info.reason))
            self.btn_hags.setEnabled(False)
            self.btn_hags.setText(tr('不可用'))
            self.hags_tip.setVisible(False)
            return

        if info.enabled:
            self.hags_pill.set_kind(tr('已开启'), "ok")
            self.hags_desc.setText(tr('已开启。GPU 自行调度命令队列，帧生成时帧时间更稳。'))
            self.btn_hags.setText(tr('关闭'))
        else:
            self.hags_pill.set_kind(tr('未开启'), "warn")
            self.hags_desc.setText(tr('未开启。帧生成会额外提交命令，开启后帧时间更稳，建议打开。'))
            self.btn_hags.setText(tr('一键开启'))

        if info.admin:
            self.btn_hags.setEnabled(True)
            self.hags_tip.setVisible(self.hags_info.needs_reboot_hint)
            if self.hags_info.needs_reboot_hint:
                self.hags_tip.setText(tr('提示：修改后需重启电脑才生效。'))
        else:
            self.btn_hags.setEnabled(False)
            self.btn_hags.setText(tr('需管理员权限'))
            self.hags_tip.setVisible(True)
            self.hags_tip.setText(tr('当前非管理员运行，无法自动修改；请用「手动设置」自行切换，或右键以管理员身份重新打开本程序。'))

    def toggle_hags(self) -> None:
        info = self.hags_info
        want = not info.enabled
        if not info.admin:
            self._log(tr('[错误] 需要管理员权限才能修改硬件加速 GPU 计划'))
            self.toast_msg(tr('需要管理员权限，请用「手动设置」'), "warn")
            return
        self.btn_hags.setEnabled(False)
        ok, msg = core.set_hags(want)
        self._log((tr('[完成] HAGS：{0}') if ok else tr('[错误] HAGS：{0}')).format(msg))
        if ok:
            # 整句成键：两段各自翻译后直接拼接在英语等语言里会粘死
            # （"Disabled" + "Hardware..."），所以这里用完整句子做键。
            self.toast_msg(tr('硬件加速 GPU 计划已开启，重启电脑后生效') if want
                           else tr('硬件加速 GPU 计划已关闭，重启电脑后生效'), "ok")
        else:
            self.toast_msg(msg, "bad")
        self._refresh_hags()

    def open_hags_settings(self) -> None:
        try:
            os.startfile("ms-settings:display-advancedgraphics")
            self._log(tr('[提示] 已打开「图形设置」页面，可手动切换硬件加速 GPU 计划'))
        except Exception as e:
            self._log(tr('[错误] 无法打开设置页面：{0}').format(e))
            self.toast_msg(tr('打开设置页失败，请手动到 设置 → 系统 → 屏幕 → 图形设置'), "warn")

    # ------------------------------------------------- 右侧详情

    def _build_detail(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_empty())
        self.stack.addWidget(self._build_game_page())
        lay.addWidget(self.stack, 1)

        self.console = QPlainTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        self.console.setFixedHeight(132)
        self.console.setLineWrapMode(QPlainTextEdit.NoWrap)
        # 注意：这里【绝对不能】给 console / viewport 加 WA_OpaquePaintEvent。
        # 该属性是「我已画满，别擦」的承诺；但 QPlainTextEdit 只保证重绘自己
        # 认为是脏区的部分，未覆盖处不会被擦除，于是底下主窗口的像素直接透出来
        # （表现为日志区半透明、能看到背景的渐变和滑动条残影）。
        # 正确做法是反过来：让 viewport 每帧自己填满背景。
        self.console.setFrameShape(QFrame.NoFrame)
        vp = self.console.viewport()
        if vp is not None:
            vp.setAutoFillBackground(True)
            vp.setAttribute(Qt.WA_OpaquePaintEvent, False)
            vp.setStyleSheet("background-color: #090C11;")
        self.console.appendPlainText("")
        lay.addWidget(self.console)
        return wrap

    def _build_empty(self) -> QWidget:
        w = QWidget()
        w.setObjectName("emptyWrap")
        lay = QVBoxLayout(w)
        lay.addStretch(1)
        t = QLabel(tr('选择左侧的游戏，查看识别结果'))
        t.setObjectName("emptyTitle")
        t.setAlignment(Qt.AlignCenter)
        s = QLabel(tr('支持 Steam / Epic / GOG / Ubisoft 库，也可深度扫描盘符或手动添加目录'))
        s.setObjectName("emptySub")
        s.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addStretch(2)
        return w

    def _build_game_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("hero")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(16, 14, 16, 14)
        hl.setSpacing(9)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.h_name = QLabel("—")
        self.h_name.setObjectName("heroTitle")
        top.addWidget(self.h_name, 0)
        self.h_pills = QHBoxLayout()
        self.h_pills.setSpacing(6)
        top.addLayout(self.h_pills)
        top.addStretch(1)
        hl.addLayout(top)
        self.h_sub = ElidedLabel("")
        self.h_sub.setObjectName("heroSub")
        hl.addWidget(self.h_sub)

        grid = QGridLayout()
        grid.setHorizontalSpacing(26)
        grid.setVerticalSpacing(5)
        self.kv_exe = KV(tr('渲染进程'), "—")
        self.kv_dir = KV(tr('安装目录'), "—")
        self.kv_res = KV(tr('当前分辨率'), "—")
        self.kv_ac = KV(tr('反作弊'), "—")
        self.kv_vram = KV(tr('显存预算'), "—")
        self.kv_state = KV(tr('部署状态'), "—")
        for i, kv in enumerate((self.kv_exe, self.kv_dir, self.kv_res,
                                self.kv_ac, self.kv_vram, self.kv_state)):
            grid.addWidget(kv, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        hl.addLayout(grid)
        lay.addWidget(hero)

        cfg = QFrame()
        cfg.setObjectName("card")
        cl = QVBoxLayout(cfg)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(12)
        t1 = QLabel(tr('插帧配置'))
        t1.setObjectName("cardTitle")
        cl.addWidget(t1)

        r1 = QHBoxLayout()
        r1.setSpacing(10)
        a = QLabel(tr('显卡路由'))
        a.setObjectName("kv")
        a.setMinimumWidth(max(66, a.sizeHint().width()))
        r1.addWidget(a)
        self.cmb_router = Combo()
        self.cmb_router.addItems([tr('自动（推荐）'), tr('SM86 · RTX 30 系'), tr('SM75 · RTX 20 系')])
        self.cmb_router.setFixedWidth(224)
        r1.addWidget(self.cmb_router)
        r1.addSpacing(14)
        b = QLabel(tr('入口 DLL'))
        b.setObjectName("kv")
        b.setMinimumWidth(max(66, b.sizeHint().width()))
        r1.addWidget(b)
        self.cmb_entry = Combo()
        self.cmb_entry.addItems([tr('自动选择')] + [e[1] for e in core.ENTRIES])
        self.cmb_entry.setFixedWidth(166)
        r1.addWidget(self.cmb_entry)
        r1.addStretch(1)
        cl.addLayout(r1)

        r2 = QHBoxLayout()
        r2.setSpacing(10)
        c = QLabel(tr('插帧倍率'))
        c.setObjectName("kv")
        c.setMinimumWidth(max(66, c.sizeHint().width()))
        r2.addWidget(c)
        self.seg_mult = Segmented(["2X", "3X", "4X"], 2)
        self.seg_mult.changed.connect(lambda _i: self._update_vram())
        r2.addWidget(self.seg_mult)
        r2.addSpacing(14)
        d = QLabel(tr('采样模式'))
        d.setObjectName("kv")
        d.setMinimumWidth(max(66, d.sizeHint().width()))
        r2.addWidget(d)
        self.sw_bilinear = Switch(False)
        r2.addWidget(self.sw_bilinear)
        self.lbl_bilinear = QLabel(tr('精确（默认）'))
        self.lbl_bilinear.setObjectName("kv")
        r2.addWidget(self.lbl_bilinear)
        r2.addStretch(1)
        e2 = QLabel(tr('诊断日志'))
        e2.setObjectName("kv")
        e2.setMinimumWidth(max(66, e2.sizeHint().width()))
        r2.addWidget(e2)
        self.sw_log = Switch(False)
        r2.addWidget(self.sw_log)
        cl.addLayout(r2)
        self.sw_bilinear.toggled.connect(
            lambda on: self.lbl_bilinear.setText(tr('近似（更快）') if on else tr('精确（默认）')))
        lay.addWidget(cfg)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.btn_install = QPushButton(tr('一键启用插帧'))
        self.btn_install.setObjectName("primary")
        self.btn_install.setCursor(Qt.PointingHandCursor)
        self.btn_install.clicked.connect(self.do_install)
        actions.addWidget(self.btn_install, 1)
        self.btn_restore = QPushButton(tr('一键恢复'))
        self.btn_restore.setObjectName("danger")
        self.btn_restore.setCursor(Qt.PointingHandCursor)
        self.btn_restore.clicked.connect(self.do_restore)
        actions.addWidget(self.btn_restore, 0)
        self.btn_open = QPushButton(tr('打开目录'))
        self.btn_open.setObjectName("ghost")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(self.open_dir)
        actions.addWidget(self.btn_open, 0)
        self.btn_copy = QPushButton(tr('复制路径'))
        self.btn_copy.setObjectName("ghost")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.clicked.connect(self.copy_path)
        actions.addWidget(self.btn_copy, 0)
        lay.addLayout(actions)

        self.hint = QLabel(
            tr('操作前请完全退出游戏。启用后重启游戏，在画面设置里打开帧生成并选择倍率；带反作弊的游戏请只在单机 / 离线模式下使用。恢复会清掉本工具写入的文件并还原备份。'))
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(f"font-size:11px; color:{C['dim']}; line-height:150%;")
        lay.addWidget(self.hint)

        lay.addStretch(1)
        return page

    # ------------------------------------------------- 日志 / 提示

    def _log(self, msg: str) -> None:
        color = C["muted"]
        for key, col in ((tr('[错误]'), C["bad"]), (tr('[警告]'), C["warn"]), (tr('[完成]'), C["ok"]),
                         (tr('[校验]'), C["accent"]), (tr('[跳过]'), C["warn"]), (tr('[提示]'), C["purple"]),
                         (tr('[移除]'), C["warn"]), (tr('[还原]'), C["ok"])):
            if msg.startswith(key) or f" {key}" in msg:
                color = col
                break
        stamp = time.strftime("%H:%M:%S")
        self.console.appendHtml(
            f'<span style="color:{C["dim"]}">{stamp}</span> '
            f'<span style="color:{color}">{escape(msg)}</span>')

    def toast_msg(self, msg: str, kind: str = "info") -> None:
        col = {"ok": C["ok"], "bad": C["bad"], "warn": C["warn"], "info": C["accent"]}.get(kind, C["accent"])
        self.toast.setStyleSheet(
            f"background:{C['card2']}; border:1px solid {col}; color:{col};"
            "border-radius:10px; padding:10px 18px; font-size:12px;")
        self.toast.setText(msg)
        self.toast.adjustSize()
        w = self.root.width()
        h = self.root.height()
        x = (w - self.toast.width()) // 2
        y0, y1 = h - 10, h - 56
        self.toast.move(x, y0)
        self.toast.show()
        self.toast.raise_()
        self._toast_anim.stop()
        self._toast_anim.setStartValue(QPoint(x, y0))
        self._toast_anim.setEndValue(QPoint(x, y1))
        self._toast_anim.start()
        QTimer.singleShot(2600, self.toast.hide)

    # ------------------------------------------------- 扫描

    def start_scan(self, deep: bool = False, roots: list[str] | None = None) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.btn_scan.setEnabled(False)
        self.btn_deep.setEnabled(False)
        self.status.setText(tr('正在扫描…'))
        self.count.setText(tr('扫描中…'))
        self.worker = ScanWorker(deep, roots or [])
        self.worker.progress.connect(self.status.setText)
        self.worker.done.connect(self.on_scan_done)
        self.worker.start()

    def on_scan_done(self, games: list, warns: list, err: str) -> None:
        self.btn_scan.setEnabled(True)
        self.btn_deep.setEnabled(True)
        if err:
            self._log(tr('[错误] 扫描失败：{0}').format(err))
            self.status.setText(tr('扫描失败'))
            self.toast_msg(tr('扫描失败，详见日志'), "bad")
            return
        for w in warns:
            self._log(tr('[警告] 运行包校验：{0}').format(w))
        self.games = games
        self._rebuild_list()
        n_ok = sum(1 for g in games if g.dlssg)
        n_on = sum(1 for g in games if g.deployed)
        self.count.setText(tr('识别到 {0} 个游戏 · {1} 个支持帧生成 · 已启用 {2}').format(len(games), n_ok, n_on))
        self.status.setText(tr('就绪'))
        self._log(tr('[完成] 扫描结束：共 {0} 个游戏，其中 {1} 个检测到 DLSSG 运行库').format(len(games), n_ok))
        if games and self.current is None:
            self.select(games[0].gid)
        self._repaint_all()

    def _rebuild_list(self) -> None:
        while self.list_lay.count() > 1:
            item = self.list_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.cards.clear()
        for g in self.games:
            card = GameCard(g)
            card.clicked.connect(self.select)
            self.cards[g.gid] = card
            self.list_lay.insertWidget(self.list_lay.count() - 1, card)
        self._filter(self.search.text())
        # 内容替换后兜底重绘一次：不依赖鼠标划过触发
        QTimer.singleShot(0, self._repaint_all)

    def _filter(self, text: str) -> None:
        q = (text or "").strip().lower()
        for g in self.games:
            card = self.cards.get(g.gid)
            if not card:
                continue
            hit = (not q) or q in g.name.lower() or q in (g.install_dir or "").lower()
            card.setVisible(hit)

    def add_root(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr('选择游戏目录（可多选后在列表里搜索）'),
                                             str(Path.home()))
        if not d:
            return
        st = core.load_state()
        roots = st.get("roots", [])
        if d not in roots:
            roots.append(d)
            st["roots"] = roots
            core.save_state(st)
        self._log(tr('[提示] 已添加自定义目录：{0}').format(d))
        self.start_scan(False)

    # ------------------------------------------------- 选择

    def select(self, gid: str) -> None:
        g = next((x for x in self.games if x.gid == gid), None)
        if not g:
            return
        self.current = g
        for k, card in self.cards.items():
            card.set_selected(k == gid)

        self.h_name.setText(g.name)
        while self.h_pills.count():
            it = self.h_pills.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.h_pills.addWidget(Pill(g.source, "muted"))
        if g.engine:
            self.h_pills.addWidget(Pill(g.engine, "purple"))
        self.h_pills.addWidget(Pill(tr('支持帧生成'), "info") if g.dlssg else Pill(tr('未检测到 DLSSG'), "muted"))
        if g.deployed:
            self.h_pills.addWidget(Pill(tr('已启用'), "ok"))
        if g.anticheat:
            self.h_pills.addWidget(Pill(tr('反作弊'), "warn"))

        self.h_sub.setRaw(tr('安装位置：{0}').format(g.install_dir))
        self.kv_exe.set(g.exe)
        self.kv_dir.set(g.exe_dir)
        w, h = g.resolution
        self.kv_res.set(f"{w}×{h}" if w else tr('未检测到'))
        self.kv_ac.set(tr('已检测到') if g.anticheat else tr('未检测到'))
        mult = self._mult()
        res = core.vram_hint(w, h, mult) if w else None
        if res and res[0]:
            self.kv_vram.set(tr('约 +{0} MiB（{1} 输出 / {2}X 额外占用）').format(res[0], res[1], mult))
        else:
            self.kv_vram.set(tr('按最终输出分辨率预留 300–800 MiB'))
        if g.deployed:
            cfg = g.config or {}
            if cfg:
                self.kv_state.set(tr('已部署 {0}（Router={1}）').format(g.entry, cfg.get('Router', '?')))
            else:
                self.kv_state.set(tr('已部署 {0}').format(g.entry))
            if cfg.get("Router") == "SM75":
                self.cmb_router.setCurrentIndex(2)
            elif cfg.get("Router") == "SM86":
                self.cmb_router.setCurrentIndex(1)
            m = int(cfg.get("MaxGeneratedFrames", "3") or 3)
            self.seg_mult.set_value({1: 0, 2: 1, 3: 2}.get(m, 2))
            self.sw_bilinear.setChecked(cfg.get("HardwareBilinear") == "1")
            if cfg.get("Level") == "2":
                self.sw_log.setChecked(True)
        else:
            self.kv_state.set(tr('未部署'))
        self.btn_install.setText(tr('重新部署 / 更新配置') if g.deployed else tr('一键启用插帧'))
        self.btn_restore.setEnabled(g.deployed or bool(g.entry))
        self.stack.setCurrentIndex(1)
        # 切页/重建控件后立即整窗补绘：修复「进入页面后不交互就有文字被遮挡」
        QTimer.singleShot(0, self._repaint_all)

        self._log(tr('[提示] 已选择：{0} → {1}').format(g.name, g.exe_dir))

    # ------------------------------------------------- 操作

    def _router(self) -> str:
        i = self.cmb_router.currentIndex()
        return {0: self.gpu.route, 1: "SM86", 2: "SM75"}[i]

    def _mult(self) -> int:
        return {0: 2, 1: 3, 2: 4}.get(self.seg_mult.value(), 4)

    def _update_vram(self) -> None:
        g = self.current
        if not g:
            return
        w, h = g.resolution
        mult = self._mult()
        res = core.vram_hint(w, h, mult) if w else None
        if res and res[0]:
            self.kv_vram.set(tr('约 +{0} MiB（{1} 输出 / {2}X 额外占用）').format(res[0], res[1], mult))
        else:
            self.kv_vram.set(tr('按最终输出分辨率预留 300–800 MiB'))

    def _entry(self) -> str:
        return "" if self.cmb_entry.currentIndex() == 0 else self.cmb_entry.currentText()

    def do_install(self) -> None:
        g = self.current
        if not g:
            return
        if g.anticheat:
            self._log(tr('[警告] 检测到反作弊，线上模式可能被视为违规，请只在单机 / 离线环境使用'))
        if not g.dlssg:
            self._log(tr('[警告] 该游戏未检测到 nvngx_dlssg.dll，可能不支持帧生成；若游戏内置 DLSSG 能力仍可尝试'))
        self.btn_install.setEnabled(False)
        self.status.setText(tr('正在部署…'))
        self.kw = ActionWorker(core.deploy, g, self._router(), self._mult(),
                               self.sw_bilinear.isChecked(), 2 if self.sw_log.isChecked() else 1,
                               self._entry())
        self.kw.done.connect(self._on_install_done)
        self.kw.start()

    def _on_install_done(self, ok: bool, logs: list, err: str) -> None:
        self.btn_install.setEnabled(True)
        for l in logs:
            self._log(l)
        if err:
            self._log(tr('[错误] {0}').format(err))
        if ok:
            self._refresh_current()
            self.status.setText(tr('已启用'))
            self.toast_msg(tr('已启用插帧，重启游戏后在画面设置里选择倍率'), "ok")
        else:
            self.status.setText(tr('部署失败'))
            self.toast_msg(tr('部署失败，详见日志'), "bad")

    def do_restore(self) -> None:
        g = self.current
        if not g:
            return
        self.btn_restore.setEnabled(False)
        self.status.setText(tr('正在恢复…'))
        self.kw = ActionWorker(core.restore, g)
        self.kw.done.connect(self._on_restore_done)
        self.kw.start()

    def _on_restore_done(self, ok: bool, logs: list, err: str) -> None:
        for l in logs:
            self._log(l)
        if err:
            self._log(tr('[错误] {0}').format(err))
        self._refresh_current()
        self.btn_restore.setEnabled(ok and self.current is not None and self.current.deployed)
        if ok:
            self.status.setText(tr('已恢复'))
            self.toast_msg(tr('已恢复原状，游戏目录已清理干净'), "ok")
        else:
            self.status.setText(tr('恢复未完成'))
            self.toast_msg(tr('没有可恢复的部署或已被占用'), "warn")

    def _refresh_current(self) -> None:
        g = self.current
        if not g:
            return
        entry, ours = core.entry_of_deployment(g.exe_dir)
        g.deployed = ours
        g.entry = entry
        g.config = core.read_deployed_config(g.exe_dir)
        card = self.cards.get(g.gid)
        if card:
            card.refresh()
        self.select(g.gid)
        n_on = sum(1 for x in self.games if x.deployed)
        n_ok = sum(1 for x in self.games if x.dlssg)
        self.count.setText(tr('识别到 {0} 个游戏 · {1} 个支持帧生成 · 已启用 {2}').format(len(self.games), n_ok, n_on))

    def open_dir(self) -> None:
        if self.current and Path(self.current.exe_dir).is_dir():
            os.startfile(self.current.exe_dir)

    def copy_path(self) -> None:
        if self.current:
            QApplication.clipboard().setText(self.current.exe_dir)
            self.toast_msg(tr('路径已复制到剪贴板'), "info")
            self._log(tr('[提示] 已复制路径：{0}').format(self.current.exe_dir))


def escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _icon_pixmap(size: int) -> QPixmap:
    """KANNI DLSS 图标：深空底 + K 字标 + 插帧弧 + 帧孔。

    设计说明：
      · 圆角方块底 = 与软件窗口同样的 r≈23% 圆角语言；
      · 「K」用「竖笔 + 一粗一细两道投影臂」构成，粗臂即帧生成的方向感；
      · 右侧一道 3/4 弧 + 弧上的实心点 = DLSS「补出中间帧」的隐喻；
      · 左上/右下两组小方孔 = 胶片齿孔，呼应「帧」。
    全部按 size 归一化绘制，因此 16px 到 512px 都锐利。
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    s = float(size)
    u = s / 100.0                       # 归一化单位：所有尺寸都乘 u

    # ---- 底：深空渐变 + 圆角
    radius = 23.0 * u
    body = QPainterPath()
    body.addRoundedRect(QRectF(0.6 * u, 0.6 * u, s - 1.2 * u, s - 1.2 * u), radius, radius)

    bg = QLinearGradient(0, 0, s, s)
    bg.setColorAt(0.0, QColor("#161C2B"))
    bg.setColorAt(0.52, QColor("#0D111A"))
    bg.setColorAt(1.0, QColor("#080A11"))
    p.fillPath(body, QBrush(bg))

    # 左上角一团冷光，让平面不至于死板
    glow = QRadialGradient(s * 0.30, s * 0.20, s * 0.72)
    glow.setColorAt(0.0, QColor(91, 140, 255, 62))
    glow.setColorAt(1.0, QColor(91, 140, 255, 0))
    p.save()
    p.setClipPath(body)
    p.fillRect(QRectF(0, 0, s, s), QBrush(glow))
    p.restore()

    # 内描边：上半亮、下半暗，做出一点厚度
    rim = QLinearGradient(0, 0, 0, s)
    rim.setColorAt(0.0, QColor(255, 255, 255, 40))
    rim.setColorAt(0.5, QColor(255, 255, 255, 12))
    rim.setColorAt(1.0, QColor(0, 0, 0, 70))
    p.setPen(QPen(QBrush(rim), max(1.0, 1.4 * u)))
    p.setBrush(Qt.NoBrush)
    p.drawPath(body)

    # ---- 胶片齿孔：上下两条，用提亮的圆角小方块 + 一点内阴影
    # 小尺寸下齿孔会糊成噪点，且会挤压 K 字标的可辨识度，故只在 >=40px 时绘制。
    if size >= 40:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(155, 184, 255, 58))
        for i in range(5):
            x = 17.0 + i * 16.5
            p.drawRoundedRect(QRectF(x * u, 6.6 * u, 10.5 * u, 8.0 * u),
                              3.2 * u, 3.2 * u)
            p.drawRoundedRect(QRectF(x * u, 85.4 * u, 10.5 * u, 8.0 * u),
                              3.2 * u, 3.2 * u)

    # ---- 插帧弧：右侧 3/4 圆弧，完整收在画布内
    arc_pen = QPen(QColor("#5B8CFF"), 6.0 * u)
    arc_pen.setCapStyle(Qt.RoundCap)
    p.setPen(arc_pen)
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(37.0 * u, 26.0 * u, 50.0 * u, 50.0 * u), -62 * 16, 272 * 16)

    # 弧末端一个实心点 = 被补出来的那一帧
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#AFC7FF"))
    p.drawEllipse(QPointF(63.0 * u, 28.6 * u), 4.8 * u, 4.8 * u)

    # ---- K 字标：竖笔 + 一粗一细两臂
    k_pen = QPen(QColor("#FFFFFF"), 11.0 * u)
    k_pen.setCapStyle(Qt.RoundCap)
    k_pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(k_pen)
    p.drawLine(QPointF(28.5 * u, 26.0 * u), QPointF(28.5 * u, 74.0 * u))

    k_pen2 = QPen(QColor("#E4ECFF"), 10.0 * u)
    k_pen2.setCapStyle(Qt.RoundCap)
    p.setPen(k_pen2)
    p.drawLine(QPointF(28.0 * u, 50.0 * u), QPointF(52.5 * u, 27.0 * u))

    k_pen3 = QPen(QColor("#9BB8FF"), 8.4 * u)
    k_pen3.setCapStyle(Qt.RoundCap)
    p.setPen(k_pen3)
    p.drawLine(QPointF(29.5 * u, 50.5 * u), QPointF(48.5 * u, 73.0 * u))

    p.end()
    return pm


def make_icon() -> QIcon:
    icon = QIcon()
    # 多尺寸塞进同一个 ICO/窗口图标，任务栏与 Alt+Tab 都清晰
    for sz in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256):
        icon.addPixmap(_icon_pixmap(sz))
    return icon


def export_icon_ico(path: str) -> str:
    """导出多尺寸 .ico（给 PyInstaller 的 --icon 用）。"""
    from PySide6.QtGui import QImage
    # Qt 的 ICO 写入器只接受单张图，这里手工拼一个多尺寸 ICO。
    import struct
    sizes = (16, 24, 32, 48, 64, 128, 256)
    pngs = []
    for sz in sizes:
        pm = _icon_pixmap(sz)
        buf = QBuffer()
        buf.open(QBuffer.WriteOnly)
        pm.save(buf, "PNG")
        pngs.append((sz, bytes(buf.data())))
        buf.close()

    n = len(pngs)
    header = struct.pack("<HHH", 0, 1, n)
    entries = b""
    offset = 6 + 16 * n
    payload = b""
    for sz, data in pngs:
        w = 0 if sz >= 256 else sz
        h = 0 if sz >= 256 else sz
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)

    with open(path, "wb") as f:
        f.write(header + entries + payload)
    return path


def run(shot: str = "", shot_delay: int = 9000) -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    f = QFont("Microsoft YaHei UI", 9)
    f.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(f)
    app.setStyleSheet(qss())

    win = MainWindow(shot_mode=bool(shot))
    win.show()

    # 注意：不要对无边框 + WA_TranslucentBackground 的窗口做 windowOpacity 动画，
    # 会让 DWM 反复整体失效重合成，表现为界面卡住 / 局部空白 / 移动窗口才刷新。
    # 需要入场效果时用 splash 的淡出即可。

    if shot:
        def grab() -> None:
            win.grab().save(shot, "PNG")
            print(f"screenshot saved: {shot}")
            app.quit()
        QTimer.singleShot(shot_delay, grab)

    return app.exec()
