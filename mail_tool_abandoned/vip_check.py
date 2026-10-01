"""
VIP 过期扫描 — 定时任务，检查并清理过期会员
由 umps.py 的 timing() 每 600 秒调用一次
"""
import datetime
import json
import glob
import os

import yaml

from mail_tool import _file_lock, log


def _read_yml(path):
    with _file_lock:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


def _read_json(path):
    with _file_lock:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def _write_json(path, data):
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


def _get_role_name(qq):
    """从 binding.yml 反查 qq → role_name"""
    binding = _read_yml("./UMPs/binding.yml")
    for name, bound_qq in binding.get("id-qq", {}).items():
        if str(bound_qq) == str(qq):
            return name
    return None


def vip_check():
    """扫描所有玩家数据，处理 VIP 过期。
    返回 list[mail]，每一项都可以被 send_list.append() 消费。
    无过期时返回空列表。
    """
    results = []
    now = datetime.datetime.now()

    pattern = os.path.join("./UMPs/PlayerData", "*.json")
    for path in glob.glob(pattern):
        try:
            pd = _read_json(path)

            vip = pd.get("vip", {})
            vip_type = vip.get("vip_type", "")
            expiry_str = vip.get("vip_Expiration_time", "")

            # 跳过无会员的
            if not vip_type:
                continue

            # 解析到期时间
            try:
                expiry = datetime.datetime.fromisoformat(expiry_str)
            except Exception:
                log.warning("vip_check: 无法解析到期时间 qq=%s expiry=%s", pd.get("qq"), expiry_str)
                continue

            # 未过期 → 跳过
            if now <= expiry:
                continue

            # ── 已过期：处理 ──
            qq = pd.get("qq")

            log.info("vip_check: VIP 过期 qq=%s type=%s expiry=%s", qq, vip_type, expiry_str)

            role_name = _get_role_name(qq)

            # 通知 MC 切换回 default 权限组
            if role_name:
                results.append({
                    "mailer": "umps",
                    "Recipient": "minecraft",
                    "web_mail": "",
                    "umps_mail": {
                        "post_type": "execute_command",
                        "request_id": "vip_expire",
                        "command": f"lp user {role_name} parent set default",
                    },
                    "ai_mail": "",
                    "minecraft_mail": "",
                    "napcat_mail": {},
                    "need": True,
                    "minecraft_online": True,
                    "mail_id": "",
                })

            # 通知玩家
            results.append({
                "mailer": "umps",
                "Recipient": "napcat",
                "web_mail": "",
                "umps_mail": {
                    "action": "send_private_msg",
                    "target": qq,
                    "text": (f"[VIP 过期通知]\n"
                             f"你的 {vip_type.upper()} 会员已过期\n"
                             f"服务器内权限已切换回普通玩家\n"
                             f"感谢你的支持！"),
                },
                "ai_mail": "",
                "minecraft_mail": "",
                "napcat_mail": {},
                "need": True,
                "minecraft_online": True,
                "mail_id": "",
            })

            # 清空 vip 字段
            pd["vip"]["vip_type"] = ""
            pd["vip"]["vip_Expiration_time"] = ""
            _write_json(path, pd)

        except Exception:
            log.exception("vip_check: 处理文件失败 path=%s", path)

    if results:
        log.info("vip_check: 本轮处理了 %s 个过期会员", len(results) // 2)

    return results
