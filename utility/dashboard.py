"""
仪表盘模块
"""

import time
import asyncio
from .log import Rlogger


class Dashboard:
    def __init__(self, vessel):
        # 1. 确定并保存默认火箭
        self._default_vessel = vessel

        # 2. 初始化内部变量 (先设为 None)
        self._vessel = None
        self.flight = None

        # 3. 使用 setter 触发初始化绑定
        self.vessel = self._default_vessel

        print("\033[2J\033[H", end="", flush=True)
        self.lines = []

    @property
    def vessel(self):
        """获取当前监控的火箭对象"""
        return self._vessel

    @vessel.setter
    def vessel(self, new_vessel):
        """
        核心逻辑：切换火箭时，自动重新绑定 flight 对象。
        """
        if new_vessel is None:
            """快速切回初始化时的默认火箭"""
            Rlogger("Dashboard").info("正在恢复默认监控目标...")
            self.vessel = self._default_vessel
            return

        self._vessel = new_vessel
        # 自动更新飞行参考系为新火箭的地表参考系
        self.flight = self._vessel.flight(self._vessel.surface_reference_frame)

        name = getattr(new_vessel, "name", "未知飞行器")
        Rlogger("Dashboard").info(f"监控目标已切换至: {name}")

    def switch_mode(self, use_orbit=False):
        """切换显示模式：地表 vs 轨道"""
        if not self.vessel:
            return

        if use_orbit:
            # 切换到轨道参考系（非旋转参考系）
            self.flight = self.vessel.flight(
                self.vessel.orbit.body.non_rotating_reference_frame
            )
            Rlogger("Dashboard").info("切换至轨道遥测模式")
        else:
            # 切换回地表参考系
            self.flight = self.vessel.flight(self.vessel.surface_reference_frame)
            Rlogger("Dashboard").info("切换至地表遥测模式")

    def data(self):
        """获取实时遥测数据字典"""
        return {
            "海拔高度 (Alt)": f"{self.flight.mean_altitude:>10.2f} m",
            "飞行速度 (Spd)": f"{self.flight.speed:>10.2f} m/s",
            "重力载荷 (G-F)": f"{self.flight.g_force:>10.2f} G",
            "大气密度 (Rho)": f"{self.flight.atmosphere_density:>10.4f} kg/m³",
        }

    def board(self, telemetry_data):
        """渲染单帧仪表盘，并保留主线程日志空间"""
        self.lines = []
        self.lines.append("=" * 40)
        self.lines.append(f"{f'KSP 任务控制中心 - {self.vessel}实时遥测':^40}")
        self.lines.append("=" * 40)

        for label, value in telemetry_data.items():
            self.lines.append(f"{label:<20}: {value}\033[K")

        self.lines.append("=" * 40)
        self.lines.append(
            f"系统状态: 运行中 | 刷新时间: {time.strftime('%H:%M:%S')}\033[K"
        )
        self.lines.append("-" * 40 + "\033[K")  # 分割线，下方留给主线程日志

        # 使用 \033[H 将光标移回左上角，但不清屏 (不使用 \033[2J)
        output = "\033[H" + "\n".join(self.lines)
        print(output, flush=True)

    async def watch(self):
        """持续监控并更新仪表盘（适合在副线程运行）"""
        try:
            while True:
                current_data = self.data()
                self.board(current_data)
                await asyncio.sleep(0.1)
        except Exception as e:
            Rlogger("Dashboard").error(f"仪表盘监控异常: {e}")
