# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.1] - 2026-04-03

### Added

- CLI stdin support: omit the input path or pass `-` to read CSV/YAML content from stdin in wide CSV mode, `--event-log`, or `--promtest`.

## [0.4.0] - 2026-04-03

### Added

- GitHub Actions CI workflow for linting, multi-version tests, packaging validation, and a Windows smoke test.
- GitHub Actions release workflow for GitHub Release-driven PyPI publishing with Trusted Publishing.
- Dependabot configuration for GitHub Actions, `uv`, and `pre-commit` updates.
- `.pre-commit-config.yaml` and `ruff` tooling for a consistent local developer loop.
- `varying_height` / `--varying-height` for non-promtest timelines, which staggers event label bubbles at multiple heights above and below the line.
- `examples/review_event_log_breaks.csv` and `images/event_log_timeline_breaks.png` as a richer documented event-log example with varying-height labels and multiple time breaks.

### Changed

- Supported Python versions are now 3.11+.
- `Makefile` now includes local lint, format, dependency lock, dist validation, and `check` targets that mirror CI.
- `DEVELOPING.md` now documents the contributor workflow, release flow, Mermaid diagrams, and the one-time PyPI/GitHub environment setup.

## [0.3.1] - 2026-03-25

### Added

- **Examples:** `examples/promtest_callout_packing.yml` plus `images/promtest_callout_packing.png` and `promtest_callout_packing_compact.png` (directional callout packing demos); `examples/promtest_alert_panel_demo.yml` and `images/promtest_alert_panel_demo.png` for dense Alert Checks rows.

### Changed

- **Promtest callout packing:** interval packing uses **directional** x-extents (left- vs right-anchored rows) so well-separated eval/alert callouts reuse lower tracks instead of over-stacking.
- **Promtest Alert Checks panel:** extra y-axis headroom from stacked label depth so labels stay inside the axes; annotations use `clip_on=True` where appropriate.
- **Promtest top series key:** first-series subtitle (metric + `values:` string) moves **below** the top subplot when callouts or a lower panel would obscure it; slightly increased multi-row vertical spacing.

### Documentation

- **PROMTEST.md** and **`examples/gen_charts.py`:** cover new fixtures and generated figures.

## [0.3.0] - 2026-03-24

### Added

- **Promtest label layouts:** `plot_promtest(..., label_layout=...)` and CLI **`--promtest-label-layout`** with **`readable`** (default), **`compact`**, and **`legacy`**. Readable/compact use **interval packing** so eval/alert callouts on different minutes can share a vertical track when their estimated widths do not overlap; figure height follows the packed row count.
- **Callout styling:** vertical accent on the leading or trailing box edge (flush with the frame), inward text padding from the bar, and point-based vertical spacing between rows.
- **Examples:** `examples/promtest_label_minimal.yml`, `examples/promtest_label_multi.yml`, and updates to `promtest_label_demo.yml` for comparing layouts.
- **Docs asset:** `images/event_log_timeline.png` plus a README figure for **long-format** `--event-log` using `examples/incident_log.csv` (ERROR/WARN filter), alongside existing promtest label screenshots.

### Changed

- Promtest multi-column **time breaks** (`break_gap_minutes` / `--promtest-break-gap`): shared x-scale per column, aligned duration tick formatting, and x-tick labels only on the bottom row; ticks omit negative minutes when padding extends left of 0.
- README hero image restored to wide-format CSV example **`timeline1.png`**; promtest quick-start figure uses **`promtest_label_multi.png`**.

### Documentation

- **PROMTEST.md:** label-layout behaviour, time-break details, checked-in figures for multi/readable fixtures, and commands for minimal/multi/dense demos.

## [0.2.1] - 2026-03-23

### Added

- `images/executive_infographic_example.png` and README section **From chart output to executive infographics** — using exported timelines with multimodal / image LLMs for stakeholder visuals.

### Documentation

- README: absolute `raw.githubusercontent.com` / `github.com` links for images and docs so the PyPI project page renders screenshots and links correctly.

## [0.2.0] - 2026-03-23

### Added

- Long-format (“event log”) timelines: `plot_event_log_timeline` — one timestamp column across many rows, optional `label_column`, and optional `filter_column` with `include_values` / `exclude_values` (e.g. log level or event type).
- CLI flags `--event-log`, `--log-time-column`, `--log-label-column`, `--log-filter-column`, `--log-include`, `--log-exclude`; with `--output-dir`, writes `event_log_timeline.png`.
- `examples/incident_log.csv` sample for long-format usage.
- Root `Makefile` for common tasks (`install`, `sync`, `test`, `build`, `clean`, `publish`, `example-charts`, `example-event-log`, etc.).
- `uv.lock` for reproducible installs with `uv sync`.

### Changed

- Wide-format `plot_timeline` now shares rendering with long format via internal `_plot_sorted_events`.

### Fixed

- CLI: removed duplicate save announcement for `--event-log` when using `--output-dir`.

### Documentation

- README and DEVELOPING.md: long-format quick start, Makefile reference, and `make example-event-log`.

## [0.1.0] - 2025-01-01

### Added

- Timeline visualisation from CSV / DataFrame timestamp data.
- Automatic timestamp column detection (columns ending `_utc`).
- Cluster detection for grouping related timestamps.
- Prometheus test file parser (`parse_promtest_file`, `parse_promtest_string`).
- `plot_promtest` step-chart visualiser with self-documenting annotations.
- `expand_values` helper for expanding Prometheus value notation.
- CLI entry point `timelineviz` with `--promtest` flag.
- 113 unit tests with >90 % coverage.
