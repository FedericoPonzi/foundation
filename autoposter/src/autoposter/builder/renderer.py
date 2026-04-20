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
    import calendar

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_get_template_dir())),
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,
    )
    template = env.get_template("post.md.j2")

    # Build 3-month metrics table (selected month + 2 previous).
    metrics_rows, metrics_columns = _build_metrics_window(
        history or [], config.year, config.month,
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
    )

    log.info("Rendered post (%d characters)", len(rendered))
    return rendered


def _build_metrics_window(
    history: list[dict], year: int, month: int,
) -> tuple[list[dict], list[str]]:
    """Return up to 3 months of metrics ending at year/month.

    Returns (rows, column_headers) where rows are dicts and
    column_headers are like ["Jan 2026", "Feb 2026", "Mar 2026"].
    """
    import calendar

    # Build the 3 target (year, month) pairs going backwards.
    targets = []
    y, m = year, month
    for _ in range(3):
        targets.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    targets.reverse()  # oldest first

    # Index history by (year, month).
    by_period = {(e["year"], e["month"]): e for e in history}

    rows = []
    columns = []
    for y, m in targets:
        entry = by_period.get((y, m))
        if entry:
            rows.append(entry)
            columns.append(f"{calendar.month_abbr[m]} {y}")

    # If we have no history at all, fall back to just the current metrics placeholder
    if not rows:
        rows.append({
            "open_issues": 0, "merged_prs": 0, "commits": 0,
            "active_contributors": 0, "new_contributors": 0,
            "google_group_messages": 0, "tlc_runs": 0,
        })
        columns.append(f"{calendar.month_abbr[month]} {year}")

    return rows, columns


def write_post(content: str, output_dir: Path, year: int, month: int) -> Path:
    """Write the rendered post to disk.

    The file is written as ``{output_dir}/{year}-{month:02d}-dev-update.md``.
    The output directory is created if it does not already exist.

    Parameters
    ----------
    content:
        Rendered Markdown string.
    output_dir:
        Directory in which to write the post file.
    year:
        Target year (e.g. 2026).
    month:
        Target month (1--12).

    Returns
    -------
    Path
        Absolute path to the written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{year}-{month:02d}-dev-update.md"
    path = output_dir / filename
    path.write_text(content)

    log.info("Wrote post to %s", path)
    return path
