import json
import copy
import yaml
from mail_tool.player_data_management import register_list_operate
"""
这里将负责审核的所有事情，主要包括AI端，QQ端和web端
"""


"""
收到的消息格式参考：
data = {
    'mailer': 'web',
    'Recipient': 'umps',
    'web_mail': '',
    'umps_mail': '',
    'ai_mail': '',
    'minecraft_mail': '',
    'napcat_mail': '',
    'need': True,
    'minecraft_online': True
    'mail_id': ''
}
"""


def napcat(mail):

    if mail["napcat_mail"]["message"] == '开始审核':
        qq = mail.get('napcat_mail', {}).get('sender_qq')
        #====因二次审核而拒绝审核====
        if register_list_operate(3,qq) == True:
            data = {
                "action": "send_msg",
                "target": qq,
                "group_id": 594051605,
                "text": "不能二次审核"
            }
            mail["mailer"],mail["Recipient"],mail["umps_mail"] = "umps","napcat",data
            return mail

        #====因为在群聊中发送"开始审核"被拒绝====
        if mail["napcat_mail"]["event_type"] == "message.group":
            data = {
                "action": "send_group_msg",
                "target": mail["napcat_mail"]["group_id"],
                "text": "此命令不能在群聊使用\n请点击我的头像与我私聊"
            }
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "napcat", data
            return mail



        #====通过验证，发送审核链接====
        data1 = {
            "post_type": "open_review_link",
            "qq": qq,
            "request_id": ""
        }
        data2 = {
            "action": "send_msg",
            "target": qq,
            "group_id": 594051605,
            "text": "正在准备链接，请稍后..."
        }
        mail1, mail2 = copy.deepcopy(mail), copy.deepcopy(mail)
        mail1["mailer"], mail1["Recipient"], mail1["umps_mail"] = "umps", "web", data1
        mail2["mailer"], mail2["Recipient"], mail2["umps_mail"] = "umps", "napcat", data2
        return [mail1,mail2]


def web(mail):
    qq = mail["web_mail"]["qq"]
    # ====收到返回的链接，发送到QQ====
    if mail.get('web_mail', {}).get('post_type') == "review_link_ready":
        data = {
            "action": "send_msg",
            "target": qq,
            "group_id": 594051605,
            "text": f"请将下面的链接复制到浏览器打开进行审核➡\n{mail["web_mail"]["url"]}\n链接30分钟内有效"
        }
        mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "napcat", data
        return mail

    # ====收到返回的答题卡，转发给 AI 判卷====
    if mail.get('web_mail', {}).get('post_type') == "review_answers":
        #====已经有审核记录了，拒绝评审====
        if register_list_operate(3, qq):
            data = {
                "action": "send_msg",
                "target": qq,
                "group_id": 594051605,
                "text": "我刚刚收到了你的一份答题卡，但是因为你已经接受过审核了，因此我不会处理这份答题卡"
            }
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "napcat", data
            return mail

        #====创建评审空文件并送检====
        with open(f"./UMPs/PlayerData/ReviewData/{qq}.json", "w", encoding="utf-8") as f:
            json.dump({"answer_sheet": mail.get('web_mail', {}).get('answers')}, f, ensure_ascii=False, indent=4)
        data = {
            "post_type": "Correction_the_review",
            "answers": mail.get('web_mail', {}).get('answers'),
            "qq": qq
        }
        mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "ai", data
        return mail


def ai(mail):
    ai_re = mail["ai_mail"]
    #====判卷失败，提示玩家转人工====
    if ai_re.get("error") is True:
        data = {
            "action": "send_msg",
            "target": ai_re["qq"],
            "group_id": 594051605,
            "text": "自动审核出现错误，已转交至人工审核"
        }
        try:
            register_list_operate(5, ai_re["qq"])
        except:
            data = {
                "action": "send_msg",
                "target": ai_re["qq"],
                "group_id": 594051605,
                "text": "审核出现重大错误，请联系管理员处理"
            }
        mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "napcat", data
        return mail
    #开始评卷
    qq = ai_re["qq"]  # 谁
    passed = ai_re["是否通过"]  # 审核结果
    reason = ai_re["评判理由"]
    score_m = ai_re["选择题总分"]
    score_q = ai_re["问答题总分"]
    review_data = {
        "passed": passed,
        "reason": reason,
        "score_m": score_m,
        "score_q": score_q,
        "qq": qq
    }
    #====保存答题卡时出错====
    re = register_list_operate(4, review_data)
    if re is False:
        data = {
            "action": "send_msg",
            "target": qq,
            "group_id": 594051605,
            "text": "在尝试保存答题卡时出现错误，请联系管理员尝试"
        }
        mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "napcat", data
        return mail
    #====ai审核通过====
    if passed is True:
        data = {
            "action": "send_msg",
            "target": qq,
            "group_id": 594051605,
            "text": "恭喜你通过服务器的审核！\n加入大群->1036440930\n一定要先看公告哦"
        }
        mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "napcat", data
        return mail
    #====ai审核不通过，转移人工====
    if passed is False:
        re = register_list_operate(5, qq)
        #添加人工审核名单纯出错
        if re is False:
            data = {
                "action": "send_msg",
                "target": qq,
                "group_id": 594051605,
                "text": "在尝试保存答题卡时出现错误，请联系管理员尝试\n且你没有通过初审"
            }
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "napcat", data
            return mail
        #正常进行
        data = {
            "action": "send_msg",
            "target": qq,
            "group_id": 594051605,
            "text": "你的答题初审并没有通过，接下来会送至人工审核\n审核通常在24h内完成，请耐心等待"
        }
        mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "napcat", data
        return mail










def review(mail):
    if mail["mailer"] == 'napcat':
        re = napcat(mail)
        return re
    if mail["mailer"] == 'web':
        re = web(mail)
        return re
    if mail["mailer"] == 'ai':
        re = ai(mail)
        return re


