# -*- coding: utf-8 -*-
"""自动实验 headless 入口 (不启动界面):
  python -B run_experiment.py --type C --limit 5 --reps 1 --sim   # sim 流程自测
  python -B run_experiment.py --type A                            # PLC 模式正式实验 (默认)
默认 PLC 模式 (cfg.plc.host 真实注入); --sim 为无 PLC 的流程自测,
输出文件名带 _selftest 后缀, 不得作为论文数据。
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import load_config
from core.app_state import AppState
from core.materials import find_material
from core.experiment import ExperimentRunner, load_cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=["A", "B", "C"], default="C")
    ap.add_argument("--limit", type=int, default=0, help="前 N 个工况, 0=全部")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--sim", action="store_true",
                    help="sim 自测模式 (无 PLC, 数据带 _selftest 后缀)")
    ap.add_argument("--exec", dest="exec_sug", action="store_true",
                    help="执行AI建议(写回PLC), 默认观察模式")
    args = ap.parse_args()

    cfg = load_config()
    st = AppState()
    st.reset_devices()
    st.material = find_material("乙醇-水体系")
    # 默认必须是 PLC 正式模式; 仅显式 --sim 才走仿真自测
    st.mode = "sim" if args.sim else "plc"
    cases = load_cases()
    if args.limit > 0:
        cases = cases[:args.limit]
    if not cases:
        print("找不到 data/test_cases.json")
        return

    # 输出文件名带类型+时间戳, 重跑不覆盖; sim 自测带 _selftest 后缀与正式数据区分
    ts = time.strftime("%Y%m%d_%H%M%S")
    tag = "_selftest" if st.mode == "sim" else ""
    base = f"experiment_log_{ts}_{args.type}{tag}"
    runner = ExperimentRunner(
        cfg, st, cases, exp_type=args.type, reps=args.reps,
        exec_suggestions=args.exec_sug,
        log_file=os.path.join("experiments", base + ".csv"),
        summary_file=os.path.join("experiments", base.replace("experiment_log", "summary") + ".md"),
        own_poll=(st.mode == "plc"),
        on_progress=lambda ci, total, rep, reps, msg: print(
            f"[{ci}/{total}] 第{rep}/{reps}次 {msg}", flush=True),
        on_step=lambda s: print("  ..", s, flush=True),
        on_done=lambda p: print("报告:", p or "(未生成)", flush=True))

    # PLC 模式启动前硬预检: 连接+读验证不通过立即终止, 防止静默跑出 sim 假数据
    if st.mode == "plc":
        host = cfg.get("plc", {}).get("host", "?")
        print(f"PLC 预检: 连接 {host} ...", flush=True)
        if not runner._connect():
            print(f"[中止] 无法连接 PLC({host}) 或读验证失败, 实验未启动。"
                  f"请确认 PLCSIM 在线后重试 (流程自测可加 --sim)。", flush=True)
            runner._drop_client()
            return
        print("PLC 预检通过, 开始正式实验。", flush=True)

    if st.mode == "sim":
        # sim 模式标注: 数据来源为直接设值, 非真实 PLC
        runner._write_row_orig = runner._write_row
        def _tagged(row):
            row["notes"] = ";".join(
                x for x in ["sim直接设值(无PLC)", row.get("notes", "")] if x)
            runner._write_row_orig(row)
        runner._write_row = _tagged
    runner.start()
    runner.join()


if __name__ == "__main__":
    main()
