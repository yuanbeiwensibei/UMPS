import asyncio
import websockets
import json
from datetime import datetime

# 五个程序的端口分配
PROGRAMS = {
    8001: {'name': 'umps', 'id': 'umps', 'connections': set(), 'last_heartbeat': None, 'online': True},  # 默认在线
    8002: {'name': 'minecraftserver', 'id': 'minecraft', 'connections': set(), 'last_heartbeat': None, 'online': False},
    # mc 默认离线
    8003: {'name': 'napcat', 'id': 'napcat', 'connections': set(), 'last_heartbeat': None, 'online': True},  # 默认在线
    8004: {'name': 'web', 'id': 'web', 'connections': set(), 'last_heartbeat': None, 'online': True},  # 默认在线
    8005: {'name': 'ai', 'id': 'ai', 'connections': set(), 'last_heartbeat': None, 'online': True},  # 默认在线
}

# 心跳配置
HEARTBEAT_INTERVAL = 15  # 15秒一次心跳
HEARTBEAT_TIMEOUT = 30  # 30秒没收到心跳就判离线

# 不需要心跳检查的程序（始终在线）
ALWAYS_ONLINE_PROGRAMS = ['umps', 'napcat', 'web', 'ai']


async def check_heartbeat():
    """定期检查心跳，更新在线状态（只检查 minecraft）"""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        now = datetime.now()

        # 只检查 minecraft 的心跳
        mc_program = PROGRAMS[8002]
        if mc_program['last_heartbeat']:
            elapsed = (now - mc_program['last_heartbeat']).total_seconds()
            if elapsed > HEARTBEAT_TIMEOUT:
                if mc_program['online']:
                    mc_program['online'] = False
                    print(f"[{datetime.now()}] minecraftserver 心跳超时，已离线")
        else:
            if mc_program['connections'] and not mc_program['online']:
                pass

        # 其他程序始终在线，不需要检查
        for program_id in ALWAYS_ONLINE_PROGRAMS:
            for port, program in PROGRAMS.items():
                if program['id'] == program_id:
                    if not program['online']:
                        program['online'] = True
                    break


async def update_minecraft_online_status(data):
    """更新请求中的 minecraft_online 字段"""
    # 获取 Minecraft 的在线状态
    minecraft_program = PROGRAMS[8002]
    minecraft_online = minecraft_program['online']

    # 更新数据
    data['minecraft_online'] = minecraft_online
    return data


async def handle_connection(websocket, port):
    """处理连接"""
    program = PROGRAMS[port]
    program_id = program['id']
    program_name = program['name']

    program['connections'].add(websocket)

    # 除了 minecraft，其他程序连接时自动标记在线
    if program_id != 'minecraft':
        program['online'] = True
        print(f"[{datetime.now()}] {program_name} 已连接（始终在线模式）")
    else:
        print(f"[{datetime.now()}] {program_name} 已连接")

    try:
        async for message in websocket:
            try:
                # 解析 JSON 数据
                data = json.loads(message)

                # 处理心跳（只有 minecraft 需要心跳）
                if data.get('type') == 'heartbeat':
                    program['last_heartbeat'] = datetime.now()
                    if program_id == 'minecraft':
                        if not program['online']:
                            program['online'] = True
                            print(f"[{datetime.now()}] {program_name} 心跳正常，已上线")
                    await websocket.send(json.dumps({'type': 'pong'}))
                    continue

                # 获取发送者和接收者
                sender = data.get('mailer')
                recipient = data.get('Recipient')

                print(f"[{datetime.now()}] 收到消息: {sender} -> {recipient}")

                # 如果需要，更新 minecraft_online 状态
                if 'minecraft_online' in data:
                    data = await update_minecraft_online_status(data)
                    print(f"[{datetime.now()}] 已更新 minecraft_online = {data['minecraft_online']}")

                # 转发给接收者（不改变其他数据）
                if recipient and recipient in [p['id'] for p in PROGRAMS.values()]:
                    await send_to_program(recipient, data)
                else:
                    print(f"[{datetime.now()}] 错误: 无效的接收者 {recipient}")

            except json.JSONDecodeError:
                print(f"[{datetime.now()}] 错误: 无效的 JSON 格式: {message}")
            except Exception as e:
                print(f"[{datetime.now()}] 处理消息时出错: {e}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[{datetime.now()}] {program_name} 连接断开")
    finally:
        program['connections'].discard(websocket)
        # 连接断开时
        if program_id == 'minecraft':
            if len(program['connections']) == 0:
                program['online'] = False
                program['last_heartbeat'] = None
                print(f"[{datetime.now()}] {program_name} 已离线（无连接）")
        else:
            # 其他程序断开连接后仍然保持在线状态
            print(f"[{datetime.now()}] {program_name} 连接断开（仍标记为在线）")
            # 不改变 online 状态，保持 True


async def send_to_program(program_id, data):
    """发送消息给指定程序"""
    for port, program in PROGRAMS.items():
        if program['id'] == program_id:
            if program['connections']:
                # 发送给该程序的第一个连接（通常只有一个）
                for conn in program['connections']:
                    try:
                        await conn.send(json.dumps(data))
                        print(f"[{datetime.now()}] 已转发消息给 {program_id}")
                        return
                    except Exception as e:
                        print(f"[{datetime.now()}] 发送给 {program_id} 失败: {e}")
            else:
                print(f"[{datetime.now()}] {program_id} 当前无连接，消息丢弃")


async def main():
    """启动5个WebSocket服务器"""
    # 启动心跳检查任务
    asyncio.create_task(check_heartbeat())

    servers = []
    for port in PROGRAMS.keys():
        server = await websockets.serve(
            lambda ws, p=port: handle_connection(ws, p),
            '0.0.0.0',
            port
        )
        servers.append(server)

        program_name = PROGRAMS[port]['name']
        if program_name == 'minecraftserver':
            print(f"[启动] {program_name} -> 端口 {port} (需要心跳)")
        else:
            print(f"[启动] {program_name} -> 端口 {port} (始终在线)")

    print("\n" + "=" * 60)
    print("中转站已启动")
    print(f"UMPS:           ws://服务器IP:8001 (始终在线)")
    print(f"MinecraftServer: ws://服务器IP:8002 (需要心跳)")
    print(f"Napcat:         ws://服务器IP:8003 (始终在线)")
    print(f"Web:            ws://服务器IP:8004 (始终在线)")
    print(f"AI:             ws://服务器IP:8005 (始终在线)")
    print(f"\n心跳间隔: {HEARTBEAT_INTERVAL}秒 (仅 Minecraft)")
    print(f"心跳超时: {HEARTBEAT_TIMEOUT}秒")
    print("=" * 60 + "\n")

    await asyncio.gather(*[server.wait_closed() for server in servers])


if __name__ == "__main__":
    asyncio.run(main())