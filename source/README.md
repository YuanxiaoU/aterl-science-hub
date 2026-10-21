# Aterl-DistSim · 精馏装置仿真与控制系统

面向乙醇–水精馏装置的仿真与控制系统，让本地轻量化大模型以监督者身份安全介入流程工业控制。

## 特点

- 动态工艺仿真 + 真实 PLC 监控 + AI 操作顾问 + 自动化实验
- 三重约束提示 / 确定性方向翻转 / 双层 ESD 硬联锁
- 本地推理，无云端依赖，数据不出厂
- 16 台设备 · 6 个控制回路 · 24 点 PLC 点表 · 31 个典型工况

## 运行

```bash
pip install -r requirements.txt
python main.py
```

本地大模型（可选，需先安装 Ollama 并拉取模型）：

```bash
ollama pull qwen2.5:7b
```

## 技术栈

Python 3.10 · PySide6 · Snap7 · Ollama · qwen2.5:7b

## 许可

Apache-2.0
