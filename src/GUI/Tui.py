from __future__ import annotations

import ctypes
import os
import sys

from Backend import DetectHardware, TMode
from Backend.TMode import CurvePoint
from Backend.Televate import ensure_running_as_admin
from config import Tconfig

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
    from PySide6.QtWidgets import (
        QApplication, QButtonGroup, QCheckBox, QFrame, QGraphicsDropShadowEffect,
        QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSlider,
        QVBoxLayout, QWidget,
    )
    QT_BINDING = "PySide6"
except ImportError:
    print('PySide6 not found. Please install it and try again.')
    """
    from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal as Signal
    from PyQt6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
    from PyQt6.QtWidgets import (
        QApplication, QButtonGroup, QCheckBox, QFrame, QGraphicsDropShadowEffect,
        QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSlider,
        QVBoxLayout, QWidget,
    )
    QT_BINDING = "PyQt6"
    """

ACCENT = "#67e8f9"
CPU_COLOR = QColor("#5eead4")
GPU_COLOR = QColor("#818cf8")
BG = QColor("#070b14")

def create_mode_icon(g_mode: bool) -> QIcon:
    """Create the shared title-bar, taskbar and tray icon for a mode."""
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = size / 64.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f97316") if g_mode else QColor("#16263a"))
        p.drawEllipse(QRectF(2 * scale, 2 * scale, 60 * scale, 60 * scale))
        if g_mode:
            bolt = QPainterPath()
            bolt.moveTo(36 * scale, 10 * scale)
            bolt.lineTo(17 * scale, 35 * scale)
            bolt.lineTo(30 * scale, 35 * scale)
            bolt.lineTo(25 * scale, 55 * scale)
            bolt.lineTo(48 * scale, 27 * scale)
            bolt.lineTo(35 * scale, 27 * scale)
            bolt.closeSubpath()
            p.setBrush(QColor("#fff7ed"))
            p.drawPath(bolt)
        else:
            p.translate(32 * scale, 32 * scale)
            p.setBrush(QColor("#67e8f9"))
            for _ in range(3):
                blade = QPainterPath()
                blade.moveTo(2 * scale, -3 * scale)
                blade.cubicTo(7 * scale, -24 * scale, 25 * scale, -20 * scale, 22 * scale, -7 * scale)
                blade.cubicTo(20 * scale, 2 * scale, 10 * scale, 8 * scale, 3 * scale, 5 * scale)
                blade.closeSubpath()
                p.drawPath(blade)
                p.rotate(120)
            p.setBrush(QColor("#e6fdff"))
            p.drawEllipse(QPointF(0, 0), 5 * scale, 5 * scale)
        p.end()
        icon.addPixmap(pixmap)
    return icon

class GaugeWidget(QWidget):

    def __init__(self, title: str, subtitle: str, color: QColor, parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.color = color
        self.temperature = 0
        self.rpm = 0
        # Keep telemetry geometry independent from the mode-specific panel below.
        self.setMinimumWidth(280)
        self.setFixedHeight(245)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, temperature: int, rpm: int) -> None:
        self.temperature = max(0, min(110, int(temperature)))
        self.rpm = max(0, int(rpm))
        self.update()

    def paintEvent(self, event):
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Card
        card = QRectF(1, 1, w - 2, h - 2)
        p.setPen(QPen(QColor("#263248"), 1))
        p.setBrush(QColor("#101827"))
        p.drawRoundedRect(card, 18, 18)

        p.setPen(QColor("#f1f5f9"))
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        p.drawText(QRectF(22, 16, w - 44, 28), Qt.AlignmentFlag.AlignLeft, self.title)
        p.setPen(QColor("#7f8da5"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(22, 42, w - 44, 20), Qt.AlignmentFlag.AlignLeft, self.subtitle)

        side = min(w * 0.55, h - 80)
        arc = QRectF(22, 70, side, side)
        pen = QPen(QColor("#253247"), 13, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(arc, 225 * 16, -270 * 16)

        gradient = QLinearGradient(arc.topLeft(), arc.bottomRight())
        gradient.setColorAt(0, self.color.lighter(135))
        gradient.setColorAt(1, self.color)
        pen.setBrush(gradient)
        p.setPen(pen)
        p.drawArc(arc, 225 * 16, int(-270 * 16 * self.temperature / 110))

        cx, cy = arc.center().x(), arc.center().y()
        p.setPen(QColor("#f8fafc"))
        p.setFont(QFont("Segoe UI", max(22, int(side / 5.5)), QFont.Weight.Bold))
        p.drawText(QRectF(arc.left(), cy - 34, side, 48), Qt.AlignmentFlag.AlignCenter,
                   f"{self.temperature}\N{DEGREE SIGN}")
        p.setPen(QColor("#8390a7"))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        p.drawText(QRectF(arc.left(), cy + 13, side, 22), Qt.AlignmentFlag.AlignCenter, "TEMPERATURE")

        x = 45 + side
        p.setPen(QColor("#66748b"))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        p.drawText(QRectF(x, 80, w - x - 22, 20), Qt.AlignmentFlag.AlignLeft, "FAN SPEED")
        p.setPen(QColor("#f8fafc"))
        p.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        p.drawText(QRectF(x, 101, w - x - 22, 42), Qt.AlignmentFlag.AlignLeft, f"{self.rpm:,}")
        p.setPen(self.color)
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.drawText(QRectF(x, 143, w - x - 22, 22), Qt.AlignmentFlag.AlignLeft, "RPM")

        # Status pulse
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#34d399") if self.rpm else QColor("#64748b"))
        p.drawEllipse(QPointF(x + 5, 190), 5, 5)
        p.setPen(QColor("#9aa7bb"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(x + 18, 180, w - x - 38, 20), Qt.AlignmentFlag.AlignLeft,
                   Tconfig.CONFIG_LOAD["Languages"]["Running"] if self.rpm else Tconfig.CONFIG_LOAD["Languages"]["Stopped"])


class SpeedControl(QFrame):
    """Slider whose public signal is emitted only after the user releases it."""

    speedChanged = Signal(str, int)

    def __init__(self, device: str, color: str, value: int, parent=None):
        super().__init__(parent)
        self.device = device
        self.setObjectName("speedControl")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel(f"{device} FAN")
        title.setObjectName("controlTitle")
        self.value_label = QLabel(f"{value}%")
        self.value_label.setStyleSheet(f"color:{color};font-size:18px;font-weight:700;")
        head.addWidget(title)
        head.addStretch()
        head.addWidget(self.value_label)
        layout.addLayout(head)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(value)
        self.slider.setProperty("accent", color)
        self.slider.setStyleSheet(
            "QSlider::groove:horizontal{height:6px;background:#253047;border-radius:3px;}"
            f"QSlider::sub-page:horizontal{{background:{color};border-radius:3px;}}"
            f"QSlider::handle:horizontal{{background:#f8fafc;border:3px solid {color};"
            "width:16px;height:16px;margin:-7px 0;border-radius:10px;}"
        )
        self.slider.valueChanged.connect(self._preview_value)
        self.slider.sliderReleased.connect(self._commit_value)
        layout.addWidget(self.slider)

        marks = QHBoxLayout()
        for text in ("0", "25", "50", "75", "100"):
            label = QLabel(text)
            label.setObjectName("tick")
            marks.addWidget(label)
            if text != "100":
                marks.addStretch()
        layout.addLayout(marks)

    def _preview_value(self, value: int):
        self.value_label.setText(f"{value}%")

    def _commit_value(self):
        self.speedChanged.emit(self.device.lower(), self.slider.value())

    def set_control_enabled(self, enabled: bool):
        self.slider.setEnabled(enabled)
        self.setProperty("controlEnabled", enabled)
        self.style().unpolish(self)
        self.style().polish(self)


class FanCurveEditor(QWidget):
    """Dependency-free interactive temperature/speed curve editor."""

    curveChanged = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.curves = {
            "cpu": [CurvePoint(t, s) for t, s in TMode.getCustomTemperatureList('cpu')],
            "gpu": [CurvePoint(t, s) for t, s in TMode.getCustomTemperatureList('gpu')],
        }
        self.visible_curves = {"cpu": True, "gpu": True}
        self.active_curve = "cpu"
        self.drag_index = None
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_curve_visible(self, name: str, visible: bool):
        self.visible_curves[name] = visible
        if visible:
            self.active_curve = name
        self.update()

    def set_active_curve(self, name: str):
        self.active_curve = name
        self.update()

    def plot_rect(self) -> QRectF:
        return QRectF(62, 26, max(100, self.width() - 88), max(100, self.height() - 76))

    def point_to_pixel(self, point: CurvePoint) -> QPointF:
        r = self.plot_rect()
        return QPointF(r.left() + (point.temperature - 30) / 70 * r.width(),
                       r.bottom() - point.speed / 100 * r.height())

    def pixel_to_speed(self, y: float) -> int:
        r = self.plot_rect()
        return round(max(0, min(100, (r.bottom() - y) / r.height() * 100)))

    def paintEvent(self, event):
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.plot_rect()
        p.fillRect(self.rect(), QColor("#0c1320"))

        p.setFont(QFont("Segoe UI", 8))
        for speed in range(0, 101, 25):
            y = r.bottom() - speed / 100 * r.height()
            p.setPen(QPen(QColor("#263249"), 1))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(QColor("#65738a"))
            p.drawText(QRectF(4, y - 9, 48, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{speed}%")
        for temp in range(30, 101, 10):
            x = r.left() + (temp - 30) / 70 * r.width()
            p.setPen(QPen(QColor("#202b40"), 1))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setPen(QColor("#65738a"))
            p.drawText(QRectF(x - 18, r.bottom() + 10, 36, 18), Qt.AlignmentFlag.AlignCenter, f"{temp}\N{DEGREE SIGN}")

        for name, color in (("gpu", GPU_COLOR), ("cpu", CPU_COLOR)):
            if not self.visible_curves[name]:
                continue
            points = [self.point_to_pixel(pt) for pt in self.curves[name]]
            path = QPainterPath(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 32), 8,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
            p.setPen(QPen(color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
            for i, pt in enumerate(points):
                p.setPen(QPen(QColor("#09111f"), 3))
                p.setBrush(color if name == self.active_curve else color.darker(130))
                radius = 7 if name == self.active_curve else 5
                p.drawEllipse(pt, radius, radius)

        p.setPen(QColor("#77859b"))
        p.drawText(QRectF(r.left(), 2, 170, 20), Qt.AlignmentFlag.AlignLeft, "FAN SPEED (%)")
        p.drawText(QRectF(r.right() - 130, r.bottom() + 30, 130, 20), Qt.AlignmentFlag.AlignRight, "TEMPERATURE (\N{DEGREE SIGN}C)")

    def mousePressEvent(self, event):
        if not self.isEnabled() or not self.visible_curves.get(self.active_curve):
            return
        pos = event.position()
        distances = [(pos - self.point_to_pixel(pt)).manhattanLength() for pt in self.curves[self.active_curve]]
        index = min(range(len(distances)), key=distances.__getitem__)
        if distances[index] <= 18:
            self.drag_index = index
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.drag_index is None:
            return
        curve = self.curves[self.active_curve]
        new_speed = self.pixel_to_speed(event.position().y())
        # Keep the curve monotonic so a hotter device never receives less cooling.
        low = curve[self.drag_index - 1].speed if self.drag_index > 0 else 0
        high = curve[self.drag_index + 1].speed if self.drag_index < len(curve) - 1 else 100
        curve[self.drag_index].speed = max(low, min(high, new_speed))
        self.update()

    def mouseReleaseEvent(self, event):
        del event
        if self.drag_index is not None:
            payload = [(p.temperature, p.speed) for p in self.curves[self.active_curve]]
            self.curveChanged.emit(self.active_curve, payload)
        self.drag_index = None
        self.unsetCursor()


class ModeButton(QPushButton):
    def __init__(self, title: str, caption: str, parent=None):
        super().__init__(f"{title}\n{caption}", parent)
        self.setCheckable(True)
        self.setFixedHeight(58)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class FanControlWindow(QMainWindow):
    """Main UI. Public signals are the integration boundary for hardware code."""

    modeRequested = Signal(str)
    fixedSpeedRequested = Signal(str, int)
    curveRequested = Signal(str, object)
    telemetryRefreshRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(Tconfig.CONFIG_LOAD["Languages"]["title"])
        self.setWindowIcon(create_mode_icon(False))
        self.resize(1120, 760) # 尺寸
        self.setMinimumSize(880, 680)
        self._build_ui()
        self._apply_style()
        self.set_mode(TMode.getMode())
        self.update_telemetry()
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.setInterval(Tconfig.CONFIG_LOAD["Refresh"]) # 刷新间隔
        self.telemetry_timer.timeout.connect(self._refresh_telemetry)
        self.telemetry_timer.start()

        # Follow the operating-system light/dark appearance for the native
        # title bar. The signal is available in current Qt 6 versions.
        style_hints = QApplication.styleHints()
        if hasattr(style_hints, "colorSchemeChanged"):
            style_hints.colorSchemeChanged.connect(self._apply_system_titlebar_theme)

    def showEvent(self, event):
        """The native window handle exists here, so DWM can style its title bar."""
        super().showEvent(event)
        self._apply_system_titlebar_theme()

    def _apply_system_titlebar_theme(self, color_scheme=None):
        """Make the Windows title bar track the current system color scheme."""
        if sys.platform != "win32":
            return

        if color_scheme is None:
            color_scheme = QApplication.styleHints().colorScheme()
        dark_scheme = getattr(Qt.ColorScheme, "Dark", None)
        light_scheme = getattr(Qt.ColorScheme, "Light", None)
        if color_scheme == dark_scheme:
            use_dark = True
        elif color_scheme == light_scheme:
            use_dark = False
        else:
            # Some Qt/Windows combinations report Unknown. Use the same
            # personalization value that Windows itself uses for app chrome.
            try:
                import winreg
                key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    apps_use_light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                use_dark = not bool(apps_use_light)
            except (OSError, ImportError):
                use_dark = QApplication.palette().window().color().lightness() < 128

        # DWMWA_USE_IMMERSIVE_DARK_MODE is 20 on supported Windows 10/11
        # builds and 19 on an older Windows 10 build. Trying both is harmless.
        enabled = ctypes.c_int(1 if use_dark else 0)
        hwnd = ctypes.c_void_p(int(self.winId()))
        try:
            dwmapi = ctypes.windll.dwmapi
            for attribute in (20, 19):
                result = dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
                )
                if result == 0:
                    break
        except (AttributeError, OSError):
            pass




    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setObjectName("mainScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)
        root = QWidget()
        root.setObjectName("root")
        root.setMinimumWidth(820)
        scroll.setWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(28, 22, 28, 24)
        page.setSpacing(18)

        gauges = QHBoxLayout()
        gauges.setSpacing(16)
        dh = DetectHardware.DetectHardware()
        self.cpu_gauge = GaugeWidget("CPU", dh.getHardwareName(dh.CPUFanIdx), CPU_COLOR) # CPU
        self.gpu_gauge = GaugeWidget("GPU", dh.getHardwareName(dh.GPUFanIdx), GPU_COLOR) # GPU
        gauges.addWidget(self.cpu_gauge)
        gauges.addWidget(self.gpu_gauge)
        # No vertical stretch factor: hiding a mode panel must not resize gauges.
        page.addLayout(gauges)

        modes = QHBoxLayout()
        modes.setSpacing(10)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        mode_data = (
            ("balanced", Tconfig.CONFIG_LOAD["Languages"]["balanced"], Tconfig.CONFIG_LOAD["Languages"]["balanced_description"]),
            ("fixed", Tconfig.CONFIG_LOAD["Languages"]["fixed"], Tconfig.CONFIG_LOAD["Languages"]["fixed_description"]),
            ("custom", Tconfig.CONFIG_LOAD["Languages"]["custom"], Tconfig.CONFIG_LOAD["Languages"]["custom_description"]),
            ("g_mode", Tconfig.CONFIG_LOAD["Languages"]["g_mode"], Tconfig.CONFIG_LOAD["Languages"]["g_mode_description"]),
        )
        self.mode_buttons = {}
        for key, cn, en in mode_data:
            button = ModeButton(cn, en)
            button.setProperty("modeKey", key)
            button.clicked.connect(lambda checked=False, k=key: self.set_mode(k))
            self.mode_group.addButton(button)
            self.mode_buttons[key] = button
            modes.addWidget(button)
        page.addLayout(modes)

        self.fixed_panel = QFrame()
        self.fixed_panel.setObjectName("panel")
        fixed_layout = QVBoxLayout(self.fixed_panel)
        fixed_layout.setContentsMargins(18, 14, 18, 16)
        fixed_head = QHBoxLayout()
        fixed_title = QLabel("固定转速")
        fixed_title.setObjectName("sectionTitle")
        self.fixed_hint = QLabel("仅在固定模式下可调整")
        self.fixed_hint.setObjectName("hint")
        fixed_head.addWidget(fixed_title)
        fixed_head.addStretch()
        fixed_head.addWidget(self.fixed_hint)
        fixed_layout.addLayout(fixed_head)
        fixed_controls = QHBoxLayout()
        fixed_controls.setSpacing(12)
        self.cpu_speed = SpeedControl("CPU", "#5eead4", TMode.getFixedTemperature('cpu'))
        self.gpu_speed = SpeedControl("GPU", "#818cf8", TMode.getFixedTemperature('gpu'))
        self.cpu_speed.speedChanged.connect(self._fixed_speed_changed)
        self.gpu_speed.speedChanged.connect(self._fixed_speed_changed)
        fixed_controls.addWidget(self.cpu_speed)
        fixed_controls.addWidget(self.gpu_speed)
        fixed_layout.addLayout(fixed_controls)
        page.addWidget(self.fixed_panel)

        self.curve_panel = QFrame()
        self.curve_panel.setObjectName("panel")
        curve_layout = QVBoxLayout(self.curve_panel)
        curve_layout.setContentsMargins(18, 14, 18, 14)
        curve_head = QHBoxLayout()
        curve_title = QLabel("温控曲线")
        curve_title.setObjectName("sectionTitle")
        curve_head.addWidget(curve_title)
        curve_head.addStretch()
        self.cpu_check = QCheckBox("CPU 曲线")
        self.gpu_check = QCheckBox("GPU 曲线")
        self.cpu_check.setChecked(True)
        self.gpu_check.setChecked(True)
        self.cpu_check.setProperty("device", "cpu")
        self.gpu_check.setProperty("device", "gpu")
        self.cpu_check.toggled.connect(lambda v: self._toggle_curve("cpu", v))
        self.gpu_check.toggled.connect(lambda v: self._toggle_curve("gpu", v))
        curve_head.addWidget(self.cpu_check)
        curve_head.addWidget(self.gpu_check)
        curve_layout.addLayout(curve_head)
        curve_help = QLabel("勾选显示曲线；点击对应标签后拖动节点。相邻节点自动保持非递减。")
        curve_help.setObjectName("hint")
        curve_layout.addWidget(curve_help)
        self.curve_editor = FanCurveEditor()
        self.curve_editor.curveChanged.connect(self._curve_changed)
        curve_layout.addWidget(self.curve_editor)
        page.addWidget(self.curve_panel)
        # Absorb all unused height below the conditional panel. This preserves
        # the gauge and mode-selector position in all four operating modes.
        page.addStretch(1)

        self.cpu_check.clicked.connect(lambda: self.curve_editor.set_active_curve("cpu"))
        self.gpu_check.clicked.connect(lambda: self.curve_editor.set_active_curve("gpu"))

    def _apply_style(self):
        self.setStyleSheet("""
            * { font-family: 'Segoe UI', 'Microsoft YaHei UI'; color: #dce6f5; }
            QWidget#root { background: #070b14; }
            QScrollArea#mainScroll { background: #070b14; border: none; }
            QScrollBar:vertical { background: #080d17; width: 8px; margin: 2px; }
            QScrollBar::handle:vertical { background: #2b3a51; min-height: 40px; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QPushButton { background: #0e1625; border: 1px solid #223048; border-radius: 12px;
                          padding: 9px; color: #8c9ab0; font-size: 10px; font-weight: 600; }
            QPushButton:hover { background: #131f31; border-color: #3a4b67; color: #dbeafe; }
            QPushButton:checked { background: #132a34; border: 1px solid #55c8cf; color: #e6fdff; }
            QFrame#panel { background: #0b121f; border: 1px solid #202d42; border-radius: 15px; }
            QLabel#sectionTitle { color: #eef5ff; font-size: 14px; font-weight: 700; }
            QLabel#hint { color: #64748b; font-size: 9px; }
            QFrame#speedControl { background: #101827; border: 1px solid #202d42; border-radius: 11px; }
            QFrame#speedControl[controlEnabled="false"] { background: #0b111c; border-color: #172235; }
            QLabel#controlTitle { color: #8493aa; font-size: 9px; font-weight: 700; }
            QLabel#tick { color: #526078; font-size: 8px; border: none; }
            QCheckBox { spacing: 8px; color: #a8b6ca; font-size: 10px; font-weight: 600; }
            QCheckBox::indicator { width: 15px; height: 15px; border-radius: 4px;
                                   border: 1px solid #40516d; background: #111a29; }
            QCheckBox::indicator:checked { background: #4fd1d9; border-color: #7ae5ea; }
            QCheckBox[device="gpu"]::indicator:checked { background: #818cf8; border-color: #a5b4fc; }
            QToolTip { background: #111827; color: #e5e7eb; border: 1px solid #334155; }
        """)

    def set_mode(self, mode: str):
        if mode not in self.mode_buttons:
            raise ValueError(f"Unknown mode: {mode}")
        self.mode_buttons[mode].setChecked(True)
        self.setWindowIcon(create_mode_icon(mode == "g_mode"))
        fixed = mode == "fixed"
        custom = mode == "custom"
        self.fixed_panel.setVisible(fixed)
        self.curve_panel.setVisible(custom)
        self.cpu_speed.set_control_enabled(fixed)
        self.gpu_speed.set_control_enabled(fixed)
        self.curve_editor.setEnabled(custom)
        self.cpu_check.setEnabled(custom)
        self.gpu_check.setEnabled(custom)
        self.fixed_panel.setGraphicsEffect(None)
        self.curve_panel.setGraphicsEffect(None)
        target = self.fixed_panel if fixed else self.curve_panel if custom else None
        if target:
            glow = QGraphicsDropShadowEffect(self)
            glow.setBlurRadius(22)
            glow.setOffset(0, 0)
            glow.setColor(QColor(80, 210, 220, 55))
            target.setGraphicsEffect(glow)
        if TMode.getMode()!= mode: TMode.on_mode_changed(mode,True,True)
        self.modeRequested.emit(mode)

    # 更新温度与转速
    def update_telemetry(self):
        self.cpu_gauge.set_values(TMode.getTemperature('cpu'), TMode.getSpeed('cpu'))
        self.gpu_gauge.set_values(TMode.getTemperature('gpu'), TMode.getSpeed('gpu'))

    # 定时刷新温度
    def _refresh_telemetry(self):
        self.update_telemetry()
        self.telemetryRefreshRequested.emit()

    def _fixed_speed_changed(self, device: str, speed: int):
        if self.mode_buttons["fixed"].isChecked():
            TMode.on_fixed_speed_changed(device, speed)
            self.fixedSpeedRequested.emit(device, speed)

    def _curve_changed(self, device: str, points: list[tuple[int, int]]):
        if self.mode_buttons["custom"].isChecked():
            TMode.on_curve_changed(device, points)
            self.curveRequested.emit(device, points)

    def _toggle_curve(self, device: str, visible: bool):
        self.curve_editor.set_curve_visible(device, visible)

    def on_telemetry_refresh(self):
        return None


def main() -> int:
    try:
        if not ensure_running_as_admin(__file__):
            return 0
    except OSError as exc:
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(None, str(exc), "无法以管理员身份启动", 0x10)
        return 1
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(sys.argv)
    app.setApplicationName("AeroTune")
    app.setFont(QFont("Segoe UI", 10))
    window = FanControlWindow()
    window.show()
    return app.exec()