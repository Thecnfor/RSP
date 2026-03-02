"""
火箭控制内核模块
"""

import asyncio
import math
import time
from utility import Utils, Rlogger
from .orbit import OrbitCalc
from .ai_interface import AIController

class RockerCore(Utils):
    """
    RockerCore 代表一个实体火箭。
    每个实例对应一个 kRPC vessel 对象，并维护其自身的控制逻辑。
    """

    def __init__(self, vessel, ai_req_queue=None):
        super().__init__(vessel)
        self.vessel_id = vessel.id
        self.name = vessel.name
        self.is_active = True
        
        # AI 相关
        self.ai = AIController() # 本地 AI 控制器 (兜底)
        self.ai_req_queue = ai_req_queue # 远程 AI 请求队列
        self.ai_control_input = None # 最新收到的 AI 控制指令
        self.last_ai_req_time = 0
        
        # 状态标记
        self.state = "IDLE" 
        self.mission_mode = "DEFAULT" # DEFAULT, RECOVERY, ORBIT
        
        # 自动推断任务模式
        self._infer_mission_mode()

    def _infer_mission_mode(self):
        """根据飞船名称或部件推断任务模式"""
        name_lower = self.name.lower()
        if "booster" in name_lower or "stage" in name_lower:
            self.mission_mode = "RECOVERY"
            Rlogger(f"Rocker-{self.name}").info("识别为助推器/回收级，进入回收模式")
        elif "debris" in name_lower:
             self.mission_mode = "DEBRIS"
        else:
            self.mission_mode = "ORBIT" # 默认为入轨级

    def on_ai_response(self, res):
        """处理来自 Kernel 分发的 AI 响应"""
        # res: {"id": "vid:ts", "action": [...], "duration": ...}
        action = res.get("action")
        if action:
            self.ai_control_input = action
            # Rlogger(f"Rocker-{self.name}").debug(f"更新 AI 控制指令: {action}")

    async def run_auto_logic(self):
        """
        每枚火箭独立的自动化逻辑：采用异步并发监测
        """
        Rlogger(f"Rocker-{self.name}").info(f"启动自动控制逻辑 (模式: {self.mission_mode})...")
        try:
            while self.is_active:
                # 0. 状态更新
                self._update_state()

                # 1. 核心任务逻辑
                if self.mission_mode == "RECOVERY":
                    await self._run_recovery_loop()
                else:
                    await self._run_default_loop()
                
                # 2. 通用辅助逻辑 (整流罩/展开)
                if self.mission_mode != "DEBRIS":
                    await self.jettison()
                    await self.auto_deploy()

                await asyncio.sleep(0.1) # 提高控制频率
        except Exception as e:
            Rlogger(f"Rocker-{self.name}").error(f"控制逻辑异常: {e}")
            self.is_active = False

    def _update_state(self):
        """更新当前飞行状态"""
        flight = self.vessel.flight()
        alt = flight.mean_altitude
        
        if self.vessel.situation == self.vessel.situation.landed:
            self.state = "LANDED"
        elif self.vessel.situation == self.vessel.situation.splashed:
            self.state = "SPLASHED"
        elif alt > 140000:
            self.state = "SPACE"
        elif flight.vertical_speed < -10:
            self.state = "DESCENT"
        elif flight.vertical_speed > 10:
            self.state = "ASCENT"

    async def _request_ai_update(self, flight):
        """发送 AI 请求"""
        now = time.time()
        # 限制请求频率，例如每 0.5 秒一次
        if now - self.last_ai_req_time < 0.5:
            return

        state = {
            'altitude': flight.mean_altitude,
            'vertical_speed': flight.vertical_speed,
            'horizontal_speed': flight.horizontal_speed,
            'mass': self.vessel.mass,
            'mode': self.mission_mode
        }

        if self.ai_req_queue:
            req_id = f"{self.vessel_id}:{now}"
            self.ai_req_queue.put({"id": req_id, "state": state})
        else:
            # 本地计算
            self.ai_control_input = self.ai.predict(state)
        
        self.last_ai_req_time = now

    async def _run_recovery_loop(self):
        """助推器回收逻辑"""
        flight = self.vessel.flight()
        
        if self.state in ["LANDED", "SPLASHED"]:
            if self.is_active:
                Rlogger(f"Rocker-{self.name}").info("回收成功: 已着陆/溅落")
                self.vessel.control.throttle = 0
                self.is_active = False 
            return

        if self.state == "DESCENT":
            # 1. 请求 AI 更新
            await self._request_ai_update(flight)
            
            # 2. 应用 AI 控制 (如果可用)
            if self.ai_control_input:
                # 假设 action 格式: [throttle, pitch, yaw, roll]
                # 这里仅作示例，实际需要映射到 kRPC control
                pass

            # 3. 姿态控制 (逆行) - 兜底逻辑
            try:
                # 仅在大气层外或高空使用 RCS/SAS
                if flight.mean_altitude > 30000:
                    self.vessel.auto_pilot.engage()
                    # 简化的逆行向量
                    self.vessel.auto_pilot.target_direction = tuple(-x for x in flight.velocity)
                elif flight.mean_altitude < 30000:
                     # 大气层内主要靠气动稳定 (Grid fins)
                     # 如果有 SAS，设置为 Retrograde
                     try:
                         self.vessel.control.sas = True
                         self.vessel.control.sas_mode = self.vessel.control.sas_mode.retrograde
                     except:
                         pass
            except:
                pass

            # 4. 自杀燃烧计算 (最高优先级，覆盖 AI 油门)
            if flight.mean_altitude < 20000: 
                surface_gravity = self.vessel.orbit.body.surface_gravity
                available_thrust = self.vessel.available_thrust
                # 考虑大气阻力影响，available_thrust 在 RSS 中随高度变化
                # 这里取当前推力 (如果引擎开启) 或最大推力
                
                burn_height = OrbitCalc.suicide_burn_height(
                    flight.vertical_speed, 
                    flight.horizontal_speed, 
                    available_thrust, 
                    self.vessel.mass, 
                    surface_gravity
                )
                
                radar_alt = flight.surface_altitude
                
                # 简单的开关控制 (Bang-Bang Control)
                if radar_alt < burn_height * 1.1:
                    self.vessel.control.throttle = 1.0
                    if radar_alt < burn_height * 1.05:
                         Rlogger(f"Rocker-{self.name}").debug(f"着陆点火! Alt: {radar_alt:.0f}")
                else:
                    # 在着陆点火前保持低推力或关闭
                    # 如果 AI 建议了油门，使用 AI 的，否则 0
                    self.vessel.control.throttle = 0.0
            
            # 5. 自动展开着陆腿
            await self.auto_land()

    async def _run_default_loop(self):
        """默认/入轨逻辑"""
        pass

    async def auto_deploy(self):
        """自动展开载荷 (太阳能/天线)"""
        flight = self.vessel.flight()
        if flight.mean_altitude > 70000 and not self.isDeployed:
             self.deploySwap() 

    async def auto_land(self):
        """自动展开着陆架"""
        flight = self.vessel.flight(self.vessel.orbit.body.reference_frame)
        if flight.surface_altitude < 2000 and flight.vertical_speed < -1 and not self.isLanded:
             self.landSwap() 
