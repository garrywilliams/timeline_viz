"""
Command-line interface for the timeline visualization library.

This module provides a command-line tool for generating timeline visualizations
from CSV files without writing Python code.
"""

import argparse
import io
import json
import os
import re
import sys

import pandas as pd

from timelineviz.promtest import parse_promtest_file, parse_promtest_string, plot_promtest
from timelineviz.timeline import (
    plot_event_log_timeline,
    plot_multiple_timelines,
)
from timelineviz.utils import create_color_scheme


def parse_args(args=None):
    """Parse command line arguments.

    Parameters:
    -----------
    args : list, optional
        Command line arguments. If None, uses sys.argv[1:]
    """
    parser = argparse.ArgumentParser(
        description="Generate timeline visualizations from CSV data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Generate timelines using auto-detected timestamp columns:
  timelineviz data.csv --output-dir timelines --detect-timestamps
  
  # Specify timestamp columns:
  timelineviz data.csv --timestamp-columns created_at updated_at completed_at
  
  # Set entity identifier column and name:
  timelineviz patients.csv --id-column patient_id --entity-name Patient
  
  # Use custom color scheme:
  timelineviz orders.csv --colors '{"line":"#336699","point_face":"#FFCC00"}'
  
  # Set custom label mappings:
  timelineviz events.csv --label-mappings '{"created_at":"Creation Date","completed_at":"Completion"}'
  
  # Process a specific number of entities:
  timelineviz large_data.csv --max-entities 5

  # Long-format log: one timestamp column, many rows (filter by level/type):
  timelineviz incident.csv --event-log --log-time-column ts \\
    --log-label-column message --log-filter-column level \\
    --log-include ERROR WARN --output-dir out

  # Raw timestamped logs from stdin:
  kubectl logs deploy/my-app --timestamps \\
    | timelineviz --event-log --raw-log-format auto --log-include ERROR WARN
""",
    )

    parser.add_argument(
        "csv_file",
        nargs="?",
        help="CSV/YAML file containing timeline data; omit or use '-' to read from stdin",
    )

    parser.add_argument(
        "--timestamp-columns", "-t", nargs="+", help="Column names containing timestamps"
    )

    parser.add_argument(
        "--detect-timestamps",
        "-d",
        action="store_true",
        help="Automatically detect timestamp columns",
    )

    parser.add_argument("--id-column", "-i", help="Column name for entity identifier")

    parser.add_argument(
        "--entity-name",
        "-e",
        default="Entity",
        help="Name to use for entities in titles (e.g., Patient, Order, User)",
    )

    parser.add_argument("--output-dir", "-o", help="Directory to save timeline images")

    parser.add_argument(
        "--max-entities", "-m", type=int, help="Maximum number of entities to process"
    )

    parser.add_argument(
        "--threshold-days",
        "-T",
        type=float,
        default=1.0,
        help="Number of days gap to consider as a break in timeline",
    )

    parser.add_argument("--figsize", default="15,5", help="Figure size in inches (width,height)")

    parser.add_argument("--point-size", type=int, default=10, help="Size of the event points")

    parser.add_argument(
        "--varying-height",
        action="store_true",
        help="Stagger non-promtest event labels at varying heights above/below the timeline",
    )

    parser.add_argument("--colors", "-c", help="JSON string with custom color scheme")

    parser.add_argument("--label-mappings", "-l", help="JSON string with custom label mappings")

    parser.add_argument(
        "--remove-suffixes", "-r", nargs="+", help="Suffixes to remove when creating labels"
    )

    parser.add_argument(
        "--no-show", action="store_true", help="Don't display plots (only save to files)"
    )

    parser.add_argument("--dpi", type=int, default=150, help="Resolution for saved images")

    parser.add_argument(
        "--promtest",
        action="store_true",
        help="Treat input as a promtool unit-test YAML file and visualise series/alerts",
    )
    parser.add_argument(
        "--promtest-break-gap",
        dest="promtest_break_gap_minutes",
        type=float,
        default=None,
        metavar="MINUTES",
        help="With --promtest: split the time axis when gaps between anchors (0, end, eval/alert times) exceed this many minutes",
    )
    parser.add_argument(
        "--promtest-label-layout",
        choices=("readable", "legacy", "compact"),
        default="readable",
        help="With --promtest: how to place eval/alert and value labels to reduce overlap (default: readable)",
    )

    parser.add_argument(
        "--event-log",
        action="store_true",
        help="Long-format mode: one timestamp column across many rows (see --log-*)",
    )
    parser.add_argument(
        "--log-time-column", metavar="COL", help="Timestamp column (required with --event-log)"
    )
    parser.add_argument(
        "--log-label-column", metavar="COL", help="Column to use as the text label for each event"
    )
    parser.add_argument(
        "--log-filter-column",
        metavar="COL",
        help="Column for --log-include / --log-exclude (e.g. level, event_type)",
    )
    parser.add_argument(
        "--log-include",
        nargs="+",
        metavar="VALUE",
        help="Keep only rows where the filter column equals one of these values",
    )
    parser.add_argument(
        "--log-exclude",
        nargs="+",
        metavar="VALUE",
        help="Drop rows where the filter column equals one of these values",
    )
    parser.add_argument(
        "--raw-log-format",
        nargs="?",
        const="auto",
        choices=("auto", "timestamped", "kubectl"),
        help="With --event-log: parse plain-text logs instead of CSV input (default: auto)",
    )

    # Parse the arguments
    args = parser.parse_args(args)

    # Validate figure size format
    try:
        width, height = map(float, args.figsize.split(","))
    except ValueError:
        parser.error("Figure size must be in format 'width,height'")

    # Convert JSON strings to dicts
    if args.colors:
        try:
            args.colors = json.loads(args.colors)
        except json.JSONDecodeError:
            parser.error("Invalid JSON format for --colors")

    if args.label_mappings:
        try:
            args.label_mappings = json.loads(args.label_mappings)
        except json.JSONDecodeError:
            parser.error("Invalid JSON format for --label-mappings")

    if args.event_log and args.promtest:
        parser.error("--event-log cannot be combined with --promtest")
    if args.raw_log_format and not args.event_log:
        parser.error("--raw-log-format requires --event-log")
    if args.promtest_break_gap_minutes is not None:
        if not args.promtest:
            parser.error("--promtest-break-gap requires --promtest")
        if args.promtest_break_gap_minutes <= 0:
            parser.error("--promtest-break-gap must be positive")
    if args.raw_log_format:
        if args.log_time_column is None:
            args.log_time_column = "ts"
        if args.log_label_column is None:
            args.log_label_column = "message"
        if args.log_filter_column is None:
            args.log_filter_column = "level"
    if args.event_log and not args.log_time_column:
        parser.error("--event-log requires --log-time-column")

    return args


def main(args=None):
    """Main entry point for the CLI tool.

    Parameters:
    -----------
    args : list, optional
        Command line arguments. If None, uses sys.argv[1:]
    """
    if args is None:
        args = sys.argv[1:]

    args = parse_args(args)

    # --- Event log (long-format) mode ---
    if args.event_log:
        return _run_event_log(args)

    # --- Promtest mode ---
    if args.promtest:
        return _run_promtest(args)

    # Parse figure size
    try:
        figsize = tuple(map(float, args.figsize.split(",")))
        if len(figsize) != 2:
            raise ValueError("Figure size must be width,height")
    except ValueError as e:
        print(f"Error parsing figure size: {e}", file=sys.stderr)
        return 1

    # Initialize color_scheme
    color_scheme = None
    input_data = None

    # Validate color scheme if provided
    if args.colors:
        required_keys = [
            "line",
            "point_edge",
            "point_face",
            "connector",
            "label_bg",
            "label_edge",
            "slashes",
            "title",
        ]
        missing_keys = [key for key in required_keys if key not in args.colors]
        if missing_keys:
            print(f"Error: Missing required color keys: {missing_keys}")
            return 1

        # Validate each color value
        try:
            color_scheme = create_color_scheme(
                base_color=args.colors.get("line"), accent_color=args.colors.get("point_face")
            )
        except ValueError as e:
            print(f"Error: Invalid color scheme: {e}")
            return 1

    # Validate label mappings if provided (wide CSV mode only)
    if args.label_mappings and not args.event_log:
        try:
            input_data = _load_csv_input(args.csv_file)
        except FileNotFoundError:
            print(f"Error: File '{args.csv_file}' not found", file=sys.stderr)
            return 1
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        df = input_data if isinstance(input_data, pd.DataFrame) else pd.read_csv(input_data)
        invalid_columns = [col for col in args.label_mappings if col not in df.columns]
        if invalid_columns:
            print(f"Error: Label mappings reference non-existent columns: {invalid_columns}")
            return 1

    # Check if either timestamp columns or detection are specified
    if not args.timestamp_columns and not args.detect_timestamps and not args.event_log:
        print(
            "Warning: No timestamp columns specified and auto-detection disabled.",
            "Will attempt to detect common timestamp column patterns anyway.",
            file=sys.stderr,
        )
        args.detect_timestamps = True

    # Generate the timelines
    try:
        if input_data is None:
            input_data = _load_csv_input(args.csv_file)

        processed = plot_multiple_timelines(
            data=input_data,
            timestamp_columns=args.timestamp_columns,
            id_column=args.id_column,
            detect_timestamps=args.detect_timestamps,
            output_dir=args.output_dir,
            max_entities=args.max_entities,
            threshold_days=args.threshold_days,
            figsize=figsize,
            point_size=args.point_size,
            color_scheme=color_scheme,
            show_plots=not args.no_show,
            dpi=args.dpi,
            label_mappings=args.label_mappings,
            remove_suffixes=args.remove_suffixes,
            entity_name=args.entity_name,
            varying_height=args.varying_height,
        )

        if not processed:
            print(
                "No timelines were generated. Check your input data and parameters.",
                file=sys.stderr,
            )
            return 1

        print(f"Successfully processed {len(processed)} timelines.")
        return 0

    except Exception as e:
        print(f"Error generating timelines: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def _uses_stdin(input_arg):
    """Return True when CLI input should be read from stdin."""
    return input_arg in (None, "-")


def _read_stdin_text():
    """Read piped stdin content with a friendly error for interactive use."""
    if getattr(sys.stdin, "isatty", lambda: False)():
        raise ValueError("No input file provided. Pass a file path or pipe data to stdin.")

    text = sys.stdin.read()
    if not text.strip():
        raise ValueError("No input data received on stdin.")
    return text


def _load_csv_input(input_arg):
    """Load CSV input from a path or stdin for CLI use."""
    if _uses_stdin(input_arg):
        try:
            return pd.read_csv(io.StringIO(_read_stdin_text()))
        except pd.errors.EmptyDataError as e:
            raise ValueError("No CSV data received on stdin.") from e

    if not os.path.isfile(input_arg):
        raise FileNotFoundError(input_arg)

    return input_arg


def _load_text_input(input_arg):
    """Load plain-text input from a path or stdin for CLI use."""
    if _uses_stdin(input_arg):
        return _read_stdin_text()

    if not os.path.isfile(input_arg):
        raise FileNotFoundError(input_arg)

    with open(input_arg, encoding="utf-8") as f:
        text = f.read()

    if not text.strip():
        raise ValueError(f"No input data found in '{input_arg}'.")
    return text


_RAW_TIMESTAMP_PREFIX_RE = re.compile(
    r"^(?P<ts>"
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?"
    r")(?P<rest>\s+.*)?$"
)
_LEVEL_PREFIX_RE = re.compile(
    r"^\s*(?:\[)?(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)(?:\])?"
    r"(?:\s*[:|,-]\s*|\s+)(?P<message>.*)$",
    re.IGNORECASE,
)


def _normalize_log_level(level):
    """Normalize parsed log levels for filtering."""
    normalized = level.strip().upper()
    if normalized == "WARNING":
        return "WARN"
    if normalized == "CRITICAL":
        return "FATAL"
    return normalized


def _parse_raw_timestamped_logs(text):
    """Parse common timestamp-first plain-text logs into a DataFrame."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        ts_match = _RAW_TIMESTAMP_PREFIX_RE.match(line)
        if not ts_match:
            continue

        rest = (ts_match.group("rest") or "").strip()
        level = ""
        message = rest

        level_match = _LEVEL_PREFIX_RE.match(rest)
        if level_match:
            level = _normalize_log_level(level_match.group("level"))
            message = level_match.group("message").strip()
        elif rest.startswith("|"):
            message = rest[1:].strip()

        rows.append(
            {
                "ts": ts_match.group("ts"),
                "level": level,
                "message": message,
            }
        )

    if not rows:
        raise ValueError("No timestamped log lines matched the expected timestamp-first format.")

    return pd.DataFrame(rows)


def _load_event_log_input(input_arg, raw_log_format=None):
    """Load event-log input from CSV or supported raw-log formats."""
    if raw_log_format is None:
        return _load_csv_input(input_arg)

    if raw_log_format in {"auto", "timestamped", "kubectl"}:
        text = _load_text_input(input_arg)
        return _parse_raw_timestamped_logs(text)

    raise ValueError(f"Unsupported raw log format: {raw_log_format}")


def _load_promtest_groups(input_arg):
    """Load promtest YAML from a path or stdin for CLI use."""
    if _uses_stdin(input_arg):
        return parse_promtest_string(_read_stdin_text())

    if not os.path.isfile(input_arg):
        raise FileNotFoundError(input_arg)

    return parse_promtest_file(input_arg)


def _run_event_log(args):
    """Handle --event-log mode."""
    try:
        figsize = tuple(map(float, args.figsize.split(",")))
        if len(figsize) != 2:
            raise ValueError("Figure size must be width,height")
    except ValueError as e:
        print(f"Error parsing figure size: {e}", file=sys.stderr)
        return 1

    color_scheme = None
    if args.colors:
        required_keys = [
            "line",
            "point_edge",
            "point_face",
            "connector",
            "label_bg",
            "label_edge",
            "slashes",
            "title",
        ]
        missing_keys = [key for key in required_keys if key not in args.colors]
        if missing_keys:
            print(f"Error: Missing required color keys: {missing_keys}", file=sys.stderr)
            return 1
        try:
            color_scheme = create_color_scheme(
                base_color=args.colors.get("line"), accent_color=args.colors.get("point_face")
            )
        except ValueError as e:
            print(f"Error: Invalid color scheme: {e}", file=sys.stderr)
            return 1

    output_file = None
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        output_file = os.path.join(args.output_dir, "event_log_timeline.png")

    try:
        input_data = _load_event_log_input(args.csv_file, raw_log_format=args.raw_log_format)
        fig, _axs = plot_event_log_timeline(
            data=input_data,
            timestamp_column=args.log_time_column,
            label_column=args.log_label_column,
            filter_column=args.log_filter_column,
            include_values=args.log_include,
            exclude_values=args.log_exclude,
            threshold_days=args.threshold_days,
            figsize=figsize,
            point_size=args.point_size,
            color_scheme=color_scheme,
            show_plot=not args.no_show,
            dpi=args.dpi,
            output_file=output_file,
            varying_height=args.varying_height,
        )
    except FileNotFoundError:
        print(f"Error: File '{args.csv_file}' not found", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error generating event log timeline: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1

    if fig is None:
        print("No event log timeline was generated. Check filters and timestamps.", file=sys.stderr)
        return 1

    # Save path is already printed by plot_event_log_timeline / _plot_sorted_events
    print("Successfully generated event log timeline.")
    return 0


def _run_promtest(args):
    """Handle --promtest mode."""
    try:
        figsize = tuple(map(float, args.figsize.split(",")))
    except ValueError:
        figsize = None

    try:
        groups = _load_promtest_groups(args.csv_file)
    except FileNotFoundError:
        print(f"Error: File '{args.csv_file}' not found", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error parsing promtest file: {e}", file=sys.stderr)
        return 1

    if not groups:
        print("No test groups found in the file.", file=sys.stderr)
        return 1

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    try:
        results = plot_promtest(
            groups,
            figsize=figsize,
            show_plot=not args.no_show,
            output_file=os.path.join(args.output_dir, "promtest.png") if args.output_dir else None,
            dpi=args.dpi,
            break_gap_minutes=args.promtest_break_gap_minutes,
            label_layout=args.promtest_label_layout,
        )
        print(f"Successfully visualised {len(results)} test group(s).")
        return 0
    except Exception as e:
        print(f"Error generating promtest visualisation: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
