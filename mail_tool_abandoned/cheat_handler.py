"""
反作弊处理 — 接收 MC 日志 → 发 AI 分析 → 记录违规 + 处罚
"""
import datetime
import hashlib
import json
import os

import yaml

from mail_tool import _file_lock, log
from mail_tool.vice_tool.config import config as _cfg
from mail_tool.vice_tool.query import query as _id_query


def _read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with _file_lock:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _find_qq(player_name):
    """通过 binding.yml 的 id-qq 找 QQ"""
    import yaml
    try:
        with _file_lock:
            with open("./UMPs/binding.yml", "r", encoding="utf-8") as f:
                binding = yaml.safe_load(f) or {}
        for name, bound in (binding.get("id-qq") or {}).items():
            if name.lower() == player_name.lower():
                return int(bound)
    except Exception:
        pass
    return None


def _get_game_group():
    groups = _cfg("游戏群", default=[1036440930])
    if isinstance(groups, list):
        return groups[0]
    return groups


def _get_admin_group():
    return _cfg("管理员群", default=0)


def cheat_handler(mail):
    """反作弊主入口"""

    # ====== 入口 A：MC 发来日志 → 转发给 AI ======
    if mail.get("mailer") == "minecraft":
        mm = mail.get("minecraft_mail") or {}
        if mm.get("post_type") != "cheat_log_batch":
            return None

        lines = mm.get("lines", [])
        if not lines:
            return None

        m = dict(mail)
        m["mailer"], m["Recipient"] = "umps", "ai"
        m["umps_mail"] = {
            "post_type": "analyze_cheat",
            "lines": lines,
            "period_start": mm.get("period_start"),
            "period_end": mm.get("period_end"),
        }
        return m

    # ====== 入口 B：AI 返回分析结果 ======
    if mail.get("mailer") == "ai":
        ai_result = mail.get("ai_mail")
        if not isinstance(ai_result, list):
            return None

        period_start = mail.get("umps_mail", {}).get("period_start", 0)
        period_end = mail.get("umps_mail", {}).get("period_end", 0)

        threshold = _cfg("反作弊", "违规分阈值", default=5)
        free_pass_hours = _cfg("反作弊", "免罚窗口小时", default=1)
        game_group = _get_game_group()
        admin_group = _get_admin_group()
        now = datetime.datetime.now()
        results = []

        for entry in ai_result:
            player = entry.get("player", "")
            points = int(entry.get("points", 0))
            reason = entry.get("reason", "")
            evidences = entry.get("evidences", [])

            if points <= 0 or not player:
                continue

            qq = _find_qq(player)
            if not qq:
                continue  # 未绑定跳过

            path = f"./UMPs/CheatRecords/{qq}.json"
            record = _read_json(path) or {
                "qq": qq,
                "player": player,
                "total_points": 0,
                "banned": False,
                "records": [],
            }

            record["player"] = player  # 玩家可能改名

            # ── 免罚金牌：上一次违规是否在窗口内 ──
            penalize = True
            if record["records"]:
                last = record["records"][-1]
                if last.get("penalized"):
                    last_time = datetime.datetime.fromisoformat(last["time"])
                    if (now - last_time).total_seconds() < free_pass_hours * 3600:
                        penalize = False

            rec = {
                "id": hashlib.md5(f"{qq}{now.isoformat()}{period_start}".encode()).hexdigest()[:6],
                "time": now.isoformat(),
                "points": points,
                "reason": reason,
                "evidences": evidences,
                "penalized": penalize,
                "status": "待处理",
                "period_start": period_start,
                "period_end": period_end,
            }
            record["records"].append(rec)

            if penalize:
                record["total_points"] = record.get("total_points", 0) + points

            # ── 检查是否达到临时封禁阈值 ──
            if record["total_points"] >= threshold and not record.get("banned"):
                record["banned"] = True
                results.append({
                    "mailer": "umps", "Recipient": "minecraft", "web_mail": "",
                    "umps_mail": {
                        "post_type": "execute_command",
                        "request_id": f"ban_{qq}",
                        "command": f"/ban {player} 反作弊系统：违规分达到{record['total_points']}",
                    },
                    "ai_mail": "", "minecraft_mail": "", "napcat_mail": {},
                    "need": True, "minecraft_online": True, "mail_id": "",
                })

            _write_json(path, record)

            # ── 通知（每次处罚都发） ──
            if penalize:
                tag = "[封禁]" if record.get("banned") else "[警告]"
                results.append({
                    "mailer": "umps", "Recipient": "napcat", "web_mail": "",
                    "umps_mail": {
                        "action": "send_group_msg", "target": game_group,
                        "text": (
                            f"{tag}\n"
                            f"玩家 {player} 被反作弊系统标记\n"
                            f"违规分：+{points}（当前 {record['total_points']}/{threshold}）\n"
                            f"理由：{reason}"
                        ),
                    },
                    "ai_mail": "", "minecraft_mail": "", "napcat_mail": {},
                    "need": True, "minecraft_online": True, "mail_id": "",
                })
                results.append({
                    "mailer": "umps", "Recipient": "napcat", "web_mail": "",
                    "umps_mail": {
                        "action": "send_private_msg", "target": qq,
                        "text": (
                            f"{tag}\n"
                            f"反作弊系统检测到你的违规行为\n"
                            f"违规分：+{points}（当前 {record['total_points']}/{threshold}）\n"
                            f"理由：{reason}\n"
                            f"如有疑问请联系管理员"
                        ),
                    },
                    "ai_mail": "", "minecraft_mail": "", "napcat_mail": {},
                    "need": True, "minecraft_online": True, "mail_id": "",
                })
                if admin_group:
                    evidence_text = "\n".join(evidences[:3]) if evidences else "无"
                    results.append({
                        "mailer": "umps", "Recipient": "napcat", "web_mail": "",
                        "umps_mail": {
                            "action": "send_group_msg", "target": admin_group,
                            "text": (
                                f"{tag}\n"
                                f"玩家 {player}（QQ: {qq}）\n"
                                f"违规分：+{points}（当前 {record['total_points']}/{threshold}）\n"
                                f"理由：{reason}\n"
                                f"证据概要：{evidence_text}"
                            ),
                        },
                        "ai_mail": "", "minecraft_mail": "", "napcat_mail": {},
                        "need": True, "minecraft_online": True, "mail_id": "",
                    })

        return results if results else None

    return None
