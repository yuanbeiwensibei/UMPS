"""审核页面视图 —— 渲染审核题、处理提交。

业务逻辑（协议、会话、校验、提交）集中在 web_tool/review.py，视图只做薄层。
"""
from django.shortcuts import render

from web_tool import questions, review


def _error(request, message, status):
    return render(request, "audit/error.html", {"message": message}, status=status)


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

    return render(request, "audit/review.html", {
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
        return render(request, "audit/review.html", {
            "questions": _questions_with_previous(request.POST),
            "link_id": link_id,
            "errors": errors,
        }, status=400)

    ok, message = review.submit_answers(link_id, answers)
    if not ok:
        return _error(request, message, 410)

    return render(request, "audit/result.html", {"link_id": link_id})
