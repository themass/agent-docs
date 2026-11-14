from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True, slots=True)
class GuestActor:
    guest_session_id: str
    kind: Literal["guest"] = "guest"
    @property
    def actor_id(self) -> str:
        return self.guest_session_id

@dataclass(frozen=True, slots=True)
class UserActor:
    user_id: str
    session_id: str
    kind: Literal["user"] = "user"
    @property
    def actor_id(self) -> str:
        return self.user_id

Actor = GuestActor | UserActor
