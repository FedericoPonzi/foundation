# TLA+ Dev Update: Semi-Automated Blog Post

Produce a Markdown post summarizing TLA+ ecosystem activity, in the
style of the [TLA+ Foundation dev updates](https://foundation.tlapl.us/blog/2025-02-dev-update/).
A bot drafts the post and opens a pull request. A maintainer reviews and
merges. Nothing is published automatically.

The post can cover either a **single month** (default) or a whole
**quarter**. The chosen period drives the title, slug, frontmatter date,
and which months feed the development-updates summary; the metrics table
and trend charts always render exactly three monthly datapoints.

## Post Format

Hugo TOML frontmatter, short intro, a placeholder for hand-written highlights,
automated sections with development updates, metrics table (3-month window),
SVG charts, and community items.

```markdown
+++
type = "blog"
title = '{Period} {Monthly|Quarterly} Development Update'
date = {YYYY}-{MM}-15
+++

{2 to 3 sentence intro about the period's focus.}

<!-- add hand-written highlights here -->

## Development Updates

Summaries of merged pull requests (and significant issues or releases) for
each project this month.

- **TLC**: Graal native-image support for SANY was improved so TLA+ modules
  embedded in the image load correctly
  ([#1116](https://github.com/tlaplus/tlaplus/pull/1116))
- **TLC**: New feature flag.
- **Vscode Extension**: Syntax highlighting no longer treats operator definitions inside
  comments as operators
  ([#362](https://github.com/tlaplus/vscode-tlaplus/pull/362)).
- **TLAPM**: Fixed a race condition in the language server when multiple backend
  provers run concurrently
  ([#194](https://github.com/tlaplus/tlapm/pull/194)).

### By the Numbers

| Metric                        | Jan 2026 | Feb 2026 | Mar 2026 |
| ----------------------------- | -------: | -------: | -------: |
| Open issues                   |      612 |      630 |      643 |
| Merged pull requests          |       28 |       33 |       46 |
| Commits                       |       82 |       71 |      136 |
| Active contributors           |        7 |        5 |       11 |
| New contributors              |        0 |        1 |        1 |
| Google Group messages          |       18 |       22 |       40 |
| Tool runs (TLC)               |   263941 |    97573 |   209261 |

![Pull requests per month](prs_per_month.svg)
![Commits per month](commits_per_month.svg)
![Active contributors per month](active_contributors_per_month.svg)

> Tool usage stats are opt-in and anonymized; actual usage is likely higher.
> Source: [metabase.tlapl.us](https://metabase.tlapl.us/public/dashboard/cf7e1a79-19b6-4be1-88bf-0a3fd5aa0dec).

### Community & Events

- [TLA+ Community Meeting 2025](https://discuss.tlapl.us/msg06684.html) - 5 replies
- [Model network using set or bag](https://discuss.tlapl.us/msg06689.html) - 10 replies
```

## How Each Section is Populated

The post mixes hand-written highlights at the top with automated sections
below. The bot generates only the automated parts; the maintainer adds
any hand-written feature sections during PR review.

### Intro

Written by the LLM last, given the other sections as context. 2 to 3
sentences naming the month's focus.

The intro is biased toward **bug-fix highlights** - especially
soundness, correctness, liveness, and verifier-engine fixes - over
feature work or tooling polish. If a fix could cause silent incorrect
results (bogus counterexamples, missed violations, wrong booleans, etc.)
the LLM is instructed to call it out by name. Examples of the kind of
fix that should be highlighted:
[tlaplus#1332](https://github.com/tlaplus/tlaplus/issues/1332).

### Hand-written feature sections

Optional. Top-level (`H2`) sections written by the maintainer for major
features that deserve more than a one-line bullet (for example
"New debugger support" or "TLA+ formatter now available into tlatools").
The bot does not generate or modify these. It emits a placeholder
comment in the post (`<!-- add hand-written highlights here -->`)
between the intro and `Development Updates` to make the insertion point
obvious during review.

### Development Updates

A single flat bulleted list. One bullet per merged PR (or significant
issue or release) across all tracked projects. Each bullet is prefixed
with the **bold project name** and is one short paragraph describing what changed,
with PR numbers linked inline. Bullets do not lead with contributor
names. When an item carries a ```changelog``` fence, the fence's
contents are used verbatim as the bullet body (see below).

Project name prefixes and source repos:

- `TLC`: [`tlaplus/tlaplus`](https://github.com/tlaplus/tlaplus)
- `Vscode Extension`: [`tlaplus/vscode-tlaplus`](https://github.com/tlaplus/vscode-tlaplus)
- `TLAPM`: [`tlaplus/tlapm`](https://github.com/tlaplus/tlapm)
- `Community Modules`: [`tlaplus/CommunityModules`](https://github.com/tlaplus/CommunityModules)
- `Examples`: [`tlaplus/Examples`](https://github.com/tlaplus/Examples)
- `Apalache`: [`apalache-mc/apalache`](https://github.com/apalache-mc/apalache)

Bullets are grouped by project in the order above and otherwise sorted
by merge date. Each bullet ends with an HTML comment carrying the
GitHub username of the author, e.g.
`... ([#123](url)) <!-- author: alice -->`. The comment is invisible in
rendered Markdown but lets a reviewer see who wrote a change without
clicking through to the PR.

#### Filtering & release-merging

Not every PR / issue / release is interesting to end users. The LLM is
asked to act as the editor and decide what to drop. The criteria the
prompt enumerates are:

- `bot`         : automated PRs (scala-steward, dependabot, renovate,
                  github-actions[bot], copilot[bot], etc.)
- `dep-update`  : dependency or version bumps with no functional change
- `testing`     : changes that only touch tests, CI, or scaffolding
- `low-impact`  : trivial typo / comment / lint fixes with no
                  user-visible effect
- `merged-into-latest` : an older release in a same-project release
                  group whose notes were folded into a single combined
                  release bullet

When the same project has multiple releases in the same month (e.g.,
Apalache 0.54.0, 0.55.0, 0.55.1), the LLM collapses them into ONE
bullet that summarises what changed across the whole range and links
only to the LATEST release. The older releases are reported in the
filtered-items comment block with reason `merged-into-latest`.

Filtered items are **not deleted** — the LLM emits a single trailing
HTML comment block at the end of the Development Updates section
listing every dropped item with its one-word reason, so an editor
reviewing the PR can re-add anything they disagree with:

```
<!--
Filtered items (editor: re-add if you disagree):
- [TLC] Bump scala-steward dep (https://...) — bot
- [Apalache] Release 0.54.0 (https://...) — merged-into-latest
-->
```

Items that carry an explicit ```changelog``` fence bypass the LLM
entirely and are always kept (see Contributor-Authored Entries below).

### By the Numbers

The metrics table always shows **three monthly datapoints**:

- **Monthly mode**: selected month + 2 prior months (e.g. for `2026-03`,
  the table shows Jan / Feb / Mar 2026).
- **Quarterly mode**: the three months of the quarter (e.g. for
  `2026-Q1`, the table shows Jan / Feb / Mar 2026).

This gives context for trends without needing to scroll through charts.

Across all tracked repos, the builder counts merged PRs, commits,
active contributors, and first-time contributors. (A `Releases` row
used to be tracked but was dropped: TLC and most projects roll
releases continuously, so the metric was misleading; release activity
is still surfaced as bullets in the Development Updates section.)
`Open issues` is computed via the GitHub Search API as
`is:issue created:<=EOM minus is:issue closed:<=EOM` so it works for
both the selected month and prior months. `Google Group messages`
comes from the public mailing list archive at
<https://discuss.tlapl.us/maillist.html> and is fetched per month.
`Tool runs (TLC)` comes from the public Metabase dashboard at
<https://metabase.tlapl.us/public/dashboard/cf7e1a79-19b6-4be1-88bf-0a3fd5aa0dec>,
queried via the dashboard card API. Only TLC runs are tracked (Apalache
telemetry is not available via the public dashboard).

Each chart-window month not yet present in `output/metrics_history.json`
is collected automatically (so a quarterly run will fill in any of its
three months that aren't already cached):
- **Commits and contributors**: from `git log` on cached bare clones (zero API calls)
- **Open issues**: 2 GitHub Search API calls per repo per month
- **Merged PRs**: 1 GitHub Search API call per repo per month
- **TLC tool runs**: from the same Metabase API response (returns all months)
- **Google Group messages**: one mailing-list scrape per prior month

Each run appends rows to `output/metrics_history.json`.
The builder renders 3 per-month line charts as SVGs placed in the same
directory as the post (`content/blog/{slug}-dev-update/`, where
`{slug}` is e.g. `2026-03` or `2026-q1`).

### Community & Events

The place for notable community discussions, workshops, grants,
conferences, and community specs. Grants are extracted automatically
from <https://foundation.tlapl.us/grants/index.html>.

The Google Group archive is used for notable discussions (threads with
more than 2 replies are considered notable).

- Source: [TLA+ Google Group archive](https://discuss.tlapl.us/maillist.html)

## Contributor-Authored Entries

If a PR description or commit message contains a fenced `changelog` block,
the block's contents are used verbatim as the bullet body in
`Development Updates`, preserving Markdown formatting and paragraph breaks.
The builder still adds the project prefix and a trailing link to the
source PR or commit.

Source (in a PR body or commit message on `vscode-tlaplus`):

````markdown
```changelog
This is a longer,

multiline

changelog entry. Most entries should be one short paragraph, but a new
feature might justify two or three.
```
````

Renders as a bullet under `Development Updates`:

> - **Vscode Extension**: This is a longer,
>
>   multiline
>
>   changelog entry. Most entries should be one short paragraph, but a
>   new feature might justify two or three.
>   ([vscode-tlaplus#362](https://github.com/tlaplus/vscode-tlaplus/pull/362))

Items with a `changelog` fence skip the LLM summarizer entirely. Multiple
fences in one item are concatenated in order. Items without a fence go
through normal LLM summarization.

## Architecture Overview

Four stages, each a module with file-based handoff (cached JSON) so
stages can be rerun independently.

1. **Collect** — Four collectors, each cached separately in `output/cache/`:
   - **GitHub** (hybrid git + API): bare blobless clones for commits/contributors
     (zero API calls), GitHub Search API for merged PRs (1 call/repo),
     REST API for releases and open issues (2 calls/repo).
   - **Google Group**: HTML scraper for `discuss.tlapl.us` using binary
     search over the MHonArc date index.
   - **Metabase**: public dashboard card API for TLC tool-run counts.
     Auto-discovers the "Exec Stats per month" card from the dashboard UUID.
   - **Grants**: HTML scraper for the Foundation grants page (Hugo Relearn theme).

2. **Summarize** — Feeds collected items to an LLM using a prompt template.
   Items carrying a ```changelog``` fence bypass the LLM. The intro is
   written last, given all other sections as context. Result cached to
   `output/cache/summarized.json`.

3. **Build** — Renders the post from a Jinja2 template (`templates/post.md.j2`),
   computes the metrics table (3 monthly datapoints — for quarterly
   posts this is the three months of the quarter; for monthly posts the
   selected month + 2 prior), backfills any chart-window months missing
   from history, renders SVG charts (pygal), and runs validation
   (no em/en dashes, well-formed TOML frontmatter, URL provenance, chart
   file existence). Output: `output/{slug}-dev-update.md` plus SVG chart
   files in `output/{slug}-dev-update/` where `{slug}` is e.g. `2026-03`
   or `2026-q1`.

4. **PR** — Copies post + charts to `content/blog/{slug}-dev-update/`,
   commits on a `devupdate/{slug}` branch with `-s` (sign-off),
   force-pushes (safe for re-runs), and opens a PR via GitHub REST API.
   If a PR already exists for that branch, it is reused (no duplicates).
   Contributors are listed in the PR body without @-mentions.

All behavior that varies period-to-period (data sources, filters,
prompt, LLM provider, target repo, schedule) lives in a single
`config.yaml`.

## Period: Monthly vs Quarterly

The CLI accepts a `--period` flag that switches between two modes:

- `--period 2026-03` (or default `--month 3 --year 2026`): a **monthly**
  post. Title: `March 2026 Monthly Development Update`. Slug: `2026-03`.
  Development-update bullets summarize one month of activity.
- `--period 2026-Q1`: a **quarterly** post. Title:
  `Q1 2026 Quarterly Development Update`. Slug: `2026-q1`. The anchor
  date is the 15th of the last month of the quarter. The collectors
  loop over the three months of the quarter, concatenate items, and
  feed the combined set to the LLM as a single batch.

In both modes the metrics table and the three trend charts always show
exactly three monthly datapoints.

## Caching

Each pipeline stage caches its output in `output/cache/`:

| File | Contents | Delete to re-run |
|------|----------|------------------|
| `github_{slug}.json` | Merged PRs, releases, repo stats (per period) | GitHub collection for that period |
| `google_group_{slug}.json` | Threads, message count (per period) | Google Group scraping for that period |
| `metabase_{slug}.json` | TLC tool-run count (per period) | Metabase query for that period |
| `grants.json` | Grant listings (global) | Grants scraping |
| `summarized.json` | LLM-generated summaries | Summarization |

Git repo bare clones are cached in `output/.repo-cache/` and reused
across runs (`git fetch` instead of full clone).

## Workflow

Two supported modes:

- **Local CLI**. A maintainer runs `devupdate run` on their machine. The
  LLM is whichever one they already use, selected via an environment
  variable (OpenAI, Anthropic, Ollama, or Azure OpenAI). This is the
  primary path for ad-hoc or corrective runs. Output is written to the
  local `output/` directory only — no PR is created.

- **GitHub Actions**. A monthly cron (`0 9 1 * *` UTC) plus
  `workflow_dispatch` (with optional month/year inputs) runs the same CLI
  inside Actions. The LLM is Azure OpenAI, configured via repo secrets
  (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`).

The Action uses the built-in `GITHUB_TOKEN` (`contents: write`,
`pull-requests: write`) to push the branch and open the PR. The PR is
authored by `github-actions[bot]`. No App or PAT is needed. All input
data is public, so the token is only used for writing back to its own
repo. The workflow must have **"Allow GitHub Actions to create and
approve pull requests"** enabled in repo settings.

Re-runs are safe: the branch is force-pushed and the existing PR updates
automatically. All output files (post, charts, cache, logs) are uploaded
as workflow artifacts for debugging.

Review workflow in both modes: the bot opens a PR; contributors and
maintainers review and can push fixes or leave comments; the maintainer
addresses comments and merges manually. The bot never merges.
