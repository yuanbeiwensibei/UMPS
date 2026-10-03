import asyncio
import json
import requests
import websockets
from mail_tool.File_Check import File_Check
from mail_tool.review import review

TransferStation = None
mail_queue = [] #接收到的消息待处理列表
send_list = [] #待发送列表
timing_time_set = 600 #定时任务触发时间间隔

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


#主要工具注册
mail_tool = [review]

#定时工具注册
timing_tool = []

"""
websocket连接主函数
"""
async def websocket():
    global TransferStation
    while True:
        try:
            async with websockets.connect("ws://127.0.0.1:8001") as TransferStation:
                print("中转站已连接成功")
                async for response in TransferStation:
                    # 处理消息为json
                    mail = json.loads(response)
                    mail_queue.append(mail) #讲消息添加进待处理列表

        except Exception as e:
            print(f"websocket链接断开，将在3s后重试:{e}")
            await asyncio.sleep(3)

"""

"""
async def deal_with():
    while True:

        if len(mail_queue) == 0: #列表没有待处理
            await asyncio.sleep(0.1)
            continue

        try:
            mail = mail_queue.pop(0)
            # 噪声过滤：静默忽略已知的无关事件类型
            noise_types = {
                "minecraft": ["log_batch"],
            }
            if mail.get("mailer") in noise_types:
                ptype = (mail.get(f"{mail['mailer']}_mail") or {}).get("post_type", "")
                if ptype in noise_types[mail["mailer"]]:
                    continue
            print(f'收到邮件{mail}')

            # 循环工具列表
            Processed = 0
            for i in mail_tool:
                re = i(mail)
                if re != None:
                    if type(re) == dict:
                        send_list.append(re)
                        Processed = 1
                        break
                    if type(re) == list:
                        for ii in re:
                            send_list.append(ii)
                        Processed = 1
                        break
            if Processed == 0:
                print(f'{mail["mailer"]}发送来的邮件没有工具处理\n邮件：{mail}')

        except Exception as e:
            print(f'deal_with函数错误报告：{e}')





async def send():
    while True:
        if len(send_list) > 0:

            try:
                mail_send = send_list.pop(0)
                print(f'发送:{mail_send}')
                await TransferStation.send(json.dumps(mail_send))
                await asyncio.sleep(1)
            except Exception as e:
                print(f'send函数出错:{e}')
        else:
            await asyncio.sleep(0.1)



async def timing():
    while True:
        for i in timing_tool:
            re = i()
            if re is not None:
                if isinstance(re, list):
                    for item in re:
                        send_list.append(item)
                else:
                    send_list.append(re)
        print('完成定时任务')
        await asyncio.sleep(timing_time_set)






async def main():
    print(1)
    File_Check()
    print(2)
    asyncio.create_task(send())
    print(3)
    asyncio.create_task(deal_with())
    print(4)
    asyncio.create_task(timing())
    print(5)
    await websocket()


asyncio.run(main())