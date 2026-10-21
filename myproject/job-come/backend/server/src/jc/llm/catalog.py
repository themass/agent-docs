"""Load prompt templates from prompts/."""

from __future__ import annotations

from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, select_autoescape

from jc.paths import PROMPTS_ROOT


@lru_cache
def get_prompt_catalog() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(PROMPTS_ROOT)),
        autoescape=select_autoescape(enabled_extensions=()),
    )


def render_prompt(template_path: str, **kwargs: object) -> str:
    env = get_prompt_catalog()
    template = env.get_template(template_path)
    return template.render(**kwargs)
