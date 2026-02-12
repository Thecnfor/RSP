"""
轨道计算内核模块
"""

import multiprocessing as mp
import time
from utility import Rlogger, config
import krpc


class OrbitKernel:
    """
    轨道计算内核 - 采用多进程架构处理高负载数学运算
    """

    def __init__(self, vessel: str):
        # 1. 实例化时立即启动一个常驻子进程跑主循环
        self._process = mp.Process(target=self._main_loop, daemon=True)
        self._process.start()
        self.Orbit = krpc.connect(name=f"OrbitKernel.{vessel}")
        Rlogger("OrbitKernel").info(
            f"轨道计算内核已在独立进程中启动 (PID: {self._process.pid})"
        )

    def _main_loop(self):
        """
        子进程中运行的常驻逻辑
        """
        Rlogger("OrbitKernel.Worker").info("子进程常驻计算逻辑已就绪")
        try:
            while True:
                # 这里可以放置需要持续计算的逻辑（如轨道预测、落点计算等）
                # 注意：如果子进程需要访问 KSP 数据，建议在此进程内重新建立 krpc 连接
                time.sleep(5)
        except Exception as e:
            Rlogger("OrbitKernel.Worker").error(f"子进程发生异常: {e}")

    def create_pool(self, size=None):
        """
        创建进程池，用于大规模并行计算（如多轨道方案并行搜寻）
        """
        pool_size = size or mp.cpu_count()
        Rlogger("OrbitKernel").info(f"正在创建计算进程池，规模: {pool_size}")
        return mp.Pool(processes=pool_size)
