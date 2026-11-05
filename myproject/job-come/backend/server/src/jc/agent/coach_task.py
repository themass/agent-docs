"""Bind mock-interview turns to the active job and question bank."""

from __future__ import annotations


def wrap_coach_mock_message(
    user_text: str,
    *,
    profile_id: str | None,
    job_id: str | None,
    mock_session_id: str | None,
    drawn_stems: list[str],
) -> str:
    bound_profile = profile_id or "（未绑定档案）"
    bound_job = job_id or "（未绑定岗位，请用户从投递看板带岗进入）"
    session = mock_session_id or "（尚未开模拟会话，请用户点「开始本轮模拟」）"
    if drawn_stems:
        drawn_block = "\n".join(f"- {stem}" for stem in drawn_stems)
        draw_rule = (
            "本轮必须先问下面「来自题库」的题目（逐题提问），再出新题。"
            f"\n来自题库：\n{drawn_block}"
        )
    else:
        draw_rule = (
            "题库还没有本题可抽，请出与岗位相关的新题，"
            "每出一题调用 jc_question_upsert。"
        )
    state_rule = (
        "用户可能已在页面上跳过或换题：每轮开始前调用 jc_mock_plan 查看本场当前状态，"
        "以它为准，不要凭记忆判断题数和覆盖。"
    )
    history_rule = (
        "如果对话较长、不确定本轮模拟会话里已经问过哪些题、用户怎么答的，"
        "先调用 jc_mock_session_history（带 mock_session_id）查出已记录的问答，"
        "不要凭记忆猜测或重复问同一题。"
    )
    return (
        "【面试模拟任务】\n"
        "只用中文。你就是这场面试的面试官，像真人一样说话：口语、简短、一次只说一件事；"
        "不要向用户提工具、登记、题库或系统。不要调用 ask_clarification。\n"
        f"档案 profile_id={bound_profile}；岗位 job_id={bound_job}；"
        f"模拟会话 mock_session_id={session}。\n"
        f"{draw_rule}\n"
        f"{state_rule}\n"
        f"{history_rule}\n"
        "每次出题后调用 jc_question_upsert（带 job_id 与 mock_session_id），"
        "再调用 jc_mock_ask 登记提问（主问题或追问）。"
        "用户作答后调用 jc_answer_save_attempt 保存原话；本场不点评、不打分，"
        "评分由独立评审在场次结束后完成。\n"
        "用户原话：\n"
        f"{user_text.strip()}\n"
    )
