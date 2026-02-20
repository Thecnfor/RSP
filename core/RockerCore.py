"""
火箭控制内核模块
"""

import asyncio
from utility import Utils, Rlogger


class RockerCore(Utils):
    """
    RockerCore 代表一个实体火箭。
    每个实例对应一个 kRPC vessel 对象，并维护其自身的控制逻辑。
    """

    def __init__(self, vessel):
        super().__init__(vessel)
        self.vessel_id = vessel.id
        self.name = vessel.name
        self.is_active = True

    async def run_auto_logic(self):
        """
        每枚火箭独立的自动化逻辑：采用异步并发监测
        """
        Rlogger(f"Rocker-{self.name}").info("启动自动控制逻辑...")
        try:
            while self.is_active:
                # 1. 监测整流罩抛离
                await self.jettison()
                
                # 2. 自动展开载荷 (太阳能板/天线)
                await self.auto_deploy()
                
                # 3. 自动展开着陆架
                await self.auto_land()
                
                await asyncio.sleep(1)
        except Exception as e:
            Rlogger(f"Rocker-{self.name}").error(f"控制逻辑异常: {e}")
            self.is_active = False
