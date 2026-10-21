# -*- coding: utf-8 -*-
"""数据记录与日志导出 (CSV 数据 + 事件日志 -> 导出 zip)"""
import os
import time
import zipfile

from .config import LOG_DIR, CASE_FILE
from . import i18n


class DataLogger:
    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.data_file = os.path.join(LOG_DIR, f"data_{ts}.csv")
        self.event_file = os.path.join(LOG_DIR, f"events_{ts}.log")
        self._header_written = False

    def write_row(self, sim_time, values):
        """values: dict {tag: value}"""
        try:
            new = not self._header_written
            with open(self.data_file, "a", encoding="utf-8") as f:
                if new:
                    f.write("time_s," + ",".join(values.keys()) + "\n")
                    self._header_written = True
                f.write(f"{sim_time:.0f}," +
                        ",".join(f"{v:.2f}" for v in values.values()) + "\n")
        except Exception:
            pass

    def write_event(self, text):
        try:
            with open(self.event_file, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass

    def export_zip(self, dst_path):
        with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as z:
            for fp in (self.data_file, self.event_file):
                if os.path.exists(fp):
                    z.write(fp, os.path.basename(fp))
            # 本地学习案例库
            if os.path.exists(CASE_FILE):
                z.write(CASE_FILE, os.path.basename(CASE_FILE))
            # 一并打包历史日志
            if os.path.isdir(LOG_DIR):
                for fn in os.listdir(LOG_DIR):
                    fp = os.path.join(LOG_DIR, fn)
                    if fp not in (self.data_file, self.event_file):
                        z.write(fp, "history/" + fn)
        return dst_path


def format_event(ev):
    """事件 -> 当前语言文本"""
    try:
        msg = i18n.tr(ev["key"], dev=ev.get("dev", ""), **ev["params"])
    except Exception:
        msg = i18n.tr(ev["key"], v=ev["params"].get("v", ""))
    dev = f"[{ev['dev']}] " if ev["dev"] else ""
    return f"{ev['t']} {dev}{msg}"
