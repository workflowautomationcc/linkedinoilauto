import os
from typing import Dict, Any

from execution.utils import load_config, query_llm, logger, DIRECTIVES_DIR


PROMPT_PATH = os.path.join(DIRECTIVES_DIR, "prompts", "analyze_post_vs_article.md")


def _load_template() -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def build_analysis_prompt(*, bucket: str, title: str, url: str, post_text: str, article_text: str) -> str:
    template = _load_template()
    return (
        template.replace("{{bucket}}", bucket or "")
        .replace("{{title}}", title or "")
        .replace("{{url}}", url or "")
        .replace("{{post_text}}", post_text or "")
        .replace("{{article_text}}", article_text or "")
    )


def analyze_post_vs_article(payload: Dict[str, Any]) -> str:
    """
    Runs an LLM analysis comparing post text vs article text.
    Guarded by `ALLOW_PREVIEW_ANALYSIS=YES` (config/env).
    """
    config = load_config()
    allow = bool(config.get("ALLOW_PREVIEW_ANALYSIS", False))
    if not allow:
        return "Preview analysis is disabled. Set `ALLOW_PREVIEW_ANALYSIS: YES` in `_run_config.md` or export `ALLOW_PREVIEW_ANALYSIS=YES`."

    model = config.get("ANALYSIS_MODEL", "gpt-4o-mini")
    temperature = float(config.get("ANALYSIS_TEMPERATURE", 0.2))

    prompt = build_analysis_prompt(
        bucket=str(payload.get("bucket") or ""),
        title=str(payload.get("title") or ""),
        url=str(payload.get("url") or ""),
        post_text=str(payload.get("post_text") or ""),
        article_text=str(payload.get("article_text") or ""),
    )

    logger.info(f"Running analysis model={model}")
    return query_llm(prompt, model=model, temperature=temperature)

