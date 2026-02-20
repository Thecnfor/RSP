"""
火箭控制内核模块
"""

import multiprocessing as mp
import time
import krpc
import asyncio

from utility import Rlogger
from .Orbit import OrbitKernel
from .RockerCore import RockerCore


class Kernel:
    """
    火箭控制内核 - 负责控制子进程的生命周期及多火箭实例分配
    """

    def __init__(self, data_queue: mp.Queue, cmd_queue: mp.Queue):
        self.data_queue = data_queue
        self.cmd_queue = cmd_queue
        self._process = mp.Process(target=self._run_worker, daemon=True)
        self._process.start()
        Rlogger("Kernel").info(f"控制内核进程已启动 (PID: {self._process.pid})")

    def _run_worker(self):
        """子进程入口"""
        asyncio.run(self._worker_loop())

    async def _worker_loop(self):
        """控制子进程的异步主循环"""
        Rlogger("Kernel.Worker").info("连接 kRPC 服务...")
        try:
            conn = krpc.connect(name="RSP_Kernel")
        except Exception as e:
            Rlogger("Kernel.Worker").error(f"kRPC 连接失败: {e}")
            return

        self.vessels = {}  # vessel_id -> RockerCore
        self.orbit_svc = OrbitKernel()

        Rlogger("Kernel.Worker").info("内核就绪，开始监测飞行器状态")

        async with asyncio.TaskGroup() as tg:
            # 1. 自动监测新产生的飞行器（如分级产生的碎片或新飞船）
            tg.create_task(self._watch_vessels(conn, tg))
            # 2. 处理来自 UI 的命令
            tg.create_task(self._handle_commands())
            # 3. 持续推送遥测数据
            tg.create_task(self._stream_telemetry(conn))

    async def _watch_vessels(self, conn, tg):
        """
        动态维护飞行器列表 - 蓝桥杯级优化：支持分级产生的碎片监测
        """
        while True:
            # 监测所有受控飞行器（不仅仅是当前活动的）
            all_vessels = conn.space_center.vessels
            for v in all_vessels:
                # 过滤掉已经失控或已经销毁的
                try:
                    if v.id not in self.vessels:
                        # 只有当它是真实的飞船（非碎片）或者我们特别感兴趣时才添加
                        # 这里简单处理：只要是新的且合法的 vessel 对象就添加
                        new_rocker = RockerCore(v)
                        self.vessels[v.id] = new_rocker
                        tg.create_task(new_rocker.run_auto_logic())
                        Rlogger("Kernel.Worker").info(
                            f"监测到新实体: {new_rocker.name} ({v.id})"
                        )
                except:
                    continue

            # 清理已经失效的 RockerCore 实例
            dead_ids = [vid for vid, r in self.vessels.items() if not r.is_active]
            for vid in dead_ids:
                del self.vessels[vid]
                Rlogger("Kernel.Worker").info(f"清理失效实体: {vid}")

            await asyncio.sleep(1)

    async def _handle_commands(self):
        """处理来自 Dashboard 的指令"""
        while True:
            if not self.cmd_queue.empty():
                cmd = self.cmd_queue.get()
                # 处理指令逻辑，例如：切换追踪、手动点火等
                Rlogger("Kernel.Worker").debug(f"收到指令: {cmd}")
            await asyncio.sleep(0.1)

    async def _stream_telemetry(self, conn):
        """采集并发送遥测数据"""
        while True:
            telemetry = {}
            for vid, rocker in self.vessels.items():
                try:
                    # 获取该火箭的遥测数据
                    # 这里的 flight 逻辑可以根据需要调整
                    flight = rocker.vessel.flight(rocker.vessel.surface_reference_frame)
                    telemetry[vid] = {
                        "name": rocker.name,
                        "alt": flight.mean_altitude,
                        "spd": flight.speed,
                        "g": flight.g_force,
                        "rho": flight.atmosphere_density,
                    }
                except:
                    continue

            if telemetry:
                self.data_queue.put(telemetry)

            await asyncio.sleep(0.1)
