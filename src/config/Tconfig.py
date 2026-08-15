import os
import sys
from pathlib import Path
import yaml

CONFIG_LOAD= None

def _application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

APP_DIR = _application_directory()
os.chdir(APP_DIR)
CONFIG_PATH = APP_DIR / "config.yaml"

def load_configuration():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def generate_configuration():
    data = {
        "Version": "1.0.0",
        "CurrentMode": "balanced",
        "ReserveMode": "null",
        "Refresh": 1000,
        "Fixed": {
            "CPU": 60,
            "GPU": 20
        },
        "Custom": {
            "Refresh": 1000,
            "Count": 5,
            "CPU": [(30, 25), (40, 40), (50, 50), (60, 60), (70, 70), (80, 80), (90, 100), (100, 100)],
            "GPU": [(30, 15), (40, 25), (50, 35), (60, 45), (70, 60), (80, 75), (90, 100), (100, 100)]
        },
        "Languages": {
            "balanced": "均衡模式",
            "balanced_description": "BALANCED",
            "g_mode": "G 模式",
            "g_mode_description": "FIXED SPEED",
            "fixed": "固定模式",
            "fixed_description": "FAN CURVE",
            "custom": "自定义模式",
            "custom_description": "MAX PERFORMANCE",
            "title": "温度控制系统 - Temperature control system",
            "Running": "运行中",
            "Stopped": "停转或故障",
            "notice_title": "Temperature control system",
            "notice_mode": "当前模式切换为{cmode}",
            "notice_hotkey_g_mode_title": "Temperature control system",
            "notice_hotkey_g_mode_on_message": "高性能模式启动",
            "notice_hotkey_g_mode_off_message": "高性能模式关闭，返回至{rmode}",
        }
    }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data,f,allow_unicode=True,sort_keys=False)

def init():
    global CONFIG_LOAD

    if not CONFIG_PATH.exists():
        generate_configuration()
        print(f"Configuration file does not exist; creating default configuration file: {CONFIG_PATH}")
    CONFIG_LOAD = load_configuration()
    print(f"Configuration file exists; loading configuration file: {CONFIG_PATH} {CONFIG_LOAD["Version"]}")

    """
    if not CONFIG_FILE.exists():
        generate_configuration()
        print(f"Configuration file does not exist; creating default configuration file: {CONFIG_FILE}")
    CONFIG_LOAD=load_configuration()
    print(f"Configuration file exists; loading configuration file: {CONFIG_FILE} {CONFIG_LOAD["Version"]}")
    """

def change_mode(mode):
    CONFIG_LOAD["CurrentMode"]=mode

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(CONFIG_LOAD,f,allow_unicode=True,sort_keys=False)

def change_fixed(device: str, speed: int):
    if device== 'cpu':
        CONFIG_LOAD["Fixed"]["CPU"]=speed
    else:
        CONFIG_LOAD["Fixed"]["GPU"]=speed

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(CONFIG_LOAD,f,allow_unicode=True,sort_keys=False)

def change_custom(device: str, points: list[tuple[int, int]]):
    if device== 'cpu':
        CONFIG_LOAD["Custom"]["CPU"]=points
    else:
        CONFIG_LOAD["Custom"]["GPU"]=points

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(CONFIG_LOAD,f,allow_unicode=True,sort_keys=False)

def change_reserve(reserveMode: str):
    CONFIG_LOAD["ReserveMode"]=reserveMode

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(CONFIG_LOAD,f,allow_unicode=True,sort_keys=False)