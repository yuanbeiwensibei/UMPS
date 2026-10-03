"""审核页面视图 —— 渲染审核题、处理提交。

业务逻辑（协议、会话、校验、提交）集中在 web_tool/review.py，视图只做薄层。
按设备（User-Agent）自动选择「移动版 / 桌面版」两套模板。
"""
from django.shortcuts import render

from web_tool import questions, review

# 移动端 UA 关键词
_MOBILE_UA = ("mobile", "android", "iphone", "ipod", "ipad",
              "windows phone", "harmonyos", "micromessenger")


def _is_mobile(request):
    """根据 User-Agent 判断是否移动端。"""
    ua = request.META.get("HTTP_USER_AGENT", "").lower()
    return any(k in ua for k in _MOBILE_UA)


def _tpl(request, name):
    """按设备选模板：移动端用 audit/<name>_mobile.html，否则 audit/<name>.html。"""
    suffix = "_mobile" if _is_mobile(request) else ""
    return f"audit/{name}{suffix}.html"


def _error(request, message, status):
    return render(request, _tpl(request, "error"), {"message": message}, status=status)


def _questions_with_previous(previous=None):
    """题目列表 + 回填值 previous（校验失败时回显）。"""
    prev = previous or {}
    out = []
    for q in questions.QUESTIONS:
        qc = dict(q)
        qc["previous"] = prev.get(f"q{q['id']}", "")
        out.append(qc)
    return out


def review_page(request, link_id):
    """GET /review/<link_id>/：渲染 17 题审核表单。"""
    session = review.get_session(link_id)
    if session is None:
        return _error(request, "审核链接无效或已过期", 404)
    if session.submitted:
        return _error(request, "该审核链接已提交过，链接已失效", 410)

    return render(request, _tpl(request, "review"), {
        "questions": _questions_with_previous(),
        "link_id": link_id,
    })


def review_submit(request, link_id):
    """POST /review/<link_id>/submit/：校验并提交答题卡。"""
    session = review.get_session(link_id)
    if session is None:
        return _error(request, "审核链接无效或已过期", 404)
    if session.submitted:
        return _error(request, "该审核链接已提交过，链接已失效", 410)

    answers, errors = review.validate_answers(request.POST)
    if errors:
        return render(request, _tpl(request, "review"), {
            "questions": _questions_with_previous(request.POST),
            "link_id": link_id,
            "errors": errors,
        }, status=400)

    ok, message = review.submit_answers(link_id, answers)
    if not ok:
        return _error(request, message, 410)

    return render(request, _tpl(request, "result"), {"link_id": link_id})
