import asyncio
import json
import websockets
from datetime import datetime

# 连接配置
NAPACT_URL = "ws://127.0.0.1:6000"
HUB_URL = "ws://127.0.0.1:8003"


async def napcat_client():
    """连接 napcat 和中转站"""
    while True:
        try:
            async with websockets.connect(NAPACT_URL) as napcat, \
                    websockets.connect(HUB_URL) as hub:
                print("Napcat 客户端已连接")
                print(f"Napcat 地址: {NAPACT_URL}")
                print(f"中转站地址: {HUB_URL}")
                print("-" * 50)

                # 心跳任务（对中转站）
                async def heartbeat():
                    while True:
                        await asyncio.sleep(15)
                        try:
                            await hub.send(json.dumps({"type": "heartbeat"}))
                        except:
                            break

                asyncio.create_task(heartbeat())

                # 同时监听 napcat 和 hub
                async def listen_napcat():
                    """监听 Napcat 原始消息，转换为老代码格式后转发给中转站"""
                    async for message in napcat:
                        try:
                            raw_data = json.loads(message)

                            # 过滤心跳
                            if raw_data.get("post_type") == "meta_event":
                                continue

                            # 过滤无用的通知消息
                            post_type = raw_data.get("post_type")
                            notice_type = raw_data.get("notice_type")
                            sub_type = raw_data.get("sub_type")

                            # 过滤掉"正在输入"的通知
                            if post_type == "notice" and notice_type == "notify" and sub_type == "input_status":
                                continue

                            # 显示原始 Napcat 消息
                            print(f"\n[Napcat 收到原始消息] {datetime.now()}")
                            print(json.dumps(raw_data, ensure_ascii=False, indent=2))

                            # 按照你老代码的格式转换
                            mail = convert_to_mail(raw_data)
                            if mail:
                                await hub.send(json.dumps(mail))
                                print(f"[转发] 已发送到中转站: napcat -> umps\n")

                        except Exception as e:
                            print(f"处理 Napcat 消息出错: {e}")

                async def listen_hub():
                    """监听中转站消息，发送给 Napcat"""
                    async for message in hub:
                        try:
                            data = json.loads(message)

                            # 如果是发给 napcat 的邮件
                            if data.get('Recipient') == 'napcat':
                                umps_mail = data.get('umps_mail', {})
                                if umps_mail:
                                    send_msg = build_onebot_msg(umps_mail)
                                    if send_msg:
                                        await napcat.send(json.dumps(send_msg))
                                        print(f"\n[Napcat 发送消息] {datetime.now()}")
                                        print(json.dumps(send_msg, ensure_ascii=False, indent=2))

                        except Exception as e:
                            print(f"处理中转站消息出错: {e}")

                # 并发运行两个监听任务
                await asyncio.gather(listen_napcat(), listen_hub())

        except Exception as e:
            print(f"连接断开: {e}，5秒后重连...")
            await asyncio.sleep(5)


def to_int(v):
    """安全转 int，str/int 都行，None 返回 None"""
    if v is None:
        return None
    return int(v)


def build_onebot_msg(umps_mail):
    """
    将 umps_mail 转换为 OneBot 发送格式：

        {"action": "send_group_msg",          "target": 123, "text": "hello"}
        {"action": "send_private_msg",        "target": 123, "text": "hello"}
        {"action": "send_msg",                "target": 123, "group_id": 456, "text": "hello"}
        {"action": "set_group_add_request",   "flag": "abc", "sub_type": "add", "approve": true}
    """
    # ====== 新格式：有 action 字段 ======
    action = umps_mail.get("action")
    if action:
        text = umps_mail.get("text")
        target = to_int(umps_mail.get("target"))
        group_id = to_int(umps_mail.get("group_id"))
        flag = umps_mail.get("flag")
        sub_type = umps_mail.get("sub_type")
        approve = umps_mail.get("approve")
        reason = umps_mail.get("reason")

        # 带 text 的消息类 action：构造 message 数组
        if text is not None:
            # send_group_msg / send_private_msg / send_msg
            params = {
                "message": [{"type": "text", "data": {"text": text}}]
            }
            if action == "send_group_msg":
                params["group_id"] = target
            elif action == "send_private_msg":
                params["user_id"] = target
            elif action == "send_msg":
                # 群临时会话：同时带 user_id 和 group_id
                params["message_type"] = "private"
                params["user_id"] = target
                if group_id:
                    params["group_id"] = group_id
            return {"action": action, "params": params}

        # set_group_add_request 类 action
        elif action == "set_group_add_request":
            params = {"flag": flag, "sub_type": sub_type, "approve": approve}
            if reason:
                params["reason"] = reason
            return {"action": action, "params": params}

        # delete_msg：撤回消息，只需要 message_id
        elif action == "delete_msg":
            return {"action": "delete_msg", "params": {"message_id": target}}

        # 其他纯 action（直接透传 params，备用的扩展点）
        return {"action": action, "params": {}}

    return None


def extract_message_text(raw_data):
    """遍历 message[] 数组，拼接所有 type=text 的片段"""
    message_array = raw_data.get("message", [])
    parts = []
    for seg in message_array:
        if seg.get("type") == "text":
            t = seg.get("data", {}).get("text", "")
            if t:
                parts.append(t)
    return "".join(parts) if parts else None


def convert_to_mail(raw_data):
    """
    将 napcat 原始消息转换为邮件格式
    napcat_mail 内统一使用 event_type 标识事件类型
    """
    post_type = raw_data.get("post_type")
    msg_type = raw_data.get("message_type")
    sub_type = raw_data.get("sub_type")
    notice_type = raw_data.get("notice_type")
    request_type = raw_data.get("request_type")
    user_id = raw_data.get("user_id")
    group_id = raw_data.get("group_id")
    t = raw_data.get("time")
    sender = raw_data.get("sender", {})

    sender_nickname = sender.get("nickname") if isinstance(sender, dict) else None
    raw_message = raw_data.get("raw_message")
    message_array = raw_data.get("message")

    # ====== 消息事件 ======
    if post_type == "message":
        message_text = extract_message_text(raw_data)

        # 群聊
        if msg_type == "group":
            event_type = "message.group"
        # 私聊 → 区分好友私聊 vs 群临时会话
        elif msg_type == "private":
            if sub_type == "group":
                event_type = "message.group_temp"
            else:
                event_type = "message.private"
        else:
            event_type = f"message.{msg_type}"

        napcat_mail = {
            "event_type": event_type,
            "sender_qq": user_id,
            "time": t,
            "post_type": post_type,
            "message_type": msg_type,
            "sub_type": sub_type,
            "notice_type": notice_type,
            "group_id": group_id,
            "message_id": raw_data.get("message_id"),
            "sender_nickname": sender_nickname,
            "message": message_text,
            "raw_message": raw_message,
            "message_array": message_array,
        }

        return {
            "mailer": "napcat",
            "Recipient": "umps",
            "web_mail": "",
            "umps_mail": "",
            "ai_mail": "",
            "minecraft_mail": "",
            "napcat_mail": napcat_mail,
            "need": True,
            "minecraft_online": True,
            "mail_id": f"napcat_{raw_data.get('message_id', t)}"
        }

    # ====== 通知事件 ======
    elif post_type == "notice":
        if notice_type == "group_increase":
            event_type = "notice.group_increase"
        elif notice_type == "group_decrease":
            event_type = "notice.group_decrease"
        else:
            event_type = f"notice.{notice_type}"

        napcat_mail = {
            "event_type": event_type,
            "sender_qq": user_id,
            "time": t,
            "post_type": post_type,
            "notice_type": notice_type,
            "sub_type": sub_type,
            "group_id": group_id,
            "operator_id": raw_data.get("operator_id"),
            "message": None,
            "message_type": None,
        }

        return {
            "mailer": "napcat",
            "Recipient": "umps",
            "web_mail": "",
            "umps_mail": "",
            "ai_mail": "",
            "minecraft_mail": "",
            "napcat_mail": napcat_mail,
            "need": True,
            "minecraft_online": True,
            "mail_id": f"napcat_notice_{t}"
        }

    # ====== 请求事件（加群申请等） ======
    elif post_type == "request":
        if request_type == "group":
            event_type = "request.group_add"
        else:
            event_type = f"request.{request_type}"

        napcat_mail = {
            "event_type": event_type,
            "sender_qq": user_id,
            "time": t,
            "post_type": post_type,
            "request_type": request_type,
            "sub_type": sub_type,
            "group_id": group_id,
            "comment": raw_data.get("comment"),
            "flag": raw_data.get("flag"),
            "message": None,
            "message_type": None,
            "notice_type": None,
        }

        return {
            "mailer": "napcat",
            "Recipient": "umps",
            "web_mail": "",
            "umps_mail": "",
            "ai_mail": "",
            "minecraft_mail": "",
            "napcat_mail": napcat_mail,
            "need": True,
            "minecraft_online": True,
            "mail_id": f"napcat_request_{t}"
        }

    return None


if __name__ == "__main__":
    asyncio.run(napcat_client())