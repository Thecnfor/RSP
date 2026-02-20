"""
仪表盘模块
"""

import time
import asyncio
from .log import Rlogger


class Dashboard:
    """
    仪表盘系统 - 运行在主进程，通过 Queue 消费来自控制进程的遥测数据
    """

    def __init__(self, data_queue, cmd_queue):
        self.data_queue = data_queue
        self.cmd_queue = cmd_queue

        self.tracking_id = None  # 当前追踪的火箭 ID
        self.display_mode = "surface"  # surface | orbit

        # UI 渲染相关
        print("\033[2J\033[H", end="", flush=True)
        self.lines = []

    def switch_vessel(self, vessel_id):
        """发送指令切换追踪目标"""
        self.tracking_id = vessel_id
        Rlogger("Dashboard").info(f"UI 切换追踪目标至: {vessel_id}")

    def switch_mode(self, mode="surface"):
        """切换显示模式"""
        self.display_mode = mode
        Rlogger("Dashboard").info(f"UI 切换显示模式: {mode}")

    def render(self, all_telemetry):
        """渲染单帧界面"""
        if not all_telemetry:
            return

        # 如果没有指定追踪 ID，默认追踪第一个
        if self.tracking_id not in all_telemetry:
            self.tracking_id = next(iter(all_telemetry.keys()))

        data = all_telemetry[self.tracking_id]

        self.lines = []
        self.lines.append("=" * 50)
        self.lines.append(f"{f'KSP 任务控制中心 - {data['name']}':^50}")
        self.lines.append(
            f"{f'ID: {self.tracking_id} | 模式: {self.display_mode.upper()}':^50}"
        )
        self.lines.append("=" * 50)

        # 动态渲染可选数据项
        telemetry_items = {
            "海拔高度 (Alt)": f"{data['alt']:>12.2f} m",
            "飞行速度 (Spd)": f"{data['spd']:>12.2f} m/s",
            "重力载荷 (G-F)": f"{data['g']:>12.2f} G",
            "大气密度 (Rho)": f"{data['rho']:>12.4f} kg/m³",
        }

        for label, value in telemetry_items.items():
            self.lines.append(f" {label:<20}: {value}\033[K")

        self.lines.append("=" * 50)
        self.lines.append(
            f" 已发现火箭数量: {len(all_telemetry)} | 刷新: {time.strftime('%H:%M:%S')}\033[K"
        )
        self.lines.append("-" * 50 + "\033[K")

        output = "\033[H" + "\n".join(self.lines)
        print(output, flush=True)

    async def watch(self):
        """持续从队列获取数据并渲染"""
        Rlogger("Dashboard").info("UI 渲染循环启动...")
        try:
            while True:
                # 非阻塞获取最新数据
                latest_data = None
                while not self.data_queue.empty():
                    latest_data = self.data_queue.get_nowait()

                if latest_data:
                    self.render(latest_data)

                await asyncio.sleep(0.1)
        except Exception as e:
            Rlogger("Dashboard").error(f"UI 渲染异常: {e}")
            Rlogger("Dashboard").error(f"仪表盘监控异常: {e}")
