from collections import deque
from dataclasses import dataclass
from typing import Any

from Backend import AWCCThermal
from Backend.AWCCThermal import AWCCThermal, NoAWCCWMIClass, CannotInstAWCCWMI
from Backend.TAlert import toast_message
from config import Tconfig


@dataclass
class CurvePoint:
    temperature: int
    speed: int

def getMode() -> str:
    return Tconfig.CONFIG_LOAD["CurrentMode"]

def getReserveMode() -> str:
    return Tconfig.CONFIG_LOAD["ReserveMode"]

def getTemperature(device: str) -> int:
    if device == 'gpu':
        return awcc.getFanRelatedTemp(awcc.GPUFanIdx)
    elif device == 'cpu':
        return awcc.getFanRelatedTemp(awcc.CPUFanIdx)
    else:
        return 100

def getSpeed(device: str) -> int:
    if device == 'gpu':
        return awcc.getFanRPM(awcc.GPUFanIdx)
    elif device == 'cpu':
        return awcc.getFanRPM(awcc.CPUFanIdx)
    else:
        return 0

def getFixedTemperature(device: str) -> int:
    if device == 'gpu':
        return Tconfig.CONFIG_LOAD["Fixed"]["GPU"]
    elif device == 'cpu':
        return Tconfig.CONFIG_LOAD["Fixed"]["CPU"]
    else:
        return 100

def getCustomTemperatureList(device: str) -> Any | None:
    if device == 'gpu':
        return Tconfig.CONFIG_LOAD["Custom"]["GPU"]
    elif device == 'cpu':
        return Tconfig.CONFIG_LOAD["Custom"]["CPU"]
    return None

def getCustomSpeed(device: str,temperature) -> int:
    points = sorted((float(t), float(s)) for t, s in list(getCustomTemperatureList(device)))
    if not points:
        raise ValueError("风扇曲线不能为空")
    if temperature <= points[0][0]:
        return round(max(0, min(100, points[0][1])))
    if temperature >= points[-1][0]:
        return round(max(0, min(100, points[-1][1])))
    for (t0, s0), (t1, s1) in zip(points, points[1:]):
        if t0 <= temperature <= t1:
            if t1 == t0:
                speed = max(s0, s1)
            else:
                speed = s0 + (temperature - t0) / (t1 - t0) * (s1 - s0)
            return round(max(0, min(100, speed)))
    raise RuntimeError("无法从风扇曲线计算转速")

SAMPLE_COUNT=5
cpu_temperatures = deque(maxlen=SAMPLE_COUNT)
gpu_temperatures = deque(maxlen=SAMPLE_COUNT)

def on_custom_trigger():
    cpu_temperatures.append(getTemperature('cpu'))
    gpu_temperatures.append(getTemperature('gpu'))
    if len(cpu_temperatures) == SAMPLE_COUNT & len(gpu_temperatures) == SAMPLE_COUNT:
        cpu_avg_temp = sum(cpu_temperatures) / SAMPLE_COUNT
        gpu_avg_temp = sum(gpu_temperatures) / SAMPLE_COUNT
        cpu_target_speed = getCustomSpeed('cpu',cpu_avg_temp)
        gpu_target_speed = getCustomSpeed('gpu',gpu_avg_temp)
        awcc.setFanSpeed(awcc.CPUFanIdx, getCustomSpeed('cpu', cpu_target_speed))
        awcc.setFanSpeed(awcc.GPUFanIdx, getCustomSpeed('gpu', gpu_target_speed))
        print(f"[DEBUG] CustomTrigger CPUAvgT {cpu_avg_temp}° to {cpu_target_speed}% / GPUAvgT {gpu_avg_temp}° to {gpu_target_speed}%")

def on_mode_changed_hotkey():
    mode=getMode()
    if mode == 'g_mode':
        reserveMod=getReserveMode()
        if reserveMod == 'null':
            reserveMod='balanced'
        on_mode_changed(reserveMod, True,False)
        toast_message(Tconfig.CONFIG_LOAD["Languages"]["notice_hotkey_g_mode_title"], Tconfig.CONFIG_LOAD["Languages"]["notice_hotkey_g_mode_off_message"],
                      rmode=Tconfig.CONFIG_LOAD["Languages"][mode], icon="information")
    else:
        Tconfig.change_reserve(mode)
        on_mode_changed('g_mode', True,False)
        toast_message(Tconfig.CONFIG_LOAD["Languages"]["notice_hotkey_g_mode_title"],
                      Tconfig.CONFIG_LOAD["Languages"]["notice_hotkey_g_mode_on_message"],
                      rmode=Tconfig.CONFIG_LOAD["Languages"][mode], icon="information")

def on_mode_changed(mode: str,wr: bool,notice: bool):
    if wr:
        Tconfig.change_mode(mode)
        if notice: toast_message(Tconfig.CONFIG_LOAD["Languages"]["notice_title"],Tconfig.CONFIG_LOAD["Languages"]["notice_mode"],cmode=Tconfig.CONFIG_LOAD["Languages"][mode],icon="information",)
        print(f"[DEBUG] mode changed: {mode}")
    if mode == 'fixed':
        awcc.setMode(awcc.Mode['fixed'])
        awcc.setFanSpeed(awcc.CPUFanIdx, getFixedTemperature('cpu'))
        awcc.setFanSpeed(awcc.GPUFanIdx, getFixedTemperature('gpu'))
    elif mode == 'custom':
        awcc.setMode(awcc.Mode['custom'])
        SAMPLE_COUNT = Tconfig.CONFIG_LOAD["Custom"]["Count"]
        # 第一时间先使用启动时的瞬时温度转速
        awcc.setFanSpeed(awcc.CPUFanIdx, getCustomSpeed('cpu',awcc.getFanRelatedTemp(awcc.CPUFanIdx)))
        awcc.setFanSpeed(awcc.GPUFanIdx, getCustomSpeed('gpu',awcc.getFanRelatedTemp(awcc.GPUFanIdx)))
    elif mode == 'g_mode':
        awcc.setMode(awcc.Mode['g_mode'])
    else:
        awcc.setMode(awcc.Mode['balanced']) # 准确来说是对应mode == 'balanced'，此处为了防止手动修改配置文件导致异常

def on_fixed_speed_changed(device: str, speed: int):
    Tconfig.change_fixed(device, speed)
    if device == 'gpu':
        awcc.setFanSpeed(awcc.GPUFanIdx,speed)
    elif device == 'cpu':
        awcc.setFanSpeed(awcc.CPUFanIdx,speed)
    print(f"[DEBUG] fixed speed: {device} -> {speed}%")

def on_curve_changed(device: str, points: list[tuple[int, int]]):
    Tconfig.change_custom(device, points)

    print(f"[DEBUG] curve updated: {device} -> {points}")

def init():
    global awcc
    try:
        awcc = AWCCThermal()
    except NoAWCCWMIClass:
        # errorExit("系统中未找到AWCC WMI","可能未安装某些驱动程序或系统不受支持")
        print("[ERROR] 系统中未找到AWCC WMI,可能未安装某些驱动程序或系统不受支持")
    except CannotInstAWCCWMI:
        # errorExit("无法初始化AWCC WMI","请确保以管理员身份运行")
        print("[ERROR] 无法初始化AWCC WMI,请确保以管理员身份运行")
    mode=getMode()
    if mode== 'balanced':
        on_mode_changed('balanced', False,False)
    elif mode == 'fixed':
        on_mode_changed('fixed', False,False)
    elif mode == 'custom':
        on_mode_changed('custom', False,False)
    elif mode == 'g_mode':
        on_mode_changed('g_mode', False,False)
    print(f"[DEBUG] init: {mode}")