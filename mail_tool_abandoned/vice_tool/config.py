"""
配置读取工具 — 支持嵌套 key，缺失时返回默认值

用法：
    config("审核群")               → 594051605
    config("checkin", "crystal_normal") → [10, 15]
    config("checkin", "xxx", default=5) → 5
"""
import yaml

from mail_tool import _file_lock


def config(*keys, default=None):
    """读取配置项，支持任意深度嵌套。key 不存在时返回 default。

    每次调用都重新读文件 — 保证线程安全且修改即时生效，
    代价很小（毫秒级 YAML 解析）。
    """
    try:
        with _file_lock:
            with open("./UMPs/config.yml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg = {}

    for k in keys:
        if isinstance(cfg, dict) and k in cfg:
            cfg = cfg[k]
        else:
            return default

    return cfg
