"""
轨道计算内核模块
"""

import math
import numpy as np

class OrbitCalc:
    """
    提供轨道力学计算功能的静态工具类
    """

    @staticmethod
    def vis_viva(r, a, mu):
        """活力公式: v^2 = mu * (2/r - 1/a)"""
        return math.sqrt(mu * (2/r - 1/a))

    @staticmethod
    def hohmann_transfer(r1, r2, mu):
        """
        计算霍曼转移所需的 delta-v
        r1: 初始圆轨道半径
        r2: 目标圆轨道半径
        mu: 引力参数
        返回: (dv1, dv2, total_time)
        """
        # 半长轴
        a_transfer = (r1 + r2) / 2
        
        # 第一次点火 (在 r1 处进入转移轨道)
        v1_circular = math.sqrt(mu / r1)
        v1_transfer = math.sqrt(mu * (2/r1 - 1/a_transfer))
        dv1 = abs(v1_transfer - v1_circular)
        
        # 第二次点火 (在 r2 处圆化)
        v2_circular = math.sqrt(mu / r2)
        v2_transfer = math.sqrt(mu * (2/r2 - 1/a_transfer))
        dv2 = abs(v2_circular - v2_transfer)
        
        # 转移时间 (半个周期)
        period = 2 * math.pi * math.sqrt(a_transfer**3 / mu)
        time = period / 2
        
        return dv1, dv2, time

    @staticmethod
    def suicide_burn_height(v_vertical, v_horizontal, thrust, mass, gravity, angle_of_attack=0):
        """
        估算自杀燃烧（着陆反推）所需的刹车距离/高度
        假设恒定推力和重力
        h = (v^2) / (2 * a_net)
        """
        v_total = math.sqrt(v_vertical**2 + v_horizontal**2)
        # 垂直分量加速度
        a_thrust = thrust / mass
        # 假设完全逆行点火，垂直分量
        # 简单模型：a_net = a_thrust - gravity
        a_net = a_thrust - gravity
        
        if a_net <= 0:
            return float('inf') # 推力不足以克服重力
            
        distance = (v_vertical**2) / (2 * a_net)
        return distance

    @staticmethod
    def impact_prediction(position, velocity, drag_coefficient, mass, area, atmosphere_density_func, dt=0.1):
        """
        简单的数值积分预测落点 (考虑空气阻力)
        注意：这只是一个简单的欧拉积分器，实际KSP/RSS建议使用内置预测或更高级的RK4
        """
        pos = np.array(position)
        vel = np.array(velocity)
        
        # 模拟直到高度 < 0
        while pos[0] > 0: # 假设pos[0]是高度 (或者需要根据坐标系调整)
             # 这里简化模型，仅作为算法示例
             # 实际需要考虑星球曲率和旋转
             pass
        return pos

    @staticmethod
    def phase_angle(r1, r2, mu):
        """计算霍曼转移所需的相位角"""
        return math.pi * (1 - math.sqrt((r1 + r2)**3 / (8 * r2**3)))

