"""
兑换工具 — 玩家用赞助订单号兑换水晶 / VIP / SVIP 到游戏内
"""
import json
import os

import yaml

from mail_tool import _file_lock, log
from mail_tool.vice_tool.config import config as _cfg


def _get_vip_duration():
    return _cfg("兑换", "VIP有效期", default=30)


def _get_crystal_amount():
    return _cfg("兑换", "每份水晶数", default=50)

# ── SKU 映射 ──────────────────────────────────────────────────
SKU_MAP = {
    "8c88c58460ca11f183225254001e7c00": "crystal",
    "ae102dca60b911f1955252540025c377": "vip",
    "0e227f6e60ca11f1b47c52540025c377": "svip",
}


# ── 工具函数 ──────────────────────────────────────────────────

def _read_yml(path):
    with _file_lock:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


def _write_yml(path, data):
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _read_json(path):
    with _file_lock:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def _write_json(path, data):
    with _file_lock:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


def _reply(mail, event_type, qq, group_id, text):
    """构造 napcat 回复"""
    m = dict(mail)
    m["mailer"], m["Recipient"] = "umps", "napcat"
    payload = {"text": text}
    if event_type == "message.group":
        payload["action"] = "send_group_msg"
        payload["target"] = group_id
    elif event_type == "message.private":
        payload["action"] = "send_private_msg"
        payload["target"] = qq
    else:
        payload["action"] = "send_msg"
        payload["target"] = qq
        payload["group_id"] = group_id
    m["umps_mail"] = payload
    return m


def _get_role_name(qq):
    """从 binding.yml 反查 qq → role_name"""
    binding = _read_yml("./UMPs/binding.yml")
    for name, bound_qq in binding.get("id-qq", {}).items():
        if str(bound_qq) == str(qq):
            return name
    return None


def _make_mc_mail(mail, role_name, group):
    """构造发给 Minecraft 的 lp 权限切换命令"""
    m = dict(mail)
    m["mailer"] = "umps"
    m["Recipient"] = "minecraft"
    m["umps_mail"] = {
        "post_type": "execute_command",
        "request_id": f"vip_{group}",
        "command": f"lp user {role_name} parent set {group}",
    }
    return m


# ── 主函数 ────────────────────────────────────────────────────

def exchange(mail):
    """兑换入口：识别"兑换 <订单号>"消息，执行水晶/VIP/SVIP 发放"""

    if mail.get("mailer") != "napcat":
        return None

    event = mail.get("napcat_mail") or {}
    event_type = event.get("event_type", "")
    if event_type not in ("message.group", "message.private", "message.group_temp"):
        return None

    message = event.get("message", "")
    if len(message) < 5:
        return None
    if not (message.startswith("兑换 ") or message == "兑换"):
        return None

    # 解析订单号
    out_trade_no_player = message[3:] if message.startswith("兑换 ") else message[2:]

    qq = event["sender_qq"]
    group_id = event.get("group_id", 0)

    # ── 群聊风险拦截 ──
    if event_type == "message.group":
        m1 = dict(mail)
        m1["mailer"], m1["Recipient"], m1["umps_mail"] = "umps", "napcat", {
            "action": "send_group_msg", "target": group_id,
            "text": "[风险提示]\n识别到兑换码消息，你不应该在群聊兑换！请私聊我",
        }
        m2 = dict(mail)
        m2["mailer"], m2["Recipient"], m2["umps_mail"] = "umps", "napcat", {
            "action": "delete_msg", "target": event.get("message_id"),
        }
        return [m1, m2]

    # ── 检查玩家是否已绑定 ──
    if not os.path.exists(f"./UMPs/PlayerData/{qq}.json"):
        return _reply(mail, event_type, qq, group_id,
            "[兑换结果]\n你还没有绑定 Minecraft 角色，请先绑定后再兑换")

    # ── 检查订单是否存在 ──
    afd = _read_yml("./UMPs/afdian.yml")
    if out_trade_no_player not in afd.get("out_trade_no", []):
        return _reply(mail, event_type, qq, group_id,
            "[兑换结果]\n不正确的或者已被使用的订单号")

    # ── 获取商品信息 ──
    sku_type = afd.get("sku", {}).get(out_trade_no_player, "")
    count = afd.get("count", {}).get(out_trade_no_player, 1)

    # ── 执行兑换 ──
    if sku_type == "crystal":
        return _exchange_crystal(mail, event_type, qq, group_id, out_trade_no_player, count)
    elif sku_type in ("vip", "svip"):
        return _exchange_vip(mail, event_type, qq, group_id, out_trade_no_player, sku_type)
    else:
        return _reply(mail, event_type, qq, group_id,
            f"[兑换结果]\n未知商品类型: {sku_type}，请联系管理员")


def _exchange_crystal(mail, event_type, qq, group_id, order_no, count):
    """兑换水晶"""
    try:
        pd = _read_json(f"./UMPs/PlayerData/{qq}.json")
        amount = _get_crystal_amount() * count
        pd["crystal"] = pd.get("crystal", 0) + amount
        _write_json(f"./UMPs/PlayerData/{qq}.json", pd)

        # 标记订单已使用
        _mark_order_used(order_no)

        log.info("兑换水晶成功 qq=%s order=%s amount=%s", qq, order_no, amount)
        return _reply(mail, event_type, qq, group_id,
            f"[兑换成功]\n你获得了 {amount} 水晶！\n当前水晶: {pd['crystal']}")
    except Exception as e:
        log.exception("水晶兑换失败 qq=%s order=%s", qq, order_no)
        return _reply(mail, event_type, qq, group_id,
            "[出错]\n兑换过程出现异常，请联系管理员")


def _exchange_vip(mail, event_type, qq, group_id, order_no, sku_type):
    """兑换 VIP / SVIP — 含升级补偿、续费叠加、MC 权限切换"""
    import datetime

    try:
        pd = _read_json(f"./UMPs/PlayerData/{qq}.json")

        # 初始化 vip 字段
        pd.setdefault("vip", {"vip_Expiration_time": "", "vip_type": ""})
        old_type = pd["vip"].get("vip_type", "")
        old_expiry_str = pd["vip"].get("vip_Expiration_time", "")

        # 解析旧到期时间
        old_expiry = None
        if old_expiry_str:
            try:
                old_expiry = datetime.datetime.fromisoformat(old_expiry_str)
            except Exception:
                old_expiry = None

        now = datetime.datetime.now()
        expired = old_expiry is not None and now > old_expiry
        role_name = _get_role_name(qq)
        new_expiry = now + datetime.timedelta(days=_get_vip_duration())
        results = []

        # ── 无会员 或 已过期 → 当作新开通 ──
        if old_type == "" or expired:
            pd["vip"]["vip_type"] = sku_type
            pd["vip"]["vip_Expiration_time"] = new_expiry.isoformat()

            if role_name:
                results.append(_make_mc_mail(mail, role_name, sku_type))

            msg = (f"[兑换成功]\n你获得了 {sku_type.upper()} 会员！"
                   f"\n到期时间: {new_expiry.strftime('%Y-%m-%d %H:%M')}")
            results.append(_reply(mail, event_type, qq, group_id, msg))

        # ── VIP 未过期 ──
        elif old_type == "vip":
            if sku_type == "vip":
                # 续费：叠加 30 天
                pd["vip"]["vip_Expiration_time"] = (old_expiry + datetime.timedelta(days=_get_vip_duration())).isoformat()
                if role_name:
                    results.append(_make_mc_mail(mail, role_name, "vip"))
                new_total = old_expiry + datetime.timedelta(days=_get_vip_duration())
                msg = (f"[兑换成功]\nVIP 会员已续费 30 天！"
                       f"\n到期时间: {new_total.strftime('%Y-%m-%d %H:%M')}")
                results.append(_reply(mail, event_type, qq, group_id, msg))
            else:
                # 升级 svip：剩余天数 × 8 水晶补偿
                remaining_days = max(1, (old_expiry - now).days)
                compensation = remaining_days * 8
                pd["crystal"] = pd.get("crystal", 0) + compensation
                pd["vip"]["vip_type"] = "svip"
                pd["vip"]["vip_Expiration_time"] = new_expiry.isoformat()

                if role_name:
                    results.append(_make_mc_mail(mail, role_name, "svip"))

                msg = (f"[兑换成功]\nVIP → SVIP 升级完成！"
                       f"\n剩余 VIP {remaining_days} 天已转换为 {compensation} 水晶"
                       f"\nSVIP 到期时间: {new_expiry.strftime('%Y-%m-%d %H:%M')}"
                       f"\n当前水晶: {pd['crystal']}")
                results.append(_reply(mail, event_type, qq, group_id, msg))

        # ── SVIP 未过期 ──
        elif old_type == "svip":
            if sku_type == "svip":
                # 续费：叠加 30 天
                pd["vip"]["vip_Expiration_time"] = (old_expiry + datetime.timedelta(days=_get_vip_duration())).isoformat()
                if role_name:
                    results.append(_make_mc_mail(mail, role_name, "svip"))
                new_total = old_expiry + datetime.timedelta(days=_get_vip_duration())
                msg = (f"[兑换成功]\nSVIP 会员已续费 30 天！"
                       f"\n到期时间: {new_total.strftime('%Y-%m-%d %H:%M')}")
                results.append(_reply(mail, event_type, qq, group_id, msg))
            else:
                # svip → vip：不降级，给 251 水晶
                pd["crystal"] = pd.get("crystal", 0) + 251

                msg = (f"[兑换结果]\n检测到你已有 SVIP 会员，VIP 订单已替换为等价物品"
                       f"\n你获得了 251 水晶！\n当前水晶: {pd['crystal']}")
                results.append(_reply(mail, event_type, qq, group_id, msg))

        _write_json(f"./UMPs/PlayerData/{qq}.json", pd)
        _mark_order_used(order_no)

        log.info("VIP兑换完成 qq=%s order=%s new=%s old=%s", qq, order_no, sku_type, old_type)

        if len(results) == 1:
            return results[0]
        return results

    except Exception as e:
        log.exception("VIP兑换失败 qq=%s order=%s", qq, order_no)
        return _reply(mail, event_type, qq, group_id,
            "[出错]\n兑换过程出现异常，请联系管理员")


def _mark_order_used(order_no):
    """从可用订单列表中移除（标记已使用）"""
    afd = _read_yml("./UMPs/afdian.yml")
    if order_no in afd.get("out_trade_no", []):
        afd["out_trade_no"].remove(order_no)
        _write_yml("./UMPs/afdian.yml", afd)
