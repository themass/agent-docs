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
            "每出一题调用 jobcome_question_upsert。"
        )
    return (
        "【面试模拟任务】\n"
        "只用中文。不要自我介绍，不要调用 ask_clarification。\n"
        f"档案 profile_id={bound_profile}；岗位 job_id={bound_job}；"
        f"模拟会话 mock_session_id={session}。\n"
        f"{draw_rule}\n"
        "每次出题后调用 jobcome_question_upsert（带 job_id 与 mock_session_id）。"
        "用户作答后点评，并调用 jobcome_answer_save_attempt。\n"
        "用户原话：\n"
        f"{user_text.strip()}\n"
    )
