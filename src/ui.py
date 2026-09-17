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
                               QVBoxLayout, QWidget, QLayout, QLayoutItem)

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
#detailScroll QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
#detailScroll QScrollBar::handle:vertical { background: #2E3648; border-radius: 5px; min-height: 28px; }
#detailScroll QScrollBar::handle:vertical:hover { background: #3A4459; }
#detailScroll QScrollBar::add-line:vertical, #detailScroll QScrollBar::sub-line:vertical { height: 0; }
#detailScroll QScrollBar::add-page:vertical, #detailScroll QScrollBar::sub-page:vertical { background: transparent; }
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

    def set_options(self, options: list[str], current: int = 0) -> None:
        """重建档位（运行库切换时倍率上限会变）。"""
        lay = self.layout()
        for b in list(self.group.buttons()):
            self.group.removeButton(b)
            lay.removeWidget(b)
            b.deleteLater()
        for i, opt in enumerate(options):
            b = QPushButton(opt)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(i == current)
            self.group.addButton(b, i)
            lay.addWidget(b)


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


class FlowLayout(QLayout):
    """自动换行布局：空间不足时把子控件换到下一行，而不是压缩/裁剪。

    用于工具栏式横向排列（显卡伪装的控件组、操作按钮组等）。
    移植自 Qt 官方 FlowLayout 示例，补上 heightForWidth 支持。
    """

    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 8,
                 v_spacing: int = 8):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h = h_spacing
        self._v = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    # --- QLayout 必需接口 ---
    def addItem(self, item) -> None:      # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):              # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):              # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):        # noqa: N802
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:   # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):                   # noqa: N802
        return self.minimumSize()

    def minimumSize(self):                # noqa: N802
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect, test_only: bool) -> int:
        m = self.contentsMargins()
        eff = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = eff.x(), eff.y(), 0
        for it in self._items:
            w = it.sizeHint().width()
            h = it.sizeHint().height()
            if w > eff.width() and eff.width() > 0:
                w = eff.width()          # 单控件超宽时收缩到可用宽度
            if x + w > eff.right() + 1 and line_h > 0:
                x = eff.x()
                y += line_h + self._v
                line_h = 0
            if not test_only:
                it.setGeometry(QRect(QPoint(x, y), QSize(w, h)))
            x += w + self._h
            line_h = max(line_h, h)
        return y + line_h - rect.y() + m.bottom()


class FlowRow(QWidget):
    """自动换行的横向行容器。

    FlowLayout 只负责摆放；但 QScrollArea 不会采纳 heightForWidth，
    换行后容器高度仍按单行算 -> 控件会重叠。这里在尺寸变化时把自身
    最小高度同步为「按当前宽度换行后真实需要的高度」，从而在任意窄宽
    下都不裁剪、不重叠，外层滚动容器自动出现滚动条。
    """

    def __init__(self, h_spacing: int = 10, v_spacing: int = 8, parent=None):
        super().__init__(parent)
        self._flow = FlowLayout(self, margin=0,
                                h_spacing=h_spacing, v_spacing=v_spacing)

    def add(self, w):
        self._flow.addWidget(w)
        return w

    def _sync_height(self) -> None:
        w = max(1, self.width())
        h = self._flow.heightForWidth(w)
        if h > 0 and h != self.minimumHeight():
            self.setMinimumHeight(h)

    def resizeEvent(self, e) -> None:      # noqa: N802
        super().resizeEvent(e)
        self._sync_height()

    def showEvent(self, e) -> None:        # noqa: N802
        super().showEvent(e)
        self._sync_height()


class KVGrid(QWidget):
    """响应式键值网格：宽度够时多列，变窄时自动降为单列。

    「渲染进程 / 安装目录 / 当前分辨率 / 反作弊 / 显存预算 / 部署状态」
    六项在窄窗口下必须完整可见，不能挤压或省略，因此按可用宽度动态决定列数。

    尺寸协商要点（此前高度塌陷为 0 的原因）：
    - __init__ 里先按单列填充一次，保证 grid 永远有内容，sizeHint 不为空；
    - 显式实现 sizeHint / minimumSizeHint，把 QGridLayout 的尺寸传上去；
    - 声明 hasHeightForWidth + heightForWidth，换行导致高度变化时父布局能感知。
    """

    def __init__(self, items: list, min_col_w: int = 300, max_cols: int = 2):
        super().__init__()
        self._items = list(items)
        self._min_col_w = min_col_w
        self._max_cols = max(1, max_cols)
        self._cols = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(26)
        self._grid.setVerticalSpacing(5)
        for kv in self._items:
            kv.setParent(self)
        # 关键：先落一次单列，避免首次布局时 grid 为空 -> 高度 0
        self._relayout(1)
        self.setMinimumHeight(self._grid.minimumSize().height())

    def _cols_for(self, width: int) -> int:
        if width <= 0:
            return 1
        n = max(1, width // max(1, self._min_col_w))
        return min(self._max_cols, n)

    def _relayout(self, cols: int) -> None:
        if cols == self._cols and self._grid.count():
            return
        self._cols = cols
        while self._grid.count():
            self._grid.takeAt(0)
        for i, kv in enumerate(self._items):
            self._grid.addWidget(kv, i // cols, i % cols)
        for c in range(self._max_cols):
            self._grid.setColumnStretch(c, 1 if c < cols else 0)
        # 内容变化后同步最小高度，保证多行内容不被压扁
        self.setMinimumHeight(self._grid.minimumSize().height())
        self.updateGeometry()

    def hasHeightForWidth(self) -> bool:   # noqa: N802
        return True

    def heightForWidth(self, w: int) -> int:   # noqa: N802
        return self._grid.heightForWidth(w) if self._grid.hasHeightForWidth() \
            else self._grid.sizeHint().height()

    def sizeHint(self):                    # noqa: N802
        if not self._grid.count():
            self._relayout(1)
        return self._grid.sizeHint()

    def minimumSizeHint(self):             # noqa: N802
        if not self._grid.count():
            self._relayout(1)
        return self._grid.minimumSize()

    def resizeEvent(self, e) -> None:      # noqa: N802
        super().resizeEvent(e)
        self._relayout(self._cols_for(self.width()))

    def showEvent(self, e) -> None:        # noqa: N802
        super().showEvent(e)
        self._relayout(self._cols_for(self.width()))


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

    def __init__(self, parent=None, embedded: bool = False):
        super().__init__(parent)
        self.setObjectName("splash")
        # embedded=True：作为主窗口的子控件内嵌显示（不弹独立窗口）；
        # embedded=False：旧的顶层窗口模式（保留以兼容）。
        self.embedded = embedded
        # 不透明绘制 + 纯自绘（无半透明）：DWM 不用做逐帧合成，
        # 从根上避免「卡住 / 局部空白 / 要鼠标划过才刷新」这类重绘残缺。
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

        # 尺寸自适应：所有几何量按容器缩放（基准 1120x720），
        # 窗口变大/变小时动画整体等比放大缩小，不再用固定字号。
        BASE_W, BASE_H = 1120.0, 720.0
        k = max(0.55, min(2.2, min(w / BASE_W, h / BASE_H)))
        self._scale = k

        # 不透明绘制：先整块铺满（避免残留），再用圆角路径画背景
        p.fillRect(self.rect(), QColor("#05070B"))
        radius = 16.0 if not self.embedded else 0.0
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
        cx, cy = w / 2, h / 2 - 8 * k

        # 中心光晕（半径随容器缩放）
        radius_glow = max(w, h) * 0.34
        radial = QRadialGradient(cx, cy, radius_glow)
        radial.setColorAt(0.0, QColor(91, 140, 255, 34))
        radial.setColorAt(1.0, QColor(91, 140, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(radial))
        p.drawEllipse(QRectF(cx - radius_glow, cy - radius_glow,
                             radius_glow * 2, radius_glow * 2))

        # KANNI 逐字渐显：每个字符有自己的 [起, 起+0.42] 窗口。
        # 字号按容器缩放（基准 46pt @1120x720），窗口越大字越大。
        f = QFont("Segoe UI")
        f.setPixelSize(max(18, int(round(62 * k))))
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
        baseline = cy + fm.capHeight() / 2 + 2 * k
        for i, ch in enumerate(self.WORD):
            t0 = i * step
            raw = (self._progress - t0) / span
            kk = max(0.0, min(1.0, raw))
            kk = 1 - (1 - kk) ** 3                    # easeOutCubic
            if kk <= 0.001:
                x += adv[i]
                continue
            # 未完成的字符带一点上浮与光晕（幅度随容器缩放）
            rise = (1 - kk) * 16 * k
            glow = 26 * (kk ** 1.6) * (1 if self._progress < 1 else 0.6)
            col = QColor("#7FA3FF")
            col.setAlphaF(min(1.0, kk * 0.42))
            # 描边发光（用同一字符描边近似）
            if glow > 1:
                gp = QPainterPath()
                gp.addText(x, baseline - rise, f, ch)
                p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(glow * 2.2)),
                              2.0 * k))
                p.setBrush(Qt.NoBrush)
                p.drawPath(gp)
            p.setPen(QColor(233, 236, 241, int(255 * kk)))
            p.drawText(QPointF(x, baseline - rise), ch)
            x += adv[i]

        # 副标题（字号随容器缩放）
        f2 = QFont("Segoe UI")
        f2.setPixelSize(max(8, int(round(12 * k))))
        f2.setLetterSpacing(QFont.PercentageSpacing, 300)
        p.setFont(f2)
        p.setPen(QColor(139, 147, 163, int(150 * a)))
        sub = self.SUB
        fm2 = QFontMetricsF(f2)
        p.drawText(QPointF(cx - fm2.horizontalAdvance(sub) / 2,
                           baseline + 34 * k), sub)

        # 载入点：三个点依次呼吸（位置与半径随容器缩放）
        dot_y = baseline + 58 * k
        gap = 16 * k
        for i in range(3):
            ph = (self._tick * 0.42 + i * 0.28) % 1.0
            breathe = 0.35 + 0.65 * (1 - abs(ph * 2 - 1))
            r = (2.6 + 1.6 * breathe) * k
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(91, 140, 255, int(210 * breathe * a)))
            p.drawEllipse(QRectF(cx - gap + i * gap - r, dot_y - r, r * 2, r * 2))
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
        # 默认高度提高：顶部新增系统栏（HAGS + 显卡伪装）后 720 偏挤，
        # 高度给到 840，同时抬高最小高度下限，保证游戏列表有充足展示空间。
        # 顶部有 GPU 条 + 系统栏，详情页与侧栏各自可滚动，
        # 因此最小尺寸可以下调，覆盖「矮宽 / 窄高」极端场景。
        self.setMinimumSize(780, 520)
        self.resize(1160, 840)
        if not shot_mode:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            # 半透明分层窗口：外圈 20px 边距真正透明，四周圆角由 RootFrame 画出。
            # 历史上它有过「残影/文字遮挡」问题，但根因其实是 ①ElidedLabel 之前的
            # 字符数截断、②kv 标签被压缩到 10-11px 两类真实布局缺陷 + 少量 DWM
            # 陈旧瓦片。①② 已根治（像素级省略 + 高度锁），重绘守卫见 changeEvent /
            # _repaint_all —— 因此这里恢复半透明以找回圆角，不再牺牲观感。
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_NoSystemBackground, True)

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
        # 系统准备 + 显卡伪装：横向系统栏，不再占用左侧游戏列表空间
        root_lay.addWidget(self._build_sys_bar())

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
        """载入动画【内嵌】在主窗口内显示（不弹独立窗口）。

        实现要点：
        - Splash 作为 root 的子控件，铺满 root 区域并置顶（raise_()）；
        - 用不透明自绘 + WA_OpaquePaintEvent，避免半透明逐帧合成的重绘残缺；
        - 随主窗口缩放：resizeEvent 里同步几何（子控件天然随父级布局，
          这里额外兜底一次，确保动画画布尺寸即时跟随）。
        """
        self.splash = Splash(self.root, embedded=True)
        self.splash.finished.connect(self._splash_gone)
        self._place_splash()
        self.splash.show()
        self.splash.raise_()
        self.splash.start()

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
        if getattr(s, "embedded", False):
            # 内嵌模式：铺满 root 区域（随 root 尺寸自适应）
            r = self.root.rect()
            if s.geometry() != r:
                s.setGeometry(r)
                s.raise_()
            return
        # 顶层模式（兼容保留）：盖满整个窗口
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
            s.hide()
            s.deleteLater()
            self.splash = None
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
        # DWM 对分层窗口的合成可能晚于 Qt 完成重绘，追加两级延迟补绘
        # （内容不变的 repaint 没有视觉开销，但能把迟到的陈旧瓦片压掉）
        QTimer.singleShot(150, self.update)
        QTimer.singleShot(450, self.update)

    def changeEvent(self, e) -> None:
        """激活/最大化等状态变化时立即整窗补绘：
        半透明窗口的状态切换是残影高发点，也让最大化后的直角重画即时生效。"""
        super().changeEvent(e)
        if e.type() in (QEvent.Type.ActivationChange, QEvent.Type.WindowStateChange):
            QTimer.singleShot(0, self._repaint_all)

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
        lay.addWidget(Pill(tr('SM86 / SM75 内核 · 0.3.2'), "purple"))
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

    # ------------------------------------------------- 显卡伪装

    def _build_mask_card(self) -> QWidget:
        """显卡伪装卡片（横向紧凑）：型号选择 → 应用 / 还原。"""
        card = QFrame()
        card.setObjectName("hagsCard")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        # 标题 + 状态
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(tr('显卡伪装'))
        t.setObjectName("cardTitle")
        t.setStyleSheet("font-size:12px; font-weight:500;")
        col.addWidget(t)
        self.mask_desc = QLabel("")
        self.mask_desc.setStyleSheet(f"font-size:11px; color:{C['dim']};")
        col.addWidget(self.mask_desc)
        lay.addLayout(col, 1)

        self.mask_pill = Pill(tr('检测中'), "muted")
        lay.addWidget(self.mask_pill, 0)

        # 型号选择：前缀（40/50 系）+ 后缀（50/60/70/80/90 及 Ti）
        self.cmb_prefix = Combo()
        self.cmb_prefix.setFixedHeight(32)
        self.cmb_prefix.setFixedWidth(96)
        for p in core.MASK_PREFIXES:
            self.cmb_prefix.addItem(tr(p), p)
        lay.addWidget(self.cmb_prefix, 0)

        self.cmb_suffix = Combo()
        self.cmb_suffix.setFixedHeight(32)
        self.cmb_suffix.setFixedWidth(92)
        for s in core.MASK_SUFFIXES:
            self.cmb_suffix.addItem(tr(s), s)
        lay.addWidget(self.cmb_suffix, 0)

        # 自定义输入（留空则用上方下拉框）
        self.ed_mask_custom = QLineEdit()
        self.ed_mask_custom.setObjectName("search")
        self.ed_mask_custom.setPlaceholderText(tr('自定义（可选）'))
        self.ed_mask_custom.setToolTip(
            tr('填了就优先用这里的型号；留空则用左侧下拉框的选择'))
        self.ed_mask_custom.setFixedHeight(32)
        self.ed_mask_custom.setFixedWidth(150)
        lay.addWidget(self.ed_mask_custom, 0)

        self.btn_mask_apply = QPushButton(tr('应用伪装'))
        self.btn_mask_apply.setObjectName("ghost")
        self.btn_mask_apply.setFixedHeight(32)
        self.btn_mask_apply.setCursor(Qt.PointingHandCursor)
        self.btn_mask_apply.clicked.connect(self.apply_mask)
        lay.addWidget(self.btn_mask_apply, 0)

        self.btn_mask_restore = QPushButton(tr('还原'))
        self.btn_mask_restore.setObjectName("ghost")
        self.btn_mask_restore.setFixedHeight(32)
        self.btn_mask_restore.setCursor(Qt.PointingHandCursor)
        self.btn_mask_restore.setToolTip(tr('恢复原始显卡名称，取消伪装'))
        self.btn_mask_restore.clicked.connect(self.restore_mask)
        lay.addWidget(self.btn_mask_restore, 0)

        self.btn_mask_restart = QPushButton(tr('重启显卡'))
        self.btn_mask_restart.setObjectName("ghost")
        self.btn_mask_restart.setFixedHeight(32)
        self.btn_mask_restart.setCursor(Qt.PointingHandCursor)
        self.btn_mask_restart.setToolTip(
            tr('立即生效：重启显卡设备使新名称对游戏可见（画面会短暂黑屏）'))
        self.btn_mask_restart.clicked.connect(self.restart_gpu)
        lay.addWidget(self.btn_mask_restart, 0)

        self._refresh_mask()
        return card

    def _refresh_mask(self) -> None:
        info = core.detect_gpu_mask(force=True)
        self.mask_info = info

        if not info.supported:
            self.mask_pill.set_kind(tr('不可用'), "muted")
            self.mask_desc.setText(tr('本机不满足条件：{0}').format(info.reason))
            self.btn_mask_apply.setEnabled(False)
            self.btn_mask_restore.setEnabled(False)
            return

        if info.masked:
            self.mask_pill.set_kind(tr('已伪装'), "warn")
            self.mask_desc.setText(
                tr('{0}（原 {1}）· 点「重启显卡」立即生效')
                .format(info.current, info.original))
        else:
            self.mask_pill.set_kind(tr('未伪装'), "muted")
            self.mask_desc.setText(tr('当前：{0}').format(info.current or tr('未知')))

        # 还原按钮只在有原始记录时可用
        self.btn_mask_restore.setEnabled(bool(info.original))

        if not info.admin:
            self.btn_mask_apply.setEnabled(False)
            self.mask_desc.setText(
                tr('当前非管理员运行，无法修改显卡注册表；请右键以管理员身份重新打开本程序。'))
        else:
            self.btn_mask_apply.setEnabled(True)

    def _mask_choice(self) -> tuple[str, str]:
        """取用户选择的型号。

        自定义输入优先；支持三种写法：
          - 纯数字 "4090"        -> RTX 4090
          - 带系列 "RTX 4090"    -> RTX 4090
          - 完整名 "NVIDIA ..."  -> 原样使用
        留空则用下拉框的前缀 + 后缀。
        """
        custom = self.ed_mask_custom.text().strip()
        if custom:
            if custom.isdigit():
                custom = f"RTX {custom}"
            return "", custom
        return self.cmb_prefix.currentData(), self.cmb_suffix.currentData()

    def apply_mask(self) -> None:
        prefix, suffix = self._mask_choice()
        preview = core.build_mask_name(prefix, suffix) if prefix else suffix
        if not preview or preview.endswith("GeForce"):
            self.toast_msg(tr('请先选择或填写要伪装的显卡型号'), "warn")
            return
        ok, msg = core.apply_gpu_mask(prefix, suffix)
        self._log((tr('[完成] {0}') if ok else tr('[错误] {0}')).format(msg))
        self.toast_msg(msg, "ok" if ok else "bad")
        self._refresh_mask()

    def restore_mask(self) -> None:
        ok, msg = core.restore_gpu_mask()
        self._log((tr('[完成] {0}') if ok else tr('[错误] {0}')).format(msg))
        self.toast_msg(msg, "ok" if ok else "bad")
        self._refresh_mask()

    def restart_gpu(self) -> None:
        """重启显卡设备，让名称改动对游戏（DXGI）立即生效。"""
        ok, msg = core.restart_gpu_device()
        self._log((tr('[完成] {0}') if ok else tr('[错误] {0}')).format(msg))
        self.toast_msg(msg, "ok" if ok else "bad")
        self._refresh_mask()

    # ------------------------------------------------- 系统准备（HAGS）

    def _build_sys_bar(self) -> QWidget:
        """系统栏：横向承载「系统准备」与「显卡伪装」，不占用游戏列表空间。"""
        bar = QWidget()
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self._build_hags_card())
        lay.addWidget(self._build_mask_card())
        return bar

    def _build_hags_card(self) -> QWidget:
        """系统准备卡片（横向紧凑）。"""
        self.hags_info = core.detect_hags(force=True)
        card = QFrame()
        card.setObjectName("hagsCard")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(tr('系统准备'))
        t.setObjectName("cardTitle")
        t.setStyleSheet("font-size:12px; font-weight:500;")
        col.addWidget(t)
        self.hags_desc = QLabel("")
        self.hags_desc.setStyleSheet(f"font-size:11px; color:{C['dim']};")
        col.addWidget(self.hags_desc)
        lay.addLayout(col, 1)

        self.hags_pill = Pill(tr('检测中'), "muted")
        lay.addWidget(self.hags_pill, 0)

        self.btn_hags = QPushButton(tr('一键开启'))
        self.btn_hags.setObjectName("ghost")
        self.btn_hags.setFixedHeight(32)
        self.btn_hags.setCursor(Qt.PointingHandCursor)
        self.btn_hags.setToolTip(tr('硬件加速 GPU 计划（HAGS）：开启后帧生成时帧时间更稳'))
        self.btn_hags.clicked.connect(self.toggle_hags)
        lay.addWidget(self.btn_hags, 0)

        self.btn_hags_manual = QPushButton(tr('手动设置'))
        self.btn_hags_manual.setObjectName("ghost")
        self.btn_hags_manual.setFixedHeight(32)
        self.btn_hags_manual.setCursor(Qt.PointingHandCursor)
        self.btn_hags_manual.setToolTip(tr('打开「设置 → 系统 → 屏幕 → 图形设置」页面，手动切换开关'))
        self.btn_hags_manual.clicked.connect(self.open_hags_settings)
        lay.addWidget(self.btn_hags_manual, 0)

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
            return

        if info.enabled:
            self.hags_pill.set_kind(tr('已开启'), "ok")
            self.btn_hags.setText(tr('关闭'))
        else:
            self.hags_pill.set_kind(tr('未开启'), "warn")
            self.btn_hags.setText(tr('一键开启'))

        if info.admin:
            self.btn_hags.setEnabled(True)
            tip = tr('硬件加速 GPU 计划（HAGS）')
            if info.enabled:
                tip += tr('：已开启，帧生成帧时间更稳。')
            else:
                tip += tr('：未开启，建议开启以获得更稳的帧时间。')
            if info.needs_reboot_hint:
                tip += tr('（修改后需重启电脑生效）')
            self.hags_desc.setText(tip)
        else:
            self.btn_hags.setEnabled(False)
            self.btn_hags.setText(tr('需管理员权限'))
            self.hags_desc.setText(
                tr('硬件加速 GPU 计划（HAGS）：非管理员运行，请用「手动设置」，'
                   '或右键以管理员身份重新打开本程序。'))

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
        """游戏详情页。

        【自适应】外层套 QScrollArea：窗口变矮 / 分辨率降低 / 容器被压缩时
        整页可滚动，任何元素都不会被裁剪、压扁或互相遮挡；
        高度充足时（setWidgetResizable）不出现滚动条，观感与原来一致。
        """
        scroll = QScrollArea()
        scroll.setObjectName("detailScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 8, 0)      # 右侧给滚动条留位
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

        self.kv_exe = KV(tr('渲染进程'), "—")
        self.kv_dir = KV(tr('安装目录'), "—")
        self.kv_res = KV(tr('当前分辨率'), "—")
        self.kv_ac = KV(tr('反作弊'), "—")
        self.kv_vram = KV(tr('显存预算'), "—")
        self.kv_state = KV(tr('部署状态'), "—")
        # 响应式网格：够宽两列，变窄自动降为单列，
        # 六项信息在任何窗口尺寸下都完整可见（不截断、不重叠）。
        self.kv_grid = KVGrid([self.kv_exe, self.kv_dir, self.kv_res,
                               self.kv_ac, self.kv_vram, self.kv_state],
                              min_col_w=320, max_cols=2)
        hl.addWidget(self.kv_grid)
        lay.addWidget(hero)

        cfg = QFrame()
        cfg.setObjectName("card")
        cl = QVBoxLayout(cfg)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(12)
        t1 = QLabel(tr('插帧配置'))
        t1.setObjectName("cardTitle")
        cl.addWidget(t1)

        # 配置行 1：运行库 + 入口 DLL。用 FlowRow 而非 QHBoxLayout，
        # 窄宽时自动换行；下拉不再写死宽度，改为可伸缩（150~280）。
        r1 = FlowRow(h_spacing=10, v_spacing=6)
        a = QLabel(tr('运行库'))
        a.setObjectName("kv")
        a.setMinimumWidth(max(66, a.sizeHint().width()))
        r1.add(a)
        self.cmb_runtime = Combo()
        for _rt, _pfx, desc in core.RUNTIMES:
            self.cmb_runtime.addItem(tr(desc), _rt)
        self.cmb_runtime.setMinimumWidth(150)
        self.cmb_runtime.setMaximumWidth(280)
        self.cmb_runtime.setToolTip(
            tr('310.9 为最新运行库，支持 6X；310.1 为老版本，上限 4X。'
               '两套内嵌运行库与上游发布结构一致，可任选其一。'))
        self.cmb_runtime.currentIndexChanged.connect(lambda _i: self._on_runtime_changed())
        r1.add(self.cmb_runtime)
        b = QLabel(tr('入口 DLL'))
        b.setObjectName("kv")
        b.setMinimumWidth(max(66, b.sizeHint().width()))
        r1.add(b)
        self.cmb_entry = Combo()
        self._fill_entry_combo()
        self.cmb_entry.setMinimumWidth(150)
        self.cmb_entry.setMaximumWidth(280)
        r1.add(self.cmb_entry)
        cl.addWidget(r1)

        # 配置行 2：插帧倍率 + 诊断日志。同样走 FlowRow，窄宽自动换行。
        r2 = FlowRow(h_spacing=10, v_spacing=6)
        c = QLabel(tr('插帧倍率'))
        c.setObjectName("kv")
        c.setMinimumWidth(max(66, c.sizeHint().width()))
        r2.add(c)
        self.seg_mult = Segmented(["2X", "3X", "4X", "5X", "6X"], 0)
        self._refresh_mult_seg()
        self.seg_mult.changed.connect(lambda _i: self._update_vram())
        r2.add(self.seg_mult)
        e2 = QLabel(tr('诊断日志'))
        e2.setObjectName("kv")
        e2.setMinimumWidth(max(66, e2.sizeHint().width()))
        r2.add(e2)
        self.sw_log = Switch(False)
        r2.add(self.sw_log)
        cl.addWidget(r2)

        # 配置行 3：一致性档位（上游 0.3.2 的 [FrameGeneration] Optimized 0–3）。
        # 判据只有一条：允许生成的画面偏离官方运行库多远。档位越高越快。
        r3 = FlowRow(h_spacing=10, v_spacing=6)
        d = QLabel(tr('一致性档位'))
        d.setObjectName("kv")
        d.setMinimumWidth(max(66, d.sizeHint().width()))
        r3.add(d)
        # 说明标签必须先建：_refresh_tier_seg() 会通过 _update_tier_hint() 写它，
        # 若顺序颠倒，首次构建时标签还不存在，说明文字会一直是空的。
        self.lb_tier = QLabel("")
        self.lb_tier.setObjectName("kvval")
        self.lb_tier.setWordWrap(True)
        self.seg_tier = Segmented([f"{i}" for i in range(core.TIER_MIN, core.TIER_MAX + 1)],
                                  core.DEFAULT_TIER)
        self.seg_tier.changed.connect(lambda _i: self._on_tier_changed())
        self._refresh_tier_seg()          # 应用运行库上限 + 写档位说明
        r3.add(self.seg_tier)
        r3.add(self.lb_tier)
        cl.addWidget(r3)
        lay.addWidget(cfg)

        # 操作按钮：窄宽时自动换行；主按钮给足最小宽度保证可点。
        actions = FlowRow(h_spacing=10, v_spacing=8)
        self.btn_install = QPushButton(tr('一键启用插帧'))
        self.btn_install.setObjectName("primary")
        self.btn_install.setCursor(Qt.PointingHandCursor)
        self.btn_install.setMinimumWidth(180)
        self.btn_install.setMinimumHeight(34)
        self.btn_install.clicked.connect(self.do_install)
        actions.add(self.btn_install)
        self.btn_restore = QPushButton(tr('一键恢复'))
        self.btn_restore.setObjectName("danger")
        self.btn_restore.setCursor(Qt.PointingHandCursor)
        self.btn_restore.setMinimumHeight(34)
        self.btn_restore.clicked.connect(self.do_restore)
        actions.add(self.btn_restore)
        self.btn_open = QPushButton(tr('打开目录'))
        self.btn_open.setObjectName("ghost")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.setMinimumHeight(34)
        self.btn_open.clicked.connect(self.open_dir)
        actions.add(self.btn_open)
        self.btn_copy = QPushButton(tr('复制路径'))
        self.btn_copy.setObjectName("ghost")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setMinimumHeight(34)
        self.btn_copy.clicked.connect(self.copy_path)
        actions.add(self.btn_copy)
        lay.addWidget(actions)

        self.hint = QLabel(
            tr('操作前请完全退出游戏。启用后重启游戏，在画面设置里打开帧生成并选择倍率；带反作弊的游戏请只在单机 / 离线模式下使用。恢复会清掉本工具写入的文件并还原备份。'))
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(f"font-size:11px; color:{C['dim']}; line-height:150%;")
        lay.addWidget(self.hint)

        lay.addStretch(1)
        scroll.setWidget(page)
        return scroll

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
            # MaxGeneratedFrames 新旧格式同名，兼容读取
            m = int(cfg.get("MaxGeneratedFrames", "1") or 1)
            self.seg_mult.set_value({1: 0, 2: 1, 3: 2, 4: 3, 5: 4}.get(m, 0))
            # 档位：0.3.2 起 INI 写 0–3；更早版本只有 0/1（读回即档位 0/1）。
            t = cfg.get("tier")
            if t is None:
                t = core.DEFAULT_TIER
            self.seg_tier.set_value(max(core.TIER_MIN, min(int(t), self._tier_cap()))
                                    - core.TIER_MIN)
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

    def _runtime(self) -> str:
        """当前选中的内嵌运行库版本（310.9 / 310.1）。"""
        rt = self.cmb_runtime.currentData() if hasattr(self, "cmb_runtime") else ""
        return rt or core.DEFAULT_RUNTIME

    def _fill_entry_combo(self) -> None:
        """入口下拉：按上游分层显示 —— 工具类优先，渲染路径单独标注。"""
        self.cmb_entry.clear()
        self.cmb_entry.addItem(tr('自动选择（推荐）'), "")
        tool = [e for e in core.ENTRIES if e[4] == "tool"]
        render = [e for e in core.ENTRIES if e[4] == "render"]
        for e in tool:
            self.cmb_entry.addItem(f"{e[1]}　· {tr(e[3])}", e[1])
        for e in render:
            self.cmb_entry.addItem(f"{e[1]}　· {tr('渲染路径，高风险')}", e[1])
        idx = self.cmb_entry.findData("") if self.cmb_entry.count() else -1
        self.cmb_entry.setCurrentIndex(max(0, idx))

    def _on_runtime_changed(self) -> None:
        """切换运行库：重建倍率档位（310.1 上限 4X）并刷新显存估算。

        0.3.2 起还需刷新档位段：310.1 构建没有有损图像内核，
        其档位上限只有 1，因此 2/3 档在该运行库下必须置灰。
        """
        self._refresh_mult_seg()
        self._refresh_tier_seg()
        self._update_vram()

    def _refresh_mult_seg(self) -> None:
        """按当前运行库的倍率上限重建倍率段。

        默认选中 4X：上游 0.3.1 把出厂 MaxGeneratedFrames 由 5 改为 3（4X），
        理由是自带 Dynamic MFG 的游戏会默认跑到上限、6X 对多数人偏高
        （上游 issue #497/#499）。上游 0.3.2 沿用该出厂值，本工具随之对齐。
        切换运行库导致上限变化时，保留用户已选倍率，越界才钳到上限。
        """
        cap = core.runtime_mult_cap(self._runtime())
        labels = [f"{m}X" for m in range(2, cap + 1)]
        if hasattr(self, "seg_mult") and self.seg_mult.group.buttons():
            want = self._mult()               # 保留当前选择
        else:
            want = 4                          # 首次构建：对齐上游出厂 4X
        want = max(2, min(want, cap))
        self.seg_mult.set_options(labels, current=want - 2)

    def _mult(self) -> int:
        return {0: 2, 1: 3, 2: 4, 3: 5, 4: 6}.get(self.seg_mult.value(), 2)

    # ------------------------------------------------- 一致性档位（0.3.2）

    def _tier_cap(self) -> int:
        """当前运行库实际支持的档位上限（310.1 为 1）。"""
        return core.tier_cap(self._runtime())

    def _tier(self) -> int:
        """当前选中的一致性档位（0–3）。"""
        return int(self.seg_tier.value()) if hasattr(self, "seg_tier") else core.DEFAULT_TIER

    def _refresh_tier_seg(self) -> None:
        """按运行库能力重建档位段，并同步下方说明文字。

        档位 2/3 依赖 310.9 构建里新增的有损图像内核；310.1 上上游会
        静默把它们当 1 处理，所以这里直接不给出这两个选项，避免用户
        选了一个实际不生效的档位。
        """
        if not hasattr(self, "seg_tier"):
            return
        cap = self._tier_cap()
        labels = [f"{t}" for t in range(core.TIER_MIN, cap + 1)]
        want = self._tier() if self.seg_tier.group.buttons() else core.DEFAULT_TIER
        want = max(core.TIER_MIN, min(want, cap))
        self.seg_tier.set_options(labels, current=want - core.TIER_MIN)
        self._update_tier_hint()

    def _on_tier_changed(self) -> None:
        self._update_tier_hint()

    def _update_tier_hint(self) -> None:
        """把档位含义写清楚：逐位一致 vs 有损，用户才知道自己在选什么。"""
        if not hasattr(self, "lb_tier"):
            return
        t = self._tier()
        cap = self._tier_cap()
        text = tr(core.tier_label(t))
        if t >= 2:
            text += tr('（不再是逐位一致，画质有损）')
        if cap == 1:
            text += tr('；310.1 无有损内核，仅支持档位 0–1')
        self.lb_tier.setText(text)

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
        """返回用户指定的入口；自动选择返回空串。"""
        return (self.cmb_entry.currentData() or "") if hasattr(self, "cmb_entry") else ""

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
        self.kw = ActionWorker(core.deploy, g, "SM86", self._mult(),
                               False, 2 if self.sw_log.isChecked() else 1,
                               self._entry(), False, self._runtime(), self._tier())
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
