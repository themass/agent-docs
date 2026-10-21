"""Translate Profile display fields into the other resume locale."""

from __future__ import annotations

import json
from typing import Any

from jc.config import settings
from jc.paths import prompt_file
from jc.schemas.profile_payload import ProfileI18nPack, ProfilePayload
from jc.services.profile_i18n import align_i18n_pack, project_i18n_pack

_PROMPT_PATH = prompt_file("elevate", "localize.md")


class LocalizeService:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def translate(self, profile: ProfilePayload, *, target_locale: str) -> ProfileI18nPack:
        fallback = project_i18n_pack(profile)
        if not settings.jc_llm_enabled:
            return fallback
        try:
            from jc.llm.call_context import llm_context
            from jc.llm.router import get_llm_router

            router = get_llm_router()
            user_payload = {
                "target_locale": target_locale,
                "profile": {
                    "summary": profile.summary,
                    "experiences": [
                        {"id": e.id, "title": e.title, "highlights": e.highlights}
                        for e in profile.experiences
                    ],
                    "education": [
                        {
                            "id": e.id,
                            "degree": e.degree,
                            "major": e.major,
                        }
                        for e in profile.education
                    ],
                    "projects": [
                        {
                            "id": p.id,
                            "name": p.name,
                            "role": p.role,
                            "description": p.description,
                            "highlights": p.highlights,
                        }
                        for p in profile.projects
                    ],
                    "skills": [s.name for s in profile.skills],
                },
            }
            def validate(response: Any) -> ProfileI18nPack:
                data = json.loads(router.content_from_response(response))
                return ProfileI18nPack.model_validate(data)

            pack = await router.acompletion(
                "flash",
                log_context=llm_context("localize"),
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False)[:40_000],
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                response_validator=validate,
            )
            return align_i18n_pack(profile, pack)
        except Exception:  # noqa: BLE001
            return fallback
