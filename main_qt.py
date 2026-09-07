"""声呐 Sonar - B站 & 贴吧 舆情分析工具 | LLM驱动采集 + 苹果质感 GUI (PySide6)

设计说明（与 Ardot 设计稿「声呐Sonar · 苹果质感UI重构」一致）：
- 浅色 Parchment 底 (#F5F5F7) + 白色卡片 (16px 圆角 + 发丝线描边)
- 单一强调色 Action Blue #0071E3；平台识别色仅用于 Cookie  tinted 按钮
- 侧边栏 / 标题栏 / 状态栏 / 次级按钮均为毛玻璃质感（Windows 11 下尝试启用真 Acrylic）
- 按钮 hover/pressed 过渡、按压轻微缩小、输入框聚焦蓝环

功能逻辑与旧版 main.py (tkinter) 完全一致，仅替换视觉与交互层。
"""
import html
import json
import os
import queue
import sys
import threading
from datetime import datetime

from PySide6.QtCore import (
    QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer, Property, Signal,
)
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QButtonGroup, QCheckBox, QFileDialog,
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QPlainTextEdit, QScrollArea, QSizePolicy,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QToolButton, QVBoxLayout, QWidget, QHeaderView,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from bilibili_collector import BilibiliCollector
from tieba_collector import TiebaCollector
from llm_analyzer import LLMAnalyzer, FunctionCallingNotSupported
import cookie_helper

# ========== Apple 设计令牌 ==========
C = {
    "accent":      "#0071E3",
    "accent_hov":  "#0077ED",
    "accent_pre":  "#0062C4",
    "ink":         "#1D1D1F",
    "ink_2":       "#3A3A3C",
    "muted":       "#6E6E73",
    "faint":       "#8E8E93",
    "placeholder": "#C7C7CC",
    "canvas":      "#FFFFFF",
    "parchment":   "#F5F5F7",
    "pearl":       "#FAFAFC",
    "sidebar":     "#EFEFF4",
    "seg_bg":      "#E9E9EE",
    "toggle_off":  "#E9E9EA",
    "green":       "#34C759",
    "orange":      "#FF9500",
    "red":         "#FF3B30",
    "bili":        "#FB7299",
    "bili_text":   "#DB3B73",
    "tieba":       "#4E6EF2",
    "hairline":    "rgba(0, 0, 0, 0.06)",
    "hairline2":   "rgba(0, 0, 0, 0.08)",
    "font":        "Segoe UI, Microsoft YaHei UI, PingFang SC, sans-serif",
    "font_mono":   "Cascadia Code, Consolas, monospace",
}

# 日志标签颜色（与旧版 tag 一一对应）
LOG_COLORS = {
    "tool": C["accent"], "result": C["green"], "think": C["orange"],
    "error": C["red"], "info": C["ink"], "success": C["green"],
    "warning": C["orange"], "time": C["faint"],
}


def qss():
    """全局样式表（QSS，等价于设计稿中的组件状态）"""
    return f"""
    * {{ font-family: {C['font']}; color: {C['ink']}; font-size: 13px; }}
    QWidget#root {{ background: {C['parchment']}; border-radius: 12px; }}

    /* ---------- 标题栏 ---------- */
    QWidget#titlebar {{ background: rgba(250, 250, 252, 0.8);
        border-top-left-radius: 12px; border-top-right-radius: 12px; }}

    /* ---------- 侧边栏（毛玻璃） ---------- */
    QFrame#sidebar {{ background: rgba(239, 239, 244, 0.72);
        border-top-left-radius: 0px; border-bottom-left-radius: 12px; }}
    QPushButton[nav] {{ text-align: left; padding: 11px 12px;
        border: 1px solid transparent; border-radius: 10px;
        color: {C['muted']}; background: transparent; font-size: 14px; }}
    QPushButton[nav]:hover {{ background: rgba(255,255,255,0.45);
        border: 1px solid rgba(0,0,0,0.05); }}
    QPushButton[nav]:checked {{ background: rgba(255,255,255,0.75);
        border: 1px solid rgba(0,0,0,0.06); color: {C['ink']}; font-weight: 600; }}
    QPushButton[nav]:pressed {{ background: rgba(255,255,255,0.95); }}

    /* ---------- 卡片 ---------- */
    QFrame#card {{ background: {C['canvas']}; border: 1px solid {C['hairline']};
        border-radius: 16px; }}

    /* ---------- 按钮 ----------
       按下态只改颜色/描边，绝不动 padding——否则会挤压相邻按钮造成布局抖动 */
    QPushButton[variant="primary"] {{ background: {C['accent']}; color: white;
        border: none; border-radius: 17px; padding: 9px 22px; font-weight: 600; }}
    QPushButton[variant="primary"]:hover {{ background: {C['accent_hov']}; }}
    QPushButton[variant="primary"]:pressed {{ background: {C['accent_pre']}; }}
    QPushButton[variant="primary"]:disabled {{ background: {C['seg_bg']}; color: {C['faint']}; }}

    /* 毛玻璃次级按钮：Accent 蓝调，与主界面白色拉开层次 */
    QPushButton[variant="glass"] {{ background: rgba(0,113,227,0.08); color: {C['accent']};
        border: 1px solid rgba(0,113,227,0.25); border-radius: 17px; padding: 9px 16px; }}
    QPushButton[variant="glass"]:hover {{ background: rgba(0,113,227,0.14);
        border: 1px solid rgba(0,113,227,0.35); }}
    QPushButton[variant="glass"]:pressed {{ background: rgba(0,113,227,0.20);
        border: 1px solid rgba(0,113,227,0.45); }}
    QPushButton[variant="glass"]:disabled {{ color: {C['placeholder']};
        background: rgba(0,0,0,0.04); border: 1px solid {C['hairline']}; }}

    QPushButton[variant="glass-danger"] {{ background: rgba(255,59,48,0.07); color: {C['red']};
        border: 1px solid rgba(255,59,48,0.25); border-radius: 17px; padding: 9px 16px; }}
    QPushButton[variant="glass-danger"]:hover {{ background: rgba(255,59,48,0.13);
        border: 1px solid rgba(255,59,48,0.35); }}
    QPushButton[variant="glass-danger"]:pressed {{ background: rgba(255,59,48,0.20);
        border: 1px solid rgba(255,59,48,0.45); }}
    QPushButton[variant="glass-danger"]:disabled {{ color: {C['placeholder']};
        background: rgba(0,0,0,0.04); border: 1px solid {C['hairline']}; }}

    QPushButton[variant="tinted-bili"] {{ background: rgba(251,114,153,0.14);
        color: {C['bili_text']}; border: none; border-radius: 15px;
        padding: 7px 16px; font-weight: 600; }}
    QPushButton[variant="tinted-bili"]:hover {{ background: rgba(251,114,153,0.22); }}
    QPushButton[variant="tinted-bili"]:pressed {{ background: rgba(251,114,153,0.30); }}

    QPushButton[variant="tinted-tieba"] {{ background: rgba(78,110,242,0.12);
        color: {C['tieba']}; border: none; border-radius: 15px;
        padding: 7px 16px; font-weight: 600; }}
    QPushButton[variant="tinted-tieba"]:hover {{ background: rgba(78,110,242,0.20); }}
    QPushButton[variant="tinted-tieba"]:pressed {{ background: rgba(78,110,242,0.28); }}

    /* ---------- 分段选择器 ---------- */
    QFrame#segmented {{ background: {C['seg_bg']}; border-radius: 9px; }}
    QPushButton[segment] {{ background: transparent; border: none; border-radius: 7px;
        padding: 5px 14px; color: {C['muted']}; }}
    QPushButton[segment]:hover {{ color: {C['ink']}; }}
    QPushButton[segment]:checked {{ background: {C['canvas']}; color: {C['ink']};
        font-weight: 600; }}

    /* ---------- 输入框 ---------- */
    QLineEdit {{ background: {C['parchment']}; border: 2px solid transparent;
        border-radius: 18px; padding: 8px 16px; selection-background-color: {C['accent']}; }}
    QLineEdit:focus {{ background: {C['canvas']}; border: 2px solid {C['accent']}; }}
    QLineEdit[field] {{ border-radius: 8px; padding: 5px 12px; }}

    /* ---------- 步进器 ---------- */
    QFrame#stepper {{ background: {C['parchment']}; border-radius: 13px; }}
    QToolButton#stepBtn {{ border: none; color: {C['muted']}; font-size: 13px;
        padding: 2px 8px; border-radius: 9px; }}
    QToolButton#stepBtn:hover {{ color: {C['ink']}; background: rgba(0,0,0,0.04); }}
    QToolButton#stepBtn:pressed {{ color: {C['accent']}; }}

    /* ---------- 表格 ---------- */
    QTableWidget {{ background: {C['canvas']}; border: none; gridline-color: transparent;
        selection-background-color: rgba(0,113,227,0.08); selection-color: {C['accent']}; }}
    QTableWidget::item {{ padding: 8px 4px; border-bottom: 1px solid rgba(0,0,0,0.05); }}
    QHeaderView::section {{ background: {C['canvas']}; color: {C['faint']}; font-size: 10px;
        border: none; border-bottom: 1px solid rgba(0,0,0,0.05); padding: 6px 4px;
        font-weight: 400; }}

    /* ---------- 标签页 ---------- */
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{ background: transparent; color: {C['muted']}; padding: 4px 2px 6px 2px;
        margin-right: 18px; border-bottom: 2px solid transparent; }}
    QTabBar::tab:hover {{ color: {C['ink']}; }}
    QTabBar::tab:selected {{ color: {C['accent']}; font-weight: 600;
        border-bottom: 2px solid {C['accent']}; }}

    /* ---------- 日志 / 文本 ---------- */
    QTextEdit, QPlainTextEdit, QTextBrowser {{ background: {C['canvas']}; border: none;
        selection-background-color: rgba(0,113,227,0.15); }}

    /* ---------- 滚动条 ---------- */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: rgba(0,0,0,0.18); border-radius: 4px;
        min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: rgba(0,0,0,0.32); }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: rgba(0,0,0,0.18); border-radius: 4px;
        min-width: 30px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ---------- 状态栏 ---------- */
    QFrame#statusbar {{ background: rgba(250, 250, 252, 0.8);
        border-top: 1px solid {C['hairline']};
        border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }}
    """


def make_icon(svg, size=14):
    """把内联 SVG 字符串渲染成 QIcon（2x 分辨率，高分屏清晰）"""
    img = QImage(size * 2, size * 2, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    QSvgRenderer(svg.encode("utf-8")).render(p)
    p.end()
    pix = QPixmap.fromImage(img)
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


# 侧边栏导航图标（与设计稿一致）
SVG_SEARCH = ('<svg width="14" height="14" viewBox="0 0 14 14" fill="none" '
              'xmlns="http://www.w3.org/2000/svg">'
              '<circle cx="6" cy="6" r="4.5" stroke="{color}" stroke-width="1.5"/>'
              '<path d="M9.5 9.5L13 13" stroke="{color}" stroke-width="1.5" '
              'stroke-linecap="round"/></svg>')
SVG_GEAR = ('<svg width="14" height="14" viewBox="0 0 14 14" fill="none" '
            'xmlns="http://www.w3.org/2000/svg">'
            '<circle cx="7" cy="7" r="1.8" stroke="{color}" stroke-width="1.3"/>'
            '<path d="M11.1 8.7l.9.7-.8 1.3-1-.4a4.2 4.2 0 01-.8.4l-.1 1.1H8.5l-.1-1.1'
            'a4.2 4.2 0 01-.8-.4l-1 .4-.8-1.3.9-.7a4.3 4.3 0 010-.9l-.9-.7.8-1.3 1 .4'
            'c.2-.2.5-.3.8-.4l.1-1.1h1.6l.1 1.1c.3.1.6.2.8.4l1-.4.8 1.3-.9.7'
            'a4.3 4.3 0 010 .9z" stroke="{color}" stroke-width="1.1" '
            'stroke-linejoin="round"/></svg>')


class WindowButton(QAbstractButton):
    """macOS 风格窗口按钮：彩色圆点 + 常驻图标（悬停加深，按下缩小）"""

    def __init__(self, color, glyph, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._glyph = glyph
        self.setFixedSize(14, 14)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # 按下时圆点缩小一圈（scale 反馈）；悬停时颜色加深
        d = 10 if self.isDown() else 12
        x = (self.width() - d) / 2
        y = (self.height() - d) / 2
        c = QColor(self._color)
        if self.underMouse() and not self.isDown():
            c = c.darker(112)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(int(x), int(y), d, d)
        # 图标常驻显示（深色半透明）
        p.setPen(QColor(0, 0, 0, 150))
        p.setFont(QFont("Segoe UI", 7, QFont.Bold))
        p.drawText(self.rect(), Qt.AlignCenter, self._glyph)
        p.end()


# ============================================================
# 自定义控件
# ============================================================

class ToggleSwitch(QAbstractButton):
    """iOS 风格开关：绿色轨道 + 白色旋钮，带滑动动画"""

    def __init__(self, checked=True, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(40, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _get_pos(self):
        return self._pos

    def _set_pos(self, v):
        self._pos = v
        self.update()

    pos = Property(float, _get_pos, _set_pos)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # 轨道颜色随位置插值（灰 -> 绿）
        off, on = QColor(C["toggle_off"]), QColor(C["green"])
        r = off.red() + (on.red() - off.red()) * self._pos
        g = off.green() + (on.green() - off.green()) * self._pos
        b = off.blue() + (on.blue() - off.blue()) * self._pos
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(int(r), int(g), int(b)))
        p.drawRoundedRect(0, 0, 40, 24, 12, 12)
        # 旋钮（带一点阴影感）
        x = 2 + self._pos * 16
        p.setBrush(QColor(0, 0, 0, 30))
        p.drawEllipse(int(x), 3, 20, 20)
        p.setBrush(QColor("white"))
        p.drawEllipse(int(x), 2, 20, 20)
        p.end()


class Stepper(QFrame):
    """胶囊步进器：− 值 + （等价旧版 Spinbox）"""
    valueChanged = Signal(int)

    def __init__(self, minimum, maximum, value, parent=None):
        super().__init__(parent)
        self.setObjectName("stepper")
        self._min, self._max = minimum, maximum
        self._value = value
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(0)
        self.minus = QToolButton(objectName="stepBtn", text="−")
        self.label = QLabel(str(value))
        self.label.setFixedWidth(22)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {C['ink']};")
        self.plus = QToolButton(objectName="stepBtn", text="+")
        self.minus.clicked.connect(lambda: self._step(-1))
        self.plus.clicked.connect(lambda: self._step(1))
        lay.addWidget(self.minus)
        lay.addWidget(self.label)
        lay.addWidget(self.plus)
        self.setFixedHeight(26)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def _step(self, d):
        v = max(self._min, min(self._max, self._value + d))
        if v != self._value:
            self._value = v
            self.label.setText(str(v))
            self.valueChanged.emit(v)

    def value(self):
        return self._value

    def setValue(self, v):
        self._value = max(self._min, min(self._max, int(v)))
        self.label.setText(str(self._value))


class Card(QFrame):
    """白色圆角卡片：标题 + 内容布局"""

    def __init__(self, title, right_text="", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 12, 16, 14)
        self.body.setSpacing(10)
        head = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {C['ink']};")
        head.addWidget(t)
        head.addStretch(1)
        if right_text:
            r = QLabel(right_text)
            r.setStyleSheet(f"font-size: 10px; color: {C['faint']};")
            head.addWidget(r)
        self.body.addLayout(head)


class Toast(QLabel):
    """底部居中 Toast，2 秒自动消失"""

    def __init__(self, parent, message, kind="info"):
        super().__init__(parent)
        color = {"info": C["ink"], "success": C["green"],
                 "error": C["red"], "warning": C["orange"]}.get(kind, C["ink"])
        self.setText(f"  ✓  {message}  ")
        self.setStyleSheet(f"background: {color}; color: white; font-weight: 600;"
                           f"border-radius: 14px; padding: 8px 14px;")
        self.adjustSize()
        pw = parent.width()
        self.move((pw - self.width()) // 2, parent.height() - self.height() - 48)
        self.show()
        QTimer.singleShot(2000, self.deleteLater)


# ============================================================
# 主窗口
# ============================================================

class SonarWindow(QWidget):
    """声呐 Sonar 主应用（无边框窗口 + 自定义标题栏）"""

    RESIZE_MARGIN = 8

    def __init__(self):
        super().__init__()
        self.setWindowTitle("声呐 Sonar — B站 & 贴吧 舆情分析")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 780)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.config = ConfigManager()
        self.message_queue = queue.Queue()

        self.bilibili_data = None
        self.tieba_data = None
        self.analysis_report = ""
        self.current_keyword = ""
        self._analyzing = False
        self.analysis_mode = "keyword"  # "keyword" | "single_video" | "bili_overview"

        self._build_window()
        self._load_config_to_ui()
        self._switch_mode("keyword")

        # 消息队列轮询（替代 tk 的 after 轮询）
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_queue)
        self._poll_timer.start(100)

        # Windows 11 真毛玻璃（失败则退回纯色，无影响）
        QTimer.singleShot(0, self._try_acrylic)

    # ---------- 窗口骨架 ----------

    def _build_window(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)  # 给投影留空间
        outer.setSpacing(0)

        self.root = QFrame(objectName="root")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.root.setGraphicsEffect(shadow)
        outer.addWidget(self.root)

        root_lay = QVBoxLayout(self.root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        root_lay.addWidget(self._build_titlebar())
        hair = QFrame()
        hair.setFixedHeight(1)
        hair.setStyleSheet(f"background: {C['hairline']};")
        root_lay.addWidget(hair)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {C['hairline']};")
        body.addWidget(sep)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_main_page())
        self.pages.addWidget(self._build_settings_page())
        body.addWidget(self.pages, 1)
        root_lay.addLayout(body, 1)

        root_lay.addWidget(self._build_statusbar())

    def _build_titlebar(self):
        bar = QWidget(objectName="titlebar")
        bar.setFixedHeight(44)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(8)

        # macOS 风格窗口按钮（红 / 黄 / 绿，图标常驻显示）
        for color, glyph, slot in [
            ("#FF5F57", "×", self.close),
            ("#FEBC2E", "−", self.showMinimized),
            ("#28C840", "+", self._toggle_maximize),
        ]:
            btn = WindowButton(color, glyph)
            btn.clicked.connect(slot)
            lay.addWidget(btn)

        lay.addStretch(1)
        title = QLabel("声呐 Sonar — B站 & 贴吧 舆情分析")
        title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {C['ink']};")
        lay.addWidget(title)
        lay.addStretch(1)
        lay.addSpacing(58)  # 与左侧三个按钮宽度平衡，让标题真正居中

        # 拖动区域
        bar.mousePressEvent = self._titlebar_drag
        return bar

    def _titlebar_drag(self, event):
        if event.button() == Qt.LeftButton:
            self.windowHandle().startSystemMove()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _build_sidebar(self):
        bar = QFrame(objectName="sidebar")
        bar.setFixedWidth(232)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(4)

        # Logo
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(8, 6, 8, 14)
        logo_row.setSpacing(10)
        icon = QLabel("◉")
        icon.setFixedSize(32, 32)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"background: {C['accent']}; color: white; font-size: 14px;"
                           f"border-radius: 8px;")
        name_col = QVBoxLayout()
        name_col.setSpacing(1)
        name = QLabel("声呐")
        name.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {C['ink']};")
        sub = QLabel("SONAR · LLM 驱动")
        sub.setStyleSheet(f"font-size: 9px; color: {C['faint']};")
        name_col.addWidget(name)
        name_col.addWidget(sub)
        logo_row.addWidget(icon)
        logo_row.addLayout(name_col)
        logo_row.addStretch(1)
        lay.addLayout(logo_row)

        # 导航（大号 + SVG 图标 + 毛玻璃选中态）
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        nav_items = [
            ("main", "搜索分析", make_icon(SVG_SEARCH.format(color="#6E6E73"), 15)),
            ("settings", "设置", make_icon(SVG_GEAR.format(color="#6E6E73"), 15)),
        ]
        for i, (page_id, label, icon) in enumerate(nav_items):
            btn = QPushButton(icon, "  " + label)
            btn.setProperty("nav", True)
            btn.setCheckable(True)
            btn.setIconSize(QSize(15, 15))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, idx=i: self.pages.setCurrentIndex(idx))
            self.nav_group.addButton(btn)
            lay.addWidget(btn)
            self.nav_buttons[page_id] = btn
        self.nav_buttons["main"].setChecked(True)

        lay.addStretch(1)
        ver = QLabel("v2.0 · LLM 驱动")
        ver.setStyleSheet(f"font-size: 10px; color: {C['faint']};")
        ver.setContentsMargins(10, 0, 0, 0)
        date = QLabel(datetime.now().strftime("%Y-%m-%d"))
        date.setStyleSheet(f"font-size: 10px; color: {C['faint']};")
        date.setContentsMargins(10, 0, 0, 0)
        lay.addWidget(ver)
        lay.addWidget(date)
        return bar

    def _build_statusbar(self):
        bar = QFrame(objectName="statusbar")
        bar.setFixedHeight(30)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {C['green']}; font-size: 8px;")
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(f"font-size: 10px; color: {C['muted']};")
        lay.addWidget(dot)
        lay.addWidget(self.status_label)
        lay.addStretch(1)
        self.status_right = QLabel("")
        self.status_right.setStyleSheet(f"font-size: 10px; color: {C['faint']};")
        lay.addWidget(self.status_right)
        return bar

    # ---------- 主页：搜索分析 ----------

    def _build_main_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 16)
        lay.setSpacing(14)

        # 页头
        head = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        t = QLabel("搜索分析")
        t.setStyleSheet(f"font-size: 24px; font-weight: 600; color: {C['ink']};")
        s = QLabel("LLM 自主采集 B站 & 贴吧数据，生成舆情分析报告")
        s.setStyleSheet(f"font-size: 12px; color: {C['muted']};")
        title_col.addWidget(t)
        title_col.addWidget(s)
        head.addLayout(title_col)
        head.addStretch(1)
        self.mode_desc = QLabel("")
        self.mode_desc.setStyleSheet(f"font-size: 11px; color: {C['faint']};")
        head.addWidget(self.mode_desc)
        lay.addLayout(head)

        # 模式分段选择器
        seg = QFrame(objectName="segmented")
        seg.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        seg_lay = QHBoxLayout(seg)
        seg_lay.setContentsMargins(2, 2, 2, 2)
        seg_lay.setSpacing(2)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_buttons = {}
        for mid, label in [("keyword", "关键词综合分析"),
                           ("single_video", "单视频深度分析"),
                           ("bili_overview", "B站视频概览")]:
            btn = QPushButton(label)
            btn.setProperty("segment", True)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, m=mid: self._switch_mode(m))
            self.mode_group.addButton(btn)
            seg_lay.addWidget(btn)
            self.mode_buttons[mid] = btn
        lay.addWidget(seg)

        # ---- 输入卡片 ----
        self.input_card = Card("关键词", "按 ⏎ 回车开始分析")
        self.input_card_title = self.input_card.findChild(QLabel)

        # 输入行（关键词 / BV号 两种）
        self.kw_entry = QLineEdit(placeholderText="输入关键词，例如：原神")
        self.kw_entry.setFixedHeight(44)
        self.kw_entry.returnPressed.connect(self._start_analysis)
        self.video_entry = QLineEdit(placeholderText="输入 BV 号或视频链接，例如：BV1xx411c7mD")
        self.video_entry.setFixedHeight(44)
        self.video_entry.returnPressed.connect(self._start_analysis)
        self.input_stack = QStackedWidget()
        self.input_stack.addWidget(self.kw_entry)
        self.input_stack.addWidget(self.video_entry)
        self.input_card.body.addWidget(self.input_stack)

        # 平台开关 + 采集深度
        ctrl = QHBoxLayout()
        ctrl.setSpacing(14)
        bili_lbl = QLabel("B站")
        bili_lbl.setStyleSheet(f"font-size: 12px; color: {C['ink']};")
        self.bili_toggle = ToggleSwitch(True)
        ctrl.addWidget(bili_lbl)
        ctrl.addWidget(self.bili_toggle)
        self.tieba_lbl = QLabel("贴吧")
        self.tieba_lbl.setStyleSheet(f"font-size: 12px; color: {C['ink']};")
        self.tieba_toggle = ToggleSwitch(True)
        ctrl.addWidget(self.tieba_lbl)
        ctrl.addWidget(self.tieba_toggle)
        divider = QFrame()
        divider.setFixedSize(1, 20)
        divider.setStyleSheet(f"background: {C['hairline2']};")
        ctrl.addWidget(divider)
        self.params_label = QLabel("采集深度")
        self.params_label.setStyleSheet(f"font-size: 11px; color: {C['faint']};")
        ctrl.addWidget(self.params_label)

        # 主页 4 个步进器（与设置页双向同步）
        self.bili_pages_s = Stepper(1, 10, 2)
        self.bili_comments_s = Stepper(0, 100, 30)
        self.tieba_pages_s = Stepper(1, 10, 3)
        self.tieba_replies_s = Stepper(0, 100, 20)
        self._main_steppers = [
            ("B站页数", self.bili_pages_s), ("评论数", self.bili_comments_s),
            ("贴吧页数", self.tieba_pages_s), ("回复数", self.tieba_replies_s),
        ]
        self._stepper_widgets = {}
        for name, st in self._main_steppers:
            w = QWidget()
            wl = QHBoxLayout(w)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(4)
            lb = QLabel(name)
            lb.setStyleSheet(f"font-size: 10px; color: {C['muted']};")
            wl.addWidget(lb)
            wl.addWidget(st)
            ctrl.addWidget(w)
            self._stepper_widgets[st] = w
        ctrl.addStretch(1)
        self.input_card.body.addLayout(ctrl)

        # 操作按钮
        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.analyze_btn = QPushButton("一键分析")
        self.analyze_btn.setProperty("variant", "primary")
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.clicked.connect(self._start_analysis)
        self.clear_btn = QPushButton("清空数据")
        self.clear_btn.setProperty("variant", "glass-danger")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_data)
        exp_report = QPushButton("导出报告")
        exp_report.setProperty("variant", "glass")
        exp_report.setCursor(Qt.PointingHandCursor)
        exp_report.clicked.connect(self._export_report)
        exp_data = QPushButton("导出数据")
        exp_data.setProperty("variant", "glass")
        exp_data.setCursor(Qt.PointingHandCursor)
        exp_data.clicked.connect(self._export_data)
        for b in (self.analyze_btn, self.clear_btn, exp_report, exp_data):
            btns.addWidget(b)
        btns.addStretch(1)
        self.input_card.body.addLayout(btns)
        lay.addWidget(self.input_card)

        # ---- LLM 活动日志 ----
        activity_card = Card("LLM 活动日志", "实时")
        self.activity_text = QTextEdit(readOnly=True)
        self.activity_text.setFixedHeight(120)
        self.activity_text.setStyleSheet(f"font-family: {C['font_mono']}; font-size: 11px;")
        activity_card.body.addWidget(self.activity_text)
        lay.addWidget(activity_card)

        # ---- 数据 & 分析报告 ----
        data_card = Card("数据 & 分析报告")
        self.tabs = QTabWidget()
        self.bili_table = self._make_table(
            ["标题", "UP主", "播放", "点赞", "回复", "收藏", "发布时间"])
        self.bili_comment_table = self._make_table(
            ["用户", "评论内容", "点赞", "时间"], stretch_col=1)
        self.tieba_table = self._make_table(
            ["标题", "贴吧", "作者", "回复数", "日期"])
        self.tieba_reply_table = self._make_table(
            ["用户", "回复内容", "楼层", "时间"], stretch_col=1)
        self.report_text = QTextEdit(readOnly=True)
        self.report_text.setStyleSheet(f"font-size: 13px; line-height: 1.5;")
        self.tabs.addTab(self.bili_table, "B站视频")
        self.tabs.addTab(self.bili_comment_table, "B站评论")
        self.tabs.addTab(self.tieba_table, "贴吧帖子")
        self.tabs.addTab(self.tieba_reply_table, "贴吧回复")
        self.tabs.addTab(self.report_text, "分析报告")
        data_card.body.addWidget(self.tabs)
        lay.addWidget(data_card, 1)
        return page

    def _make_table(self, headers, stretch_col=0):
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setShowGrid(False)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        hdr = table.horizontalHeader()
        for i in range(len(headers)):
            hdr.setSectionResizeMode(
                i, QHeaderView.Stretch if i == stretch_col else QHeaderView.ResizeToContents)
        return table

    # ---------- 设置页 ----------

    def _build_settings_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        scroll.setWidget(page)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)

        t = QLabel("设置")
        t.setStyleSheet(f"font-size: 24px; font-weight: 600; color: {C['ink']};")
        s = QLabel("配置 LLM API、Cookie 及采集参数")
        s.setStyleSheet(f"font-size: 12px; color: {C['muted']};")
        lay.addWidget(t)
        lay.addWidget(s)

        # === LLM API 配置 ===
        llm_card = Card("LLM API 配置")
        self.llm_base = self._field(llm_card, "API 地址", "https://api.deepseek.com/v1")
        self.llm_key = self._field(llm_card, "API Key", "", password=True)
        self.llm_model = self._field(llm_card, "模型名", "deepseek-chat")

        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        pl = QLabel("快捷预设")
        pl.setStyleSheet(f"font-size: 10px; color: {C['faint']};")
        preset_row.addWidget(pl)
        for name, base, model in [
            ("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat"),
            ("通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
            ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
            ("Moonshot", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
        ]:
            btn = QPushButton(name)
            btn.setProperty("variant", "glass")
            btn.setStyleSheet("padding: 5px 12px; font-size: 11px;")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, b=base, m=model: self._apply_preset(b, m))
            preset_row.addWidget(btn)
        preset_row.addStretch(1)
        llm_card.body.addLayout(preset_row)
        hint = QLabel("支持 OpenAI 兼容格式的任意 API，LLM 将通过函数调用自主采集数据并分析。")
        hint.setStyleSheet(f"font-size: 10px; color: {C['faint']};")
        llm_card.body.addWidget(hint)
        lay.addWidget(llm_card)

        # === B站 Cookie ===
        bili_card = Card("B站 Cookie")
        self.bili_sessdata = self._field(bili_card, "SESSDATA", "")
        self.bili_jct = self._field(bili_card, "bili_jct", "")
        self.bili_dedeuid = self._field(bili_card, "DedeUserID", "")
        brow = QHBoxLayout()
        brow.setSpacing(10)
        get_bili = QPushButton("一键获取 Cookie")
        get_bili.setProperty("variant", "tinted-bili")
        get_bili.setCursor(Qt.PointingHandCursor)
        get_bili.clicked.connect(self._get_bilibili_cookie)
        open_bili = QPushButton("打开登录页")
        open_bili.setProperty("variant", "glass")
        open_bili.setStyleSheet("padding: 7px 16px; font-size: 12px;")
        open_bili.setCursor(Qt.PointingHandCursor)
        open_bili.clicked.connect(cookie_helper.open_bilibili_login)
        brow.addWidget(get_bili)
        brow.addWidget(open_bili)
        brow.addStretch(1)
        bili_card.body.addLayout(brow)
        bhint = QLabel("自动从浏览器提取（需已登录 B站），或手动：F12 → Application → Cookies")
        bhint.setStyleSheet(f"font-size: 10px; color: {C['faint']};")
        bili_card.body.addWidget(bhint)
        lay.addWidget(bili_card)

        # === 贴吧 Cookie ===
        tieba_card = Card("贴吧 Cookie")
        self.tieba_bduss = self._field(tieba_card, "BDUSS", "")
        self.tieba_stoken = self._field(tieba_card, "STOKEN", "")
        trow = QHBoxLayout()
        trow.setSpacing(10)
        get_tieba = QPushButton("一键获取 Cookie")
        get_tieba.setProperty("variant", "tinted-tieba")
        get_tieba.setCursor(Qt.PointingHandCursor)
        get_tieba.clicked.connect(self._get_tieba_cookie)
        open_tieba = QPushButton("打开登录页")
        open_tieba.setProperty("variant", "glass")
        open_tieba.setStyleSheet("padding: 7px 16px; font-size: 12px;")
        open_tieba.setCursor(Qt.PointingHandCursor)
        open_tieba.clicked.connect(cookie_helper.open_tieba_login)
        trow.addWidget(get_tieba)
        trow.addWidget(open_tieba)
        trow.addStretch(1)
        tieba_card.body.addLayout(trow)
        thint = QLabel("自动从浏览器提取（需已登录贴吧），或手动：F12 → Application → Cookies")
        thint.setStyleSheet(f"font-size: 10px; color: {C['faint']};")
        tieba_card.body.addWidget(thint)
        lay.addWidget(tieba_card)

        # === 采集参数（与主页步进器双向同步） ===
        param_card = Card("采集参数")
        prow = QHBoxLayout()
        prow.setSpacing(18)
        self.bili_pages_s2 = Stepper(1, 10, 2)
        self.bili_comments_s2 = Stepper(0, 100, 30)
        self.tieba_pages_s2 = Stepper(1, 10, 3)
        self.tieba_replies_s2 = Stepper(0, 100, 20)
        for name, st in [("B站搜索页数", self.bili_pages_s2),
                         ("每视频评论数", self.bili_comments_s2),
                         ("贴吧搜索页数", self.tieba_pages_s2),
                         ("每帖子回复数", self.tieba_replies_s2)]:
            lb = QLabel(name)
            lb.setStyleSheet(f"font-size: 11px; color: {C['muted']};")
            prow.addWidget(lb)
            prow.addWidget(st)
        prow.addStretch(1)
        param_card.body.addLayout(prow)
        phint = QLabel("这些参数作为 LLM 工具调用的默认上限，LLM 会根据需要自主决定采集深度。")
        phint.setStyleSheet(f"font-size: 10px; color: {C['faint']};")
        param_card.body.addWidget(phint)
        lay.addWidget(param_card)

        for main_st, settings_st in [
            (self.bili_pages_s, self.bili_pages_s2),
            (self.bili_comments_s, self.bili_comments_s2),
            (self.tieba_pages_s, self.tieba_pages_s2),
            (self.tieba_replies_s, self.tieba_replies_s2),
        ]:
            main_st.valueChanged.connect(lambda v, s=settings_st: s.setValue(v))
            settings_st.valueChanged.connect(lambda v, s=main_st: s.setValue(v))

        # === 操作按钮 ===
        arow = QHBoxLayout()
        arow.setSpacing(10)
        save_btn = QPushButton("保存配置")
        save_btn.setProperty("variant", "primary")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save_config)
        arow.addWidget(save_btn)
        for label, slot in [("测试 B站", self._test_bilibili),
                            ("测试 贴吧", self._test_tieba),
                            ("测试 LLM", self._test_llm)]:
            btn = QPushButton(label)
            btn.setProperty("variant", "glass")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(slot)
            arow.addWidget(btn)
        arow.addStretch(1)
        lay.addLayout(arow)

        # === 运行日志 ===
        log_card = Card("运行日志")
        self.log_text = QTextEdit(readOnly=True)
        self.log_text.setFixedHeight(140)
        self.log_text.setStyleSheet(f"font-family: {C['font_mono']}; font-size: 10px;")
        log_card.body.addWidget(self.log_text)
        lay.addWidget(log_card)
        lay.addStretch(1)
        return scroll

    def _field(self, card, label_text, default="", password=False):
        """设置页字段行：标签 + 圆角输入框"""
        row = QHBoxLayout()
        row.setSpacing(10)
        lb = QLabel(label_text)
        lb.setFixedWidth(80)
        lb.setStyleSheet(f"font-size: 11px; color: {C['muted']};")
        entry = QLineEdit(default)
        entry.setProperty("field", True)
        entry.setFixedHeight(30)
        if password:
            entry.setEchoMode(QLineEdit.Password)
        row.addWidget(lb)
        row.addWidget(entry, 1)
        card.body.addLayout(row)
        return entry

    # ---------- 模式切换 ----------

    def _switch_mode(self, mode):
        """切换分析模式，更新 UI 显示（逻辑与旧版一致）"""
        self.analysis_mode = mode
        self.mode_buttons[mode].setChecked(True)
        descs = {
            "keyword": "搜索关键词，分析B站+贴吧舆情",
            "single_video": "输入BV号，分析视频评论区舆论偏向",
            "bili_overview": "搜索关键词，LLM总结相关视频观点与情绪",
        }
        self.mode_desc.setText(descs.get(mode, ""))

        card_text = {"keyword": "关键词", "single_video": "视频链接",
                     "bili_overview": "关键词"}.get(mode, "关键词")
        # Card 标题是 body 第一项里的第一个 QLabel
        head_item = self.input_card.body.itemAt(0).layout().itemAt(0).widget()
        head_item.setText(card_text)

        is_single = mode == "single_video"
        self.input_stack.setCurrentIndex(1 if is_single else 0)
        # 单视频 / 概览模式隐藏贴吧相关控件
        show_tieba = mode == "keyword"
        self.tieba_lbl.setVisible(show_tieba)
        self.tieba_toggle.setVisible(show_tieba)
        for st in (self.tieba_pages_s, self.tieba_replies_s):
            self._stepper_widgets[st].setVisible(show_tieba)

    # ========== 配置读写（与旧版一致） ==========

    def _load_config_to_ui(self):
        self.bili_sessdata.setText(self.config.get("bilibili", "cookies", "SESSDATA", default=""))
        self.bili_jct.setText(self.config.get("bilibili", "cookies", "bili_jct", default=""))
        self.bili_dedeuid.setText(self.config.get("bilibili", "cookies", "DedeUserID", default=""))
        self.tieba_bduss.setText(self.config.get("tieba", "cookies", "BDUSS", default=""))
        self.tieba_stoken.setText(self.config.get("tieba", "cookies", "STOKEN", default=""))
        self.llm_base.setText(self.config.get("llm", "api_base", default="https://api.deepseek.com/v1"))
        self.llm_key.setText(self.config.get("llm", "api_key", default=""))
        self.llm_model.setText(self.config.get("llm", "model", default="deepseek-chat"))
        for st, key, default in [
            (self.bili_pages_s, "bilibili_max_pages", 2),
            (self.bili_comments_s, "bilibili_comments_per_video", 30),
            (self.tieba_pages_s, "tieba_max_pages", 3),
            (self.tieba_replies_s, "tieba_replies_per_post", 20),
            (self.bili_pages_s2, "bilibili_max_pages", 2),
            (self.bili_comments_s2, "bilibili_comments_per_video", 30),
            (self.tieba_pages_s2, "tieba_max_pages", 3),
            (self.tieba_replies_s2, "tieba_replies_per_post", 20),
        ]:
            st.setValue(int(self.config.get("collect", key, default=default)))

    def _update_config_from_ui(self):
        self.config.set("bilibili", "cookies", "SESSDATA", self.bili_sessdata.text())
        self.config.set("bilibili", "cookies", "bili_jct", self.bili_jct.text())
        self.config.set("bilibili", "cookies", "DedeUserID", self.bili_dedeuid.text())
        self.config.set("tieba", "cookies", "BDUSS", self.tieba_bduss.text())
        self.config.set("tieba", "cookies", "STOKEN", self.tieba_stoken.text())
        self.config.set("llm", "api_base", self.llm_base.text().strip())
        self.config.set("llm", "api_key", self.llm_key.text().strip())
        self.config.set("llm", "model", self.llm_model.text().strip())
        self.config.set("collect", "bilibili_max_pages", self.bili_pages_s.value())
        self.config.set("collect", "bilibili_comments_per_video", self.bili_comments_s.value())
        self.config.set("collect", "tieba_max_pages", self.tieba_pages_s.value())
        self.config.set("collect", "tieba_replies_per_post", self.tieba_replies_s.value())

    def _save_config(self):
        self._update_config_from_ui()
        self.config.save()
        self._log("配置已保存", "success")
        self._show_toast("配置已保存", "success")

    def _apply_preset(self, base, model):
        self.llm_base.setText(base)
        self.llm_model.setText(model)

    # ========== Cookie 一键获取（与旧版一致） ==========

    def _get_bilibili_cookie(self):
        self._fetch_cookie("bilibili")

    def _get_tieba_cookie(self):
        self._fetch_cookie("tieba")

    def _fetch_cookie(self, platform):
        name = "B站" if platform == "bilibili" else "贴吧"
        self._log(f"正在从浏览器提取{name}Cookie...", "info")
        if not cookie_helper.is_browser_cookie3_available():
            self._log("browser_cookie3 未安装，无法自动获取。请手动填写或安装: pip install browser_cookie3", "error")
            QMessageBox.warning(self, "提示", "browser_cookie3 未安装，无法自动获取Cookie。\n\n"
                                            "请手动填写或运行:\npip install browser_cookie3")
            return

        def _do():
            try:
                fn = (cookie_helper.get_bilibili_cookies if platform == "bilibili"
                      else cookie_helper.get_tieba_cookies)
                self.message_queue.put(("cookie_result", platform, fn()))
            except Exception as e:
                self.message_queue.put(("cookie_result", platform, str(e)))
        threading.Thread(target=_do, daemon=True).start()

    # ========== 测试连接（与旧版一致） ==========

    def _test_bilibili(self):
        self._update_config_from_ui()
        if not self.config.is_bilibili_configured():
            self._log("请先填写 B站 SESSDATA", "error")
            return
        self._log("正在测试B站连接...", "info")

        def _do():
            try:
                collector = BilibiliCollector(self.config.get_bilibili_cookie_str())
                hot = collector.get_hot_searches()
                if hot:
                    self.message_queue.put(("log", f"B站连接成功！热搜: {', '.join(hot[:5])}", "success"))
                    self.message_queue.put(("status", "B站连接正常"))
                else:
                    self.message_queue.put(("log", "B站连接成功（热搜为空）", "success"))
            except Exception as e:
                self.message_queue.put(("log", f"B站连接失败: {e}", "error"))
                self.message_queue.put(("status", "B站连接失败"))
        threading.Thread(target=_do, daemon=True).start()

    def _test_tieba(self):
        self._update_config_from_ui()
        if not self.config.is_tieba_configured():
            self._log("请先填写贴吧 BDUSS", "error")
            return
        self._log("正在测试贴吧连接...", "info")

        def _do():
            try:
                collector = TiebaCollector(self.config.get_tieba_cookie_str())
                posts = collector.get_bar_posts("测试", page=1)
                self.message_queue.put(("log", f"贴吧连接成功！获取到 {len(posts)} 条帖子", "success"))
                self.message_queue.put(("status", "贴吧连接正常"))
            except Exception as e:
                self.message_queue.put(("log", f"贴吧连接失败: {e}", "error"))
                self.message_queue.put(("status", "贴吧连接失败"))
        threading.Thread(target=_do, daemon=True).start()

    def _test_llm(self):
        self._update_config_from_ui()
        if not self.config.is_llm_configured():
            self._log("请先填写 LLM API Key", "error")
            return
        self._log("正在测试LLM连接...", "info")

        def _do():
            try:
                analyzer = LLMAnalyzer(
                    self.config.get("llm", "api_base"),
                    self.config.get("llm", "api_key"),
                    self.config.get("llm", "model"),
                )
                result = analyzer._chat("你是测试助手", "请回复'连接成功'四个字",
                                        temperature=0, max_tokens=20)
                self.message_queue.put(("log", f"LLM连接成功！模型回复: {result}", "success"))
                self.message_queue.put(("status", "LLM连接正常"))
            except Exception as e:
                self.message_queue.put(("log", f"LLM连接失败: {e}", "error"))
                self.message_queue.put(("status", "LLM连接失败"))
        threading.Thread(target=_do, daemon=True).start()

    # ========== 核心分析流程（与旧版一致） ==========

    def _start_analysis(self):
        if self._analyzing:
            return
        self._update_config_from_ui()

        mode = self.analysis_mode
        if mode == "single_video":
            video_input = self.video_entry.text().strip()
            if not video_input:
                self._log("请输入BV号或视频URL", "error")
                return
            self.current_keyword = video_input
        else:
            keyword = self.kw_entry.text().strip()
            if not keyword:
                self._log("请输入关键词", "error")
                return
            self.current_keyword = keyword

        if not self.config.is_llm_configured():
            self._log("请先配置 LLM API Key", "error")
            self.pages.setCurrentIndex(1)
            self.nav_buttons["settings"].setChecked(True)
            return

        use_bili = self.bili_toggle.isChecked() if mode != "single_video" else True
        use_tieba = self.tieba_toggle.isChecked() and mode == "keyword"

        if mode != "single_video" and use_bili and not self.config.is_bilibili_configured():
            self._log("B站未配置 Cookie，请在设置页填写", "warning")
        if mode == "keyword" and use_tieba and not self.config.is_tieba_configured():
            self._log("贴吧未配置 Cookie，请在设置页填写", "warning")
        if mode == "single_video" and not self.config.is_bilibili_configured():
            self._log("B站未配置 Cookie，请在设置页填写", "warning")

        self._analyzing = True
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("分析中…")
        self.clear_btn.setEnabled(False)
        self._clear_data()
        self._set_status("LLM 分析中…")
        self.activity_text.clear()

        bili_cookie = self.config.get_bilibili_cookie_str() if use_bili else ""
        tieba_cookie = self.config.get_tieba_cookie_str() if use_tieba else ""

        mode_names = {"keyword": "关键词综合分析", "single_video": "单视频深度分析",
                      "bili_overview": "B站相关视频概览"}
        self._activity(f"开始分析 [{mode_names.get(mode, '')}] {self.current_keyword}", "info")

        def _do():
            try:
                analyzer = LLMAnalyzer(
                    self.config.get("llm", "api_base"),
                    self.config.get("llm", "api_key"),
                    self.config.get("llm", "model"),
                )

                def on_tool_call(name, args):
                    desc = self._format_tool_call_desc(name, args)
                    self.message_queue.put(("activity", f"🔍 调用工具: {desc}", "tool"))

                def on_tool_result(name, summary):
                    self.message_queue.put(("activity", f"  ✓ {summary}", "result"))

                def on_thinking(text):
                    if text and len(text) < 200:
                        self.message_queue.put(("activity", f"🤔 {text[:100]}", "think"))

                try:
                    if mode == "keyword":
                        result = analyzer.analyze_agentic(
                            self.current_keyword,
                            bili_cookie=bili_cookie, tieba_cookie=tieba_cookie,
                            use_bilibili=use_bili, use_tieba=use_tieba,
                            on_tool_call=on_tool_call, on_tool_result=on_tool_result,
                            on_thinking=on_thinking)
                    elif mode == "single_video":
                        result = analyzer.analyze_single_video(
                            self.current_keyword, bili_cookie=bili_cookie,
                            on_tool_call=on_tool_call, on_tool_result=on_tool_result,
                            on_thinking=on_thinking)
                    elif mode == "bili_overview":
                        result = analyzer.analyze_bili_overview(
                            self.current_keyword, bili_cookie=bili_cookie,
                            on_tool_call=on_tool_call, on_tool_result=on_tool_result,
                            on_thinking=on_thinking)

                    self.bilibili_data = result.get("bilibili_data")
                    self.tieba_data = result.get("tieba_data")
                    self.analysis_report = result.get("report", "")
                    self.message_queue.put(("data_ready", "bilibili"))
                    if self.tieba_data:
                        self.message_queue.put(("data_ready", "tieba"))
                    self.message_queue.put(("report", self.analysis_report))
                    self.message_queue.put(("activity", "✅ 分析完成！", "result"))
                    self.message_queue.put(("log", f"{mode_names.get(mode, '')}完成", "success"))
                    self.message_queue.put(("done", "complete"))

                except FunctionCallingNotSupported:
                    self.message_queue.put(("activity", "⚠ API不支持函数调用，回退到传统模式", "think"))
                    self.message_queue.put(("log", "API不支持函数调用，使用传统模式", "warning"))
                    if mode == "keyword":
                        bili_data, tieba_data = self._traditional_collect(
                            self.current_keyword, use_bili, use_tieba)
                    elif mode == "single_video":
                        bili_data = self._traditional_collect_single_video(self.current_keyword)
                        tieba_data = None
                    else:
                        bili_data = self._traditional_collect_bili_overview(self.current_keyword)
                        tieba_data = None

                    if bili_data:
                        self.bilibili_data = bili_data
                        self.message_queue.put(("data_ready", "bilibili"))
                    if tieba_data:
                        self.tieba_data = tieba_data
                        self.message_queue.put(("data_ready", "tieba"))
                    self.message_queue.put(("activity", "采集完成，正在分析...", "info"))

                    report = analyzer.analyze_traditional(self.current_keyword, bili_data,
                                                          tieba_data if mode == "keyword" else None)
                    self.analysis_report = report
                    self.message_queue.put(("report", report))
                    self.message_queue.put(("activity", "✅ 分析完成（传统模式）！", "result"))
                    self.message_queue.put(("log", "传统模式分析完成", "success"))
                    self.message_queue.put(("done", "complete"))

            except Exception as e:
                self.message_queue.put(("activity", f"❌ 分析失败: {e}", "error"))
                self.message_queue.put(("log", f"分析出错: {e}", "error"))
                self.message_queue.put(("done", "error"))

        threading.Thread(target=_do, daemon=True).start()

    # ---- 传统模式回退采集（与旧版一致） ----

    def _traditional_collect(self, keyword, use_bili, use_tieba):
        bili_data = None
        tieba_data = None
        if use_bili:
            self.message_queue.put(("activity", "正在采集B站数据...", "info"))
            try:
                collector = BilibiliCollector(self.config.get_bilibili_cookie_str())
                bili_data = collector.collect_keyword_data(
                    keyword, max_pages=self.bili_pages_s.value(),
                    comments_per_video=self.bili_comments_s.value())
                self.message_queue.put(("activity",
                    f"  ✓ B站: {bili_data['total_videos']}视频, {bili_data['total_comments']}评论", "result"))
            except Exception as e:
                self.message_queue.put(("activity", f"  ❌ B站采集失败: {e}", "error"))
        if use_tieba:
            self.message_queue.put(("activity", "正在采集贴吧数据...", "info"))
            try:
                collector = TiebaCollector(self.config.get_tieba_cookie_str())
                tieba_data = collector.collect_keyword_data(
                    keyword, max_pages=self.tieba_pages_s.value(),
                    replies_per_post=self.tieba_replies_s.value())
                self.message_queue.put(("activity",
                    f"  ✓ 贴吧: {tieba_data['total_posts']}帖子, {tieba_data['total_replies']}回复", "result"))
            except Exception as e:
                self.message_queue.put(("activity", f"  ❌ 贴吧采集失败: {e}", "error"))
        return bili_data, tieba_data

    def _traditional_collect_single_video(self, video_input):
        bvid = BilibiliCollector.resolve_bvid(video_input)
        if not bvid:
            self.message_queue.put(("activity", f"  ❌ 无法解析BV号: {video_input}", "error"))
            return None
        self.message_queue.put(("activity", f"正在获取视频信息: {bvid}...", "info"))
        try:
            collector = BilibiliCollector(self.config.get_bilibili_cookie_str())
            info = collector.get_video_info(bvid)
            self.message_queue.put(("activity",
                f"  ✓ 视频: 《{info['title'][:30]}》 播放:{info['play']}", "result"))
            self.message_queue.put(("activity", "正在获取评论...", "info"))
            comments = []
            for page in range(1, 4):
                try:
                    page_comments = collector.get_video_comments(info["aid"], page=page, ps=20)
                    if not page_comments:
                        break
                    comments.extend(page_comments)
                    if len(comments) >= 60:
                        break
                except Exception:
                    break
            self.message_queue.put(("activity", f"  ✓ 获取到 {len(comments)} 条评论", "result"))
            return {"videos": [info], "comments": comments, "video_info": info,
                    "total_videos": 1, "total_comments": len(comments)}
        except Exception as e:
            self.message_queue.put(("activity", f"  ❌ 视频采集失败: {e}", "error"))
            return None

    def _traditional_collect_bili_overview(self, keyword):
        self.message_queue.put(("activity", "正在搜索B站相关视频...", "info"))
        try:
            collector = BilibiliCollector(self.config.get_bilibili_cookie_str())
            bili_data = collector.collect_keyword_data(
                keyword, max_pages=self.bili_pages_s.value(),
                comments_per_video=self.bili_comments_s.value())
            self.message_queue.put(("activity",
                f"  ✓ B站: {bili_data['total_videos']}视频, {bili_data['total_comments']}评论", "result"))
            return bili_data
        except Exception as e:
            self.message_queue.put(("activity", f"  ❌ B站采集失败: {e}", "error"))
            return None

    def _format_tool_call_desc(self, name, args):
        if name == "search_bilibili":
            return f"搜索B站「{args.get('keyword', '?')}」(第{args.get('page', 1)}页)"
        elif name == "get_bilibili_comments":
            return f"获取B站评论(av{args.get('aid', '?')}, 限{args.get('limit', 20)}条)"
        elif name == "get_video_info":
            return f"获取视频详情({args.get('bvid', '?')})"
        elif name == "search_tieba":
            return f"搜索贴吧「{args.get('keyword', '?')}」(第{args.get('page', 1)}页)"
        elif name == "get_tieba_replies":
            return f"获取贴吧回复(帖子{args.get('post_id', '?')})"
        return f"{name}({args})"

    # ========== UI 更新辅助 ==========

    def _append_log_line(self, widget, msg, tag):
        """向日志控件追加一行带颜色的文本"""
        ts = datetime.now().strftime("%H:%M:%S")
        color = LOG_COLORS.get(tag, C["ink"])
        widget.append(
            f'<span style="color:{C["faint"]}">[{ts}]</span> '
            f'<span style="color:{color}">{html.escape(msg)}</span>')
        sb = widget.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _log(self, msg, level="info"):
        self._append_log_line(self.log_text, msg, level)

    def _activity(self, text, tag="info"):
        self._append_log_line(self.activity_text, text, tag)

    def _set_status(self, text):
        self.status_label.setText(text)

    def _set_report(self, text):
        if text:
            self.report_text.setMarkdown(text)
        else:
            self.report_text.clear()

    def _show_toast(self, message, kind="info"):
        Toast(self.root, message, kind)

    def _clear_data(self):
        self.bilibili_data = None
        self.tieba_data = None
        self.analysis_report = ""
        for t in (self.bili_table, self.bili_comment_table,
                  self.tieba_table, self.tieba_reply_table):
            t.setRowCount(0)
        self._set_report("")

    # ---- 数据填充 ----

    @staticmethod
    def _fill_table(table, rows):
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if j > 0:
                    item.setForeground(QColor(C["ink_2"]))
                table.setItem(i, j, item)

    def _populate_bilibili_data(self):
        if not self.bilibili_data:
            return
        videos = [(v.get("title", "")[:50], v.get("author", ""), v.get("play", 0),
                   v.get("like", 0), v.get("reply", 0), v.get("favorites", 0),
                   v.get("pubdate", "")) for v in self.bilibili_data.get("videos", [])]
        self._fill_table(self.bili_table, videos)
        comments = [(c.get("user", ""), c.get("content", "")[:100], c.get("like", 0),
                     c.get("ctime", "")) for c in self.bilibili_data.get("comments", [])]
        self._fill_table(self.bili_comment_table, comments)

    def _populate_tieba_data(self):
        if not self.tieba_data:
            return
        posts = [(p.get("title", "")[:50], p.get("bar", ""), p.get("author", ""),
                  p.get("reply_count", 0), p.get("date", ""))
                 for p in self.tieba_data.get("posts", [])]
        self._fill_table(self.tieba_table, posts)
        replies = [(r.get("user", ""), r.get("content", "")[:100], r.get("floor", ""),
                    r.get("time", "")) for r in self.tieba_data.get("replies", [])]
        self._fill_table(self.tieba_reply_table, replies)

    # ---- 导出 ----

    def _export_report(self):
        if not self.analysis_report:
            self._log("暂无分析报告", "warning")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出报告",
            f"声呐报告_{self.current_keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            "Markdown (*.md);;文本文件 (*.txt);;所有文件 (*.*)")
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# 关键词「{self.current_keyword}」舆情分析报告\n\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
                f.write(self.analysis_report)
            self._log(f"报告已保存: {filename}", "success")
            self._show_toast("报告已导出", "success")

    def _export_data(self):
        if not self.bilibili_data and not self.tieba_data:
            self._log("暂无采集数据", "warning")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出数据",
            f"声呐数据_{self.current_keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON (*.json);;所有文件 (*.*)")
        if filename:
            data = {"keyword": self.current_keyword,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "bilibili": self.bilibili_data, "tieba": self.tieba_data}
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log(f"数据已保存: {filename}", "success")
            self._show_toast("数据已导出", "success")

    # ========== 消息队列轮询（与旧版协议一致） ==========

    def _poll_queue(self):
        try:
            while True:
                msg_type, *parts = self.message_queue.get_nowait()

                if msg_type == "log":
                    self._log(parts[0] if parts else "",
                              parts[1] if len(parts) > 1 else "info")

                elif msg_type == "activity":
                    text = parts[0] if parts else ""
                    tag = parts[1] if len(parts) > 1 else "info"
                    self._activity(text, tag)

                elif msg_type == "status":
                    self._set_status(parts[0])

                elif msg_type == "report":
                    self._set_report(parts[0])
                    n = self._data_count()
                    self.status_right.setText(f"{n} 条数据 · 更新于 "
                                              f"{datetime.now().strftime('%H:%M')}")

                elif msg_type == "data_ready":
                    if parts[0] == "bilibili":
                        self._populate_bilibili_data()
                    elif parts[0] == "tieba":
                        self._populate_tieba_data()

                elif msg_type == "cookie_result":
                    self._handle_cookie_result(parts[0], parts[1])

                elif msg_type == "done":
                    self._analyzing = False
                    self.analyze_btn.setEnabled(True)
                    self.analyze_btn.setText("一键分析")
                    self.clear_btn.setEnabled(True)
                    status = parts[0] if parts else ""
                    self._set_status("完成" if status == "complete" else "出错")

        except queue.Empty:
            pass

    def _data_count(self):
        n = 0
        if self.bilibili_data:
            n += len(self.bilibili_data.get("videos", []))
            n += len(self.bilibili_data.get("comments", []))
        if self.tieba_data:
            n += len(self.tieba_data.get("posts", []))
            n += len(self.tieba_data.get("replies", []))
        return n

    def _handle_cookie_result(self, platform, result):
        name = "B站" if platform == "bilibili" else "贴吧"
        if isinstance(result, dict):
            if platform == "bilibili":
                self.bili_sessdata.setText(result.get("SESSDATA", ""))
                self.bili_jct.setText(result.get("bili_jct", ""))
                self.bili_dedeuid.setText(result.get("DedeUserID", ""))
            else:
                self.tieba_bduss.setText(result.get("BDUSS", ""))
                self.tieba_stoken.setText(result.get("STOKEN", ""))
            self._log(f"{name}Cookie获取成功！", "success")
            self._show_toast(f"{name}Cookie获取成功", "success")
        elif result is None:
            self._log(f"未找到{name}Cookie，请确保浏览器已登录{name}", "error")
            QMessageBox.warning(self, "提示", f"未找到{name}Cookie。\n请确保浏览器已登录{name}后重试。")
        else:
            self._log(f"{name}Cookie获取出错: {result}", "error")

    # ========== 无边框窗口：拖拽调整大小 & 真毛玻璃 ==========

    def _edge_at(self, pos):
        """判断鼠标是否处于窗口边缘（用于系统级缩放）"""
        if self.isMaximized():
            return None
        m = self.RESIZE_MARGIN
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()
        edges = Qt.Edge(0)
        if x < m:
            edges |= Qt.LeftEdge
        if x > w - m:
            edges |= Qt.RightEdge
        if y < m:
            edges |= Qt.TopEdge
        if y > h - m:
            edges |= Qt.BottomEdge
        return edges if edges != Qt.Edge(0) else None

    def mousePressEvent(self, event):
        edges = self._edge_at(event.position().toPoint())
        if edges:
            self.windowHandle().startSystemResize(edges)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        edges = self._edge_at(event.position().toPoint())
        cursors = {
            Qt.LeftEdge: Qt.SizeHorCursor, Qt.RightEdge: Qt.SizeHorCursor,
            Qt.TopEdge: Qt.SizeVerCursor, Qt.BottomEdge: Qt.SizeVerCursor,
            Qt.LeftEdge | Qt.TopEdge: Qt.SizeFDiagCursor,
            Qt.RightEdge | Qt.BottomEdge: Qt.SizeFDiagCursor,
            Qt.LeftEdge | Qt.BottomEdge: Qt.SizeBDiagCursor,
            Qt.RightEdge | Qt.TopEdge: Qt.SizeBDiagCursor,
        }
        self.setCursor(QCursor(cursors.get(edges, Qt.ArrowCursor)))
        super().mouseMoveEvent(event)

    def changeEvent(self, event):
        # 最大化时去掉投影边距与圆角，铺满屏幕
        if getattr(self, "root", None) is not None and self.layout() is not None:
            maximized = self.isMaximized()
            m = 0 if maximized else 12
            self.layout().setContentsMargins(m, m, m, m)
            self.root.setStyleSheet(
                f"QWidget#root {{ background: {C['parchment']}; "
                f"border-radius: {0 if maximized else 12}px; }}")
        super().changeEvent(event)

    def _try_acrylic(self):
        """Windows 11 真 Acrylic 毛玻璃背景（best-effort，失败静默）"""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            class ACCENTPOLICY(ctypes.Structure):
                _fields__ = [("AccentState", ctypes.c_int),
                             ("AccentFlags", ctypes.c_int),
                             ("GradientColor", ctypes.c_ulong),
                             ("AnimationId", ctypes.c_int)]

            class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
                _fields_ = [("Attribute", ctypes.c_int),
                            ("Data", ctypes.c_void_p),
                            ("SizeOfData", ctypes.c_size_t)]

            accent = ACCENTPOLICY()
            accent.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
            accent.AccentFlags = 2
            accent.GradientColor = 0x99F7F5F5  # ABGR：浅 Parchment 色调
            data = WINDOWCOMPOSITIONATTRIBDATA()
            data.Attribute = 19  # WCA_ACCENT_POLICY
            data.Data = ctypes.addressof(accent)
            data.SizeOfData = ctypes.sizeof(accent)
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        except Exception:
            pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("声呐 Sonar")
    app.setStyleSheet(qss())
    win = SonarWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
