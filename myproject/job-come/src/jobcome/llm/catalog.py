"""Load prompt templates from prompts/."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_ROOT = Path(__file__).resolve().parents[3] / "prompts"


@lru_cache
def get_prompt_catalog() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_ROOT)),
        autoescape=select_autoescape(enabled_extensions=()),
    )


def render_prompt(template_path: str, **kwargs: object) -> str:
    env = get_prompt_catalog()
    template = env.get_template(template_path)
    return template.render(**kwargs)
