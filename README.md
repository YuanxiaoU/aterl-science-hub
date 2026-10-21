# ATERL · Aterl-DistSim

精馏装置仿真与控制系统 —— 面向化工过程控制的桌面仿真平台，毕业设计成果，以开源方式公开。

🌐 官网：**https://aterl.com**
⬇️ 下载：**https://github.com/YuanxiaoU/aterl-science-hub/releases/latest**

## 站点结构

```
index.html      官网页面
style.css       样式（黑白大色块 + 品牌蓝 #2E7CF6）
main.js         中英文切换 / 模块切换 / 数字与进度动画
effects.js      鼠标视差 / 时间轴 / 全球部署点阵图
assets/         LOGO 与软件界面截图
CNAME           GitHub Pages 自定义域名
source/         Aterl-DistSim 源码
```

## 源码

`source/` 为 Aterl-DistSim 完整源码，运行方式：

```bash
pip install -r source/requirements.txt
python source/main.py
```

依赖 Siemens PLCSIM（通过 Snap7 通信）与 Ollama（AI 助手，可选）。

## 能力

- 16 台设备 / 6 个控制回路 / 24 点表 / 31 个内置工况
- 双层 ESD 安全联锁
- 操作方向正确率：原始提示 16.1% → 三重约束 91.4%
- 3B 与 14B 模型正确率仅差 0.9pp，可靠性主要取决于提示设计

## 许可

Apache-2.0。个人学习与非商业用途，无任何商业行为。
