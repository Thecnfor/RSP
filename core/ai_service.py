"""
AI 服务进程模块
"""
import multiprocessing as mp
import time
from utility import Rlogger
from .ai_interface import AIController

class AIService:
    """
    独立运行的 AI 计算服务进程
    """
    def __init__(self, req_queue: mp.Queue, res_queue: mp.Queue):
        self.req_queue = req_queue
        self.res_queue = res_queue
        self._process = mp.Process(target=self._run_worker, daemon=True)
        self._process.start()
        Rlogger("AI_Service").info(f"AI 计算服务进程已启动 (PID: {self._process.pid})")

    def _run_worker(self):
        """AI 服务主循环"""
        # 在子进程中初始化 AI 控制器（加载模型）
        controller = AIController(model_path="model.pth")
        Rlogger("AI_Service").info("AI 模型初始化完成，等待请求...")
        
        while True:
            try:
                # 阻塞式获取请求，避免空转
                # request format: {"id": "req_id", "state": {...}}
                req = self.req_queue.get()
                
                req_id = req.get("id")
                state = req.get("state")
                
                if req_id and state:
                    start_time = time.time()
                    # 执行预测
                    action = controller.predict(state)
                    duration = time.time() - start_time
                    
                    # 发送结果
                    # response format: {"id": "req_id", "action": [...]}
                    self.res_queue.put({
                        "id": req_id,
                        "action": action,
                        "duration": duration
                    })
                    
            except Exception as e:
                Rlogger("AI_Service").error(f"AI 推理异常: {e}")
                time.sleep(0.1)
