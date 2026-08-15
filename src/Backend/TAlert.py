"""Windows Toast messages delivered through the application's tray icon."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

try:
    from PySide6.QtWidgets import QSystemTrayIcon
except ImportError:
    print('PySide6 not found. Please install it and try again.')
    # from PyQt6.QtWidgets import QSystemTrayIcon


_tray_icon: QSystemTrayIcon | None = None


def register_tray_icon(tray_icon: QSystemTrayIcon) -> None:
    """Register the tray icon used to deliver subsequent Toast messages."""
    global _tray_icon
    if not isinstance(tray_icon, QSystemTrayIcon):
        raise TypeError("tray_icon 必须是 QSystemTrayIcon 实例")
    _tray_icon = tray_icon


def unregister_tray_icon(tray_icon: QSystemTrayIcon | None = None) -> None:
    global _tray_icon
    if tray_icon is None or tray_icon is _tray_icon:
        _tray_icon = None


def format_text(template: str, /, *values: Any, **variables: Any) -> str:
    """Format text using ``{name}``, ``{0}`` and Python format specifications."""
    try:
        return str(template).format(*values, **variables)
    except (KeyError, IndexError, ValueError, AttributeError) as exc:
        raise ValueError(f"通知文本格式化失败：{exc}") from exc


def _message_icon(icon: str | QSystemTrayIcon.MessageIcon):
    if isinstance(icon, QSystemTrayIcon.MessageIcon):
        return icon
    icons = {
        "none": QSystemTrayIcon.MessageIcon.NoIcon,
        "information": QSystemTrayIcon.MessageIcon.Information,
        "info": QSystemTrayIcon.MessageIcon.Information,
        "warning": QSystemTrayIcon.MessageIcon.Warning,
        "critical": QSystemTrayIcon.MessageIcon.Critical,
        "error": QSystemTrayIcon.MessageIcon.Critical,
    }
    try:
        return icons[str(icon).lower()]
    except KeyError as exc:
        raise ValueError("icon 必须是 none、information、warning 或 critical") from exc


def toast_message(
    title: str,
    message: str,
    /,
    *values: Any,
    tray_icon: QSystemTrayIcon | None = None,
    icon: str | QSystemTrayIcon.MessageIcon = "information",
    duration_ms: int = 5000,
    **variables: Any,
) -> None:
    """Send a Windows Toast message through the visible system tray icon."""
    target = tray_icon or _tray_icon
    if target is None:
        raise RuntimeError("尚未注册托盘图标，请先调用 register_tray_icon()")
    if not target.isVisible():
        raise RuntimeError("托盘图标尚未显示，无法发送 Toast message")
    if not QSystemTrayIcon.supportsMessages():
        raise RuntimeError("当前系统托盘不支持 Toast message")

    target.showMessage(
        format_text(title, *values, **variables),
        format_text(message, *values, **variables),
        _message_icon(icon),
        max(0, int(duration_ms)),
    )


show_notification = toast_message
notifyf = toast_message


def show_notification_from_dict(
    title: str,
    message: str,
    variables: Mapping[str, Any],
    /,
    **options: Any,
) -> None:
    toast_message(title, message, **options, **dict(variables))


__all__ = [
    "format_text", "notifyf", "register_tray_icon", "show_notification",
    "show_notification_from_dict", "toast_message", "unregister_tray_icon",
]
