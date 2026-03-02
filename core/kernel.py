"""
火箭控制内核模块
"""

import multiprocessing as mp
import time
import krpc
import asyncio

from utility import Rlogger
from .orbit import OrbitCalc
from .RockerCore import RockerCore


class Kernel:
    """
    火箭控制内核 - 负责控制子进程的生命周期及多火箭实例分配
    """

    def __init__(self, data_queue: mp.Queue, cmd_queue: mp.Queue, ai_req_queue: mp.Queue = None, ai_res_queue: mp.Queue = None):
        self.data_queue = data_queue
        self.cmd_queue = cmd_queue
        self.ai_req_queue = ai_req_queue
        self.ai_res_queue = ai_res_queue
        
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

        Rlogger("Kernel.Worker").info("内核就绪，开始监测飞行器状态")

        async with asyncio.TaskGroup() as tg:
            # 1. 自动监测新产生的飞行器
            tg.create_task(self._watch_vessels(conn, tg))
            # 2. 处理来自 UI 的指令
            tg.create_task(self._handle_commands())
            # 3. 持续推送遥测数据
            tg.create_task(self._stream_telemetry(conn))
            # 4. 处理 AI 响应分发 (如果使用了 AI 服务)
            if self.ai_res_queue:
                tg.create_task(self._dispatch_ai_responses())

    async def _dispatch_ai_responses(self):
        """分发 AI 计算结果到对应的 RockerCore"""
        while True:
            try:
                if not self.ai_res_queue.empty():
                    res = self.ai_res_queue.get_nowait()
                    # 假设 req_id 格式为 "vessel_id:timestamp"
                    req_id = res.get("id")
                    if req_id and ":" in req_id:
                        vid = req_id.split(":")[0]
                        if vid in self.vessels:
                            # 将结果推送到 RockerCore 的内部队列或直接调用回调
                            # 这里简单起见，假设 RockerCore 有个 handle_ai_response 方法
                            # 或者 RockerCore 使用了 asyncio.Future 等待结果
                            # 为简单起见，我们暂不实现复杂的 Future 映射，
                            # 而是让 RockerCore 自行轮询或者通过 Kernel 分发
                            # 更好的方式是 RockerCore 传入一个回调或者 Queue
                            self.vessels[vid].on_ai_response(res)
            except:
                pass
            await asyncio.sleep(0.01)

    async def _watch_vessels(self, conn, tg):
        """动态维护飞行器列表"""
        while True:
            try:
                active_vessel = conn.space_center.active_vessel
                all_vessels = conn.space_center.vessels
                
                for v in all_vessels:
                    if v.id in self.vessels:
                        continue
                        
                    v_type = v.type
                    v_name = v.name
                    
                    is_valid_type = v_type in [
                        conn.space_center.VesselType.ship,
                        conn.space_center.VesselType.probe,
                        conn.space_center.VesselType.lander,
                        conn.space_center.VesselType.relay
                    ]
                    
                    is_target_name = "Booster" in v_name or "Stage" in v_name or "RSP" in v_name
                    
                    if (is_valid_type or is_target_name) and v.orbit.body == active_vessel.orbit.body:
                        try:
                            # 传递 AI 队列
                            new_rocker = RockerCore(v, self.ai_req_queue)
                            self.vessels[v.id] = new_rocker
                            tg.create_task(new_rocker.run_auto_logic())
                            Rlogger("Kernel.Worker").info(
                                f"监测到新实体: {new_rocker.name} ({v.id}) Type: {v_type}"
                            )
                        except Exception as e:
                            Rlogger("Kernel.Worker").warning(f"初始化实体失败 {v_name}: {e}")

                dead_ids = [vid for vid, r in self.vessels.items() if not r.is_active]
                for vid in dead_ids:
                    del self.vessels[vid]
                    Rlogger("Kernel.Worker").info(f"清理失效实体: {vid}")

            except Exception as e:
                 Rlogger("Kernel.Worker").error(f"监测循环异常: {e}")

            await asyncio.sleep(2)

    async def _handle_commands(self):
        """处理来自 Dashboard 的指令"""
        while True:
            if not self.cmd_queue.empty():
                try:
                    cmd = self.cmd_queue.get_nowait()
                    Rlogger("Kernel.Worker").debug(f"收到指令: {cmd}")
                except:
                    pass
            await asyncio.sleep(0.1)

    async def _stream_telemetry(self, conn):
        """采集并发送遥测数据"""
        while True:
            telemetry = {}
            current_vessels = list(self.vessels.items())
            
            for vid, rocker in current_vessels:
                try:
                    if not rocker.is_active: 
                        continue
                    
                    # 简单的频率控制，每5次循环发送一次完整数据?
                    # 这里保持简单
                    flight = rocker.vessel.flight(rocker.vessel.surface_reference_frame)
                    telemetry[vid] = {
                        "name": rocker.name,
                        "mode": rocker.mission_mode,
                        "state": rocker.state,
                        "alt": flight.mean_altitude,
                        "spd": flight.speed,
                        "v_spd": flight.vertical_speed,
                        "g": flight.g_force,
                    }
                except:
                    continue

            if telemetry:
                self.data_queue.put(telemetry)

            await asyncio.sleep(0.2)
