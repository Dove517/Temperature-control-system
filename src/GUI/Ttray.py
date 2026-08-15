from __future__ import annotations

import os
import sys
import subprocess
import keyboard
from pathlib import Path

from Backend import TMode, Televate
from Backend.Televate import ensure_running_as_admin
from Backend.TAlert import register_tray_icon, unregister_tray_icon
from GUI.Tui import FanControlWindow, create_mode_icon
from config import Tconfig

try:
    from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
    from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
    from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon
except ImportError:
    print('PySide6 not found. Please install it and try again.')
    """
    from PyQt6.QtCore import QObject, QSettings, Qt, QTimer, pyqtSignal as Signal
    from PyQt6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
    from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon
    """

APP_NAME = "TemperatureControlSystemTray"
STARTUP_TASK_NAME = "TemperatureControlSystemElevated"
SETTINGS_ORGANIZATION = "LocalFanControl"
MODE_LABELS = {
    "balanced": "均衡模式",
    "fixed": "固定模式",
    "custom": "自定义模式",
    "g_mode": "G 模式",
}

class TrayControlWindow(FanControlWindow):
    """Closing the UI hides it; the tray process continues running."""

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class FanTrayController:
    """Owns tray icon, menu state, persistence and the optional UI window."""

    def __init__(self, app: QApplication):
        self.app = app
        self.settings = QSettings(SETTINGS_ORGANIZATION, APP_NAME)
        saved_mode=TMode.getMode()
        self.current_mode = saved_mode if saved_mode in MODE_LABELS else "balanced"
        self.window: TrayControlWindow | None = None
        self.icon_normal = create_mode_icon(False)
        self.icon_g_mode = create_mode_icon(True)

        self.tray = QSystemTrayIcon(self.app)
        register_tray_icon(self.tray)
        self.tray.setToolTip("散热风扇控制")
        self.menu = QMenu()
        self.menu.setObjectName("trayMenu")
        self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._tray_activated)
        self._sync_mode(self.current_mode, notify_backend=False)
        self._sync_startup_action()
        self._apply_menu_theme()

        style_hints = QApplication.styleHints()
        if hasattr(style_hints, "colorSchemeChanged"):
            style_hints.colorSchemeChanged.connect(self._apply_menu_theme)

        self.background_timer = QTimer(self.menu)
        self.background_timer.setInterval(Tconfig.CONFIG_LOAD["Custom"]["Refresh"])
        self.background_timer.timeout.connect(self.run_background_task)
        self.background_timer.start()

    def run_background_task(self):
        if self.current_mode=='custom':
            TMode.on_custom_trigger()
        pass

    def _build_menu(self):
        # Section 1: operating mode.
        mode_header = QAction("模式切换", self.menu)
        mode_header.setEnabled(False)
        self.menu.addAction(mode_header)

        self.mode_group = QActionGroup(self.menu)
        self.mode_group.setExclusive(True)
        self.mode_actions: dict[str, QAction] = {}
        for mode, label in MODE_LABELS.items():
            action = QAction(label, self.menu)
            action.setCheckable(True)
            action.setData(mode)
            action.triggered.connect(lambda checked=False, m=mode: self.set_mode(m))
            self.mode_group.addAction(action)
            self.menu.addAction(action)
            self.mode_actions[mode] = action

        self.menu.addSeparator()

        # Section 2: show the control UI.
        self.open_action = QAction("打开控制界面", self.menu)
        self.open_action.triggered.connect(self.show_control_ui)
        self.menu.addAction(self.open_action)

        self.menu.addSeparator()

        # Section 3: startup and process lifecycle.
        self.startup_action = QAction("开机自动启动", self.menu)
        self.startup_action.setCheckable(True)
        self.startup_action.triggered.connect(self._set_startup_enabled)
        self.menu.addAction(self.startup_action)

        self.exit_action = QAction("退出程序", self.menu)
        self.exit_action.triggered.connect(self.quit)
        self.menu.addAction(self.exit_action)

    def show(self):
        self.tray.show()

    def set_mode(self, mode: str):
        if mode not in MODE_LABELS:
            return
        self._sync_mode(mode, notify_backend=True)

    def _sync_mode(self, mode: str, notify_backend: bool):
        self.current_mode = mode
        self.settings.setValue("mode", mode)
        self.mode_actions[mode].setChecked(True)
        self.tray.setIcon(self.icon_g_mode if mode == "g_mode" else self.icon_normal)
        self.tray.setToolTip(f"散热风扇控制 · {MODE_LABELS[mode]}")

        if self.window is not None and self.window.mode_buttons[mode].isChecked() is False:
            self.window.set_mode(mode)
        elif notify_backend:
            # Create the controller lazily only when a backend hook must receive
            # a tray-originated mode request. It remains hidden in the tray.
            self._ensure_window()
            if self.window.mode_buttons[mode].isChecked() is False:
                self.window.set_mode(mode)

    def _ensure_window(self) -> TrayControlWindow:
        if self.window is None:
            self.window = TrayControlWindow()
            self.window.modeRequested.connect(self._mode_changed_from_ui)
            if not self.window.mode_buttons[self.current_mode].isChecked():
                self.window.set_mode(self.current_mode)
        return self.window

    def _mode_changed_from_ui(self, mode: str):
        # Updating actions/icons directly avoids calling the UI hook twice.
        if mode in MODE_LABELS:
            self.current_mode = mode
            self.settings.setValue("mode", mode)
            self.mode_actions[mode].setChecked(True)
            self.tray.setIcon(self.icon_g_mode if mode == "g_mode" else self.icon_normal)
            self.tray.setToolTip(f"散热风扇控制 · {MODE_LABELS[mode]}")

    def show_control_ui(self):
        window = self._ensure_window()
        window.showNormal()
        window.raise_()
        window.activateWindow()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_control_ui()

    @staticmethod
    def _startup_command() -> str:
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable).resolve()}"'
        script = Path(__file__).resolve()
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        interpreter = pythonw if pythonw.exists() else Path(sys.executable)
        return f'"{interpreter.resolve()}" "{script}"'

    @staticmethod
    def _read_startup_command() -> str | None:
        if sys.platform != "win32":
            return None
        try:
            import winreg
            path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
            return str(value)
        except OSError:
            return None

    @staticmethod
    def _startup_task_exists() -> bool:
        if sys.platform != "win32":
            return False
        result = subprocess.run(
            ["schtasks.exe", "/Query", "/TN", STARTUP_TASK_NAME],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0

    @staticmethod
    def _remove_legacy_run_entry():
        """Remove the old non-elevated registry startup entry, if present."""
        if sys.platform != "win32":
            return
        try:
            import winreg
            path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        except OSError:
            pass

    def _create_startup_task(self):
        result = subprocess.run(
            [
                "schtasks.exe", "/Create",
                "/TN", STARTUP_TASK_NAME,
                "/TR", self._startup_command(),
                "/SC", "ONLOGON",
                "/RL", "HIGHEST",
                "/F",
            ],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "未知错误").strip()
            raise OSError(f"无法创建最高权限开机任务：{detail}")

    @staticmethod
    def _delete_startup_task():
        result = subprocess.run(
            ["schtasks.exe", "/Delete", "/TN", STARTUP_TASK_NAME, "/F"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        # 1 commonly means the task did not exist, which is already disabled.
        if result.returncode not in (0, 1):
            detail = (result.stderr or result.stdout or "未知错误").strip()
            raise OSError(f"无法删除开机任务：{detail}")

    def _sync_startup_action(self):
        if sys.platform == "win32":
            enabled = self._startup_task_exists()
            # Migrate the previous non-elevated Run entry while this process is
            # elevated. If migration fails, keep the old checked state visible.
            legacy_enabled = self._read_startup_command() == self._startup_command()
            if legacy_enabled and not enabled:
                try:
                    self._create_startup_task()
                    self._remove_legacy_run_entry()
                    enabled = True
                except OSError:
                    enabled = True
            self.startup_action.setChecked(enabled)
            self.startup_action.setEnabled(True)
        else:
            self.startup_action.setChecked(False)
            self.startup_action.setEnabled(False)
            self.startup_action.setToolTip("当前示例仅实现 Windows 开机自启")

    def _set_startup_enabled(self, enabled: bool):
        if sys.platform != "win32":
            self.startup_action.setChecked(False)
            return
        try:
            if enabled:
                self._create_startup_task()
                self._remove_legacy_run_entry()
            else:
                self._delete_startup_task()
                self._remove_legacy_run_entry()
        except OSError as exc:
            self.startup_action.setChecked(not enabled)
            QMessageBox.warning(None, "设置失败", f"无法修改开机自启设置：\n{exc}")

    def _system_is_dark(self, color_scheme=None) -> bool:
        if color_scheme is None:
            color_scheme = QApplication.styleHints().colorScheme()
        if color_scheme == Qt.ColorScheme.Dark:
            return True
        if color_scheme == Qt.ColorScheme.Light:
            return False
        if sys.platform == "win32":
            try:
                import winreg
                path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                    apps_use_light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return not bool(apps_use_light)
            except OSError:
                pass
        return QApplication.palette().window().color().lightness() < 128

    def _apply_menu_theme(self, color_scheme=None):
        if self._system_is_dark(color_scheme):
            self.menu.setStyleSheet("""
                QMenu { background:#111827; color:#e5edf8; border:1px solid #344258;
                        border-radius:8px; padding:7px; font:10pt 'Segoe UI','Microsoft YaHei UI'; }
                QMenu::item { padding:8px 30px 8px 26px; border-radius:5px; }
                QMenu::item:selected { background:#213149; color:#ffffff; }
                QMenu::item:disabled { color:#75839a; font-weight:600; }
                QMenu::indicator { width:14px; height:14px; }
                QMenu::indicator:checked { background:#55d8df; border:2px solid #baf8fb; border-radius:7px; }
                QMenu::separator { height:1px; background:#2a374b; margin:6px 8px; }
            """)
        else:
            self.menu.setStyleSheet("""
                QMenu { background:#ffffff; color:#172033; border:1px solid #cbd5e1;
                        border-radius:8px; padding:7px; font:10pt 'Segoe UI','Microsoft YaHei UI'; }
                QMenu::item { padding:8px 30px 8px 26px; border-radius:5px; }
                QMenu::item:selected { background:#e1f5f7; color:#0f4450; }
                QMenu::item:disabled { color:#718096; font-weight:600; }
                QMenu::indicator { width:14px; height:14px; }
                QMenu::indicator:checked { background:#16aab5; border:2px solid #d2f8fa; border-radius:7px; }
                QMenu::separator { height:1px; background:#d8e0ea; margin:6px 8px; }
            """)

    def quit(self):
        self.background_timer.stop()
        unregister_tray_icon(self.tray)
        self.tray.hide()
        self.app.quit()


# 主要初始化程序
def main() -> int:
    try:
        if not ensure_running_as_admin(__file__):
            return 0
    except OSError as exc:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(exc), "无法以管理员身份启动", 0x10)
        return 1

    global MODE_LABELS

    TMode.init()
    MODE_LABELS=MODE_LABELS = {
    "balanced": Tconfig.CONFIG_LOAD["Languages"]["balanced"],
    "fixed": Tconfig.CONFIG_LOAD["Languages"]["fixed"],
    "custom": Tconfig.CONFIG_LOAD["Languages"]["custom"],
    "g_mode": Tconfig.CONFIG_LOAD["Languages"]["g_mode"],
    }

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(SETTINGS_ORGANIZATION)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "启动失败", "当前系统未提供可用的系统托盘。")
        return 1

    controller = FanTrayController(app)
    controller.show()
    # Keep a Python reference alive for the entire Qt event loop.
    app._fan_tray_controller = controller
    return app.exec()
