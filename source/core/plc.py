# -*- coding: utf-8 -*-
"""PLC 通讯 (Modbus TCP / RTU / Snap7-S7):
- 保持寄存器块: 基址 100 + 设备序号*10
  +0 温度x10 | +1 压力x10 | +2 液位x10 | +3 开度 R/W | +4 转速 R/W | +5 运行 R/W | +6 报警位
- Snap7 映射: DB 号可配置(默认 100), 设备 i 位于字节偏移 i*20,
  每字段为 16 位大端字(DBW): 偏移 = 字偏移*2, 与 Modbus 词布局一一对应
- PLC 模式下: 周期读取寄存器/DB -> 刷新本地设备状态; 本地下发设定 -> 写回
"""
import socket
import struct
import traceback

from PySide6.QtCore import QThread, Signal

from . import i18n
from .app_state import DEVICE_DEFS, DEVICE_ORDER

BASE_ADDR = 100
BLOCK = 10
S7_DB_DEFAULT = 100


def s7_word_addr(dev_index, word_off):
    """S7 DB 内字节地址: 设备 i 的第 word_off 个字"""
    return dev_index * BLOCK * 2 + word_off * 2


def reg_map_rows(proto="modbus", tags=None):
    """生成寄存器/DB 地址映射表 (用于界面显示)"""
    rows = []
    if proto == "grad":
        field_desc = {"temp": "温度", "press": "压力", "level": "液位",
                      "opening": "开度", "speed": "转速", "running": "运行",
                      "power": "功率/设定",
                      "sp_temp": "温度设定", "sp_level": "液位设定"}
        for t in (tags if tags is not None else DEFAULT_TAGS):
            typ = "REAL" if t.get("dtype", "real") == "real" else "INT"
            dbd = "DBD" if typ == "REAL" else "DBW"
            conv = ""
            sc, of = float(t.get("scale", 1)), float(t.get("offset", 0))
            if abs(sc - 1.0) > 1e-9:
                conv = f" ×{sc:g}"
            if of != 0:
                conv += f"{of:+g}"
            rows.append((t["dev"], field_desc.get(t["field"], t["field"]),
                         f"DB{t['db']}.{dbd} {t['off']} ({typ}){conv}",
                         t.get("scale", 1.0), t.get("rw", "R"), t["field"]))
        return rows
    for dev_id, dtype in DEVICE_DEFS:
        base = BASE_ADDR + DEVICE_ORDER[dev_id] * BLOCK
        # (描述, 字偏移, 读写, 系数, 字段名)
        fields = [("温度x10", 0, "R", 0.1, "temp"),
                  ("压力x10", 1, "R", 0.1, "press")]
        if dtype in ("tank", "column"):
            fields.append(("液位x10", 2, "R", 0.1, "level"))
        if dtype in ("valve", "pump"):
            fields.append(("开度", 3, "R/W", 1.0, "opening"))
        if dtype == "pump":
            fields.append(("转速", 4, "R/W", 1.0, "speed"))
            fields.append(("运行", 5, "R/W", 1.0, "running"))
        if dtype == "exchanger":
            fields.append(("功率", 4, "R/W", 1.0, "power"))
        fields.append(("报警位", 6, "R", 1.0, "alarm"))
        for desc, off, rw, scale, fname in fields:
            if proto == "s7":
                addr = f"DB{S7_DB_DEFAULT}.DBW {s7_word_addr(DEVICE_ORDER[dev_id], off)}"
            else:
                addr = str(base + off)
            rows.append((dev_id, desc, addr, scale, rw, fname))
    return rows


PARAM_OFFSET = {"opening": 3, "speed": 4, "running": 5, "power": 4}
# 允许从界面下发到 PLC 的设备参数 (逐点布局按点表查地址; 白名单只拦截非法字段)
WRITABLE_PARAMS = set(PARAM_OFFSET) | {"sp_temp", "sp_level", "trigger"}

# ---- Snap7 通用点表 (可在界面编辑, 保存于 config.json 的 plc.tags) ----
# 标签: dev设备 / field字段 / db数据块 / off字节偏移 / dtype: real(4字节浮点)|int(2字节有符号字)
#       rw: R只读|W只写|R/W读写 / scale系数 / offset偏置
# 显示值 = 原始值 * scale + offset ;  写入原始值 = (设定值 - offset) / scale
# 当前工厂布局: DB1 测量(温度/压力/液位), DB2 塔设定+FV104, DB4 其余设定/阀位/液位/泵/功率
DEFAULT_TAGS = [
    # ---- DB1: 过程测量 ----
    {"dev": "T101",  "field": "temp",    "db": 1, "off":  0, "dtype": "real", "rw": "R",   "scale": 1.0, "offset": 0.0},
    {"dev": "E102",  "field": "temp",    "db": 1, "off":  8, "dtype": "real", "rw": "R",   "scale": 1.0, "offset": 0.0},
    {"dev": "T101",  "field": "press",   "db": 1, "off": 12, "dtype": "real", "rw": "R",   "scale": 1.0, "offset": 0.0},
    {"dev": "T101",  "field": "level",   "db": 1, "off": 32, "dtype": "real", "rw": "R",   "scale": 1.0, "offset": 0.0},
    # ---- DB2: 塔设定值 / 回流阀 / 馏出阀 ----
    {"dev": "T101",  "field": "sp_temp", "db": 2, "off":  0, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    {"dev": "FV105", "field": "opening", "db": 2, "off":  8, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    {"dev": "FV104", "field": "opening", "db": 2, "off": 12, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    # ---- DB4: 再沸器设定/功率 + 各阀位/储罐液位/泵转速/预热器功率 ----
    {"dev": "E102",  "field": "sp_temp", "db": 4, "off":  0, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    {"dev": "T101",  "field": "sp_level","db": 4, "off":  4, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    {"dev": "E102",  "field": "power",   "db": 4, "off":  8, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    {"dev": "FV106", "field": "opening", "db": 4, "off": 12, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    {"dev": "V101",  "field": "level",   "db": 4, "off": 16, "dtype": "real", "rw": "R",   "scale": 1.0, "offset": 0.0},
    {"dev": "V102",  "field": "level",   "db": 4, "off": 20, "dtype": "real", "rw": "R",   "scale": 1.0, "offset": 0.0},
    {"dev": "V103",  "field": "level",   "db": 4, "off": 24, "dtype": "real", "rw": "R",   "scale": 1.0, "offset": 0.0},
    {"dev": "V104",  "field": "level",   "db": 4, "off": 28, "dtype": "real", "rw": "R",   "scale": 1.0, "offset": 0.0},
    {"dev": "P101",  "field": "speed",   "db": 4, "off": 32, "dtype": "real", "rw": "R",   "scale": 1.0, "offset": 0.0},
    {"dev": "P102",  "field": "speed",   "db": 4, "off": 36, "dtype": "real", "rw": "R",   "scale": 1.0, "offset": 0.0},
    {"dev": "E101",  "field": "power",   "db": 4, "off": 40, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    # FV102/FV103 偏移以 plc.scl 中 DB_Loops 的 STRUCT 声明顺序为准:
    # ...E101_Power@40, FV101_Opening@44, FV102_Opening@48, FV103_Opening@52, P101_Running@56...
    {"dev": "FV101", "field": "opening", "db": 4, "off": 44, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    {"dev": "FV102", "field": "opening", "db": 4, "off": 48, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    {"dev": "FV103", "field": "opening", "db": 4, "off": 52, "dtype": "real", "rw": "R/W", "scale": 1.0, "offset": 0.0},
    # ---- DB4 扩展: 泵运行状态 + ESD 联锁位 (Int=2字节) ----
    {"dev": "P101", "field": "running", "db": 4, "off": 56, "dtype": "int",  "rw": "R/W", "scale": 1.0, "offset": 0.0},
    {"dev": "P102", "field": "running", "db": 4, "off": 58, "dtype": "int",  "rw": "R/W", "scale": 1.0, "offset": 0.0},
    {"dev": "ESD",  "field": "trigger", "db": 4, "off": 60, "dtype": "int",  "rw": "R/W", "scale": 1.0, "offset": 0.0},
]


def get_tags(cfg):
    """取生效点表: config 里有(可能被用户编辑过)用 config, 否则用内置默认"""
    tags = cfg.get("plc", {}).get("tags")
    if isinstance(tags, list):
        return tags
    return [dict(t) for t in DEFAULT_TAGS]


def diagnose_s7_error(ip, exc):
    """把 Snap7/Python 网络异常映射为可操作的中文诊断文本"""
    msg = str(exc).lower()
    if isinstance(exc, (TimeoutError, socket.timeout)) or "timed out" in msg:
        return i18n.tr("plc.diag.timeout", ip=ip)
    if isinstance(exc, ConnectionRefusedError) or "refused" in msg:
        return i18n.tr("plc.diag.refused", ip=ip)
    if "closed by peer" in msg or "connection reset" in msg or "connection closed" in msg:
        return i18n.tr("plc.diag.closed")
    if "host is unreachable" in msg or "unreachable" in msg or "no route" in msg:
        return i18n.tr("plc.diag.unreachable", ip=ip)
    return i18n.tr("plc.diag.other", e=str(exc)[:160])


# snap7 连接级异常 (区别于"DB/偏移配置错误"这类 S7 协议级单点异常)
try:
    from snap7.error import S7ConnectionError, S7TimeoutError
    _S7_FATAL = (S7ConnectionError, S7TimeoutError)
except Exception:                       # 未安装 snap7 / 版本差异 (走 Modbus 时无关)
    _S7_FATAL = ()

# 连接级故障的文本特征: socket 已死/对端关闭/超时重置 —— 这类错误必须重连,
# 而不是误报成"点表配置错误"
_CONN_HINTS = ("not connected", "closed by peer", "connection closed",
               "connection reset", "broken pipe", "timed out", "timeout",
               "10053", "10054", "10060", "10061", "no route", "unreachable",
               "receive error", "receive failed", "send failed", "send error")


def _is_conn_error(exc):
    """判断异常是否为连接级 (TCP/ISO 链路断了), 否则视为 S7 协议级单点错误"""
    if isinstance(exc, (OSError,) + _S7_FATAL):
        return True
    msg = str(exc).lower()
    return any(k in msg for k in _CONN_HINTS)


def _read_regs(client, address, count, slave):
    try:
        rr = client.read_holding_registers(address, count=count, slave=slave)
    except TypeError:
        try:
            rr = client.read_holding_registers(address, count=count, device_id=slave)
        except TypeError:
            rr = client.read_holding_registers(address, count)
    if rr is None or getattr(rr, "isError", lambda: True)():
        raise IOError(f"modbus read error: {rr}")
    return rr.registers


def _write_reg(client, address, value, slave):
    try:
        wr = client.write_register(address, int(value), slave=slave)
    except TypeError:
        wr = client.write_register(address, int(value), device_id=slave)
    if wr is None or getattr(wr, "isError", lambda: True)():
        raise IOError(f"modbus write error: {wr}")


class PLCWorker(QThread):
    """PLC 轮询线程: 读状态 -> state_ready; 写设定 -> 内部队列"""
    state_ready = Signal(dict)          # {dev_id: {field: value}}
    status = Signal(str)                # 连接状态文本
    diag = Signal(str)                  # 软诊断: 不改变连接状态 (单点配置错误/重连进度)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._stop = False
        self._write_queue = []          # (dev_id, param, value)
        self.connected = False
        self._paused = False            # 实验期间暂停主轮询, 避免双连接抢占

    # ---- 对外接口 ----
    def write_param(self, dev_id, param, value):
        if param in WRITABLE_PARAMS:
            self._write_queue.append((dev_id, param, value))

    def stop_worker(self):
        self._stop = True

    def set_paused(self, paused):
        """暂停/恢复主轮询 (实验线程独占 PLC 连接时使用);
        暂停期间不读不写, 写队列保留, 恢复后补发"""
        self._paused = bool(paused)

    # ---- 通用辅助 ----
    def _interruptible_sleep(self, seconds):
        """可被 stop_worker 立即打断的等待 (100ms 粒度)"""
        ticks = max(1, int(seconds * 10))
        for _ in range(ticks):
            if self._stop:
                return
            self.msleep(100)

    @staticmethod
    def _drop_client(client):
        """关闭并销毁 snap7 client, 忽略所有异常"""
        if client is None:
            return
        try:
            client.disconnect()
        except Exception:
            pass
        try:
            client.destroy()
        except Exception:
            pass

    def _s7_open_client(self):
        """新建并连通一个 snap7 client, 失败抛异常"""
        import snap7
        p = self.cfg["plc"]
        c = snap7.client.Client()
        c.connect(p["host"], int(p.get("rack", 0)),
                  int(p.get("slot", 1)),
                  tcp_port=int(p.get("s7_port", 102)))
        if not c.get_connected():
            self._drop_client(c)
            raise IOError(i18n.tr("plc.diag.closed"))
        return c

    def _s7_reconnect(self, client):
        """连接级中断后的自动重连: 销毁死连接 -> UI 转"重连中"(画面冻结)
        -> 每 2s 重试, PLC 恢复 (TIA 下载完成/CPU 重启/网线插回) 后自动接续。
        成功返回新 client; 用户停止时返回 None。"""
        self._drop_client(client)
        if self.connected:
            self.connected = False
            self.status.emit("reconnecting")
        attempt = 0
        while not self._stop:
            attempt += 1
            try:
                new_client = self._s7_open_client()
            except Exception as e:
                # 第1次与之后每10次提示一次, 重连过程不刷屏
                if attempt == 1 or attempt % 10 == 0:
                    self.diag.emit(i18n.tr("plc.diag.retrying",
                                           n=attempt, e=str(e)[:80]))
                self._interruptible_sleep(2.0)
                continue
            self.connected = True
            self.status.emit("reconnected")
            return new_client
        return None

    # ---- 线程主体 ----
    def run(self):
        proto = self.cfg["plc"].get("proto", "tcp")
        if proto == "s7":
            self._run_s7()
        else:
            self._run_modbus(proto)

    # ---- Snap7 (西门子 S7) ----
    def _run_s7(self):
        try:
            import snap7
            try:
                from snap7.type import Areas
            except ImportError:                      # python-snap7 1.x/2.x
                from snap7.types import Areas
        except Exception as e:
            self.status.emit(f"snap7 import error: {e}")
            return

        p = self.cfg["plc"]
        host = p["host"]
        db_number = int(p.get("db", S7_DB_DEFAULT))
        read_size = BLOCK * 2 * len(DEVICE_DEFS)

        # 直接 S7 连接 (与 S7-PLCSIM Advanced 验证过的方式一致, 不做额外 TCP 预检,
        # 避免虚拟网卡偶发抖动时预检重试反而拖慢/阻断连接)
        try:
            client = self._s7_open_client()
        except Exception as e:
            self.status.emit(diagnose_s7_error(host, e))
            return
        self.connected = True
        self.status.emit("connected")
        interval = max(0.2, int(p.get("interval", 500)) / 1000.0)

        if p.get("s7_layout", "grad") == "grad":
            self._s7_loop_real(client, interval, get_tags(self.cfg))
            return

        segmented = False       # 整块读失败 -> 逐设备分段读
        short_warned = False

        try:
            while not self._stop:
                if self._paused:
                    # 实验线程独占连接: 主轮询挂起, 不读不写
                    self.msleep(200)
                    continue
                data = None
                if not segmented:
                    try:
                        data = client.read_area(Areas.DB, db_number, 0, read_size)
                    except Exception as e:
                        if _is_conn_error(e):
                            # 链路中断 (TIA 下载/CPU STOP/网线): 自动重连, 不再退出
                            client = self._s7_reconnect(client)
                            if client is None:
                                return
                            continue
                        m = str(e).lower()
                        if any(k in m for k in ("object does not exist", "0x0a",
                                                "out of range", "address")):
                            # DB 长度不足: 降级为分段读
                            segmented = True
                            if not short_warned:
                                short_warned = True
                                self.status.emit(i18n.tr(
                                    "plc.diag.dbshort", n=db_number, size=read_size))
                        else:
                            self.status.emit(i18n.tr("plc.diag.read",
                                                     e=str(e)[:120]))
                            break

                valid = set()
                if segmented:
                    data = bytearray(read_size)
                    seg_exc = None
                    for idx in range(len(DEVICE_DEFS)):
                        off = idx * BLOCK * 2
                        try:
                            seg = client.read_area(Areas.DB, db_number,
                                                   off, BLOCK * 2)
                            data[off:off + len(seg)] = seg
                            valid.add(idx)
                        except Exception as se:
                            seg_exc = se
                    if not valid:
                        if seg_exc is not None and _is_conn_error(seg_exc):
                            client = self._s7_reconnect(client)
                            if client is None:
                                return
                            continue
                        self.status.emit(i18n.tr("plc.diag.db", n=db_number))
                        break

                states = {}
                for dev_id, dtype in DEVICE_DEFS:
                    i = DEVICE_ORDER[dev_id]
                    if segmented and i not in valid:
                        continue                    # 该设备段在 DB 中不存在, 不刷新
                    b = i * BLOCK * 2
                    item = {"temp": self._s7_word(data, b) / 10.0,
                            "press": self._s7_word(data, b + 2) / 10.0}
                    if dtype in ("tank", "column"):
                        item["level"] = self._s7_word(data, b + 4) / 10.0
                    if dtype == "valve":
                        item["opening"] = float(self._s7_word(data, b + 6))
                    if dtype == "pump":
                        item["opening"] = float(self._s7_word(data, b + 6))
                        item["speed"] = float(self._s7_word(data, b + 8))
                        item["running"] = bool(self._s7_word(data, b + 10))
                    if dtype == "exchanger":
                        item["power"] = float(self._s7_word(data, b + 8))
                    states[dev_id] = item
                if states:
                    self.state_ready.emit(states)

                # 写设定
                while self._write_queue:
                    item = self._write_queue.pop(0)
                    dev_id, param, value = item
                    i = DEVICE_ORDER.get(dev_id)
                    word_off = PARAM_OFFSET.get(param)
                    if i is None or word_off is None:
                        continue            # 旧块布局无该参数槽位 (如 sp_*), 跳过
                    addr = s7_word_addr(i, word_off)
                    try:
                        client.write_area(Areas.DB, db_number, addr,
                                          struct.pack(">H", round(value)))
                    except Exception as e:
                        if _is_conn_error(e):
                            self._write_queue.insert(0, item)   # 重连后补写
                            client = self._s7_reconnect(client)
                            if client is None:
                                return
                            break
                        self.diag.emit(i18n.tr("plc.diag.write",
                                               e=str(e)[:120]))
                self.msleep(int(interval * 1000))
        finally:
            self.connected = False
            self._drop_client(client)
            self.status.emit("closed")

    @staticmethod
    def _s7_word(data, pos):
        return struct.unpack_from(">H", bytes(data[:]), pos)[0]

    # ---- Snap7 通用点表循环 (REAL/INT, 线性换算, 可界面配置) ----
    @staticmethod
    def _tag_raw(tag, raw_bytes):
        if tag.get("dtype", "real") == "real":
            x = struct.unpack(">f", bytes(raw_bytes))[0]
        else:
            x = float(struct.unpack(">h", bytes(raw_bytes))[0])
        return x * float(tag.get("scale", 1.0)) + float(tag.get("offset", 0.0))

    def _s7_loop_real(self, client, interval, tags):
        writable = {(t["dev"], t["field"]): t for t in tags
                    if "W" in t.get("rw", "R").upper()}
        fail_counts = {}      # (dev, field) -> 连续失败次数, 用于过滤偶发抖动
        write_fail = {}       # (dev, param) -> 连续写入失败次数
        try:
            while not self._stop:
                if self._paused:
                    # 实验线程独占连接: 主轮询挂起, 不读不写
                    self.msleep(200)
                    continue
                states = {}
                conn_dead = False
                for t in tags:
                    if "R" not in t.get("rw", "R").upper():
                        continue                    # 只写点不读
                    size = 4 if t.get("dtype", "real") == "real" else 2
                    key = (t["dev"], t["field"])
                    try:
                        raw = client.db_read(int(t["db"]), int(t["off"]), size)
                        v = self._tag_raw(t, raw)
                    except Exception as e:
                        if _is_conn_error(e):
                            # 连接级故障: 本拍剩余点必然全败, 立即进入自动重连,
                            # 不再误报"DB/偏移配置错误"
                            conn_dead = True
                            break
                        # S7 协议级单点错误: 连接是活的, 仅该点 DB/偏移/类型不对。
                        # 软诊断, 不改变连接状态, 不影响其它点和画面动画
                        fail_counts[key] = fail_counts.get(key, 0) + 1
                        n = fail_counts[key]
                        # 第3次连续失败首次提示, 之后每10次再提示一次, 避免刷屏
                        if n == 3 or (n >= 10 and n % 10 == 0):
                            self.diag.emit(i18n.tr("plc.diag.pointfail",
                                                   dev=t["dev"],
                                                   field=t["field"],
                                                   e=str(e)[:60]))
                        continue
                    fail_counts[key] = 0             # 成功重置计数
                    if v != v:                      # NaN 过滤
                        continue
                    states.setdefault(t["dev"], {})[t["field"]] = float(v)

                if conn_dead:
                    client = self._s7_reconnect(client)
                    if client is None:
                        return
                    fail_counts.clear()
                    continue                        # 重连成功, 下一拍重新读全部点
                if states:
                    self.state_ready.emit(states)

                # 写设定: 按该点系数反算为原始值
                q = self._write_queue
                i = 0
                write_dead = False
                while i < len(q):
                    dev_id, param, value = q[i]
                    t = writable.get((dev_id, param))
                    i += 1
                    if not t:
                        continue
                    scale = float(t.get("scale", 1.0)) or 1.0
                    raw_val = (float(value) - float(t.get("offset", 0.0))) / scale
                    try:
                        if t.get("dtype", "real") == "real":
                            payload = struct.pack(">f", raw_val)
                        else:
                            payload = struct.pack(">h", int(round(raw_val)))
                        client.db_write(int(t["db"]), int(t["off"]), payload)
                    except Exception as e:
                        if _is_conn_error(e):
                            # 未处理的写入项保留在队首, 重连后补写
                            i -= 1
                            write_dead = True
                            break
                        wkey = (dev_id, param)
                        write_fail[wkey] = write_fail.get(wkey, 0) + 1
                        n = write_fail[wkey]
                        if n == 3 or (n >= 10 and n % 10 == 0):
                            self.diag.emit(i18n.tr("plc.diag.write",
                                                   e=str(e)[:120]))
                    else:
                        write_fail[(dev_id, param)] = 0
                if i:
                    del q[:i]
                if write_dead:
                    client = self._s7_reconnect(client)
                    if client is None:
                        return
                    write_fail.clear()
                    continue
                self.msleep(int(interval * 1000))
        finally:
            self.connected = False
            self._drop_client(client)
            self.status.emit("closed")

    # ---- Modbus TCP / RTU ----
    def _mb_make_client(self, proto):
        from pymodbus.client import ModbusTcpClient, ModbusSerialClient
        if proto == "tcp":
            return ModbusTcpClient(self.cfg["plc"]["host"],
                                   port=int(self.cfg["plc"]["port"]), timeout=2)
        return ModbusSerialClient(
            port=self.cfg["plc"]["com"],
            baudrate=int(self.cfg["plc"]["baud"]),
            bytesize=8, parity="N", stopbits=1, timeout=2)

    def _mb_reconnect(self, client, proto):
        """Modbus 链路中断后自动重连, 语义同 _s7_reconnect"""
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        if self.connected:
            self.connected = False
            self.status.emit("reconnecting")
        attempt = 0
        while not self._stop:
            attempt += 1
            try:
                new_client = self._mb_make_client(proto)
                ok = new_client.connect()
            except Exception as e:
                ok = False
                err = e
            else:
                err = None
            if not ok:
                if attempt == 1 or attempt % 10 == 0:
                    self.diag.emit(i18n.tr(
                        "plc.diag.retrying", n=attempt,
                        e=(str(err)[:80] if err is not None else "connect failed")))
                self._interruptible_sleep(2.0)
                continue
            self.connected = True
            self.status.emit("reconnected")
            return new_client
        return None

    def _run_modbus(self, proto):
        try:
            client = self._mb_make_client(proto)
        except Exception as e:
            self.status.emit(f"PLC init error: {e}")
            return

        if not client.connect():
            self.status.emit("PLC connect failed")
            return
        self.connected = True
        self.status.emit("connected")
        interval = max(0.2, int(self.cfg["plc"].get("interval", 500)) / 1000.0)
        slave = int(self.cfg["plc"].get("slave", 1))

        try:
            while not self._stop:
                try:
                    regs = _read_regs(client, BASE_ADDR,
                                      BLOCK * len(DEVICE_DEFS), slave)
                except Exception:
                    client = self._mb_reconnect(client, proto)
                    if client is None:
                        return
                    continue
                states = {}
                for dev_id, dtype in DEVICE_DEFS:
                    i = DEVICE_ORDER[dev_id]
                    b = i * BLOCK
                    item = {"temp": regs[b] / 10.0, "press": regs[b + 1] / 10.0}
                    if dtype in ("tank", "column"):
                        item["level"] = regs[b + 2] / 10.0
                    if dtype == "valve":
                        item["opening"] = float(regs[b + 3])
                    if dtype == "pump":
                        item["opening"] = float(regs[b + 3])
                        item["speed"] = float(regs[b + 4])
                        item["running"] = bool(regs[b + 5])
                    if dtype == "exchanger":
                        item["power"] = float(regs[b + 4])
                    states[dev_id] = item
                self.state_ready.emit(states)

                # 写设定
                q = self._write_queue
                i = 0
                write_dead = False
                while i < len(q):
                    item = q[i]
                    dev_id, param, value = item
                    idx = DEVICE_ORDER.get(dev_id)
                    word_off = PARAM_OFFSET.get(param)
                    i += 1
                    if idx is None or word_off is None:
                        continue
                    addr = BASE_ADDR + idx * BLOCK + word_off
                    try:
                        _write_reg(client, addr, round(value), slave)
                    except Exception:
                        i -= 1                          # 重连后补写
                        write_dead = True
                        break
                if i:
                    del q[:i]
                if write_dead:
                    client = self._mb_reconnect(client, proto)
                    if client is None:
                        return
                    continue
                self.msleep(int(interval * 1000))
        finally:
            self.connected = False
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            self.status.emit("closed")
