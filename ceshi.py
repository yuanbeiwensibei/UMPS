import json
import hashlib
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


def Decrypt(binding_code):
    """
    解密绑定凭证
    输入: 密文字符串（可以带或不带 B- 前缀）
    返回:
        - 成功: 返回解密后的 JSON 字典
        - 失败: 返回 False
    """
    PASSWORD = "431124ww"
    ENCRYPTION_KEY = hashlib.sha256(PASSWORD.encode()).digest()

    try:
        # 清理输入：移除 "B- " 或 "B-" 前缀和所有空白字符
        if isinstance(binding_code, str):
            # 移除前缀
            if binding_code.startswith("B- "):
                binding_code = binding_code[3:]
            elif binding_code.startswith("B-"):
                binding_code = binding_code[2:]
            # 移除所有空白字符（空格、换行、制表符等）
            binding_code = ''.join(binding_code.split())

        # Base64 解码
        combined = base64.b64decode(binding_code)

        # 检查长度是否足够（IV 16字节 + 至少1字节密文）
        if len(combined) < 17:
            print(f"数据长度不足: {len(combined)}")
            return False

        # 分离 IV（前16字节）和密文
        iv = combined[:16]
        ciphertext = combined[16:]

        # AES-CBC 解密
        cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
        padded_plaintext = cipher.decrypt(ciphertext)

        # 去除 PKCS7 填充
        plaintext = unpad(padded_plaintext, AES.block_size)

        # 解析 JSON
        data = json.loads(plaintext.decode('utf-8'))

        # 验证必需字段
        required_fields = ['minecraft_id', 'littleskin_id', 'role_uuid', 'role_name', 'timestamp', 'nonce']
        if not all(field in data for field in required_fields):
            print("缺少必需字段")
            return False

        return data

    except Exception as e:
        print(f"解密失败: {e}")
        return False


# 测试数据
bin_data = "B- HISTUWvGuhH8OztYKixPZs+cuiia9zdjbaVoaESC8ka2oU531tudO5zhnuG3u1ERpR+0vx4wR9V0uIEOeSHay2r3Q6wVhKu+gAjueQF+aKPElAA4dr4d9ex9JiheO9KqTVlYqaZYYdW4FccYwv+Cm5WKkm4EDBJm3gHQmVPgz10ACT4UTBH3LVgyr4D9LDpl6Q1oiSkAdu8x0i7ZOvq00uOxs8Du2qinrYtwWHDu2AhkXHziSzJkySAlgoScq00EZ53p2Dmh/SRueDtgaiTu3dxR9djnoO2JC8EnM9HmIiB9anGLY/9kgxA8zqAK0673"

print(Decrypt(bin_data))