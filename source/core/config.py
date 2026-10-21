# -*- coding: utf-8 -*-
"""全局配置: 加载/保存 config.json"""
import json
import os
import sys

if getattr(sys, "frozen", False):   # PyInstaller 打包后: exe 所在目录
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
CUSTOM_MATERIAL_FILE = os.path.join(APP_DIR, "materials_custom.json")
CASE_FILE = os.path.join(APP_DIR, "cases.jsonl")   # 本地学习案例库 (不改模型)
LOG_DIR = os.path.join(APP_DIR, "logs")

DEFAULTS = {
    "language": "zh",                 # zh / en
    "ollama_url": "http://127.0.0.1:11434",
    "ai_model": "qwen2.5:7b-instruct-q4_K_M",
    "ui": {"geom": None, "state": None, "focus": False},   # 窗口/布局记忆
    "pid": {"loops": {}},             # 控制回路参数 (首启由 LOOP_DEFAULTS 填充)
    "plc": {
        "proto": "tcp",               # tcp / rtu / s7
        "host": "192.168.0.10",
        "port": 502,
        "rack": 0,                    # Snap7 机架
        "slot": 1,                    # Snap7 插槽
        "db": 100,                    # Snap7 DB 号 (block 布局)
        "s7_layout": "grad",          # grad=REAL点表(DB1/DB2) / block=连续寄存器
        "com": "COM3",
        "baud": 9600,
        "slave": 1,
        "interval": 500,              # 轮询周期 ms
    },
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
