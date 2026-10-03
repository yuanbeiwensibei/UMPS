"""TS 2.0 —— WebSocket 中转站（同步/多线程版，不依赖 asyncio）

作用与 TS.py 相同：
  1. 在 8001~8005 各起一个 WebSocket 服务器，分别代表 umps / minecraft / napcat / web / ai；
  2. 收到 JSON 消息后，按 mailer -> Recipient 转发给对应程序；
  3. 消息里若带 minecraft_online 字段，则用 minecraft 当前在线状态覆盖它；
  4. minecraft 靠心跳维持在线（15s 检查 / 30s 超时），其余程序始终在线。

为什么不用 asyncio：
  在 Windows 上 asyncio 创建事件循环时要建一个 self-pipe（socket.socketpair），
  而 CPython 的 socketpair 在 Windows 是纯 Python 的 _fallback_socketpair——它会
  在 127.0.0.1 上自连一次。本机（Python 3.14.0b4）这一步会偶发卡死在 accept()，
  于是程序连一行日志都打不出来。这里改用 websockets 的线程版 API
  （websockets.sync.server）：每端口一个服务线程、每连接一个处理线程，
  全程不创建事件循环，稳定性不受该问题影响。
"""

import json
import threading
import time
from datetime import datetime

from websockets.sync.server import serve

HEARTBEAT_INTERVAL = 15  # 秒：多久检查一次心跳
HEARTBEAT_TIMEOUT = 30   # 秒：多久没心跳就判 minecraft 离线

# 程序 id -> 运行时状态。needs_beat 表示该程序需要靠心跳判在线。
STATE = {
    "umps":      {"port": 8001, "needs_beat": False, "online": True,  "last_beat": None, "conns": set()},
    "minecraft": {"port": 8002, "needs_beat": True,  "online": False, "last_beat": None, "conns": set()},
    "napcat":    {"port": 8003, "needs_beat": False, "online": True,  "last_beat": None, "conns": set()},
    "web":       {"port": 8004, "needs_beat": False, "online": True,  "last_beat": None, "conns": set()},
    "ai":        {"port": 8005, "needs_beat": False, "online": True,  "last_beat": None, "conns": set()},
}

LOCK = threading.Lock()  # 保护 STATE 里的 online / last_beat / conns


def log(text):
    print(f"[{datetime.now():%H:%M:%S}] {text}", flush=True)


def check_heartbeat():
    """后台线程：只有需要心跳的程序（minecraft）会被判离线。"""
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        with LOCK:
            s = STATE["minecraft"]
            if s["online"] and s["last_beat"] is not None:
                if time.time() - s["last_beat"] > HEARTBEAT_TIMEOUT:
                    s["online"] = False
                    log("minecraft 心跳超时，已离线")


def forward(recipient, data):
    """把消息转发给 recipient 这个程序的所有连接。"""
    with LOCK:
        s = STATE.get(recipient)
        if s is None:
            log(f"错误: 无效的接收者 {recipient}")
            return
        conns = list(s["conns"])

    if not conns:
        log(f"{recipient} 当前无连接，消息丢弃")
        return
    for conn in conns:
        try:
            conn.send(json.dumps(data, ensure_ascii=False))
            log(f"已转发消息给 {recipient}")
        except Exception as e:
            log(f"发送给 {recipient} 失败: {e}")


def handle(conn, pid):
    """处理某个程序的一条连接（每个连接跑在一个线程里）。"""
    s = STATE[pid]
    with LOCK:
        s["conns"].add(conn)
        if s["needs_beat"]:
            log(f"{pid} 已连接")
        else:
            s["online"] = True
            log(f"{pid} 已连接（始终在线）")

    try:
        for raw in conn:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                log(f"错误: 无效的 JSON 格式: {raw}")
                continue

            # 心跳：任何程序都回 pong；只有需要心跳的程序据此判在线
            if data.get("type") == "heartbeat":
                with LOCK:
                    s["last_beat"] = time.time()
                    if s["needs_beat"] and not s["online"]:
                        s["online"] = True
                        log(f"{pid} 心跳正常，已上线")
                conn.send(json.dumps({"type": "pong"}))
                continue

            sender = data.get("mailer")
            recipient = data.get("Recipient")
            log(f"收到消息: {sender} -> {recipient}")

            # 用 minecraft 当前状态覆盖消息里的字段
            if "minecraft_online" in data:
                with LOCK:
                    data["minecraft_online"] = STATE["minecraft"]["online"]
                log(f"已更新 minecraft_online = {data['minecraft_online']}")

            forward(recipient, data)

    except Exception as e:
        log(f"{pid} 连接异常: {e}")
    finally:
        with LOCK:
            s["conns"].discard(conn)
            if s["needs_beat"] and not s["conns"]:
                s["online"] = False
                s["last_beat"] = None
                log(f"{pid} 已离线（无连接）")
            else:
                log(f"{pid} 连接断开（仍标记为在线）")


def main():
    servers = []
    for pid, s in STATE.items():
        server = serve(lambda conn, p=pid: handle(conn, p), "0.0.0.0", s["port"])
        servers.append(server)
        tag = "需要心跳" if s["needs_beat"] else "始终在线"
        log(f"[启动] {pid} -> 端口 {s['port']} ({tag})")

    threading.Thread(target=check_heartbeat, daemon=True).start()
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()

    sep = "=" * 50
    print(sep, flush=True)
    print("中转站已启动", flush=True)
    for pid, s in STATE.items():
        print(f"  {pid:<10} ws://服务器IP:{s['port']}", flush=True)
    print(f"心跳: 每 {HEARTBEAT_INTERVAL}s 检查 / {HEARTBEAT_TIMEOUT}s 超时（仅 minecraft）", flush=True)
    print(sep, flush=True)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        log("正在关闭...")
        for server in servers:
            server.shutdown()


if __name__ == "__main__":
    main()
