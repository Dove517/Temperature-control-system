from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path


def is_running_as_admin() -> bool:

    if sys.platform != "win32":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def ensure_running_as_admin(entry_file: str | Path) -> bool:

    if sys.platform != "win32" or is_running_as_admin():
        return True

    entry_path = Path(entry_file).resolve()
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        arguments = sys.argv[1:]
        working_directory = executable.parent
    else:
        python_path = Path(sys.executable).resolve()
        pythonw_path = python_path.with_name("pythonw.exe")
        executable = pythonw_path if pythonw_path.exists() else python_path
        arguments = [str(entry_path), *sys.argv[1:]]
        working_directory = entry_path.parent

    parameters = subprocess.list2cmdline(arguments)
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        str(executable),
        parameters,
        str(working_directory),
        1,
    )
    if result <= 32:
        raise OSError(int(result), "管理员权限启动被取消或失败")
    return False