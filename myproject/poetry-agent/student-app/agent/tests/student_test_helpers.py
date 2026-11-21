"""Plain helpers shared by the student agent tests (importable regardless of pytest's import mode)."""
from __future__ import annotations

from student_agent.models import TurnRequest

HASH = "60279d333becba38e65414e58d433ee58235acb08841277ddf7d62a598f91d11"
WORK = "work-chun-wang"


def make_req(step, action, **args):
    return TurnRequest(bundle_hash=HASH, work_id=WORK, step=step, action=action, args=args)
