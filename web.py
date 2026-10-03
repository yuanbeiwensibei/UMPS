"""
web.py —— web 端核心进程（与 umps.py 同级、同等重要）。

职责（对标 umps.py）：
  1. 连接中转站 8004，收发 web_mail（umps 连 8001）；
  2. 用 web_tool 插件列表分发邮件（umps 用 mail_tool）；
  3. 启动 Django 审核页面服务（监听 80 端口）。

并发模型：
  用 websockets.sync.client（线程版），避免 asyncio 在 Windows/Python3.14
  上创建事件循环时偶发卡死的问题（与 TS2.py 同理）。
"""

import json
import os
import queue
import sys
import threading
import time

from websockets.sync.client import connect

# ── 配置 ──────────────────────────────────────────────────────
HUB_URL = "ws://127.0.0.1:8004"   # 中转站 web 端口
WEB_ADDR = "0.0.0.0:80"           # 审核页面监听地址（80 端口）

# 确保能 import 根目录下的 web_tool 插件集
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from web_tool import log, outbox          # noqa: E402
from web_tool import review               # noqa: E402

# ── 插件注册（像 umps.py 的 mail_tool 列表）──────────────────
web_tool_list = [review.review]


def _handle_mail(mail):
    """分发一封 mail：按顺序喂给插件，第一个返回非 None 的插件认领。"""
    for plugin in web_tool_list:
        try:
            re = plugin(mail)
        except Exception as e:
            log.exception("插件 %s 出错", getattr(plugin, "__name__", str(plugin)))
            continue
        if re is not None:
            items = re if isinstance(re, list) else [re]
            for m in items:
                outbox.put(m)
            return
    log.debug("邮件未被任何插件处理: %s", mail.get("web_mail", {}).get("post_type"))


def _flush(ws):
    """把 outbox 里的回信全部发给中转站。"""
    while True:
        try:
            mail = outbox.get_nowait()
        except queue.Empty:
            return
        try:
            ws.send(json.dumps(mail, ensure_ascii=False))
            log.info("已发送 %s -> %s",
                     mail.get("web_mail", {}).get("post_type"), mail.get("Recipient"))
        except Exception:
            outbox.put(mail)  # 发送失败放回，重连后再发
            return


def ws_loop():
    """连接中转站 8004，循环收发邮件。"""
    while True:
        try:
            with connect(HUB_URL, open_timeout=10) as ws:
                log.info("已连接中转站 %s", HUB_URL)
                while True:
                    _flush(ws)
                    try:
                        raw = ws.recv(timeout=0.5)
                    except TimeoutError:
                        continue
                    if raw is None:
                        break
                    try:
                        mail = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    _handle_mail(mail)
        except Exception as e:
            log.warning("连接断开，5 秒后重连: %s", e)
            time.sleep(5)


def start_django():
    """启动 Django 审核页面服务（监听 80 端口）。"""
    web_site_dir = os.path.join(ROOT, "web_site")
    if web_site_dir not in sys.path:
        sys.path.insert(0, web_site_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_site.settings")

    import django
    django.setup()

    from django.core.management import call_command
    log.info("启动审核页面服务 %s", WEB_ADDR)
    # use_reloader=False：关闭 autoreload，避免它把 web.py 的 main() 再执行一遍
    # （否则 ws 客户端线程会被起两次、审核会话状态被拆到两个进程）。
    call_command("runserver", WEB_ADDR, use_reloader=False)


def main():
    # 起 WebSocket 客户端线程（连 8004）
    threading.Thread(target=ws_loop, daemon=True).start()
    # 起 Django 页面服务（阻塞）
    start_django()


if __name__ == "__main__":
    main()
