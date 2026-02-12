import asyncio
from utility import Rlogger, Dashboard
from core import Kernel

Core = Kernel("core")
Dashboard = Dashboard()


async def main():
    # 逻辑调整：先监测抛离，抛离后再部署
    async with asyncio.TaskGroup() as tg:
        # 保持仪表盘持续运行
        tg.create_task(Dashboard.watch())

        # 顺序逻辑：等待整流罩抛离 -> 自动展开载荷
        # await Utils.jettison()
        if not Utils.isDeployed:
            Utils.deploySwap()
        if Utils.isLanded:
            Utils.landSwap()


if __name__ == "__main__":
    Rlogger("Sync").info("火箭辅助系统控制系统-RSP已启动，进入全监测模式。")
    try:
        asyncio.run(main())
    except Exception as e:
        Rlogger("Sync").error(f"\nRsp控制系统停机: {e}")
