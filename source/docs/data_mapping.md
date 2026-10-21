# Aterl-DistSim 数据映射对照表

> 生成时间: 2026-09-21  
> 物料体系: 乙醇-水 (轻组分 bp=78.4°C, 重组分 bp=100.0°C)  
> 字段约定: **T101.temp = 塔顶温度**, **E102.temp = 塔釜温度**

---

## 表格 1：PLC 变量总表（DB 块定义）

### DB1（DB_Process）—— 过程变量（只读）

| 变量名 | DB | 偏移 | 类型 | 读写 | 起始值 | 含义 |
|---|---|---|---|---|---|---|
| Temp_Top | 1 | 0.0 | Real | R | 78.0 | 塔顶温度 |
| Temp_Mid | 1 | 4.0 | Real | R | 82.0 | 中部温度（备用） |
| Temp_Bottom | 1 | 8.0 | Real | R | 105.0 | 塔釜温度 |
| Pressure_Top | 1 | 12.0 | Real | R | 101.3 | 塔顶压力 |
| Pressure_Bottom | 1 | 16.0 | Real | R | 110.0 | 塔釜压力（备用） |
| Flow_Distillate | 1 | 20.0 | Real | R | 50.0 | 馏出流量（备用） |
| Flow_Bottom | 1 | 24.0 | Real | R | 50.0 | 釜液流量（备用） |
| Flow_Reflux | 1 | 28.0 | Real | R | 30.0 | 回流流量（备用） |
| Level_Bottom | 1 | 32.0 | Real | R | 50.0 | 塔釜液位 |
| Level_Tank | 1 | 36.0 | Real | R | 50.0 | 回流罐液位（备用，实际用 DB4.20） |
| Temp_Feed | 1 | 40.0 | Real | R | 25.0 | 进料温度（备用） |

### DB2（DB_Control）—— 控制变量

| 变量名 | DB | 偏移 | 类型 | 读写 | 起始值 | 含义 |
|---|---|---|---|---|---|---|
| SP_Temp_Top | 2 | 0.0 | Real | R/W | 77.0 | 塔顶温度设定值 |
| SP_Reflux_Ratio | 2 | 4.0 | Real | R | 2.5 | 回流比设定（备用） |
| Valve_Distillate | 2 | 8.0 | Real | R/W | 50.0 | 馏出阀 FV105 开度 |
| Valve_Reflux | 2 | 12.0 | Real | R/W | 50.0 | 回流阀 FV104 开度 |
| Feed_Position | 2 | 16.0 | Int | R | 1 | 进料位置（备用） |
| Mode | 2 | 18.0 | Int | R | 1 | 模式（备用） |

### DB4（DB_Loops）—— 多回路控制

| 变量名 | DB | 偏移 | 类型 | 读写 | 起始值 | 含义 |
|---|---|---|---|---|---|---|
| SP_Temp_Bottom | 4 | 0.0 | Real | R/W | 104.0 | 塔釜温度设定值 |
| SP_Level | 4 | 4.0 | Real | R/W | 50.0 | 塔釜液位设定值 |
| Heater_Power | 4 | 8.0 | Real | R/W | 60.0 | 再沸器 E102 功率 |
| Valve_Bottom | 4 | 12.0 | Real | R/W | 50.0 | 釜液阀 FV106 开度 |
| V101_Level | 4 | 16.0 | Real | R | 70.0 | 进料罐液位 |
| V102_Level | 4 | 20.0 | Real | R | 60.0 | 回流罐液位 |
| V103_Level | 4 | 24.0 | Real | R | 50.0 | 塔顶产品罐液位 |
| V104_Level | 4 | 28.0 | Real | R | 40.0 | 塔釜产品罐液位 |
| P101_Speed | 4 | 32.0 | Real | R | 80.0 | 进料泵转速 |
| P102_Speed | 4 | 36.0 | Real | R | 80.0 | 回流泵转速 |
| E101_Power | 4 | 40.0 | Real | R/W | 60.0 | 预热器功率 |
| FV101_Opening | 4 | 44.0 | Real | R/W | 50.0 | 进料阀开度 |
| FV102_Opening | 4 | 48.0 | Real | R/W | 60.0 | 蒸汽阀开度 |
| FV103_Opening | 4 | 52.0 | Real | R/W | 70.0 | 冷却水阀开度 |

---

## 表格 2：Aterl-DistSim 点表（DEFAULT_TAGS，共 24 点）

| # | 设备 | 字段 | DB | 偏移 | 类型 | 读写 | 系数 | 偏置 | 含义 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | T101 | temp | 1 | 0 | real | R | 1.0 | 0.0 | 塔顶温度 |
| 2 | E102 | temp | 1 | 8 | real | R | 1.0 | 0.0 | 塔釜温度 |
| 3 | T101 | press | 1 | 12 | real | R | 1.0 | 0.0 | 塔顶压力 |
| 4 | T101 | level | 1 | 32 | real | R | 1.0 | 0.0 | 塔釜液位 |
| 5 | T101 | sp_temp | 2 | 0 | real | R/W | 1.0 | 0.0 | 塔顶温度设定 |
| 6 | FV105 | opening | 2 | 8 | real | R/W | 1.0 | 0.0 | 馏出阀开度 |
| 7 | FV104 | opening | 2 | 12 | real | R/W | 1.0 | 0.0 | 回流阀开度 |
| 8 | E102 | sp_temp | 4 | 0 | real | R/W | 1.0 | 0.0 | 塔釜温度设定 |
| 9 | T101 | sp_level | 4 | 4 | real | R/W | 1.0 | 0.0 | 塔釜液位设定 |
| 10 | E102 | power | 4 | 8 | real | R/W | 1.0 | 0.0 | 再沸器功率 |
| 11 | FV106 | opening | 4 | 12 | real | R/W | 1.0 | 0.0 | 釜液阀开度 |
| 12 | V101 | level | 4 | 16 | real | R | 1.0 | 0.0 | 进料罐液位 |
| 13 | V102 | level | 4 | 20 | real | R | 1.0 | 0.0 | 回流罐液位 |
| 14 | V103 | level | 4 | 24 | real | R | 1.0 | 0.0 | 塔顶产品罐液位 |
| 15 | V104 | level | 4 | 28 | real | R | 1.0 | 0.0 | 塔釜产品罐液位 |
| 16 | P101 | speed | 4 | 32 | real | R | 1.0 | 0.0 | 进料泵转速 |
| 17 | P102 | speed | 4 | 36 | real | R | 1.0 | 0.0 | 回流泵转速 |
| 18 | E101 | power | 4 | 40 | real | R/W | 1.0 | 0.0 | 预热器功率 |
| 19 | FV101 | opening | 4 | 44 | real | R/W | 1.0 | 0.0 | 进料阀开度 |
| 20 | FV102 | opening | 4 | 48 | real | R/W | 1.0 | 0.0 | 蒸汽阀开度 |
| 21 | FV103 | opening | 4 | 52 | real | R/W | 1.0 | 0.0 | 冷却水阀开度 |
| 22 | P101 | running | 4 | 56 | int | R/W | 1.0 | 0.0 | 进料泵运行 (0/1) |
| 23 | P102 | running | 4 | 58 | int | R/W | 1.0 | 0.0 | 回流泵运行 (0/1) |
| 24 | ESD | trigger | 4 | 60 | int | R/W | 1.0 | 0.0 | ESD联锁位 (0正常/1联锁/2人工) |

> 显示值 = 原始值 × 系数 + 偏置；写入原始值 = (设定值 - 偏置) / 系数  
> 注：DB1.36 (Level_Tank) 未绑定，V102 液位统一用 DB4.20。  
> Int 类型占 2 字节，Real 类型占 4 字节。

---

## 表格 3：AI snapshot 实际用到的字段清单

snapshot 函数输出 JSON 结构: `{sim_time_s, devices: {dev_id: {type, temp, press, ...}}}`

| 设备类型 | 输出字段 | 数据来源 | 说明 |
|---|---|---|---|
| **全部** | type, temp, press | dev.dtype, dev.temp, dev.press | 通用字段 |
| tank | level | dev.level | 储罐液位 |
| valve | opening | dev.opening | 阀门开度 0-100 |
| pump | speed, running | dev.speed, dev.running | 泵转速/运行 |
| exchanger | power | dev.power | 换热器功率 0-100 |
| **column (T101)** | top_temp, bot_temp | dev.temp (塔顶), E102.temp (塔釜) | 塔顶/塔釜温度 |
| 全部 | alarms | dev.alarms | 报警 key 列表 |

### T101 输出示例
```json
{
  "type": "column",
  "temp": 78.4,
  "press": 101.3,
  "top_temp": 78.4,
  "bot_temp": 100.2,
  "alarms": []
}
```

### AI 关键决策依赖的字段
| AI 决策 | 依赖字段 | 来源 |
|---|---|---|
| 塔顶温度偏高→开大回流阀 FV104 | T101.temp (top_temp) | DB1.0 |
| 塔釜温度偏低→开大蒸汽阀 FV102 | E102.temp (bot_temp) | DB1.8 |
| 塔压高→关蒸汽/开冷却水 | T101.press | DB1.12 |
| 回流罐液位→调节馏出阀 FV105 | V102.level | DB4.20 |
| 回流阀开度 | FV104.opening | DB2.12 |

---

## 表格 4：PID 回路 PV/SP/MV 映射

| 回路 | 名称 | PV (测量值) | SP (设定值) | MV (执行器) | 作用方向 | 阈值 big/dead |
|---|---|---|---|---|---|---|
| **L1** | 塔釜温度 | E102.temp (DB1.8) | E102.sp_temp (DB4.0) | E102.power (DB4.8) | +1 正作用 | 2.0 / 0.5 |
| **L2** | 塔压 | T101.press (DB1.12) | manual=106.0 | FV103.opening (DB4.52) | -1 反作用 | 15.0 / 2.0 |
| **L3** | 塔顶温度 | T101.temp (DB1.0) | T101.sp_temp (DB2.0) | FV104.opening (DB2.12) | -1 反作用 | 2.0 / 0.5 |
| **L4** | 回流罐液位 | V102.level (DB4.20) | manual=50.0 | FV105.opening (DB2.8) | +1 正作用 | 20.0 / 3.0 |
| **L5** | 塔釜产品罐液位 | V104.level (DB4.28) | manual=50.0 | FV106.opening (DB4.12) | +1 正作用 | 20.0 / 3.0 |
| **L6** | 进料罐液位 (禁用) | V101.level (DB4.16) | manual=60.0 | FV101.opening (DB4.44) | -1 反作用 | 20.0 / 3.0 |

### SP 模式说明
- **plc**: 从 PLC 点表读设定值（L1, L3）
- **manual**: 用配置中的 sp 数值（L2, L4, L5, L6）
- **auto**: 按物料沸点自动给定（塔顶→轻组分 bp 78.4°C，塔釜→重组分 bp 100.0°C）

### 方向校验规则（AI 建议执行前）
| 偏差 (SP-PV) | PV 状态 | 正作用 MV (+1) | 反作用 MV (-1) |
|---|---|---|---|
| > +2.0 | 偏低 | increase | decrease |
| < -2.0 | 偏高 | decrease | increase |
| [-2.0, +2.0] | 正常 | hold | hold |

- 幅度限制: 单次变化 ≤ 量程 10% (0-100 → ≤10)
- 范围限制: 0-100 clamp

---

## 字段语义统一约定

| 设备 | 字段 | 含义 | 备注 |
|---|---|---|---|
| T101 | temp | **塔顶温度** | 与画布/PLC/L3 一致 |
| T101 | press | 塔顶压力 | |
| T101 | level | 塔釜液位 | |
| T101 | sp_temp | 塔顶温度设定 | |
| T101 | sp_level | 塔釜液位设定 | |
| E102 | temp | **塔釜温度** | |
| E102 | power | 再沸器功率 | |
| E102 | sp_temp | 塔釜温度设定 | |
| FV104 | opening | 回流阀开度 | L3 MV |
| FV105 | opening | 馏出阀开度 | L4 MV |
| FV102 | opening | 蒸汽阀开度 | |
| E101 | power | 预热器功率 | |

> ⚠️ `T101.top_temp` 字段已废弃（仿真不再更新），塔顶温度统一用 `T101.temp`。
