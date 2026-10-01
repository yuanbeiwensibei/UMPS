import json
import yaml

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


def QQ(mail):


def review(mail):
    if mail("mailer") == 'qq':
        QQ(mail)



