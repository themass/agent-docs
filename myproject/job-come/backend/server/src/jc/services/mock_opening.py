"""The interviewer's opening, written by the server rather than by the model (ADR-008).

The opening says the same things every time: who the interviewer is, the company and role, how many
questions, and a request for a one-to-two minute self-introduction.
"""

from __future__ import annotations


def opening_text(company: str | None, title: str | None) -> str:
    where = f"{company or ''}{title or ''}".strip()
    role = f"{where}的面试官" if where else "这个岗位的面试官"
    head = f"你好，我是{role}，今天由我来面你。"
    return (
        f"{head}大概五到六个问题，中间我会顺着你的回答追问，你随时可以说“结束”。"
        "先请你用一到两分钟做个自我介绍吧。"
    )
