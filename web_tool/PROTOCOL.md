# UMPS web 端通讯协议与扩展指南

> 本文档描述 **web 端** 与 **umps** 之间经由中转站交换的消息格式，以及 web 端「如何新增功能」。
> 以后每次给 web 加新功能，照着本文档写即可。协议实现的唯一代码来源是 `web_tool/review.py` 里的常量与 `_build_mail()`，本文档与其保持一致。

---

## 1. web 端在架构中的位置

```
（根目录）
├── TS.py / TS2.py      # 中转站：监听 8001~8005，按 Recipient 转发邮件
├── umps.py             # umps 核心进程（连 8001，用 mail_tool 插件列表）
├── web.py              # web 核心进程（连 8004，用 web_tool 插件列表）← 本文档主角
├── mail_tool/          # umps 的插件集
├── web_tool/           # web 的插件集（每个功能一个 .py）
└── web_site/           # web 的 Django 页面（审核页等，由 web.py 启动，监听 80）
```

- web 端与 umps 平级、同等重要，运行方式：`python web.py`（一条命令同时起 WebSocket 客户端 + Django 页面）。
- web.py 连接中转站 **8004**，和 umps 连 8001 一样，收发 JSON「邮件」。

---

## 2. 邮件统一结构（所有进程通用）

一封邮件（mail）长这样，web 端只用 `web_mail` 槽，其余槽留空：

```json
{
  "mailer": "web",
  "Recipient": "umps",
  "web_mail": { },
  "umps_mail": "",
  "ai_mail": "",
  "minecraft_mail": "",
  "napcat_mail": "",
  "need": true,
  "minecraft_online": true,
  "mail_id": "review_answers_a1b2c3"
}
```

| 字段 | 说明 |
|------|------|
| `mailer` | 发送方：`"web"` / `"umps"` |
| `Recipient` | 接收方：`"umps"` / `"web"`（中转站据此路由） |
| `web_mail` | web 程序专用槽：**web → umps 的内容**放这里（ums 读它） |
| `umps_mail` | umps 程序专用槽：**umps → web 的内容**放这里（web 读它） |
| `ai_mail` / `minecraft_mail` / `napcat_mail` | 其他程序的槽，web 端不涉及，恒为空 |
| `minecraft_online` | 由中转站回填真实状态，web 不关心 |
| `mail_id` | 消息唯一 id，便于日志追踪 |

---

## 3. web ↔ umps 消息协议（槽位约定）

> **槽位约定（全系统通用，务必遵守）**：邮件里每个 `xxx_mail` 槽对应一个程序，**谁发消息，就填谁的槽**；接收方读「发送方」的槽。
> - `umps → web`：ums 把内容填在 `umps_mail`，**web 读 `umps_mail`**
> - `web → umps`：web 把内容填在 `web_mail`，ums 读 `web_mail`
>
> 因此下文每种消息标注了「方向」和「放哪个槽」，写插件时别读错槽。

**核心约定：`qq` 贯穿全程** —— umps 请求开链接时一定带 `qq`，web 返回链接、交答题卡时也一定带 `qq`，这样 umps 拿到任何回信都能直接知道是哪个玩家。

用 `web_mail.post_type` 区分消息类型，目前有三种：

| post_type | 方向 | 含义 |
|-----------|------|------|
| `open_review_link` | umps → web | 请求开启一个入服审核链接 |
| `review_link_ready` | web → umps | 返回生成的审核链接 |
| `review_answers` | web → umps | 玩家提交的「链接 id + 答题卡」 |

### 3.1 `open_review_link`（umps → web）

```json
{
  "post_type": "open_review_link",
  "qq": 123456789,
  "request_id": ""
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `qq` | int/str | 待审核玩家 QQ（**ums 一定带**） |
| `request_id` | str | 可选，ums 端用于关联请求 |

### 3.2 `review_link_ready`（web → umps）

```json
{
  "post_type": "review_link_ready",
  "qq": 123456789,
  "link_id": "K2vX9m...",
  "url": "http://127.0.0.1/review/K2vX9m.../",
  "ok": true
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `qq` | int/str | 玩家 QQ |
| `link_id` | str | 链接 id（即 URL 路径段，`secrets.token_urlsafe` 生成，每用户唯一） |
| `url` | str | 完整可打开的审核链接 |
| `ok` | bool | 是否成功生成 |

### 3.3 `review_answers`（web → umps）

```json
{
  "post_type": "review_answers",
  "link_id": "K2vX9m...",
  "qq": 123456789,
  "answers": [
    { "question_id": 1,  "answer": "A" },
    { "question_id": 15, "answer": "我叫小明，来自……" }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `link_id` | str | 提交所属的审核链接 id |
| `qq` | int/str | 玩家 QQ（**答题卡一定带**） |
| `answers` | list | 答题卡：`[{question_id, answer}]` |

**答题卡约定**：选择题 `answer` 用选项字母（`A`/`B`/`C`/`D`），问答题用原文。该格式直接对齐 `UMP_AI.py` 判卷插件的解析方式（它读 `mail["web_mail"]["answers"]`），ums 端无需二次转换即可转给 AI 判卷。

---

## 4. 一次完整交互时序

```
ums                                web（中转站 8004）
 │  open_review_link {qq}            │
 │ ────────────────────────────────> │  建会话 link_id
 │                                   │
 │  review_link_ready {qq,link_id,url}│
 │ <──────────────────────────────── │
 │  （ums 把 url 经 napcat 发给玩家） │
 │                                   │  玩家打开 url 做题
 │                                   │  提交 → 校验 → 构造 mail
 │  review_answers {qq,link_id,answers}│
 │ <──────────────────────────────── │
```

---

## 5. 插件机制（对标 umps 的 mail_tool）

web.py 里注册插件的方式和 umps.py 完全一样：

```python
# web.py
from web_tool import review
web_tool_list = [review.review]   # 插件列表，按顺序分发
```

每个插件是一个函数，入参是整封 mail，返回值：

| 返回值 | 含义 |
|--------|------|
| `None` | 不处理这封邮件（继续喂下一个插件） |
| 一封 mail（dict） | 处理完成，作为回信 |
| 多封 mail（list） | 处理完成，多封回信 |

web.py 把邮件按顺序喂给 `web_tool_list`，**第一个返回非 None 的插件认领**，其回信进 `outbox`（出站队列）发给中转站。

### 共享设施（`web_tool/__init__.py`）

- `outbox`：出站队列（`queue.Queue`）。插件回信、HTTP 提交产生的回信都放进这里，由 web.py 的发送循环发给中转站。
- `log`：logger，替代 print。

---

## 6. 新增一个 web 功能的步骤（照着做）

假设要给 web 加一个叫 `xxx` 的新功能（ums 发 `do_xxx`，web 处理后回 `xxx_done`）：

**第 1 步**：在 `web_tool/` 新建 `xxx.py`

```python
"""xxx 功能插件。"""
from web_tool import log, outbox

DO_XXX = "do_xxx"
XXX_DONE = "xxx_done"


def _build_mail(mailer, recipient, web_mail, mail_id=""):
    return {
        "mailer": mailer, "Recipient": recipient,
        "web_mail": web_mail,
        "umps_mail": "", "ai_mail": "", "minecraft_mail": "", "napcat_mail": "",
        "need": True, "minecraft_online": True, "mail_id": mail_id,
    }


def xxx(mail):
    """插件入口：只处理 do_xxx。"""
    if mail.get("Recipient") != "web":
        return None
    wm = mail.get("web_mail") or {}
    if wm.get("post_type") != DO_XXX:
        return None

    # ... 你的业务逻辑 ...
    result = "处理结果"

    return _build_mail("web", "umps", {
        "post_type": XXX_DONE,
        "qq": wm.get("qq"),          # 记得带 qq
        "result": result,
    })
```

**第 2 步**：在 `web.py` 里把插件挂进列表

```python
from web_tool import review, xxx          # 新增 import
web_tool_list = [review.review, xxx.xxx]  # 追加注册
```

**第 3 步**（如果新功能需要网页）：在 `web_site/audit/` 里加 view + 模板 + 路由，view 里调插件函数、通过 `outbox` 回信（参考 `web_site/audit/views.py` 里怎么调 `web_tool.review`）。

**第 4 步**：回信里**记得带 `qq`**（从请求邮件里取），保证 umps 能识别是谁的。

---

## 7. 约定与注意

- **QQ 贯穿**：任何 web → umps 的消息都带上 `qq`。
- **链接规则**：链接 `http://<域名>/review/<link_id>/`；`link_id` 每用户唯一；**提交后链接即失效**（再次访问返回 410），不可二次提交；默认 30 分钟过期。
- **错误与边界**：web 对 `Recipient != "web"` 或未知 `post_type` 的邮件一律忽略，不报错。
- **配置项**（`web.py` 顶部 / `web_site/web_site/settings.py`）：

| 配置 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| `HUB_URL` | `web.py` | `ws://127.0.0.1:8004` | 中转站 web 端口 |
| `WEB_ADDR` | `web.py` | `0.0.0.0:80` | 审核页面监听地址 |
| `REVIEW_BASE_URL` | `web_tool/review.py` | `http://127.0.0.1` | 审核链接对外基地址（生产改成域名） |
| `REVIEW_LINK_TTL` | `web_tool/review.py` | `1800`（秒） | 链接有效期 |

---

## 8. 运行与部署

```bash
# 运行（一条命令：WebSocket 客户端 + Django 审核页面）
python web.py

# 依赖（只两个包，其余标准库）
pip install -r web_site/requirements.txt   # Django==6.1.1 + websockets==17.1
```

**目录速查**：

| 路径 | 作用 |
|------|------|
| `web.py` | 核心进程：连 8004、插件分发、起 Django 页面 |
| `web_tool/__init__.py` | 共享 `outbox` / `log` |
| `web_tool/review.py` | 审核插件（协议常量 + 会话 + 校验 + 提交） |
| `web_tool/questions.py` | 17 道审核题 |
| `web_site/` | Django 页面项目（审核页渲染 + 收提交） |

---

## 9. 页面模板约定（移动优先）

**以后新增网页，一律先写移动版。**

- 每个页面提供两套模板，放在 `web_site/audit/templates/audit/`：
  - **移动版**：`<name>_mobile.html`，继承 `base_mobile.html`（主路径 —— 审核链接由 QQ 发给玩家，基本用手机打开）
  - **桌面版**：`<name>.html`，继承 `base.html`
- 视图用 `web_site/audit/views.py` 的 `_tpl(request, name)` 按 `User-Agent` 自动选版本（移动端 → `_mobile`）。加新页面时照此接入，两个模板名都提供即可。
- **风格统一用「孟菲斯绿色主题」**：单色绿 + 黑色硬阴影（`box-shadow: Npx Npx 0 0 var(--ink)`）+ 粗描边（`border: 2px solid var(--ink)`）+ 回弹动画（`cubic-bezier(.34,1.56,.64,1)`）+ 几何背景装饰。设计令牌见 `base_mobile.html` / `base.html` 顶部的 `:root`。
- 移动版要点：`viewport-fit=cover` + `env(safe-area-inset-*)` 适配刘海屏；顶部固定栏（品牌 + 已答计数 + 滚动进度）；底部固定提交栏（拇指可达）；选项行触控目标足够大；`font-size ≥ 16px` 防 iOS 自动缩放；尊重 `prefers-reduced-motion`。
- 示例：审核页 = `base_mobile.html` + `review_mobile.html` / `result_mobile.html` / `error_mobile.html`。
