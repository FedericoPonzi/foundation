"""Publisher that creates a git branch, commits the rendered post, and opens a draft PR.

Orchestrates the final pipeline stage: branch creation, file staging, commit,
push, and draft pull-request via the GitHub REST API (``httpx``).
"""

from __future__ import annotations

import calendar
import logging
import subprocess
from pathlib import Path

import httpx

__all__ = [
    "create_branch",
    "commit_post",
    "open_draft_pr",
    "publish",
]

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run_git(args: list[str], repo_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command inside *repo_dir* and return the result.

    Raises
    ------
    RuntimeError
        If the command exits with a non-zero status. The error message
        includes both stdout and stderr from git.
    """
    cmd = ["git", *args]
    logger.debug("Running: %s (cwd=%s)", " ".join(cmd), repo_dir)
    result = subprocess.run(
        cmd,
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "no output").strip()
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}): {detail}"
        )
    return result


def _month_name(month: int) -> str:
    """Return the full English month name for *month* (1–12)."""
    return calendar.month_name[month]


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def create_branch(year: int, month: int, repo_dir: Path) -> str:
    """Switch to the branch for the monthly update, creating it if needed.

    If the branch already exists (from a prior run), it is checked out
    and reset to the current HEAD of the default branch so the new
    commit replaces the old one.

    Returns the branch name, e.g. ``devupdate/2025-06``.
    """
    branch = f"devupdate/{year}-{month:02d}"
    logger.info("Switching to branch %s", branch)

    try:
        _run_git(["checkout", "-b", branch], repo_dir)
    except RuntimeError:
        # Branch already exists locally — switch to it and reset.
        _run_git(["checkout", branch], repo_dir)
        _run_git(["reset", "--hard", "HEAD~1"], repo_dir)
        logger.info("Branch %s already existed — reset for fresh commit", branch)

    return branch


def commit_post(
    post_path: Path,
    asset_paths: list[Path],
    repo_dir: Path,
    year: int,
    month: int,
) -> str:
    """Stage the post and assets, then create a commit.

    Parameters
    ----------
    post_path:
        Path to the rendered blog-post file (e.g. a ``.md`` file).
    asset_paths:
        Paths to any accompanying asset files (images, charts, etc.).
    repo_dir:
        Path to the local git repository.
    year:
        Four-digit year for the commit message.
    month:
        Month number (1–12) for the commit message.

    Returns
    -------
    str
        The full SHA of the newly created commit.
    """
    files_to_stage = [str(post_path), *(str(p) for p in asset_paths)]
    logger.info("Staging %d file(s)", len(files_to_stage))
    _run_git(["add", "--", *files_to_stage], repo_dir)

    message = f"{_month_name(month)} {year} development update"
    logger.info("Committing: %s", message)
    _run_git(["commit", "-s", "-m", message], repo_dir)

    result = _run_git(["rev-parse", "HEAD"], repo_dir)
    sha = result.stdout.strip()
    logger.info("Commit SHA: %s", sha)
    return sha


def open_draft_pr(
    branch: str,
    target_repo: str,
    year: int,
    month: int,
    contributors: list[str],
    github_token: str,
) -> str:
    """Open a draft PR, or return the existing one if already open.

    On re-runs, the branch is force-pushed with the updated commit.
    If a PR already exists for that branch, its URL is returned without
    creating a duplicate.
    """
    title = f"{_month_name(month)} {year} Development Update"

    mention_lines = "\n".join(f"- @{c}" for c in contributors)
    body = (
        f"## {title}\n\n"
        "Auto-generated monthly development update.\n\n"
        "### Contributors\n\n"
        f"{mention_lines}\n"
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Check if a PR already exists for this branch.
    existing_url = _find_existing_pr(target_repo, branch, headers)
    if existing_url:
        logger.info("PR already exists for branch %s: %s", branch, existing_url)
        return existing_url

    url = f"{_GITHUB_API}/repos/{target_repo}/pulls"
    payload = {
        "title": title,
        "head": branch,
        "base": "main",
        "body": body,
    }

    logger.info("Opening PR on %s: %s", target_repo, title)
    response = httpx.post(url, headers=headers, json=payload, timeout=30)

    if response.status_code >= 400:
        detail = response.text[:500]
        raise RuntimeError(
            f"PR creation failed (HTTP {response.status_code}): {detail}"
        )

    pr_url: str = response.json()["html_url"]
    logger.info("PR created: %s", pr_url)
    return pr_url


def _find_existing_pr(
    target_repo: str,
    branch: str,
    headers: dict[str, str],
) -> str | None:
    """Return the URL of an open PR for *branch*, or None."""
    url = f"{_GITHUB_API}/repos/{target_repo}/pulls"
    params = {"head": branch, "state": "open", "per_page": "1"}
    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        prs = resp.json()
        if prs:
            return prs[0]["html_url"]
    except httpx.HTTPError:
        logger.debug("Could not check for existing PR", exc_info=True)
    return None


def publish(
    post_path: Path,
    asset_paths: list[Path],
    target_repo: str,
    year: int,
    month: int,
    contributors: list[str],
    github_token: str,
    repo_dir: Path,
) -> str:
    """Orchestrate the full publish flow: branch → commit → push → draft PR.

    Parameters
    ----------
    post_path:
        Path to the rendered blog-post file.
    asset_paths:
        Paths to any accompanying asset files.
    target_repo:
        GitHub ``owner/repo`` slug for the PR.
    year:
        Four-digit year.
    month:
        Month number (1–12).
    contributors:
        GitHub usernames to @-mention.
    github_token:
        GitHub API token.
    repo_dir:
        Path to the local git repository.

    Returns
    -------
    str
        The URL of the newly created draft pull request.
    """
    branch = create_branch(year, month, repo_dir)
    commit_post(post_path, asset_paths, repo_dir, year, month)

    logger.info("Pushing branch %s to origin (force)", branch)
    _run_git(["push", "--force", "--set-upstream", "origin", branch], repo_dir)

    pr_url = open_draft_pr(
        branch=branch,
        target_repo=target_repo,
        year=year,
        month=month,
        contributors=contributors,
        github_token=github_token,
    )
    return pr_url
