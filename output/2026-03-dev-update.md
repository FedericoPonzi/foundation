---
title: "March 2026 Development Update"
layout: post
---

# March 2026 Development Update

This month centers on tightening TLC liveness checking, unifying formatting across the core toolchain, and expanding Apalache's JSON-RPC for more efficient remote exploration. Highlights include more precise temporal counterexamples and error messages in TLC, the TLA+ formatter now shipping directly with `tlatools` and used by the VS Code extension, and a series of Apalache releases that add compressed JSON-RPC methods, new exploration primitives, and improved Quint-to-TLA+ translation.

<!-- add hand-written highlights here -->

## Development Updates

Summaries of merged pull requests (and significant issues or releases) for
each project this month.


- This month focuses on improving TLC's liveness checking and tooling ergonomics, integrating the TLA+ formatter into core tools, and extending Apalache's JSON-RPC capabilities for more efficient remote exploration. TLC tightens correctness around temporal properties and clarifies the transition away from the Toolbox, while the VS Code extension and XML exporter adapt to the new formatter and parsing behavior. Apalache delivers several JSON-RPC enhancements, performance-oriented features, and Quint-to-TLA+ translation improvements.

- TLC: Extends the XML exporter schema with explicit documentation and enumeration of built-in operator names and runs the exporter over all `tlaplus/examples` specs as a regression test to catch schema-related parsing issues early ([#1324](https://github.com/tlaplus/tlaplus/pull/1324)).

- TLC: Adds a deprecation notice to the Toolbox welcome page and release notes, directing users toward the actively maintained VS Code and Cursor extensions and command-line TLC, and linking to migration resources ([#1339](https://github.com/tlaplus/tlaplus/pull/1339)).

- TLC: Documents the expected git commit message format in `CONTRIBUTING.md`, making contribution guidelines clearer for new and existing contributors ([#1341](https://github.com/tlaplus/tlaplus/pull/1341)).

- TLC: Adds regression tests for a soundness bug in `ENABLED` when Java-overridden operators receive lambdas referencing primed variables through `INSTANCE` substitution, guarding against silent boolean mis-evaluations in future changes ([#1342](https://github.com/tlaplus/tlaplus/pull/1342)).

- TLC: Updates CI workflows to run on `windows-latest` alongside other platforms and adjusts build steps conditionally, improving cross-platform coverage and catching Windows-specific issues earlier ([#1343](https://github.com/tlaplus/tlaplus/pull/1343)).

- TLC: Refactors architecture detection from `x86/x86_64` to `BIT_32/BIT_64`, fixing incorrect reporting of `x86` on non-x86 architectures such as ARM and aligning REPL, TLC, and tests with the new enumeration ([#1345](https://github.com/tlaplus/tlaplus/pull/1345)).

- TLC: Expands the README usage section with notes on GUI-based workflows and adds `USE.md` to document using TLC as a Java library and consuming its outputs from non-Java tools, making integration paths more discoverable ([#1340](https://github.com/tlaplus/tlaplus/pull/1340)).

- TLC: Fixes a bug where liveness checking could report a bogus safety counterexample when encountering an accepting tableau node, now ensuring that PossibleErrorModel conditions are checked before treating a finite prefix as a valid safety violation ([#1348](https://github.com/tlaplus/tlaplus/pull/1348)).

- TLC: Implements lazy evaluation of operator arguments in `Liveness.java` via `getVal`, improving handling of state-level expressions and adding regression tests for properties defined through parameterized operators in `INSTANCE`d modules ([#1350](https://github.com/tlaplus/tlaplus/pull/1350)).

- TLC: Integrates the TLA+ formatter into `tla2tools` so it ships with `tlatools.jar` alongside SANY and TLC, updates the Ant build and tests (including Windows support), and removes web-specific formatter dependencies ([#1347](https://github.com/tlaplus/tlaplus/pull/1347)).

- TLC: Adds comprehensive documentation comments and TODOs to the XML exporter schema file without changing the schema itself, making the XML format and built-in operator handling easier to understand and evolve ([#1346](https://github.com/tlaplus/tlaplus/pull/1346)).

- TLC: Defers raising `TLC_CONFIG_NO_SPEC_BUT_PROPERTY` and `TLC_CONFIG_NO_FAIRNESS_BUT_LIVE_PROPERTY` until after liveness processing, avoiding misleading warnings when property violations are actually safety violations caught by earlier enhancements ([#1351](https://github.com/tlaplus/tlaplus/pull/1351)).

- TLC: Adds `-suppressMessages` and `-warningsAsErrors` CLI flags to SANY, enabling fine-grained control over specific diagnostic codes and allowing users to silence or promote selected warnings to errors in automated workflows ([#1344](https://github.com/tlaplus/tlaplus/pull/1344)).

- TLC: Adjusts CI to skip example specs that require Apalache, removing a dependency on the Apalache build system and stabilizing the TLC CI pipeline ([#1354](https://github.com/tlaplus/tlaplus/pull/1354)).

- TLC: Changes SANY to run the linter only after successful semantic analysis and level checking, preventing crashes when semantic analysis is skipped and ensuring linting is applied at the most appropriate analysis stage ([#1356](https://github.com/tlaplus/tlaplus/pull/1356)).

- TLC: Improves the XML exporter so that parse failures no longer dump Java stack traces, instead returning standardized exit codes and printing only SANY's user-friendly parse errors, which is important for TLAPM integration ([#1327](https://github.com/tlaplus/tlaplus/pull/1327)).

- TLC: Hardens CI security by removing some third-party GitHub Actions and pinning the remaining ones to specific versions, reducing supply-chain risk in the build pipeline ([#1364](https://github.com/tlaplus/tlaplus/pull/1364)).

- TLC: Discontinues macOS code signing and notarization due to expired certificates and developer membership, advising users to manually whitelist the Toolbox or switch to the recommended VS Code and Cursor workflows ([#1365](https://github.com/tlaplus/tlaplus/pull/1365)).

- TLC: Enhances error reporting so TLC now shows which temporal property is violated when a liveness check fails, making it easier to correlate counterexamples with specific properties ([#1355](https://github.com/tlaplus/tlaplus/pull/1355)).

- VS Code Extension: Updates the formatter URL to point at the formatter now bundled with `tlatools`, aligning the extension with the new distribution model ([#506](https://github.com/tlaplus/vscode-tlaplus/pull/506)).

- VS Code Extension: Fixes the MCP TLC tools to honor an explicitly provided `cfgFile` parameter instead of re-running discovery, enabling workflows with multiple configuration files per module without spurious "No .cfg found" errors ([#509](https://github.com/tlaplus/vscode-tlaplus/pull/509)).

- VS Code Extension: Switches the extension to use the formatter included in `tlatools`, simplifying installation and ensuring consistent formatting behavior with the core TLA+ tools ([#510](https://github.com/tlaplus/vscode-tlaplus/pull/510)).

- VS Code Extension: Updates tests to expect that linting is no longer run after SANY parse failures, reflecting the new SANY behavior from tlaplus PR [#1356](https://github.com/tlaplus/tlaplus/pull/1356) ([#512](https://github.com/tlaplus/vscode-tlaplus/pull/512)).

- VS Code Extension: Aligns the CI workflow with the release workflow so that passing CI is a stronger predictor of release success, reducing the chance of regressions slipping through ([#511](https://github.com/tlaplus/vscode-tlaplus/pull/511)).

- TLAPM: Fixes several example specs that reused identifiers from enclosing scopes, updating them to avoid shadowing so they parse cleanly with SANY and remain valid TLA+ examples ([#251](https://github.com/tlaplus/tlapm/pull/251)).

- Apalache: Releases version [0.56.1](https://github.com/apalache-mc/apalache/releases/tag/v0.56.1), adding support for the `leadsTo` operator in Quint-to-TLA+ translation and fixing LET-IN printing and `UNCHANGED` handling to avoid scoping and "used before assigned" errors.

- Apalache: Releases version [0.56.0](https://github.com/apalache-mc/apalache/releases/tag/v0.56.0), upgrading Jetty to 12.1.7, adding gzip and Zstandard compression to the JSON-RPC server, and extending the `query` method with a `STATE` kind to return only the last state.

- Apalache: Releases version [0.55.0](https://github.com/apalache-mc/apalache/releases/tag/v0.55.0), introducing a `compact` JSON-RPC method that resets solver complexity by reasserting the last concrete state as a synthetic transition.

- Apalache: Releases version [0.54.0](https://github.com/apalache-mc/apalache/releases/tag/v0.54.0), continuing the regular release cadence and bundling recent JSON-RPC and tooling improvements.

- Apalache: Releases version [0.52.3](https://github.com/apalache-mc/apalache/releases/tag/v0.52.3), adding the ordered JSON-RPC method `applyInOrder` for batching exploration steps and fixing a lexer bug affecting `RecvNotification`.

- Apalache: Restructures macOS integration tests to avoid Nix, installing required tools directly to prevent out-of-memory failures during `nix develop` while keeping the Nix-based path for Linux unchanged ([#3279](https://github.com/apalache-mc/apalache/pull/3279)).

- Apalache: Fixes a `Type1Lexer` corner case where tags like `RecvNotification(...)` were incorrectly tokenized, adding tests to ensure such variant tags are parsed correctly going forward ([#3278](https://github.com/apalache-mc/apalache/pull/3278)).

- Apalache: Adds the JSON-RPC `applyInOrder` method to execute multiple exploration operations in a single request, reducing client-server round trips for typical step sequences ([#3280](https://github.com/apalache-mc/apalache/pull/3280)).

- Apalache: Prepares and merges the [0.52.3 release PR](https://github.com/apalache-mc/apalache/pull/3281), finalizing the changelog and versioning for that release.

- Apalache: Prepares and merges the [0.54.0 release PR](https://github.com/apalache-mc/apalache/pull/3283), coordinating the release process and documentation updates.

- Apalache: Implements the JSON-RPC `compact` method that extracts the last concrete state, reverts to a snapshot, and reasserts it as a synthetic transition, helping recover from long symbolic explorations ([#3285](https://github.com/apalache-mc/apalache/pull/3285)).

- Apalache: Prepares and merges the [0.55.0 release PR](https://github.com/apalache-mc/apalache/pull/3286), promoting the new `compact` functionality and related changes.

- Apalache: Updates `sbt` and `scripted-plugin` from 1.12.2 to 1.12.6, keeping the build tooling current and benefiting from upstream fixes and improvements ([#3277](https://github.com/apalache-mc/apalache/pull/3277)).

- Apalache: Upgrades `sbt-scalafix` to 0.14.6, improving code rewriting and linting support in the Scala build ([#3272](https://github.com/apalache-mc/apalache/pull/3272)).

- Apalache: Upgrades the JSON-RPC server's Jetty dependency to 12.x, aligning with newer APIs and enabling later compression features ([#3289](https://github.com/apalache-mc/apalache/pull/3289)).

- Apalache: Extends the JSON-RPC `query` method with a `STATE` kind that returns only the last state, reducing payload sizes when full traces are unnecessary ([#3288](https://github.com/apalache-mc/apalache/pull/3288)).

- Apalache: Adds compression (gzip and Zstandard) to the JSON-RPC server using Jetty 12.1.x and `CompressionHandler`, significantly reducing bandwidth usage for large JSON responses ([#3290](https://github.com/apalache-mc/apalache/pull/3290)).

- Apalache: Updates `logback-classic` and `logback-core` to 1.5.32, bringing in logging fixes and improvements ([#3268](https://github.com/apalache-mc/apalache/pull/3268)).

- Apalache: Updates `jackson-module-scala` to 2.20.2, keeping JSON serialization components up to date ([#3251](https://github.com/apalache-mc/apalache/pull/3251)).

- Apalache: Updates `scalafmt-core` to 3.10.7, maintaining consistent Scala code formatting with the latest formatter version ([#3265](https://github.com/apalache-mc/apalache/pull/3265)).

- Apalache: Prepares and merges the [0.56.0 release PR](https://github.com/apalache-mc/apalache/pull/3291), packaging Jetty upgrades, compression, and JSON-RPC enhancements into a tagged release.

- Apalache: Adds Quint-to-TLA+ conversion for `leadsTo` and fixes a LET-IN caching bug in `setBy` transpilation that could cause function/conjunction evaluation errors, improving correctness of generated TLA+ ([#3294](https://github.com/apalache-mc/apalache/pull/3294)).

- Apalache: Fixes inlining of nullary operators in `UNCHANGED` so grouped-variable `UNCHANGED` constructs with nested operator references are handled correctly, resolving issue [#3143](https://github.com/apalache-mc/apalache/issues/3143) ([#3295](https://github.com/apalache-mc/apalache/pull/3295)).

- Apalache: Updates `sbt` and `scripted-plugin` from 1.12.6 to 1.12.7, continuing incremental build tool maintenance ([#3296](https://github.com/apalache-mc/apalache/pull/3296)).

- Apalache: Prepares and merges the [0.56.1 release PR](https://github.com/apalache-mc/apalache/pull/3297), publishing the `leadsTo` support and UNCHANGED inlining fixes.


### By the Numbers

| Metric                        | Mar 2026 |

| ----------------------------- | -----------: |

| Open issues                   | 643 |

| Merged pull requests          | 46 |

| Commits                       | 136 |

| Releases                      | 5 |

| Active contributors           | 11 |

| New contributors              | 1 |

| Google Group messages          | 40 |

| Tool runs (TLC / Apalache)    | 209261 / 0 |


![Pull requests per month](./assets/2026-03/prs_per_month.svg)
![Commits per month](./assets/2026-03/commits_per_month.svg)
![Active contributors per month](./assets/2026-03/active_contributors_per_month.svg)

> Tool usage stats are opt-in and anonymized; actual usage is likely higher.
> Source: [metabase.tlapl.us](https://metabase.tlapl.us/public/dashboard/cf7e1a79-19b6-4be1-88bf-0a3fd5aa0dec).

### Community & Events


- In [“Describing unless condition in lisp”](https://discuss.tlapl.us/msg06687.html), the community discusses how to express TLA+ `UNLESS` conditions in a Lisp-based specification environment.

- [“In SANY, what is the APSubstInNode AST node used for?”](https://discuss.tlapl.us/msg06676.html) clarifies the role of `APSubstInNode` in the TLA+ parser’s AST and how it represents substitution constructs.

- The Outreach Committee invites everyone to the next community call in [“Join us at the next TLA+ Outreach Committee meeting on January 15, 11am Pacific Time”](https://discuss.tlapl.us/msg06684.html).

- [“Leader backs up followers quickly with persistance”](https://discuss.tlapl.us/msg06686.html) explores modeling a Raft-like protocol where the leader rapidly persists and replicates state to followers.

- In [“Model network using set or bag”](https://discuss.tlapl.us/msg06689.html), practitioners compare sets vs. bags (multisets) for accurately modeling network message behavior.

- [“Request for review?”](https://discuss.tlapl.us/msg06677.html) features a community review of a user’s TLA+ spec, with feedback on structure, invariants, and style.

- [“Stuttering: abstraction vs. implementation”](https://discuss.tlapl.us/msg06708.html) revisits how stuttering steps relate refinement mappings between abstract and concrete specifications.

- [“TLX — TLA+ specifications in Elixir syntax, with TLC integration”](https://discuss.tlapl.us/msg06712.html) announces TLX, a toolchain for writing TLA+ specs in Elixir syntax and model checking them with TLC.

- The thread [“Using TLA+ to Fix a Very Difficult glibc Bug - Malte Skarupke - C++Now 2025”](https://discuss.tlapl.us/msg06675.html) shares and discusses a conference talk on applying TLA+ to diagnose a subtle glibc concurrency bug.

- [“What is the plan for Distributed PlusCal?”](https://discuss.tlapl.us/msg06673.html) asks about the roadmap and current status of Distributed PlusCal support.

- The TLA+ Foundation announces its [Grant Program Call for Proposals](https://foundation.tlapl.us/grants/2024-grant-program/index.html), offering USD $1,000–$100,000 for projects that advance TLA+ research, tooling, and industrial use.

- Newly funded projects are highlighted on the [Grant Recipients](https://foundation.tlapl.us/grants/grant-recipients/index.html) page, showcasing work selected for its potential impact on TLA+ technology and the broader community.

