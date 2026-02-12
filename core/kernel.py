"""
火箭控制内核模块
"""

import multiprocessing as mp
import time
from utility import Utils, Rlogger, config
from .orbit import OrbitKernel
import krpc
import asyncio


class Kernel(Utils):
    def __init__(self, vessel: str):
        self._process = mp.Process(target=self.Core, daemon=True)
        self._process.start()
        self.Kernel = krpc.connect(name=vessel)
        super().__init__(self.Kernel.space_center.active_vessel)
        self.Orbit = OrbitKernel(vessel)

        Rlogger("Kernel").info(f"火箭控制内核初始化(PID: {self._process.pid})")

    @property
    def info(self):
        return {"vessel": self.Kernel.space_center.active_vessel}

    def Core(self):
        Rlogger("Kernel.Worker").info("火箭控制内核运行")
        async def run():
            try:
                while True:
                    await asyncio.sleep(1)
            except Exception as e:
                Rlogger("Kernel.Worker").error(f"火箭控制内核运行异常: {e}")
        asyncio.run(run())

    def pool(self):
        return self.Kernel
