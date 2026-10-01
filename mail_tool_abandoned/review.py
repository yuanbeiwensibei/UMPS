"""
审核工具 — 处理审核码验证、AI 判卷、通过/拒绝流程
"""
import base64
import json
import os

import yaml
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from mail_tool import ENCRYPTION_KEY, _file_lock, log
from mail_tool.vice_tool.config import config


def review(mail):
    """审核主入口"""

    # ── 审核群内「开始审核」指令 ──
    if mail.get("mailer") == "napcat":
        nm = mail.get("napcat_mail") or {}
        if nm.get("message") != "开始审核":
            return None
        # 群聊公屏 → 撤回 + 提示私聊
        if nm.get("event_type") == "message.group":
            # 群聊公屏 → 撤回 + 提示私聊
            return _delete_and_reply_group(
                mail, nm["sender_qq"], nm["group_id"], nm["message_id"],
                "[提示]\n请将开始审核的指令私聊发送给我，避免在群内暴露审核信息"
            )
        elif nm.get("event_type") in ("message.private", "message.group_temp"):
            if nm.get("event_type") == "message.private" or \
               nm.get("group_id") == config("审核群"):
                qq = nm["sender_qq"]
                if review_True(qq=qq, type_="query") or review_False(qq=qq, type_="query"):
                    return _reply_napcat(mail, qq, "无法二次审核")
                enc_qq = encryption_and_decryption({"type": "encryption", "content": str(qq)})
                return _reply_napcat(
                    mail, qq,
                    f"[审核]\n你的审核码是：\n===============\n{enc_qq}\n===============\n"
                    f"请进入 utopiasmp.top/review 开始审核（建议复制到浏览器打开）"
                )

    # ── Web / AI 来源 ──
    if mail.get("mailer") not in ("web", "ai"):
        return None
    wm = mail.get("web_mail") or {}
    if wm.get("post_type") not in ("Review_QQ_verification", "Review_answers"):
        return None

    # ── 解密审核码 ──
    if wm["post_type"] == "Review_QQ_verification":
        qq = encryption_and_decryption({"type": "decryption", "content": wm["QQ_to_be_verified"]})
        if qq is False:
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = (
                "umps", "web",
                {"Review_results": False, "reason": "无效的审核密码", "qq": None}
            )
            return mail

        if not review_True(qq=qq, type_="query") and not review_False(qq=qq, type_="query"):
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = (
                "umps", "web",
                {"Review_results": True, "reason": "识别成功", "qq": qq}
            )
            return mail
        else:
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = (
                "umps", "web",
                {"Review_results": False, "reason": "此QQ的审核已提交", "qq": None}
            )
            return mail

    # ── 审核答卷处理 ──
    if wm["post_type"] == "Review_answers":
        qq = int(wm["qq"])

        if mail["mailer"] == "web":
            # Web 提交 → 转发给 AI 判卷
            if not review_True(qq=qq, type_="query") and not review_False(qq=qq, type_="query"):
                mail["mailer"], mail["Recipient"], mail["umps_mail"] = (
                    "umps", "ai",
                    {"post_type": "Correction_the_review"}
                )
                return mail
            else:
                return _reply_napcat(mail, qq, "你的审核已经被处理\n无法二次审核")

        if mail["mailer"] == "ai":
            # AI 返回判卷结果
            if mail.get("ai_mail") is False:
                return _reply_napcat(mail, qq,
                    "[发生错误]\n你好，审核程序出现了一些问题，请联系管理员解决\n"
                    "在此之前，你的提交的答卷无法被审核\n在此之后，你可以重新填写")

            passTrue = mail["ai_mail"]["是否通过"]
            reason = mail["ai_mail"]["评判理由"]

            # 保存答卷
            review_data = {
                "review": passTrue,
                "Multiple_choice_question_score": mail["ai_mail"]["选择题总分"],
                "Question_and_answer_score": mail["ai_mail"]["问答题总分"],
                "reason": reason,
                "answers": wm.get("answers"),
            }
            try:
                os.makedirs("./UMPs/Review", exist_ok=True)
                with _file_lock:
                    with open(f"./UMPs/Review/{qq}.json", "w", encoding="utf-8") as f:
                        json.dump(review_data, f, ensure_ascii=False, indent=4)
            except Exception as e:
                log.exception("保存答卷失败 qq=%s", qq)
                return _reply_napcat(mail, qq,
                    "[发生错误]\n在尝试记录您的答卷时出错了，请联系管理员解决")

            # 更新审核状态
            if passTrue:
                try:
                    review_True(qq=qq, type_="add")
                except Exception as e:
                    log.exception("review_True add 失败 qq=%s", qq)
                    return _reply_napcat(mail, qq,
                        "[发生错误]\n在尝试允许您进入游戏群聊时出错了，请联系管理员解决")

                game_groups = config("游戏群")
                return _reply_napcat(mail, qq,
                    f"[通知]\n你好，恭喜你通过了服务器的审核，从现在开始你是UMP大家族的一员啦！\n"
                    f"现在你可以进入我们的游戏群聊{game_groups}\n"
                    f"在进入群聊的第一时间，你应该仔细阅读服务器手册，否则，你将无法进入游戏！或者错过关键内容")
            else:
                try:
                    review_False(qq=qq, type_="add")
                except Exception as e:
                    log.exception("review_False add 失败 qq=%s", qq)
                    return _reply_napcat(mail, qq,
                        "[发生错误]\n在尝试记录审核结果时出错了，请联系管理员解决")

                return _reply_napcat(mail, qq,
                    f"[通知]\n你好，很遗憾你不满足进入服务器游玩的条件！\n"
                    f"你能来到并支持UMP，是UMP的荣幸，感谢你对UMP的支持与喜爱\n再会\n\n\n理由:{reason}")


def _delete_and_reply_group(mail, qq, group_id, msg_id, text):
    """群聊公屏：撤回原消息 + 发送群提示"""
    m1, m2 = dict(mail), dict(mail)
    m1["mailer"], m1["Recipient"] = "umps", "napcat"
    m1["umps_mail"] = {"action": "delete_msg", "target": msg_id}
    m2["mailer"], m2["Recipient"] = "umps", "napcat"
    m2["umps_mail"] = {
        "action": "send_group_msg", "target": group_id,
        "text": f"{text}\n[CQ:at,qq={qq}]",
    }
    return [m1, m2]


def _reply_napcat(mail, qq, text):
    """构造 napcat 回复邮件，私聊/临时会话自动区分"""
    et = mail.get("napcat_mail", {}).get("event_type", "")
    m = dict(mail)
    m["mailer"], m["Recipient"] = "umps", "napcat"
    if et == "message.private":
        m["umps_mail"] = {"action": "send_private_msg", "target": qq, "text": text}
    else:
        m["umps_mail"] = {
            "action": "send_msg", "target": qq,
            "group_id": config("审核群"), "text": text,
        }
    return m


# ── AES 加解密 ─────────────────────────────────────────────────

def encryption_and_decryption(data):
    """加密或解密审核码。data = { 'type', 'content' }"""

    def _aes_encrypt(plain_text):
        iv = os.urandom(16)
        cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
        padded = pad(plain_text.encode("utf-8"), AES.block_size)
        return base64.urlsafe_b64encode(iv + cipher.encrypt(padded)).decode("utf-8")

    def _aes_decrypt(cipher_text):
        try:
            # 兼容 urlsafe（- → +, _ → /）和 windows 空格（+ → 空格）
            c = cipher_text.replace(" ", "+").replace("-", "+").replace("_", "/")
            raw = base64.b64decode(c)
            # 格式1: base64(IV + ciphertext)
            if len(raw) > 16:
                try:
                    iv, enc = raw[:16], raw[16:]
                    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
                    return unpad(cipher.decrypt(enc), AES.block_size).decode("utf-8")
                except Exception:
                    pass
            # 格式2: 旧格式 — 全零 IV
            iv = b"\x00" * 16
            cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
            return unpad(cipher.decrypt(raw), AES.block_size).decode("utf-8")
        except Exception:
            return None

    if data.get("type") == "encryption":
        return _aes_encrypt(data.get("content", ""))
    elif data.get("type") == "decryption":
        result = _aes_decrypt(data.get("content", ""))
        return result if result is not None else False
    return False


# ── 通过 / 未通过名单管理 ──────────────────────────────────────

def review_True(qq, type_):
    with _file_lock:
        with open("./UMPs/review.yml", "r", encoding="utf-8") as f:
            lst = yaml.safe_load(f)
    if type_ == "query":
        return qq in lst
    if type_ == "add":
        if qq in lst:
            return False
        lst.append(qq)
        try:
            with _file_lock:
                with open("./UMPs/review.yml", "w", encoding="utf-8") as f:
                    yaml.dump(lst, f, default_flow_style=False, allow_unicode=True)
        except Exception:
            return False
        return True


def review_False(qq, type_):
    with _file_lock:
        with open("./UMPs/Review_failed.yml", "r", encoding="utf-8") as f:
            lst = yaml.safe_load(f)
    if type_ == "query":
        return qq in lst
    if type_ == "add":
        if qq in lst:
            return True
        lst.append(qq)
        try:
            with _file_lock:
                with open("./UMPs/Review_failed.yml", "w", encoding="utf-8") as f:
                    yaml.dump(lst, f, default_flow_style=False, allow_unicode=True)
        except Exception:
            return False
        return True
