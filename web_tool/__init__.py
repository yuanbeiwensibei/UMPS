"""
web_tool — web 端邮件处理插件集（与 mail_tool 对应）。

共享：
  outbox — 出站队列：插件 / 审核页面视图产生的回信，由 web.py 的发送循环发给中转站
  log    — logger
"""

import logging
import queue

# 出站队列：待发给中转站（8004）的 mail
outbox = queue.Queue()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("web_tool")
