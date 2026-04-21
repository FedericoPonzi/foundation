"""Render a monthly TLA+ blog post from summarized data and a Jinja2 template.

This module loads the ``post.md.j2`` template, injects summarized data, and
writes the final Markdown file to disk.
"""

from __future__ import annotations

import logging
from pathlib import Path

import jinja2

from autoposter.config import Config
from autoposter.models import SummarizedData

__all__ = ["render_post", "write_post"]

log = logging.getLogger(__name__)

def _get_template_dir() -> Path:
    from autoposter import PROJECT_ROOT
    return PROJECT_ROOT / "templates"


def render_post(
    summarized: SummarizedData,
    config: Config,
    chart_paths: list[Path],
    history: list[dict] | None = None,
) -> str:
    """Render the monthly blog post Markdown from *summarized* data.

    Parameters
    ----------
    summarized:
        Output of the Summarize stage containing intro text, development
        update bullets, community bullets, and metrics.
    config:
        Resolved pipeline configuration (provides month/year helpers).
    chart_paths:
        Paths to generated chart images.
    history:
        Full metrics history. Used to render a multi-month table
        (current month + up to 2 previous months).

    Returns
    -------
    str
        The fully-rendered Markdown string.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_get_template_dir())),
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,
    )
    template = env.get_template("post.md.j2")

    # Build 3-month metrics table.
    metrics_rows, metrics_columns = _build_metrics_window(
        history or [], config.display_months,
    )

    rendered = template.render(
        intro=summarized.intro,
        dev_updates=summarized.dev_update_bullets,
        dev_filtered_comment=summarized.dev_filtered_comment,
        metrics=summarized.metrics,
        metrics_rows=metrics_rows,
        metrics_columns=metrics_columns,
        community_items=summarized.community_bullets,
        month_name=config.month_name,
        year=config.year,
        month_padded=config.month_padded,
        period_label=config.period_label,
        period_kind_label=config.period_kind_label,
        period_kind_word="quarter" if config.period_kind == "quarter" else "month",
        period_slug=config.period_slug,
        frontmatter_date=config.frontmatter_date,
    )

    log.info("Rendered post (%d characters)", len(rendered))
    return rendered


def _build_metrics_window(
    history: list[dict],
    display_months: list[tuple[int, int]],
) -> tuple[list[dict], list[str]]:
    """Return metrics rows + column headers for *display_months*.

    *display_months* is a chronological list of ``(year, month)`` tuples
    (typically 3 entries — quarterly = the three months of the quarter,
    monthly = selected month + 2 prior).
    """
    import calendar

    # Index history by (year, month).
    by_period = {(e["year"], e["month"]): e for e in history}

    rows: list[dict] = []
    columns: list[str] = []
    for y, m in display_months:
        entry = by_period.get((y, m))
        if entry:
            rows.append(entry)
            columns.append(f"{calendar.month_abbr[m]} {y}")

    # If we have no history at all, fall back to an empty placeholder for
    # the most recent month so the table still renders.
    if not rows and display_months:
        y, m = display_months[-1]
        rows.append({
            "open_issues": 0, "merged_prs": 0, "commits": 0,
            "active_contributors": 0, "new_contributors": 0,
            "google_group_messages": 0, "tlc_runs": 0,
        })
        columns.append(f"{calendar.month_abbr[m]} {y}")

    return rows, columns


def write_post(content: str, output_dir: Path, slug: str) -> Path:
    """Write the rendered post to disk.

    The file is written as ``{output_dir}/{slug}-dev-update.md``.
    The output directory is created if it does not already exist.

    Parameters
    ----------
    content:
        Rendered Markdown string.
    output_dir:
        Directory in which to write the post file.
    slug:
        Period slug, e.g. ``"2026-03"`` or ``"2026-q1"``.

    Returns
    -------
    Path
        Absolute path to the written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{slug}-dev-update.md"
    path = output_dir / filename
    path.write_text(content)

    log.info("Wrote post to %s", path)
    return path
