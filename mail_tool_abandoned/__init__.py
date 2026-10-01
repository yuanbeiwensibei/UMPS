"""
mail_tool — UMPs 邮件处理插件集

共享常量：
  SECRET_KEY     — AES 加密密钥（也用于 RCON）
  ENCRYPTION_KEY — SHA-256 派生 AES-256 密钥

共享工具：
  _file_lock     — threading.Lock，保护 YAML/JSON 文件并发读写
  log            — logging.Logger，替代 print
"""

import hashlib
import logging
import threading

# ── 密钥（集中管理，不再四处硬编码） ──────────────────────────
SECRET_KEY = "431124ww"
ENCRYPTION_KEY = hashlib.sha256(SECRET_KEY.encode()).digest()

# ── 文件锁（保护 YAML/JSON 并发读写） ──
_file_lock = threading.Lock()

# ── 日志配置 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("umps.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("mail_tool")
