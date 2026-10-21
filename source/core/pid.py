# -*- coding: utf-8 -*-
"""单回路 PID 控制器 (工业实用型)
- 位置式算法, 输出限幅 + 变化率限制
- 抗积分饱和: 输出饱和时回算修正积分项
- 抗设定值冲击: 微分项只对测量值(PV)求导
- 无扰切换: 手动/首次投用时积分项跟踪当前实际输出
- 死区: |SP-PV| 在死区内输出保持, 不动作
- 作用方向: direction=+1 正作用(MV↑→PV↑, 如加热); -1 反作用(MV↑→PV↓, 如冷却)
"""


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class PIDController:
    def __init__(self, kp=1.0, ki=0.0, kd=0.0,
                 out_min=0.0, out_max=100.0, max_step=5.0, direction=1):
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.out_min = float(out_min)
        self.out_max = float(out_max)
        self.max_step = float(max_step)      # 每秒最大变化量 (输出单位/s)
        self.direction = 1 if direction >= 0 else -1
        self.i_term = None                   # 积分项 (未初始化=未投用)
        self.prev_pv = None
        self.last_out = None

    def configure(self, cfg):
        self.kp = float(cfg.get("kp", self.kp))
        self.ki = float(cfg.get("ki", self.ki))
        self.kd = float(cfg.get("kd", self.kd))
        self.out_min = float(cfg.get("out_min", self.out_min))
        self.out_max = float(cfg.get("out_max", self.out_max))
        self.max_step = float(cfg.get("max_step", self.max_step))
        d = int(cfg.get("direction", self.direction))
        self.direction = 1 if d >= 0 else -1

    def reset(self, current_mv=None):
        """切手动/急停/重置: 积分项跟踪当前阀位, 保证再次投自动无跳变"""
        self.i_term = None if current_mv is None else float(current_mv)
        self.prev_pv = None
        self.last_out = None if current_mv is None else float(current_mv)

    def compute(self, sp, pv, dt, auto, manual_mv, dead=0.0):
        """返回 (输出值, 本拍是否动作)。auto=False 时跟踪手动输出, 不计算。"""
        if not auto:
            # 手动状态: 持续跟踪实际阀位, 投自动瞬间无扰
            self.last_out = float(manual_mv)
            self.i_term = float(manual_mv)
            self.prev_pv = float(pv)
            return float(manual_mv), False

        if dt is None or dt <= 0:
            return (self.last_out if self.last_out is not None
                    else clamp(float(manual_mv), self.out_min, self.out_max)), False

        if self.i_term is None or self.last_out is None:
            # 首次投自动: 从当前阀位起步 (无扰)
            start = clamp(float(manual_mv), self.out_min, self.out_max)
            self.i_term = start
            self.last_out = start
        if self.prev_pv is None:
            self.prev_pv = float(pv)

        err = (float(sp) - float(pv)) * self.direction

        # 死区内: 输出保持, 但仍刷新 prev_pv 防止恢复时微分跳变
        if abs(float(sp) - float(pv)) <= float(dead):
            self.prev_pv = float(pv)
            return self.last_out, False

        # 微分对 PV 求导 (设定值变化不会造成 D 冲击)
        d_pv = (float(pv) - self.prev_pv) / dt
        self.prev_pv = float(pv)

        p = self.kp * err
        d_term = -self.kd * d_pv * self.direction

        # 积分预估 + 抗饱和回算
        i_try = self.i_term + self.ki * err * dt
        raw = p + i_try + d_term
        sat = clamp(raw, self.out_min, self.out_max)

        # 变化率限制 (相对上一拍输出, 按 dt 折算)
        step = self.max_step * dt
        out = clamp(sat, self.last_out - step, self.last_out + step)
        out = clamp(out, self.out_min, self.out_max)

        # 回算: 让 i_term 与"实际限幅后的输出"一致, 退饱和时无深积分
        self.i_term = out - p - d_term
        self.i_term = clamp(self.i_term, self.out_min, self.out_max)

        moved = abs(out - self.last_out) > 1e-6
        self.last_out = out
        return out, moved
