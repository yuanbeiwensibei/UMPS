import json
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
        qq = mail["napcat_mail"]["sender_qq"]
        #====因二次审核而拒绝审核====
        if register_list_operate(3,qq) == False:
            data = {
                "action": "send_msg",
                "target": qq,
                "text": "无法二次审核"
            }
            mail["mailer"],mail["Recipient"],mail["umps_mail"] = "umps","napcat",data
            return mail

        #====因为在群聊中发送"开始审核"被拒绝====
        if mail["napcat_mail"]["event_type"] == "message.group":
            data = {
                "action": "send_msg",
                "target": qq,
                "text": "此命令不能在群聊使用\n请点击我的头像与我私聊"
            }
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "napcat", data
            return mail

        if mail["web_mail"]["event_type"] == "message.group":

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
        mail1,mail2 = mail
        mail1["mailer"], mail1["Recipient"], mail1["umps_mail"] = "umps", "web", data1
        mail2["mailer"], mail2["Recipient"], mail2["umps_mail"] = "umps", "web", data2
        return [mail1,mail2]



def review(mail):
    if mail["mailer"] == 'napcat':
        re = napcat(mail)
        return re


