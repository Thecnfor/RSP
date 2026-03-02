import asyncio
import multiprocessing as mp
from utility import Rlogger, Dashboard
from core import Kernel
from core.ai_service import AIService


async def main():
    # 1. 创建进程间通信队列
    data_queue = mp.Queue()  # Telemetry: Control -> UI
    cmd_queue = mp.Queue()   # Commands: UI -> Control
    
    # AI 服务队列
    ai_req_queue = mp.Queue()
    ai_res_queue = mp.Queue()

    # 2. 启动 AI 服务进程
    ai_service = AIService(ai_req_queue, ai_res_queue)

    # 3. 启动控制内核（在独立子进程中）
    # 内核会自动连接 kRPC 并管理 RockerCore 实例
    # 将 AI 队列传递给内核，以便内核中的 RockerCore 发起 AI 请求
    kernel = Kernel(data_queue, cmd_queue, ai_req_queue, ai_res_queue)

    # 4. 启动仪表盘（在主进程中）
    ui = Dashboard(data_queue, cmd_queue)

    Rlogger("Sync").info("系统重构完成：进入三进程协同模式 (Kernel + AI + UI)。")

    try:
        # 保持主进程活跃，运行 UI 渲染循环
        await ui.watch()
    except asyncio.CancelledError:
        Rlogger("Sync").info("系统正在关闭...")
    finally:
        # 清理工作（可选）
        pass


if __name__ == "__main__":
    # Windows 下使用 multiprocessing 必须在 if __name__ == "__main__": 下
    mp.freeze_support()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        Rlogger("Sync").error(f"系统崩溃: {e}")
