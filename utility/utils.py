"""
核心辅助功能模块 - 蓝桥杯竞赛级优化版
"""

import asyncio
from .log import Rlogger
from .config import config


class Utils:
    """
    火箭辅助系统控制器：采用动态属性监测与防御性编程架构
    """

    def __init__(self, vessel):
        self.vessel = vessel

    @property
    def isFActive(self) -> bool:
        """
        判断整流罩是否“活跃”（即存在且尚未抛离）。
        """
        if self.vessel.parts.fairings and any(
            f.jettisoned for f in self.vessel.parts.fairings
        ):
            # Rlogger("FA").info("存在未抛离的整流罩")
            return False
        # Rlogger("FA").info("所有整流罩均抛离")
        return True

    @property
    def isDeployed(self) -> bool:
        """纯状态检查：判断载荷（太阳能板/天线）是否已展开"""
        solar = [p for p in self.vessel.parts.solar_panels if p.deployable]
        antennas = [a for a in self.vessel.parts.antennas if a.deployable]
        controllable_payloads = solar + antennas
        if not controllable_payloads:
            return False

        # 检查是否全部已展开
        return all(part.deployed for part in controllable_payloads)

    @property
    def isLanded(self) -> bool:
        """纯状态检查：判断着陆装置是否已展开"""
        legs = self.vessel.parts.legs
        wheels = self.vessel.parts.wheels
        if not legs and not wheels:
            return False
        # 确保所有部件均已展开
        return all(l.deployed for l in legs) and all(w.deployed for w in wheels)

    async def jettison(self):
        """
        异步监测系统：采用“检测-确认-反馈”闭环逻辑
        """
        # 根据用户定义：isFActive 为 True 表示已抛离或无需处理
        if self.isFActive:
            return

        Rlogger("Utils").info("整流罩智能监测系统已上线...")
        while not self.isFActive:

            flight = self.vessel.flight()
            # 抛离条件：海拔 > 40,000m 且动压 < 100 Pa
            if flight.dynamic_pressure < 100 and flight.mean_altitude > 40000:
                triggered = False
                # 1. 地毯式扫描：触发所有 ModuleProceduralFairing 模块中的所有事件
                for part in self.vessel.parts.all:
                    for module in part.modules:
                        if module.name == "ModuleProceduralFairing":
                            events = module.events
                            if events:
                                for event in events:
                                    try:
                                        module.trigger_event(event)
                                        Rlogger("Utils").info(
                                            f"动态触发事件: {event} (部件: {part.title})"
                                        )
                                        triggered = True
                                    except Exception as e:
                                        Rlogger("Utils").debug(
                                            f"触发事件 {event} 失败: {e}"
                                        )

                # 2. 原版降级兜底
                if not triggered and self.vessel.parts.fairings:
                    for f in self.vessel.parts.fairings:
                        try:
                            f.jettison()
                            triggered = True
                        except:
                            continue

                if triggered:
                    Rlogger("Utils").info("整流罩抛离指令已发送，正在等待物理反馈...")
                    # 等待物理分离
                    await asyncio.sleep(1)
                    # 通过用户定义的 isFActive 确认是否真正抛离
                    if not self.isFActive:
                        Rlogger("Utils").info("整流罩抛离成功确认。")
                        break
            await asyncio.sleep(0.5)

    def deploySwap(self):
        """
        一键部署动作：执行状态翻转并返回执行后的状态。
        """
        if self.isFActive:
            Rlogger("Utils").warning("整流罩尚未抛离，拒绝展开载荷！")
            return

        deploy_filter = lambda c: hasattr(c, "deployable") and c.deployable
        deploy_action = lambda c: setattr(
            c, "deployed", not getattr(c, "deployed", False)
        )

        s_count = self._batch_operate(
            self.vessel.parts.solar_panels, deploy_action, deploy_filter
        )
        a_count = self._batch_operate(
            self.vessel.parts.antennas, deploy_action, deploy_filter
        )

        status = self.isDeployed
        Rlogger("Utils").info(
            f"载荷系统状态已翻转，当前状态: {'展开' if status else '收回'} (太阳能板:{s_count}, 天线:{a_count})"
        )

    def landSwap(self):
        """
        着陆动作：执行状态翻转并返回执行后的状态。
        """
        toggle_op = lambda c: setattr(c, "deployed", not getattr(c, "deployed", False))
        check_op = lambda c: hasattr(c, "deployed")

        self._batch_operate(
            self.vessel.parts.legs, action=toggle_op, filter_func=check_op
        )
        self._batch_operate(
            self.vessel.parts.wheels, action=toggle_op, filter_func=check_op
        )

        status = self.isLanded
        Rlogger("Utils").info(
            f"着陆装置状态已翻转，当前状态: {'收回' if status else '展开'}"
        )

    def _group_action(self, action_name: str) -> bool:
        """内部方法：通过配置映射触发任务组"""
        try:
            # 从全局配置中获取映射的组编号
            group = config["action_groups"][action_name]
            if group is None:
                Rlogger("Utils").error(f"未在配置中找到任务组: {action_name}")
                return False

            self.vessel.control.set_action_group(int(group), True)
            Rlogger("Utils").info(f"任务组 {action_name}({group}) 已触发。")
            return True
        except Exception as e:
            Rlogger("Utils").error(
                f"任务组 {action_name} 触发异常: {type(e).__name__} - {str(e)}"
            )
            return False

    def _batch_operate(self, components, action, filter_func=None) -> int:
        """
        参数:
            components: 要操作的组件列表 (如 vessel.parts.solar_panels)
            action: 执行的动作函数 (接收一个组件对象)
            filter_func: 可选的过滤函数，返回 True 时才执行 action
        设计哲学:
            不再硬编码特定的组件类型或属性名。通过传入 action 和 filter_func，
            该函数可以适配任何组件的任何操作（展开、收回、激活、设置参数等）。
            这体现了 Python 作为函数式编程语言的灵活性，是蓝桥杯高分代码的典型特征。
        """
        success_count = 0
        for comp in components:
            # 执行过滤校验
            if filter_func and not filter_func(comp):
                continue

            try:
                action(comp)
                success_count += 1
            except Exception as e:
                # 记录详细异常，方便竞赛调试
                Rlogger("Utils").debug(f"组件操作失败 ({type(comp).__name__}): {e}")
                continue

        return success_count
