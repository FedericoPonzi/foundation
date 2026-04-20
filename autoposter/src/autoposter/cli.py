"""CLI entry point for the ``devupdate`` command.

Orchestrates the TLA+ monthly blog-post pipeline:
Collect → Summarize → Build → PR.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from autoposter.config import Config, load_config
from autoposter.models import CollectedData, SummarizedData

__all__ = ["main"]

log = logging.getLogger(__name__)


def _now() -> str:
    """Return a human-readable timestamp."""
    return datetime.now().strftime("%H:%M:%S")


def _step(label: str) -> float:
    """Print a step start message with timestamp. Returns time.monotonic()."""
    click.echo(f"[{_now()}] {label}")
    return time.monotonic()


def _done(start: float) -> None:
    """Print elapsed time since *start*."""
    elapsed = time.monotonic() - start
    click.echo(f"  done ({elapsed:.1f}s)")


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


def _cache_path(cfg: Config, filename: str) -> Path:
    """Return the path for a stage cache file."""
    out = Path(cfg.output_dir) / "cache"
    out.mkdir(parents=True, exist_ok=True)
    return out / filename


def _load_or_run_json(cache: Path, label: str, fn: callable) -> Any:
    """Load cached JSON if it exists, otherwise run *fn* and save."""
    if cache.exists():
        click.echo(f"  → {label}: cached ✓")
        return json.loads(cache.read_text())
    result = fn()
    cache.write_text(json.dumps(result, indent=2, default=str))
    return result


def _prior_months(year: int, month: int, count: int = 2) -> list[tuple[int, int]]:
    """Return *count* (year, month) pairs preceding the given month."""
    result = []
    y, m = year, month
    for _ in range(count):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
        result.append((y, m))
    result.reverse()
    return result


def _ensure_prior_months(
    cfg: Config,
    history: list[dict],
    history_path: Path,
) -> list[dict]:
    """Collect metrics for the 2 months prior to cfg.month if missing from history."""
    from autoposter.builder.metrics import append_to_history
    from autoposter.collectors.github_collector import collect_github_metrics_only
    from autoposter.collectors.google_group import collect_google_group
    from autoposter.collectors.metabase import collect_metabase_multi
    from autoposter.models import MetricsSnapshot

    existing = {(e["year"], e["month"]) for e in history}
    prior = _prior_months(cfg.year, cfg.month, count=2)
    missing = [(y, m) for y, m in prior if (y, m) not in existing]

    if not missing:
        click.echo("  prior months already in history")
        return history

    # Fetch TLC runs for all missing months in one API call.
    tlc_by_month: dict[tuple[int, int], int] = {}
    try:
        tlc_by_month = collect_metabase_multi(cfg.metabase.dashboard_url, missing)
    except Exception:
        log.warning("Failed to fetch prior Metabase data", exc_info=True)

    # Fetch git stats for each missing month.
    repos = [{"name": r.name, "slug": r.slug} for r in cfg.repos]
    cache_dir = Path(cfg.output_dir) / ".repo-cache"

    for y, m in missing:
        click.echo(f"  collecting metrics for {y}-{m:02d}")

        # Git-based stats (+ open-issues snapshot + merged-PR count via Search API)
        repo_stats = collect_github_metrics_only(
            repos, y, m, cache_dir=cache_dir,
            fetch_open_issues=True, fetch_merged_prs=True,
        )
        commits = sum(rs.commits for rs in repo_stats)
        open_issues = sum(rs.open_issues for rs in repo_stats)
        merged_prs = sum(rs.merged_prs for rs in repo_stats)
        active = set()
        new = set()
        for rs in repo_stats:
            active |= rs.active_contributors
            new |= rs.new_contributors

        # Google Group messages for this prior month
        gg_count = 0
        try:
            _threads, gg_count = collect_google_group(
                cfg.google_group.archive_url, y, m,
            )
        except Exception:
            log.warning(
                "Failed to fetch prior Google Group data for %d-%02d",
                y, m, exc_info=True,
            )

        snapshot = MetricsSnapshot(
            month=m,
            year=y,
            open_issues=open_issues,
            merged_prs=merged_prs,
            commits=commits,
            active_contributors=len(active),
            new_contributors=len(new),
            google_group_messages=gg_count,
            tlc_runs=tlc_by_month.get((y, m), 0),
        )
        history = append_to_history(snapshot, history_path)

    return history


def _do_collect(cfg: Config) -> CollectedData:
    """Run all four collectors, each cached separately.

    Per-collector caches live in ``output/cache/``.  Delete individual
    files to re-run a specific collector::

        rm output/cache/github.json      # re-collect GitHub only
        rm output/cache/google_group.json # re-collect Google Group only
        rm output/cache/*.json            # re-collect everything
    """
    from autoposter.collectors.github_collector import collect_github
    from autoposter.collectors.google_group import collect_google_group
    from autoposter.collectors.grants import collect_grants
    from autoposter.collectors.metabase import collect_metabase
    from autoposter.models import (
        CommunityThread,
        CollectedItem,
        GrantInfo,
        RepoStats,
        ToolRunStats,
    )

    _step(f"Collecting data for {cfg.month_name} {cfg.year}")

    # --- GitHub ---
    gh_cache = _cache_path(cfg, "github.json")
    if gh_cache.exists():
        click.echo(f"[{_now()}]   → GitHub repos: cached ✓")
        gh_data = json.loads(gh_cache.read_text())
        items = [CollectedItem(**i) for i in gh_data["items"]]
        repo_stats = [RepoStats.from_dict(rs) for rs in gh_data["repo_stats"]]
    else:
        t = _step("  → GitHub repos")
        repos = [{"name": r.name, "slug": r.slug} for r in cfg.repos]
        cache_dir = Path(cfg.output_dir) / ".repo-cache"
        items, repo_stats = collect_github(
            repos, cfg.year, cfg.month,
            github_token=cfg.github_token,
            cache_dir=cache_dir,
        )
        gh_cache.write_text(json.dumps({
            "items": [asdict(i) for i in items],
            "repo_stats": [rs.to_dict() for rs in repo_stats],
        }, indent=2, default=str))
        _done(t)
        click.echo(f"    {len(items)} items, {len(repo_stats)} repos")

    # --- Google Group ---
    gg_cache = _cache_path(cfg, "google_group.json")
    if gg_cache.exists():
        click.echo(f"[{_now()}]   → Google Group: cached ✓")
        gg_data = json.loads(gg_cache.read_text())
        threads = [CommunityThread(**t) for t in gg_data["threads"]]
        message_count = gg_data["message_count"]
    else:
        t = _step("  → Google Group")
        threads, message_count = collect_google_group(
            cfg.google_group.archive_url, cfg.year, cfg.month,
        )
        gg_cache.write_text(json.dumps({
            "threads": [asdict(t) for t in threads],
            "message_count": message_count,
        }, indent=2, default=str))
        _done(t)
        click.echo(f"    {len(threads)} threads, {message_count} messages")

    # --- Metabase ---
    mb_cache = _cache_path(cfg, "metabase.json")
    if mb_cache.exists():
        click.echo(f"[{_now()}]   → Metabase: cached ✓")
        mb_data = json.loads(mb_cache.read_text())
        tool_runs = ToolRunStats(**mb_data)
    else:
        t = _step("  → Metabase")
        tool_runs = collect_metabase(
            cfg.metabase.dashboard_url,
            cfg.metabase.card_uuids,
            cfg.year,
            cfg.month,
        )
        mb_cache.write_text(json.dumps(asdict(tool_runs), indent=2))
        _done(t)
        click.echo(f"    TLC runs={tool_runs.tlc_runs}")

    # --- Grants ---
    gr_cache = _cache_path(cfg, "grants.json")
    if gr_cache.exists():
        click.echo(f"[{_now()}]   → Grants: cached ✓")
        gr_data = json.loads(gr_cache.read_text())
        grants = [GrantInfo(**g) for g in gr_data]
    else:
        t = _step("  → Grants")
        grants = collect_grants(cfg.grants.url)
        gr_cache.write_text(json.dumps([asdict(g) for g in grants], indent=2))
        _done(t)
        click.echo(f"    {len(grants)} grants")

    collected = CollectedData(
        month=cfg.month,
        year=cfg.year,
        items=items,
        repo_stats=repo_stats,
        community_threads=threads,
        grants=grants,
        tool_runs=tool_runs,
        google_group_message_count=message_count,
    )
    click.echo(
        f"Collected {len(items)} items, {len(threads)} threads, "
        f"{len(grants)} grants.",
    )
    return collected


def _do_summarize(
    collected: CollectedData,
    cfg: Config,
    *,
    dry_run: bool = False,
) -> SummarizedData:
    """Summarize collected data (or produce placeholders when *dry_run*).

    Results are cached to ``summarized.json``. Delete the file to re-summarize.
    """
    cache = _cache_path(cfg, "summarized.json")
    if not dry_run and cache.exists():
        click.echo(f"[{_now()}] Summarize: cached ✓")
        return SummarizedData.load(cache)

    if dry_run:
        click.echo(f"[{_now()}] Dry-run mode - using placeholder summaries.")
        # Group items by project and format like real output
        dev_bullets = []
        for item in collected.items:
            link = f"[#{item.number}]({item.url})" if item.url else ""
            dev_bullets.append(
                f"**{item.project_name}**: {item.title} ({link})"
            )
        community_bullets = []
        for t in collected.community_threads:
            community_bullets.append(
                f"[{t.subject}]({t.url}) - {t.reply_count} replies"
            )
        return SummarizedData(
            month=collected.month,
            year=collected.year,
            intro="[placeholder intro - LLM was skipped with --dry-run]",
            dev_update_bullets=dev_bullets,
            community_bullets=community_bullets,
        )

    from autoposter.summarizer.llm import summarize

    t = _step("Summarizing with LLM")
    llm_kwargs: dict[str, str] = {}
    if cfg.llm.provider == "azure_openai":
        model = cfg.llm.azure_deployment or cfg.llm.model
        if cfg.llm.azure_api_version:
            llm_kwargs["azure_api_version"] = cfg.llm.azure_api_version
        click.echo(f"  deployment={model}, api_version={cfg.llm.azure_api_version}")
    else:
        model = cfg.llm.model
    if cfg.llm.provider == "ollama" and cfg.llm.ollama_base_url:
        llm_kwargs["ollama_base_url"] = cfg.llm.ollama_base_url

    summarized = summarize(
        collected,
        provider=cfg.llm.provider,
        model=model,
        **llm_kwargs,
    )
    _done(t)
    click.echo(
        f"  {len(summarized.dev_update_bullets)} dev bullets, "
        f"{len(summarized.community_bullets)} community bullets.",
    )
    summarized.save(cache)
    return summarized


def _do_build(
    summarized: SummarizedData,
    collected: CollectedData,
    cfg: Config,
) -> tuple[str, Path, list[Path]]:
    """Compute metrics, render charts, render & validate the post.

    Returns ``(content, post_path, chart_paths)``.
    """
    from autoposter.builder.charts import render_charts
    from autoposter.builder.metrics import append_to_history, compute_metrics
    from autoposter.builder.renderer import render_post, write_post
    from autoposter.builder.validator import validate_post

    output_dir = Path(cfg.output_dir)
    history_path = output_dir / "metrics_history.json"

    # Current month metrics
    t = _step("Computing metrics")
    snapshot = compute_metrics(collected)
    summarized.metrics = snapshot
    history = append_to_history(snapshot, history_path)
    _done(t)

    # Collect prior 2 months if missing from history
    t = _step("Collecting prior month metrics")
    history = _ensure_prior_months(cfg, history, history_path)
    _done(t)

    # Charts — render into the article's content folder so they sit next to index.md
    t = _step("Rendering charts")
    article_dir = output_dir / f"{cfg.year}-{cfg.month:02d}-dev-update"
    article_dir.mkdir(parents=True, exist_ok=True)
    chart_paths = render_charts(history, article_dir)
    _done(t)

    # Render
    t = _step("Rendering post")
    content = render_post(summarized, cfg, chart_paths, history=history)
    _done(t)

    # Validate
    t = _step("Validating")
    collected_urls: set[str] = set()
    for item in collected.items:
        if item.url:
            collected_urls.add(item.url)
    for thread in collected.community_threads:
        if thread.url:
            collected_urls.add(thread.url)
    for grant in collected.grants:
        if grant.url:
            collected_urls.add(grant.url)

    errors = validate_post(content, collected_urls, article_dir)
    _done(t)
    if errors:
        click.echo(f"  {len(errors)} validation warning(s) - see output/devupdate.log")
        for err in errors:
            log.warning("Validation: %s", err)

    # Write
    post_path = write_post(content, output_dir, cfg.year, cfg.month)
    click.echo(f"[{_now()}] Wrote {post_path}")

    return content, post_path, chart_paths


# ---------------------------------------------------------------------------
# Config override helper
# ---------------------------------------------------------------------------


def _apply_overrides(
    cfg: Config,
    month: int | None,
    year: int | None,
    output_dir: str | None,
) -> Config:
    """Return a new :class:`Config` with any CLI overrides applied."""
    overrides: dict[str, object] = {}
    if month is not None:
        overrides["month"] = month
    if year is not None:
        overrides["year"] = year
    if output_dir is not None:
        overrides["output_dir"] = output_dir
    if overrides:
        cfg = replace(cfg, **overrides)
    return cfg


# ---------------------------------------------------------------------------
# Click CLI
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to config.yaml (default: autoposter/config.yaml).",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable DEBUG logging.")
@click.pass_context
def main(ctx: click.Context, config_path: Path | None, verbose: bool) -> None:
    """devupdate — TLA+ monthly development update generator."""
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error loading config: {exc}", err=True)
        sys.exit(1)

    # All logging to file, nothing on terminal.
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    log_file = out / "devupdate.log"

    logging.root.handlers.clear()
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    file_handler.setLevel(logging.DEBUG)
    logging.root.addHandler(file_handler)
    logging.root.setLevel(logging.DEBUG if verbose else logging.INFO)

    for name in ("httpx", "httpcore", "openai", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)

    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg


# -- run --------------------------------------------------------------------


@main.command()
@click.option("--month", type=int, default=None, help="Override target month.")
@click.option("--year", type=int, default=None, help="Override target year.")
@click.option("--output-dir", type=str, default=None, help="Override output directory.")
@click.option("--dry-run", is_flag=True, help="Skip LLM calls; use placeholder text.")
@click.pass_context
def run(
    ctx: click.Context,
    month: int | None,
    year: int | None,
    output_dir: str | None,
    dry_run: bool,
) -> None:
    """Run the full pipeline (collect -> summarize -> build)."""
    cfg = _apply_overrides(ctx.obj["config"], month, year, output_dir)
    pipeline_start = time.monotonic()
    click.echo(f"[{_now()}] Pipeline started for {cfg.month_name} {cfg.year}")
    try:
        collected = _do_collect(cfg)
        summarized = _do_summarize(collected, cfg, dry_run=dry_run)
        _content, post_path, chart_paths = _do_build(summarized, collected, cfg)
    except Exception as exc:
        click.echo(f"[{_now()}] Pipeline failed: {exc}", err=True)
        log.debug("Traceback:", exc_info=True)
        sys.exit(1)

    total = time.monotonic() - pipeline_start
    click.echo(f"[{_now()}] ----------------------------------------")
    click.echo(f"  Post:   {post_path}")
    click.echo(f"  Charts: {len(chart_paths)} file(s)")
    click.echo(f"  Log:    {Path(cfg.output_dir) / 'devupdate.log'}")
    click.echo(f"  Total:  {total:.1f}s")
    click.echo(f"[{_now()}] Done")


# -- collect ----------------------------------------------------------------


@main.group(invoke_without_command=True)
@click.option("--month", type=int, default=None, help="Override target month.")
@click.option("--year", type=int, default=None, help="Override target year.")
@click.option("--output-dir", type=str, default=None, help="Override output directory.")
@click.pass_context
def collect(
    ctx: click.Context,
    month: int | None,
    year: int | None,
    output_dir: str | None,
) -> None:
    """Run collectors and save data as JSON.

    Without a subcommand, runs ALL collectors. Use a subcommand to run
    one at a time: github, google-group, metabase, grants.
    """
    cfg = _apply_overrides(ctx.obj["config"], month, year, output_dir)
    ctx.obj["config"] = cfg

    # If no subcommand given, run all collectors.
    if ctx.invoked_subcommand is not None:
        return

    try:
        collected = _do_collect(cfg)
    except Exception as exc:
        click.echo(f"Collection failed: {exc}", err=True)
        log.debug("Traceback:", exc_info=True)
        sys.exit(1)

    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "collected.json"
    collected.save(dest)
    click.echo(f"Saved collected data to {dest}")


@collect.command("github")
@click.pass_context
def collect_github_cmd(ctx: click.Context) -> None:
    """Collect merged PRs, releases, and stats from tracked GitHub repos."""
    from autoposter.collectors.github_collector import collect_github

    cfg: Config = ctx.obj["config"]
    click.echo(f"Collecting GitHub data for {cfg.month_name} {cfg.year} …")
    repos = [{"name": r.name, "slug": r.slug} for r in cfg.repos]
    cache_dir = Path(cfg.output_dir) / ".repo-cache"
    try:
        items, repo_stats = collect_github(
            repos, cfg.year, cfg.month,
            github_token=cfg.github_token,
            cache_dir=cache_dir,
        )
    except Exception as exc:
        click.echo(f"GitHub collection failed: {exc}", err=True)
        log.debug("Traceback:", exc_info=True)
        sys.exit(1)

    click.echo(f"\nResults: {len(items)} items across {len(repo_stats)} repos")
    for rs in repo_stats:
        click.echo(
            f"  {rs.repo_slug}: {rs.merged_prs} PRs, {rs.commits} commits, "
            f"{rs.open_issues} open issues, "
            f"{len(rs.active_contributors)} contributors"
        )

    _save_json(cfg, "collected_github.json", {
        "items": [_item_to_dict(i) for i in items],
        "repo_stats": [rs.to_dict() for rs in repo_stats],
    })


@collect.command("google-group")
@click.pass_context
def collect_google_group_cmd(ctx: click.Context) -> None:
    """Collect discussion threads from the TLA+ Google Group archive."""
    from autoposter.collectors.google_group import collect_google_group

    cfg: Config = ctx.obj["config"]
    click.echo(f"Collecting Google Group threads for {cfg.month_name} {cfg.year} …")
    try:
        threads, message_count = collect_google_group(
            cfg.google_group.archive_url, cfg.year, cfg.month,
        )
    except Exception as exc:
        click.echo(f"Google Group collection failed: {exc}", err=True)
        log.debug("Traceback:", exc_info=True)
        sys.exit(1)

    notable = [t for t in threads if t.is_notable]
    click.echo(f"\nResults: {len(threads)} threads, {message_count} messages")
    click.echo(f"Notable threads (>2 replies): {len(notable)}")
    for t in notable:
        click.echo(f"  [{t.reply_count} replies] {t.subject}")

    from dataclasses import asdict
    _save_json(cfg, "collected_google_group.json", {
        "threads": [asdict(t) for t in threads],
        "message_count": message_count,
    })


@collect.command("metabase")
@click.pass_context
def collect_metabase_cmd(ctx: click.Context) -> None:
    """Collect tool-run telemetry from the Metabase public dashboard."""
    from autoposter.collectors.metabase import collect_metabase

    cfg: Config = ctx.obj["config"]
    click.echo(f"Collecting Metabase data for {cfg.month_name} {cfg.year} …")
    try:
        tool_runs = collect_metabase(
            cfg.metabase.dashboard_url, cfg.metabase.card_uuids,
            cfg.year, cfg.month,
        )
    except Exception as exc:
        click.echo(f"Metabase collection failed: {exc}", err=True)
        log.debug("Traceback:", exc_info=True)
        sys.exit(1)

    click.echo(f"\nResults: TLC runs={tool_runs.tlc_runs}")

    from dataclasses import asdict
    _save_json(cfg, "collected_metabase.json", asdict(tool_runs))


@collect.command("grants")
@click.pass_context
def collect_grants_cmd(ctx: click.Context) -> None:
    """Collect grant listings from the TLA+ Foundation grants page."""
    from autoposter.collectors.grants import collect_grants

    cfg: Config = ctx.obj["config"]
    click.echo("Collecting grants …")
    try:
        grants = collect_grants(cfg.grants.url)
    except Exception as exc:
        click.echo(f"Grants collection failed: {exc}", err=True)
        log.debug("Traceback:", exc_info=True)
        sys.exit(1)

    click.echo(f"\nResults: {len(grants)} grants")
    for g in grants:
        click.echo(f"  {g.title}: {g.url}")

    from dataclasses import asdict
    _save_json(cfg, "collected_grants.json", [asdict(g) for g in grants])


# -- collect helpers --------------------------------------------------------


def _item_to_dict(item: object) -> dict:
    """Convert a dataclass to a dict."""
    from dataclasses import asdict
    return asdict(item)  # type: ignore[arg-type]


def _save_json(cfg: Config, filename: str, data: object) -> None:
    """Write *data* as JSON to the output directory and print the path."""
    import json
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / filename
    dest.write_text(json.dumps(data, indent=2, default=str))
    click.echo(f"Saved to {dest}")


# -- summarize --------------------------------------------------------------


@main.command()
@click.option("--month", type=int, default=None, help="Override target month.")
@click.option("--year", type=int, default=None, help="Override target year.")
@click.option("--output-dir", type=str, default=None, help="Override output directory.")
@click.pass_context
def summarize(
    ctx: click.Context,
    month: int | None,
    year: int | None,
    output_dir: str | None,
) -> None:
    """Collect and summarize data, then save as JSON."""
    cfg = _apply_overrides(ctx.obj["config"], month, year, output_dir)
    try:
        collected = _do_collect(cfg)
        summarized = _do_summarize(collected, cfg)
    except Exception as exc:
        click.echo(f"Summarize failed: {exc}", err=True)
        log.debug("Traceback:", exc_info=True)
        sys.exit(1)

    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "summarized.json"
    summarized.save(dest)
    click.echo(f"Saved summarized data to {dest}")


# -- build ------------------------------------------------------------------


@main.command()
@click.option("--month", type=int, default=None, help="Override target month.")
@click.option("--year", type=int, default=None, help="Override target year.")
@click.option("--output-dir", type=str, default=None, help="Override output directory.")
@click.pass_context
def build(
    ctx: click.Context,
    month: int | None,
    year: int | None,
    output_dir: str | None,
) -> None:
    """Collect, summarize, and build the final Markdown post."""
    cfg = _apply_overrides(ctx.obj["config"], month, year, output_dir)
    try:
        collected = _do_collect(cfg)
        summarized = _do_summarize(collected, cfg)
        _content, post_path, chart_paths = _do_build(summarized, collected, cfg)
    except Exception as exc:
        click.echo(f"Build failed: {exc}", err=True)
        log.debug("Traceback:", exc_info=True)
        sys.exit(1)

    click.echo("──────────────────────────────────────")
    click.echo(f"Post:   {post_path}")
    click.echo(f"Charts: {len(chart_paths)} file(s)")
    click.echo("Done ✓")


# -- pr ---------------------------------------------------------------------


@main.command()
@click.option("--month", type=int, default=None, help="Override target month.")
@click.option("--year", type=int, default=None, help="Override target year.")
@click.option("--output-dir", type=str, default=None, help="Override output directory.")
@click.option(
    "--repo-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Path to the local git repo for committing and pushing.",
)
@click.pass_context
def pr(
    ctx: click.Context,
    month: int | None,
    year: int | None,
    output_dir: str | None,
    repo_dir: Path,
) -> None:
    """Run the full pipeline and open a draft pull request."""
    from autoposter.publisher.pr import publish

    cfg = _apply_overrides(ctx.obj["config"], month, year, output_dir)
    try:
        collected = _do_collect(cfg)
        summarized = _do_summarize(collected, cfg)
        _content, post_path, chart_paths = _do_build(summarized, collected, cfg)

        # Gather contributors from collected items
        contributors = sorted(
            {item.author for item in collected.items if item.author},
        )

        click.echo("Opening draft PR …")
        pr_url = publish(
            post_path=post_path,
            asset_paths=chart_paths,
            target_repo=cfg.target_repo,
            year=cfg.year,
            month=cfg.month,
            contributors=contributors,
            github_token=cfg.github_token,
            repo_dir=repo_dir,
        )
    except Exception as exc:
        click.echo(f"PR failed: {exc}", err=True)
        log.debug("Traceback:", exc_info=True)
        sys.exit(1)

    click.echo("──────────────────────────────────────")
    click.echo(f"Post:   {post_path}")
    click.echo(f"PR:     {pr_url}")
    click.echo("Done ✓")
