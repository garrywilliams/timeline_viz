# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
