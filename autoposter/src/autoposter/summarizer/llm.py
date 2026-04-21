"""LLM-powered summarizer for collected TLA+ ecosystem items.

Supports multiple LLM providers (Azure OpenAI, OpenAI, Ollama) via the
``openai`` Python SDK.  Items that carry a ``changelog_body`` bypass the
LLM and are formatted directly.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from openai import AzureOpenAI, OpenAI

from autoposter.models import (
    CollectedData,
    CollectedItem,
    CommunityThread,
    GrantInfo,
    SummarizedData,
)

__all__ = ["LlmClient", "summarize"]

log = logging.getLogger(__name__)

# Canonical project ordering for bullet grouping.
PROJECT_ORDER: list[str] = ["TLC", "Vscode Extension", "TLAPM", "Community Modules", "Examples", "Apalache"]

# Default prompt template path (relative to the project root).
def _get_prompt_dir() -> Path:
    from autoposter import PROJECT_ROOT
    return PROJECT_ROOT / "prompts"


# ---------------------------------------------------------------------------
# LLM client abstraction
# ---------------------------------------------------------------------------


def _build_openai_client(provider: str, **kwargs: Any) -> OpenAI:
    """Return an ``OpenAI``-compatible client for the requested *provider*."""

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        return OpenAI(api_key=api_key, **kwargs)

    if provider == "azure_openai":
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get(
            "OPENAI_API_KEY", ""
        )
        api_version = kwargs.pop("azure_api_version", "2024-10-21")
        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            **kwargs,
        )

    if provider == "ollama":
        base_url = kwargs.pop("ollama_base_url", "http://localhost:11434") + "/v1"
        return OpenAI(base_url=base_url, api_key="ollama", **kwargs)

    if provider == "anthropic":
        raise NotImplementedError(
            "The 'anthropic' provider is not yet implemented. "
            "Install the anthropic SDK and add support, or use "
            "'openai', 'azure_openai', or 'ollama' instead."
        )

    raise ValueError(f"Unknown LLM provider: {provider!r}")


class LlmClient:
    """Thin wrapper around an OpenAI-compatible chat completions API.

    Parameters
    ----------
    provider:
        One of ``"openai"``, ``"azure_openai"``, ``"ollama"``, or
        ``"anthropic"`` (not yet implemented).
    model:
        Model name / deployment to use for completions.
    prompt_dir:
        Directory containing prompt templates (``summarize.txt``).
    **kwargs:
        Extra keyword arguments forwarded to the underlying client
        constructor (e.g. ``azure_api_version``, ``ollama_base_url``).
    """

    def __init__(
        self,
        provider: str,
        model: str,
        prompt_dir: Path | None = None,
        **kwargs: Any,
    ) -> None:
        self._client = _build_openai_client(provider, **kwargs)
        self._model = model
        self._prompt_dir = prompt_dir or _get_prompt_dir()
        self._prompt_template = self._load_prompt("summarize.txt")

    # -- internal helpers ---------------------------------------------------

    def _load_prompt(self, filename: str) -> str:
        path = self._prompt_dir / filename
        log.debug("Loading prompt template from %s", path)
        return path.read_text()

    def _chat(self, system: str, user: str) -> str:
        """Send a single chat completion request and return the response."""
        log.debug("LLM request (model=%s, %d chars)", self._model, len(user))
        # Suppress any stray stdout/stderr from the SDK.
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
            )
        text = response.choices[0].message.content or ""
        log.debug("LLM response length: %d chars", len(text))
        return _sanitize_text(text.strip())

    # -- public API ---------------------------------------------------------

    def summarize_items(
        self, items: list[CollectedItem]
    ) -> tuple[list[str], str]:
        """Return (bullets, filtered_comment) for the dev-update section.

        Bot-authored items are dropped here (they never reach the LLM).
        Items with a ``changelog_body`` are formatted directly and
        prepended to the LLM's bullets in canonical project order; the
        rest are sent to the LLM in a single batch and the LLM decides
        what to keep, skip, or merge (per ``prompts/summarize.txt``).

        ``filtered_comment`` is the trailing ``<!-- Filtered items ... -->``
        block emitted by the LLM (empty string when nothing was filtered or
        no LLM call was made).
        """
        non_bot = [it for it in items if not _is_bot_author(it.author)]
        bot_count = len(items) - len(non_bot)
        if bot_count:
            log.info("Pre-filtered %d bot-authored item(s)", bot_count)

        grouped = _group_and_sort(non_bot)
        changelog_bullets: list[str] = []
        llm_items: list[CollectedItem] = []

        for item in grouped:
            if item.changelog_body:
                changelog_bullets.append(_format_changelog_bullet(item))
                log.info(
                    "Item #%d (%s #%d) uses changelog fence, skipping LLM",
                    item.number,
                    item.project_name,
                    item.number,
                )
            else:
                llm_items.append(item)

        llm_bullets: list[str] = []
        filtered_comment = ""
        if llm_items:
            items_text = _format_items_for_prompt(llm_items)
            prompt = self._prompt_template.replace("{items}", items_text)
            raw = self._chat(
                system="You are a concise technical writer for the TLA+ Foundation.",
                user=prompt,
            )
            llm_bullets, filtered_comment = _split_bullets_and_comment(raw)

        return changelog_bullets + llm_bullets, filtered_comment

    def summarize_community(
        self,
        threads: list[CommunityThread],
        grants: list[GrantInfo],
        period_kind: str = "month",
    ) -> list[str]:
        """Return community bullet strings for notable threads and grants."""
        if not threads and not grants:
            return []

        parts: list[str] = []
        for t in threads:
            parts.append(
                f"- Thread: \"{t.subject}\" ({t.reply_count} replies, {t.date}) — {t.url}"
            )
        for g in grants:
            desc = f" — {g.description}" if g.description else ""
            parts.append(f"- Grant: \"{g.title}\"{desc} — {g.url}")

        period_word = "quarterly" if period_kind == "quarter" else "monthly"
        user_msg = (
            f"Summarize these TLA+ community items into concise bullets for a "
            f"{period_word} blog post. Each bullet should be one sentence. Use "
            "Markdown links.\n\n" + "\n".join(parts)
        )
        raw = self._chat(
            system="You are a concise technical writer for the TLA+ Foundation.",
            user=user_msg,
        )
        return _parse_bullet_list(raw)

    def generate_intro(
        self,
        dev_bullets: list[str],
        community_bullets: list[str],
        period_kind: str = "month",
        period_label: str = "",
    ) -> str:
        """Generate a 2-3 sentence intro given the already-written sections."""
        context = "## Development Updates\n\n"
        context += "\n".join(f"- {b}" for b in dev_bullets)
        if community_bullets:
            context += "\n\n## Community & Events\n\n"
            context += "\n".join(f"- {b}" for b in community_bullets)

        period_word = "quarter" if period_kind == "quarter" else "month"
        period_word_adj = "quarterly" if period_kind == "quarter" else "monthly"
        period_phrase = f" ({period_label})" if period_label else ""
        user_msg = (
            f"Given the following sections of a TLA+ {period_word_adj} development "
            f"update blog post{period_phrase}, write a 2-3 sentence intro paragraph "
            f"that names the {period_word}'s focus areas and references the most "
            "significant changes.\n\n"
            "PRIORITISE bug fixes - especially soundness, correctness, "
            "liveness, and verifier-engine bugs - over feature work or "
            "tooling polish. If a bullet describes a bug fix that could "
            "cause silent incorrect results (e.g., bogus counterexamples, "
            "missed violations, wrong booleans), call it out by name.\n\n"
            f"Refer to the time period as \"this {period_word}\" (not "
            f"\"this month\" if it is a quarter).\n\n"
            "Do not use bullet points. Do not use em dashes, en dashes, "
            "or horizontal bars - use regular hyphens instead.\n\n"
            + context
        )
        return self._chat(
            system="You are a concise technical writer for the TLA+ Foundation.",
            user=user_msg,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_bot_author(author: str) -> bool:
    """True when *author* looks like an automated account (case-insensitive)."""
    if not author:
        return False
    name = author.lower()
    if name.endswith("[bot]"):
        return True
    return name in {
        "scala-steward",
        "dependabot",
        "renovate",
        "renovate-bot",
        "github-actions",
        "copilot",
        "pre-commit-ci",
    }


def _group_and_sort(items: list[CollectedItem]) -> list[CollectedItem]:
    """Group items by project in canonical order, then sort by merge date."""
    project_index = {name: i for i, name in enumerate(PROJECT_ORDER)}
    # Items whose project isn't recognised go at the end.
    return sorted(
        items,
        key=lambda it: (
            project_index.get(it.project_name, len(PROJECT_ORDER)),
            it.merged_at or "",
        ),
    )


def _format_changelog_bullet(item: CollectedItem) -> str:
    """Build a bullet string from a changelog-fenced item (no LLM)."""
    body = (item.changelog_body or "").strip()
    link = f"[#{item.number}]({item.url})"
    bullet = f"{item.project_name}: {body} ({link})"
    if item.author:
        bullet += f" <!-- author: {item.author} -->"
    return bullet


def _sanitize_text(text: str) -> str:
    """Strip terminal control characters and escape sequences."""
    import re
    # Remove ANSI escape sequences
    text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    # Remove other control chars except newline/tab
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


def _format_items_for_prompt(items: list[CollectedItem]) -> str:
    """Render items as text for insertion into the prompt template."""
    lines: list[str] = []
    for item in items:
        parts = [
            f"Project: {item.project_name}",
            f"Title: {item.title}",
            f"URL: {item.url}",
            f"Kind: {item.kind}",
            f"Number: #{item.number}",
        ]
        if item.merged_at:
            parts.append(f"Merged: {item.merged_at}")
        if item.author:
            parts.append(f"Author: {item.author}")
        if item.description:
            # Truncate long descriptions and sanitize control chars
            desc = _sanitize_text(item.description)
            if len(desc) > 500:
                desc = desc[:500] + " [...]"
            parts.append(f"Description: {desc}")
        lines.append("\n".join(parts))
    return "\n\n---\n\n".join(lines)


def _parse_bullet_list(text: str) -> list[str]:
    """Extract bullet bodies from a Markdown bulleted list returned by the LLM."""
    bullets: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        # A new top-level bullet starts with "- " or "* ".
        if re.match(r"^[-*]\s", stripped):
            if current:
                bullets.append(" ".join(current))
            current = [stripped.lstrip("-* ").strip()]
        elif stripped and current:
            # Continuation line of the current bullet.
            current.append(stripped)
    if current:
        bullets.append(" ".join(current))
    return bullets


def _split_bullets_and_comment(text: str) -> tuple[list[str], str]:
    """Split an LLM response into (bullets, html_comment_block).

    The prompt produces a Markdown bulleted list optionally followed by
    a single multi-line ``<!-- Filtered items ... -->`` block. Each
    bullet may also contain an inline ``<!-- author: name -->`` comment
    appended to its last line.

    To avoid mistaking the per-bullet author comment for the trailing
    filtered-items block, we treat as the trailing block only a comment
    whose opening ``<!--`` sits on its own line (i.e. preceded by start
    of input or a newline + only whitespace before it). All inline
    comments are left embedded in the bullets where they belong.
    """
    text = text.strip()
    candidates = list(
        re.finditer(r"(?m)^[ \t]*<!--.*?-->", text, flags=re.DOTALL)
    )
    if candidates:
        match = candidates[-1]
        bullets_text = text[: match.start()].rstrip()
        comment = match.group(0).strip()
    else:
        bullets_text = text
        comment = ""
    return _parse_bullet_list(bullets_text), comment


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def summarize(
    collected: CollectedData,
    provider: str,
    model: str,
    prompt_dir: Path | None = None,
    period_kind: str = "month",
    period_label: str = "",
    **llm_kwargs: Any,
) -> SummarizedData:
    """Summarize collected data into a :class:`SummarizedData` ready for rendering.

    Parameters
    ----------
    collected:
        The full output of the Collect stage.
    provider:
        LLM provider name (``"openai"``, ``"azure_openai"``, ``"ollama"``,
        ``"anthropic"``).
    model:
        Model name / deployment.
    prompt_dir:
        Optional override for the prompts directory.
    **llm_kwargs:
        Extra arguments forwarded to the LLM client constructor.
    """
    log.info(
        "Summarizing %d items with provider=%s model=%s",
        len(collected.items),
        provider,
        model,
    )

    client = LlmClient(
        provider=provider,
        model=model,
        prompt_dir=prompt_dir,
        **llm_kwargs,
    )

    # 1. Development update bullets.
    dev_bullets, dev_filtered_comment = client.summarize_items(collected.items)
    log.info(
        "Generated %d development bullets (%d chars filtered comment)",
        len(dev_bullets),
        len(dev_filtered_comment),
    )

    # 2. Community & events bullets.
    community_bullets = client.summarize_community(
        collected.community_threads,
        collected.grants,
        period_kind=period_kind,
    )
    log.info("Generated %d community bullets", len(community_bullets))

    intro = client.generate_intro(
        dev_bullets,
        community_bullets,
        period_kind=period_kind,
        period_label=period_label,
    )
    log.info("Generated intro (%d chars)", len(intro))

    return SummarizedData(
        month=collected.month,
        year=collected.year,
        intro=intro,
        dev_update_bullets=dev_bullets,
        dev_filtered_comment=dev_filtered_comment,
        community_bullets=community_bullets,
    )
