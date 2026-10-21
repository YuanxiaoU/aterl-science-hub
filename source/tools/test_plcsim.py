# -*- coding: utf-8 -*-
"""
S7-PLCSIM Advanced 连接诊断脚本
用法:
    python tools/test_plcsim.py <实例IP> [DB号]
例:
    python tools/test_plcsim.py 192.168.0.10 100

依次检测:
  1. TCP 102 端口是否可达 (区分: 拒接/超时/防火墙)
  2. snap7 多组 rack/slot 连接尝试 (0/1, 0/2, 1/1)
  3. 连接成功后尝试读取 DB 前若干字节 (验证 PUT/GET 与优化块设置)
"""
import socket
import sys
import time


def check_tcp(ip, port=102, timeout=3):
    t0 = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        dt = (time.time() - t0) * 1000
        print(f"  [1] TCP {ip}:{port} 可达  ({dt:.0f} ms)")
        return True
    except ConnectionRefusedError:
        print(f"  [1] TCP {ip}:{port} 被拒绝 -> 实例未 RUN / 端口未监听 / IP 不对")
    except socket.timeout:
        print(f"  [1] TCP {ip}:{port} 超时 -> 防火墙拦截 或 IP 不可达 (ping 一下确认)")
    except Exception as e:
        print(f"  [1] TCP {ip}:{port} 异常: {type(e).__name__}: {e}")
    finally:
        s.close()
    return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    ip = sys.argv[1]
    db = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    print(f"目标 PLCSIM Advanced: {ip}  测试 DB{db}")
    if not check_tcp(ip):
        print("\n结论: 网络层不通, 先确认实例 IP (PLCSIM Advanced 管理器里查)")
        print("      - 实例处于 RUN 状态")
        print("      - 本机 ping 该 IP 能通")
        print("      - Windows 防火墙允许 Python/程序访问专用网络")
        return 2

    try:
        import snap7
        from snap7.type import Areas
    except Exception as e:
        print("snap7 导入失败:", e)
        return 3

    combos = [(0, 1), (0, 2), (1, 1)]
    ok = None
    for rack, slot in combos:
        print(f"  [2] 尝试 rack={rack} slot={slot} ... ", end="", flush=True)
        c = snap7.client.Client()
        try:
            t0 = time.time()
            c.connect(ip, rack, slot, tcp_port=102)
            print(f"连接成功 ({(time.time()-t0)*1000:.0f} ms)")
            ok = (c, rack, slot)
            break
        except Exception as e:
            msg = str(e).strip().splitlines()
            tail = msg[-1] if msg else repr(e)
            print(f"失败: {type(e).__name__}: {tail[:100]}")
            try:
                c.destroy()
            except Exception:
                pass

    if not ok:
        print("\n结论: TCP 通但 S7 通信握手失败, 常见原因:")
        print("      - rack/slot 不对 (S7-1500/1200 试 0/1; S7-300 试 0/2)")
        print("      - TIA CPU 属性未勾选 '允许 PUT/GET 远程访问'")
        print("      - 实例不是 RUN 状态")
        return 4

    c, rack, slot = ok
    print(f"  >>> 请在程序里填写: rack={rack}, slot={slot}")

    print(f"  [3] 读 DB{db} 前 20 字节 ... ", end="", flush=True)
    try:
        data = c.read_area(Areas.DB, db, 0, 20)
        print("成功:", " ".join(f"{b:02X}" for b in data[:10]))
        print(f"\n全部通过: 连接参数 rack={rack}/slot={slot}, DB{db} 可读")
        print("提示: 若读到的全是 0, 说明连接没问题, 只是 PLC 里还没写数据")
        rc = 0
    except Exception as e:
        msg = str(e).strip().splitlines()
        tail = msg[-1] if msg else repr(e)
        print(f"失败: {tail[:120]}")
        print("\n连接已成功但读 DB 失败, 检查:")
        print(f"      - DB{db} 是否在 TIA 项目里存在")
        print(f"      - DB{db} 属性取消勾选 '优化的块访问' (Optimized block access)")
        print("      - 数据块已下载到仿真实例")
        rc = 5

    try:
        c.disconnect()
        c.destroy()
    except Exception:
        pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
