import io
import json
from types import SimpleNamespace

import pandas as pd
import pytest

import timelineviz.cli as cli_module
from timelineviz.cli import main, parse_args


class _FakeStdin(io.StringIO):
    def __init__(self, text, is_tty=False):
        super().__init__(text)
        self._is_tty = is_tty

    def isatty(self):
        return self._is_tty


def test_parse_args_basic():
    # Test minimal arguments
    args = parse_args(["data.csv"])
    assert args.csv_file == "data.csv"
    assert args.detect_timestamps is False
    assert args.output_dir is None
    assert args.figsize is None  # auto size
    assert args.output_format == "png"

    # Test with output directory
    args = parse_args(["data.csv", "--output-dir", "output"])
    assert args.output_dir == "output"

    # Test with timestamp columns
    args = parse_args(["data.csv", "--timestamp-columns", "created_at", "updated_at"])
    assert args.timestamp_columns == ["created_at", "updated_at"]

    # Test omitted input file defaults to stdin
    args = parse_args([])
    assert args.csv_file is None


def test_parse_args_validation():
    # Test invalid figure size
    with pytest.raises(SystemExit):
        parse_args(["data.csv", "--figsize", "invalid"])

    # Test invalid JSON in colors
    with pytest.raises(SystemExit):
        parse_args(["data.csv", "--colors", "invalid json"])

    # Test invalid JSON in label mappings
    with pytest.raises(SystemExit):
        parse_args(["data.csv", "--label-mappings", "invalid json"])


def test_parse_args_numeric_options():
    # Test numeric options
    args = parse_args(
        [
            "data.csv",
            "--max-entities",
            "10",
            "--threshold-days",
            "5",
            "--point-size",
            "12",
            "--varying-height",
            "--dpi",
            "300",
        ]
    )
    assert args.max_entities == 10
    assert args.threshold_days == 5
    assert args.point_size == 12
    assert args.varying_height is True
    assert args.dpi == 300


def test_parse_args_event_log_requires_time_column():
    with pytest.raises(SystemExit):
        parse_args(["data.csv", "--event-log"])


def test_parse_args_raw_log_format_requires_event_log():
    with pytest.raises(SystemExit):
        parse_args(["logs.txt", "--raw-log-format", "auto"])


def test_parse_args_event_log_conflicts_with_promtest():
    with pytest.raises(SystemExit):
        parse_args(
            [
                "data.csv",
                "--event-log",
                "--log-time-column",
                "ts",
                "--promtest",
            ]
        )


def test_parse_args_promtest_break_gap_requires_promtest():
    with pytest.raises(SystemExit):
        parse_args(["t.yml", "--promtest-break-gap", "30"])


def test_parse_args_promtest_break_gap_invalid():
    with pytest.raises(SystemExit):
        parse_args(["t.yml", "--promtest", "--promtest-break-gap", "0"])
    with pytest.raises(SystemExit):
        parse_args(["t.yml", "--promtest", "--promtest-break-gap", "-5"])


def test_parse_args_promtest_break_gap_ok():
    args = parse_args(["t.yml", "--promtest", "--promtest-break-gap", "45"])
    assert args.promtest_break_gap_minutes == 45.0


def test_parse_args_event_log_ok():
    args = parse_args(
        [
            "log.csv",
            "--event-log",
            "--log-time-column",
            "ts",
            "--log-label-column",
            "msg",
            "--log-filter-column",
            "level",
            "--log-include",
            "ERROR",
            "WARN",
            "--log-exclude",
            "DEBUG",
        ]
    )
    assert args.event_log is True
    assert args.log_time_column == "ts"
    assert args.log_label_column == "msg"
    assert args.log_filter_column == "level"
    assert args.log_include == ["ERROR", "WARN"]
    assert args.log_exclude == ["DEBUG"]
    assert args.varying_height is False


def test_parse_args_raw_log_event_log_defaults():
    args = parse_args(["--event-log", "--raw-log-format"])
    assert args.log_time_column == "ts"
    assert args.log_label_column == "message"
    assert args.log_filter_column == "level"
    assert args.raw_log_format == "auto"


def test_main_basic_functionality(tmp_path):
    # Create a test CSV file
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame({"id": [1], "timestamp": ["2024-01-01"]})
    df.to_csv(csv_path, index=False)

    # Test basic functionality
    output_dir = tmp_path / "output"
    result = main(
        [
            str(csv_path),
            "--output-dir",
            str(output_dir),
            "--timestamp-columns",
            "timestamp",
            "--no-show",
        ]
    )
    assert result == 0
    assert output_dir.exists()
    assert len(list(output_dir.glob("*.png"))) > 0


def test_main_error_handling(tmp_path):
    # Test file not found
    result = main(["nonexistent.csv"])
    assert result == 1

    # Test invalid CSV
    invalid_file = tmp_path / "invalid.csv"
    invalid_file.write_text("not,a,valid,csv\nfile")
    result = main([str(invalid_file)])
    assert result == 1

    # Test no timestamp columns found
    no_timestamps = tmp_path / "no_timestamps.csv"
    pd.DataFrame({"id": [1], "name": ["test"]}).to_csv(no_timestamps, index=False)
    result = main([str(no_timestamps), "--detect-timestamps"])
    assert result == 1


def test_main_reads_wide_csv_from_stdin(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli_module.sys,
        "stdin",
        _FakeStdin("id,timestamp\n1,2024-01-01 10:00:00\n"),
    )
    output_dir = tmp_path / "out"
    result = main(
        [
            "--output-dir",
            str(output_dir),
            "--timestamp-columns",
            "timestamp",
            "--no-show",
        ]
    )
    assert result == 0
    assert (output_dir / "entity_row_0_timeline.png").is_file()


def test_main_reads_wide_csv_from_dash_stdin(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli_module.sys,
        "stdin",
        _FakeStdin("id,timestamp\n1,2024-01-01 10:00:00\n"),
    )
    output_dir = tmp_path / "out"
    result = main(
        [
            "-",
            "--output-dir",
            str(output_dir),
            "--timestamp-columns",
            "timestamp",
            "--no-show",
        ]
    )
    assert result == 0
    assert (output_dir / "entity_row_0_timeline.png").is_file()


def test_main_reads_event_log_from_stdin(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli_module.sys,
        "stdin",
        _FakeStdin(
            "ts,level,message\n2024-06-01 10:01:00,ERROR,failed\n2024-06-01 10:02:00,WARN,retry\n"
        ),
    )
    output_dir = tmp_path / "out"
    result = main(
        [
            "--event-log",
            "--log-time-column",
            "ts",
            "--log-label-column",
            "message",
            "--log-filter-column",
            "level",
            "--log-include",
            "ERROR",
            "WARN",
            "--output-dir",
            str(output_dir),
            "--no-show",
        ]
    )
    assert result == 0
    assert (output_dir / "event_log_timeline.png").is_file()


def test_main_reads_raw_kubectl_log_from_stdin(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli_module.sys,
        "stdin",
        _FakeStdin(
            "2026-04-02T04:21:43.796757292Z INFO | first message\n"
            "2026-04-02T04:21:44.796757292Z WARN | second message\n"
        ),
    )
    output_dir = tmp_path / "out"
    result = main(
        [
            "--event-log",
            "--raw-log-format",
            "auto",
            "--log-label-column",
            "message",
            "--log-filter-column",
            "level",
            "--log-include",
            "INFO",
            "--output-dir",
            str(output_dir),
            "--no-show",
        ]
    )
    assert result == 0
    assert (output_dir / "event_log_timeline.png").is_file()


def test_main_reads_raw_kubectl_log_from_file(tmp_path):
    log_path = tmp_path / "kubectl.log"
    log_path.write_text(
        "2026-04-02T04:21:43.796757292Z INFO | first message\n"
        "2026-04-02T04:21:44.796757292Z ERROR | second message\n"
    )
    output_dir = tmp_path / "out"
    result = main(
        [
            str(log_path),
            "--event-log",
            "--raw-log-format",
            "auto",
            "--log-include",
            "INFO",
            "--output-dir",
            str(output_dir),
            "--no-show",
        ]
    )
    assert result == 0
    assert (output_dir / "event_log_timeline.png").is_file()


def test_main_reads_generic_timestamped_log_from_stdin(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli_module.sys,
        "stdin",
        _FakeStdin(
            "2026-04-02 04:21:43,796 INFO app booted\n2026-04-02 04:21:44,123 ERROR app failed\n"
        ),
    )
    output_dir = tmp_path / "out"
    result = main(
        [
            "--event-log",
            "--raw-log-format",
            "timestamped",
            "--log-include",
            "INFO",
            "--output-dir",
            str(output_dir),
            "--no-show",
        ]
    )
    assert result == 0
    assert (output_dir / "event_log_timeline.png").is_file()


def test_main_reads_promtest_from_stdin(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli_module.sys,
        "stdin",
        _FakeStdin(
            "evaluation_interval: 1m\n"
            "tests:\n"
            "  - interval: 1m\n"
            "    input_series:\n"
            "      - series: metric_name\n"
            "        values: '0+0x1'\n"
        ),
    )
    output_dir = tmp_path / "out"
    result = main(["--promtest", "--output-dir", str(output_dir), "--no-show"])
    assert result == 0
    assert (output_dir / "promtest.png").is_file()


def test_main_omitted_input_without_pipe_errors(monkeypatch, capsys):
    monkeypatch.setattr(cli_module.sys, "stdin", _FakeStdin("", is_tty=True))
    result = main(["--timestamp-columns", "timestamp", "--no-show"])
    assert result == 1
    assert "No input file provided" in capsys.readouterr().err


def test_main_raw_kubectl_log_without_matches(monkeypatch, capsys):
    monkeypatch.setattr(cli_module.sys, "stdin", _FakeStdin("not a kubectl log line\n"))
    result = main(["--event-log", "--raw-log-format", "auto", "--no-show"])
    assert result == 1
    assert "No timestamped log lines matched" in capsys.readouterr().err


def test_main_label_mappings_file_not_found(capsys):
    result = main(
        [
            "missing.csv",
            "--timestamp-columns",
            "timestamp",
            "--label-mappings",
            '{"timestamp":"When"}',
            "--no-show",
        ]
    )
    assert result == 1
    assert "File 'missing.csv' not found" in capsys.readouterr().err


def test_main_label_mappings_stdin_error(monkeypatch, capsys):
    monkeypatch.setattr(cli_module.sys, "stdin", _FakeStdin("", is_tty=True))
    result = main(
        [
            "--timestamp-columns",
            "timestamp",
            "--label-mappings",
            '{"timestamp":"When"}',
            "--no-show",
        ]
    )
    assert result == 1
    assert "No input file provided" in capsys.readouterr().err


def test_main_with_all_options(tmp_path):
    # Create test CSV
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame(
        {
            "id": [1],
            "created": ["2024-01-01 10:00:00"],  # Use full datetime
            "updated": ["2024-01-02 15:30:00"],
        }
    )
    df.to_csv(csv_path, index=False)

    # Create output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)

    # Full color scheme
    color_scheme = {
        "line": "#FF0000",
        "point_edge": "#FF0000",
        "point_face": "#00FF00",
        "connector": "#FF0000",
        "label_bg": "#FFFFFF",
        "label_edge": "#FF0000",
        "slashes": "#FF0000",
        "title": "#FF0000",
    }

    # Test with all options
    result = main(
        [
            str(csv_path),
            "--output-dir",
            str(output_dir),
            "--timestamp-columns",
            "created",
            "updated",
            "--id-column",
            "id",
            "--entity-name",
            "Test",
            "--max-entities",
            "1",
            "--threshold-days",
            "5",
            "--figsize",
            "15,5",
            "--point-size",
            "10",
            "--colors",
            json.dumps(color_scheme),
            "--label-mappings",
            '{"created":"Created At"}',
            "--remove-suffixes",
            "_utc",
            "--dpi",
            "300",
            "--no-show",
        ]
    )
    assert result == 0
    assert output_dir.exists()
    assert len(list(output_dir.glob("*.png"))) > 0


def test_main_auto_detection(tmp_path):
    # Create test CSV with detectable timestamp columns
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame({"id": [1], "created_at": ["2024-01-01"], "updated_at": ["2024-01-02"]})
    df.to_csv(csv_path, index=False)

    # Test auto-detection
    result = main([str(csv_path), "--detect-timestamps", "--no-show"])
    assert result == 0


def test_main_invalid_options(tmp_path):
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"id": [1]}).to_csv(csv_path, index=False)

    # Test invalid max_entities
    result = main([str(csv_path), "--max-entities", "-1"])
    assert result == 1

    # Test invalid threshold_days
    result = main([str(csv_path), "--threshold-days", "0"])
    assert result == 1

    # Test invalid point_size
    result = main([str(csv_path), "--point-size", "-5"])
    assert result == 1


def test_main_output_handling(tmp_path):
    # Test output directory creation
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"id": [1], "timestamp": ["2024-01-01"]}).to_csv(csv_path, index=False)

    output_dir = tmp_path / "nonexistent"
    result = main(
        [
            str(csv_path),
            "--output-dir",
            str(output_dir),
            "--timestamp-columns",
            "timestamp",
            "--no-show",
        ]
    )
    assert result == 0
    assert output_dir.exists()


def test_parse_args_comprehensive():
    # Test all options
    args = parse_args(
        [
            "data.csv",
            "--output-dir",
            "output",
            "--timestamp-columns",
            "created_at",
            "updated_at",
            "--id-column",
            "order_id",
            "--entity-name",
            "Order",
            "--detect-timestamps",
            "--max-entities",
            "10",
            "--threshold-days",
            "5",
            "--point-size",
            "12",
            "--dpi",
            "300",
            "--no-show",
            "--colors",
            '{"line":"#FF0000"}',
            "--label-mappings",
            '{"created_at":"Created"}',
            "--remove-suffixes",
            "_utc",
            "_at",
        ]
    )
    assert args.csv_file == "data.csv"
    assert args.output_dir == "output"
    assert args.timestamp_columns == ["created_at", "updated_at"]
    assert args.id_column == "order_id"
    assert args.entity_name == "Order"
    assert args.detect_timestamps is True
    assert args.max_entities == 10
    assert args.threshold_days == 5
    assert args.point_size == 12
    assert args.dpi == 300
    assert args.no_show is True
    assert isinstance(args.colors, dict)
    assert isinstance(args.label_mappings, dict)
    assert args.remove_suffixes == ["_utc", "_at"]


def test_cli_invalid_json(tmp_path):
    # Create a test CSV file
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"id": [1], "timestamp": ["2024-01-01"]}).to_csv(csv_path, index=False)

    # Test invalid JSON in colors
    with pytest.raises(SystemExit):
        parse_args([str(csv_path), "--colors", "invalid json"])

    # Test invalid JSON in label mappings
    with pytest.raises(SystemExit):
        parse_args([str(csv_path), "--label-mappings", "invalid json"])


def test_cli_figure_size():
    # Test valid figure size
    args = parse_args(["data.csv", "--figsize", "10,5"])
    assert args.figsize == "10,5"

    # Test invalid figure size format
    with pytest.raises(SystemExit):
        parse_args(["data.csv", "--figsize", "invalid"])


def test_cli_with_all_options(tmp_path):
    # Create a test CSV file
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"id": [1], "timestamp": ["2024-01-01"]}).to_csv(csv_path, index=False)

    # Create output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)

    # Full color scheme with all required keys
    color_scheme = {
        "line": "#FF0000",
        "point_edge": "#FF0000",
        "point_face": "#00FF00",
        "connector": "#FF0000",
        "label_bg": "#FFFFFF",
        "label_edge": "#FF0000",
        "slashes": "#FF0000",
        "title": "#FF0000",
    }

    # Test with all options specified
    result = main(
        [
            str(csv_path),
            "--output-dir",
            str(output_dir),
            "--timestamp-columns",
            "timestamp",
            "--id-column",
            "id",
            "--entity-name",
            "Test",
            "--max-entities",
            "1",
            "--threshold-days",
            "5",
            "--figsize",
            "15,5",
            "--point-size",
            "10",
            "--colors",
            json.dumps(color_scheme),
            "--label-mappings",
            '{"timestamp":"Time"}',
            "--remove-suffixes",
            "_utc",
            "--dpi",
            "300",
            "--no-show",
        ]
    )
    assert result == 0


def test_main_invalid_json_handling(tmp_path):
    # Create test CSV
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"id": [1], "ts": ["2024-01-01"]}).to_csv(csv_path, index=False)

    # Test invalid JSON in colors - should exit with error code 2 (argparse error)
    with pytest.raises(SystemExit) as exc_info:
        main([str(csv_path), "--colors", "invalid json", "--timestamp-columns", "ts"])
    assert exc_info.value.code == 2

    # Test invalid JSON in label mappings
    with pytest.raises(SystemExit) as exc_info:
        main([str(csv_path), "--label-mappings", "invalid json", "--timestamp-columns", "ts"])
    assert exc_info.value.code == 2


def test_main_invalid_numeric_options(tmp_path):
    # Create test CSV
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"id": [1], "ts": ["2024-01-01"]}).to_csv(csv_path, index=False)

    # Test invalid DPI format - should exit with error code 2 (argparse error)
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                str(csv_path),
                "--dpi",
                "not_a_number",  # Changed from -100 to non-numeric value
                "--timestamp-columns",
                "ts",
                "--no-show",
            ]
        )
    assert exc_info.value.code == 2

    # Test invalid figure size
    with pytest.raises(SystemExit) as exc_info:
        main([str(csv_path), "--figsize", "invalid,size", "--timestamp-columns", "ts", "--no-show"])
    assert exc_info.value.code == 2


def test_main_with_detect_timestamps(tmp_path):
    # Create test CSV with timestamp-like columns
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame(
        {
            "id": [1],
            "created_at": ["2024-01-01"],
            "updated_at": ["2024-01-02"],
            "description": ["text"],  # Changed from not_a_date to avoid detection
        }
    )
    df.to_csv(csv_path, index=False)

    # Create output directory
    output_dir = tmp_path / "output"

    # Test with detect_timestamps
    result = main(
        [str(csv_path), "--detect-timestamps", "--output-dir", str(output_dir), "--no-show"]
    )
    assert result == 0
    assert output_dir.exists()
    assert len(list(output_dir.glob("*.png"))) > 0


def test_main_with_invalid_paths(tmp_path):
    # Test with invalid output directory permissions
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"ts": ["2024-01-01"]}).to_csv(csv_path, index=False)

    output_dir = tmp_path / "readonly"
    output_dir.mkdir()
    output_dir.chmod(0o444)  # Read-only

    result = main(
        [str(csv_path), "--output-dir", str(output_dir), "--timestamp-columns", "ts", "--no-show"]
    )
    assert result == 1


def test_main_color_scheme_validation(tmp_path):
    # Create test CSV
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"ts": ["2024-01-01"]}).to_csv(csv_path, index=False)

    # A partial scheme is fine: unspecified keys fall back to defaults
    partial_colors = {"line": "#FF0000"}

    result = main(
        [
            str(csv_path),
            "--colors",
            json.dumps(partial_colors),
            "--timestamp-columns",
            "ts",
            "--no-show",
        ]
    )
    assert result == 0

    # Unknown keys are rejected rather than silently ignored
    result = main(
        [
            str(csv_path),
            "--colors",
            json.dumps({"lien": "#FF0000"}),
            "--timestamp-columns",
            "ts",
            "--no-show",
        ]
    )
    assert result == 1

    # A JSON value that is not an object is rejected
    result = main(
        [str(csv_path), "--colors", '["#FF0000"]', "--timestamp-columns", "ts", "--no-show"]
    )
    assert result == 1

    # Test invalid color values
    invalid_colors = {
        "line": "#FF0000",
        "point_edge": "#FF0000",
        "point_face": "not-a-color",  # Invalid color
        "connector": "#FF0000",
        "label_bg": "#FFFFFF",
        "label_edge": "#FF0000",
        "slashes": "#FF0000",
        "title": "#FF0000",
    }

    result = main(
        [
            str(csv_path),
            "--colors",
            json.dumps(invalid_colors),
            "--timestamp-columns",
            "ts",
            "--no-show",
        ]
    )
    assert result == 1


def test_main_no_timestamp_columns(tmp_path):
    # Create test CSV with no timestamp columns
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame({"id": [1], "name": ["test"], "value": [100]})
    df.to_csv(csv_path, index=False)

    # Test with no timestamp columns and no detection
    result = main([str(csv_path), "--no-show"])
    assert result == 1


def test_main_label_mappings_validation(tmp_path):
    # Create test CSV
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"ts": ["2024-01-01"], "other_ts": ["2024-01-02"]}).to_csv(csv_path, index=False)

    # Test label mapping for non-existent column
    invalid_mappings = {"nonexistent": "Label", "ts": "Timestamp"}

    result = main(
        [
            str(csv_path),
            "--label-mappings",
            json.dumps(invalid_mappings),
            "--timestamp-columns",
            "ts",
            "--no-show",
        ]
    )
    assert result == 1


def test_main_invalid_figsize_format():
    # Test completely invalid format
    with pytest.raises(SystemExit) as exc_info:
        main(["data.csv", "--figsize", "not-a-size"])
    assert exc_info.value.code == 2

    # Test wrong number of values
    with pytest.raises(SystemExit) as exc_info:
        main(["data.csv", "--figsize", "10,5,2"])
    assert exc_info.value.code == 2

    # Test non-numeric values
    with pytest.raises(SystemExit) as exc_info:
        main(["data.csv", "--figsize", "a,b"])
    assert exc_info.value.code == 2


def test_main_invalid_csv_format(tmp_path):
    # Create an invalid CSV file
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text("not,a,valid\ncsv,file\nwith,wrong,columns")

    # Test with invalid CSV format
    result = main([str(csv_path), "--timestamp-columns", "ts", "--no-show"])
    assert result == 1


def test_main_file_not_found():
    # Test with non-existent file
    result = main(["nonexistent.csv", "--no-show"])
    assert result == 1


def test_main_figure_size_parsing():
    # Test with invalid figure size format
    with pytest.raises(SystemExit) as exc_info:
        main(["data.csv", "--figsize", "invalid"])
    assert exc_info.value.code == 2


def test_main_event_log_mode(tmp_path):
    csv_path = tmp_path / "incident.csv"
    csv_path.write_text(
        "ts,level,message\n"
        "2024-06-01 10:00:00,INFO,started\n"
        "2024-06-01 10:01:00,ERROR,failed\n"
        "2024-06-01 10:02:00,WARN,retry\n"
    )
    out = tmp_path / "out"
    result = main(
        [
            str(csv_path),
            "--event-log",
            "--log-time-column",
            "ts",
            "--log-label-column",
            "message",
            "--log-filter-column",
            "level",
            "--log-include",
            "ERROR",
            "WARN",
            "--output-dir",
            str(out),
            "--no-show",
        ]
    )
    assert result == 0
    assert (out / "event_log_timeline.png").is_file()


def test_main_event_log_no_matching_rows(tmp_path):
    csv_path = tmp_path / "log.csv"
    csv_path.write_text("ts,level\n2024-01-01 10:00:00,INFO\n")
    result = main(
        [
            str(csv_path),
            "--event-log",
            "--log-time-column",
            "ts",
            "--log-filter-column",
            "level",
            "--log-include",
            "ERROR",
            "--no-show",
        ]
    )
    assert result == 1


def test_main_event_log_invalid_filter_column(tmp_path):
    csv_path = tmp_path / "log.csv"
    csv_path.write_text("ts,level\n2024-01-01 10:00:00,INFO\n")
    result = main(
        [
            str(csv_path),
            "--event-log",
            "--log-time-column",
            "ts",
            "--log-filter-column",
            "missing",
            "--log-include",
            "INFO",
            "--no-show",
        ]
    )
    assert result == 1


def test_main_event_log_invalid_timestamps(tmp_path):
    csv_path = tmp_path / "log.csv"
    csv_path.write_text("ts,msg\nnot-a-date,hello\nalso-bad,world\n")
    result = main(
        [
            str(csv_path),
            "--event-log",
            "--log-time-column",
            "ts",
            "--log-label-column",
            "msg",
            "--no-show",
        ]
    )
    assert result == 1


def test_main_event_log_partial_colors(tmp_path):
    csv_path = tmp_path / "log.csv"
    csv_path.write_text("ts\n2024-01-01 10:00:00\n")
    result = main(
        [
            str(csv_path),
            "--event-log",
            "--log-time-column",
            "ts",
            "--colors",
            '{"line":"#0046be"}',
            "--no-show",
        ]
    )
    assert result == 0


def test_main_event_log_invalid_color_value(tmp_path):
    csv_path = tmp_path / "log.csv"
    csv_path.write_text("ts\n2024-01-01 10:00:00\n")
    result = main(
        [
            str(csv_path),
            "--event-log",
            "--log-time-column",
            "ts",
            "--colors",
            '{"title":"not-a-color"}',
            "--no-show",
        ]
    )
    assert result == 1


def test_main_event_log_success_without_output_dir(tmp_path):
    csv_path = tmp_path / "log.csv"
    csv_path.write_text("ts\n2024-01-01 10:00:00\n")
    result = main(
        [
            str(csv_path),
            "--event-log",
            "--log-time-column",
            "ts",
            "--no-show",
        ]
    )
    assert result == 0


def test_main_promtest_with_break_gap(tmp_path):
    yml = tmp_path / "gap.yml"
    yml.write_text(
        "evaluation_interval: 1m\n"
        "tests:\n"
        "  - interval: 1m\n"
        "    input_series:\n"
        "      - series: s\n"
        "        values: '0+0x9 1+0x4'\n"
        "    promql_expr_test:\n"
        "      - expr: a\n"
        "        eval_time: 5m\n"
        "      - expr: b\n"
        "        eval_time: 12m\n"
    )
    out = tmp_path / "out"
    result = main(
        [
            str(yml),
            "--promtest",
            "--promtest-break-gap",
            "3",
            "--output-dir",
            str(out),
            "--no-show",
        ]
    )
    assert result == 0
    assert (out / "promtest.png").is_file()


def test_main_uses_sys_argv_when_args_none(tmp_path, monkeypatch):
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"timestamp": ["2024-01-01"]}).to_csv(csv_path, index=False)
    monkeypatch.setattr(
        cli_module.sys,
        "argv",
        ["timelineviz", str(csv_path), "--timestamp-columns", "timestamp", "--no-show"],
    )
    assert cli_module.main() == 0


def test_main_invalid_figsize_after_parse_args(tmp_path, monkeypatch, capsys):
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({"timestamp": ["2024-01-01"]}).to_csv(csv_path, index=False)
    parsed = SimpleNamespace(
        csv_file=str(csv_path),
        event_log=False,
        promtest=False,
        figsize="1,2,3",
        colors=None,
        label_mappings=None,
        timestamp_columns=["timestamp"],
        detect_timestamps=False,
        id_column=None,
        output_dir=None,
        max_entities=None,
        threshold_days=1,
        point_size=10,
        no_show=True,
        dpi=150,
        remove_suffixes=None,
        entity_name="Entity",
    )
    monkeypatch.setattr(cli_module, "parse_args", lambda _args: parsed)
    assert cli_module.main(["ignored"]) == 1
    assert "Error parsing figure size" in capsys.readouterr().err


def test_run_event_log_invalid_figsize(capsys):
    args = SimpleNamespace(figsize="1,2,3", colors=None, raw_log_format=None)
    assert cli_module._run_event_log(args) == 1
    assert "Error parsing figure size" in capsys.readouterr().err


def test_run_event_log_invalid_color_scheme(capsys):
    args = SimpleNamespace(
        figsize="15,5",
        colors={
            "line": "#0046be",
            "point_edge": "#0046be",
            "point_face": "not-a-color",
            "connector": "#0046be",
            "label_bg": "#ffffff",
            "label_edge": "#0046be",
            "slashes": "#0046be",
            "title": "#0046be",
        },
        output_dir=None,
        csv_file="unused.csv",
        log_time_column="ts",
        log_label_column=None,
        log_filter_column=None,
        log_include=None,
        log_exclude=None,
        threshold_days=1,
        point_size=10,
        varying_height=False,
        raw_log_format=None,
        no_show=True,
        dpi=150,
    )
    assert cli_module._run_event_log(args) == 1
    assert "Invalid color scheme" in capsys.readouterr().err


def test_run_event_log_unexpected_exception(monkeypatch, capsys):
    args = SimpleNamespace(
        figsize="15,5",
        colors=None,
        output_dir=None,
        csv_file="unused.csv",
        log_time_column="ts",
        log_label_column=None,
        log_filter_column=None,
        log_include=None,
        log_exclude=None,
        threshold_days=1,
        point_size=10,
        varying_height=False,
        raw_log_format=None,
        no_show=True,
        dpi=150,
    )

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        cli_module,
        "_load_csv_input",
        lambda _input: pd.DataFrame({"ts": ["2024-01-01 10:00:00"]}),
    )
    monkeypatch.setattr(cli_module, "plot_event_log_timeline", boom)
    assert cli_module._run_event_log(args) == 1
    assert "Error generating event log timeline: boom" in capsys.readouterr().err


def test_run_event_log_file_not_found(capsys):
    args = SimpleNamespace(
        figsize="15,5",
        colors=None,
        output_dir=None,
        csv_file="missing.csv",
        log_time_column="ts",
        log_label_column=None,
        log_filter_column=None,
        log_include=None,
        log_exclude=None,
        threshold_days=1,
        point_size=10,
        varying_height=False,
        raw_log_format=None,
        no_show=True,
        dpi=150,
    )
    assert cli_module._run_event_log(args) == 1
    assert "File 'missing.csv' not found" in capsys.readouterr().err


def test_run_promtest_invalid_figsize_falls_back(monkeypatch):
    args = SimpleNamespace(
        figsize="bad",
        csv_file="unused.yml",
        output_dir=None,
        no_show=True,
        dpi=150,
        promtest_break_gap_minutes=None,
        promtest_label_layout="readable",
    )
    monkeypatch.setattr(cli_module, "_load_promtest_groups", lambda _path: ["group"])
    monkeypatch.setattr(cli_module, "plot_promtest", lambda *_args, **_kwargs: [("fig", [])])
    assert cli_module._run_promtest(args) == 0


def test_parse_raw_timestamped_logs_normalizes_level_and_pipe():
    df = cli_module._parse_raw_timestamped_logs(
        "2026-04-02T04:21:43.796757292Z INFO     | first message\n"
        "2026-04-02T04:21:44.796757292Z WARN second message\n"
    )
    assert df.to_dict(orient="records") == [
        {
            "ts": "2026-04-02T04:21:43.796757292Z",
            "level": "INFO",
            "message": "first message",
        },
        {
            "ts": "2026-04-02T04:21:44.796757292Z",
            "level": "WARN",
            "message": "second message",
        },
    ]


def test_parse_raw_timestamped_logs_rejects_unmatched_text():
    with pytest.raises(ValueError, match="No timestamped log lines matched"):
        cli_module._parse_raw_timestamped_logs("hello world\nstill not logs\n")


def test_parse_raw_timestamped_logs_skips_blank_lines():
    df = cli_module._parse_raw_timestamped_logs(
        "\n2026-04-02T04:21:43.796757292Z INFO | first message\n\n"
    )
    assert df["level"].tolist() == ["INFO"]


def test_parse_raw_timestamped_logs_handles_no_level():
    df = cli_module._parse_raw_timestamped_logs(
        "2026-04-02T04:21:43.796757292Z request completed successfully\n"
    )
    assert df.to_dict(orient="records") == [
        {
            "ts": "2026-04-02T04:21:43.796757292Z",
            "level": "",
            "message": "request completed successfully",
        }
    ]


def test_parse_raw_timestamped_logs_handles_pipe_without_level():
    df = cli_module._parse_raw_timestamped_logs(
        "2026-04-02T04:21:43.796757292Z | request completed successfully\n"
    )
    assert df.to_dict(orient="records") == [
        {
            "ts": "2026-04-02T04:21:43.796757292Z",
            "level": "",
            "message": "request completed successfully",
        }
    ]


def test_parse_raw_timestamped_logs_handles_bracketed_level():
    df = cli_module._parse_raw_timestamped_logs(
        "2026-04-02 04:21:43,796 [WARNING] cache warming slowly\n"
    )
    assert df.to_dict(orient="records") == [
        {
            "ts": "2026-04-02 04:21:43,796",
            "level": "WARN",
            "message": "cache warming slowly",
        }
    ]


def test_parse_raw_timestamped_logs_normalizes_critical_to_fatal():
    df = cli_module._parse_raw_timestamped_logs(
        "2026-04-02 04:21:43,796 CRITICAL cache warming failed\n"
    )
    assert df.to_dict(orient="records") == [
        {
            "ts": "2026-04-02 04:21:43,796",
            "level": "FATAL",
            "message": "cache warming failed",
        }
    ]


def test_load_text_input_file_not_found():
    with pytest.raises(FileNotFoundError):
        cli_module._load_text_input("missing.log")


def test_load_text_input_rejects_empty_file(tmp_path):
    log_path = tmp_path / "empty.log"
    log_path.write_text("")
    with pytest.raises(ValueError, match="No input data found"):
        cli_module._load_text_input(str(log_path))


def test_load_event_log_input_rejects_unknown_raw_format():
    with pytest.raises(ValueError, match="Unsupported raw log format"):
        cli_module._load_event_log_input("-", raw_log_format="unknown")


def test_run_promtest_file_not_found(capsys):
    args = SimpleNamespace(
        figsize="15,5",
        csv_file="missing.yml",
        output_dir=None,
        no_show=True,
        dpi=150,
        promtest_break_gap_minutes=None,
        promtest_label_layout="readable",
    )
    assert cli_module._run_promtest(args) == 1
    assert "File 'missing.yml' not found" in capsys.readouterr().err


def test_run_promtest_parse_error(monkeypatch, capsys):
    args = SimpleNamespace(
        figsize="15,5",
        csv_file="unused.yml",
        output_dir=None,
        no_show=True,
        dpi=150,
        promtest_break_gap_minutes=None,
        promtest_label_layout="readable",
    )

    def boom(_path):
        raise ValueError("bad yaml")

    monkeypatch.setattr(cli_module, "_load_promtest_groups", boom)
    assert cli_module._run_promtest(args) == 1
    assert "Error parsing promtest file: bad yaml" in capsys.readouterr().err


def test_run_promtest_no_groups(monkeypatch, capsys):
    args = SimpleNamespace(
        figsize="15,5",
        csv_file="unused.yml",
        output_dir=None,
        no_show=True,
        dpi=150,
        promtest_break_gap_minutes=None,
        promtest_label_layout="readable",
    )
    monkeypatch.setattr(cli_module, "_load_promtest_groups", lambda _path: [])
    assert cli_module._run_promtest(args) == 1
    assert "No test groups found" in capsys.readouterr().err


def test_run_promtest_plot_error(monkeypatch, capsys):
    args = SimpleNamespace(
        figsize="15,5",
        csv_file="unused.yml",
        output_dir=None,
        no_show=True,
        dpi=150,
        promtest_break_gap_minutes=None,
        promtest_label_layout="readable",
    )
    monkeypatch.setattr(cli_module, "_load_promtest_groups", lambda _path: ["group"])

    def boom(*_args, **_kwargs):
        raise RuntimeError("plot failed")

    monkeypatch.setattr(cli_module, "plot_promtest", boom)
    assert cli_module._run_promtest(args) == 1
    assert "Error generating promtest visualisation: plot failed" in capsys.readouterr().err


def test_read_stdin_text_rejects_empty_pipe(monkeypatch):
    monkeypatch.setattr(cli_module.sys, "stdin", _FakeStdin(""))
    with pytest.raises(ValueError, match="No input data received on stdin"):
        cli_module._read_stdin_text()


def test_load_csv_input_translates_empty_data_error(monkeypatch):
    monkeypatch.setattr(cli_module, "_read_stdin_text", lambda: "header_only")

    def raise_empty(*_args, **_kwargs):
        raise pd.errors.EmptyDataError("no columns")

    monkeypatch.setattr(cli_module.pd, "read_csv", raise_empty)
    with pytest.raises(ValueError, match="No CSV data received on stdin"):
        cli_module._load_csv_input("-")


@pytest.mark.parametrize(
    "value,expected",
    [(None, None), ("12", (12.0, None)), ("12,4", (12.0, 4.0))],
)
def test_parse_figsize_arg(value, expected):
    assert cli_module._parse_figsize_arg(value) == expected


def test_parse_args_figsize_width_only_and_errors():
    assert parse_args(["data.csv", "--figsize", "12"]).figsize == "12"
    with pytest.raises(SystemExit):
        parse_args(["data.csv", "--figsize", "1,2,3"])


@pytest.mark.parametrize("fmt", ["svg", "pdf"])
def test_main_wide_output_format(tmp_path, fmt):
    csv_path = tmp_path / "d.csv"
    pd.DataFrame({"created_at": ["2024-01-01 10:00"], "done_at": ["2024-01-01 12:00"]}).to_csv(
        csv_path, index=False
    )
    out = tmp_path / "out"
    rc = main(
        [
            str(csv_path),
            "-t",
            "created_at",
            "done_at",
            "-o",
            str(out),
            "--format",
            fmt,
            "--no-show",
            "--figsize",
            "10",
        ]
    )
    assert rc == 0
    assert (out / f"entity_row_0_timeline.{fmt}").is_file()


def test_main_event_log_output_format_svg(tmp_path):
    csv_path = tmp_path / "log.csv"
    csv_path.write_text("ts,msg\n2024-01-01 10:00:00,a\n2024-01-01 10:05:00,b\n")
    out = tmp_path / "out"
    rc = main(
        [
            str(csv_path),
            "--event-log",
            "--log-time-column",
            "ts",
            "--log-label-column",
            "msg",
            "-o",
            str(out),
            "--format",
            "svg",
            "--no-show",
        ]
    )
    assert rc == 0
    assert (out / "event_log_timeline.svg").read_text().lstrip().startswith("<?xml")


def test_main_promtest_output_format_and_width_only_figsize(tmp_path):
    yml = tmp_path / "t.yml"
    yml.write_text("tests:\n  - input_series:\n      - series: 'up'\n        values: '1x3'\n")
    out = tmp_path / "out"
    rc = main(
        [str(yml), "--promtest", "-o", str(out), "--format", "svg", "--figsize", "10", "--no-show"]
    )
    assert rc == 0
    assert (out / "promtest.svg").is_file()


# --- swimlanes & mermaid ---------------------------------------------------

RAW_LOG = (
    "2026-04-03T09:00:01Z INFO app.server boot\n"
    "2026-04-03T09:00:05Z WARN app.queue slow\n"
    "2026-04-03T09:00:08Z ERROR app.queue failed\n"
    "2026-04-03T09:00:09Z INFO app.queue retry\n"
)

ORDERS = (
    "order_id,placed_at,shipped_at\n"
    "A,2025-03-03 09:00:00,2025-03-03 12:00:00\n"
    "B,2025-04-10 10:00:00,2025-04-10 11:30:00\n"
)


@pytest.fixture
def raw_log(tmp_path):
    p = tmp_path / "app.log"
    p.write_text(RAW_LOG)
    return p


@pytest.fixture
def orders_csv(tmp_path):
    p = tmp_path / "orders.csv"
    p.write_text(ORDERS)
    return p


def test_parse_args_swimlane_options():
    args = parse_args(["x.log", "--event-log", "--raw-log-format", "--swimlanes"])
    assert args.lane_column == "level"  # raw logs default lanes to the level column
    assert args.align == "auto" and args.mermaid_style == "sequence"
    assert args.threshold_explicit is False and args.threshold_days == 1.0
    args = parse_args(["x.csv", "--event-log", "--log-time-column", "ts", "--lane-column", "svc"])
    assert args.swimlanes is True
    assert parse_args(["x.csv", "-T", "2"]).threshold_explicit is True


@pytest.mark.parametrize(
    "argv",
    [
        ["x.csv", "--lane-column", "svc"],  # needs --event-log
        ["x.yml", "--promtest", "--swimlanes"],
        ["x.yml", "--promtest", "--format", "mmd"],
        ["x.csv", "--format", "mmd"],  # wide mode without --swimlanes
        ["x.csv", "--event-log", "--log-time-column", "ts", "--swimlanes"],  # no lane column
    ],
)
def test_parse_args_swimlane_errors(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_main_event_log_swimlanes_png(tmp_path, raw_log):
    out = tmp_path / "out"
    rc = main(
        [
            str(raw_log),
            "--event-log",
            "--raw-log-format",
            "--swimlanes",
            "-o",
            str(out),
            "--no-show",
        ]
    )
    assert rc == 0
    assert (out / "event_log_swimlanes.png").is_file()


def test_main_event_log_swimlanes_mermaid_stdout(raw_log, capsys):
    rc = main([str(raw_log), "--event-log", "--raw-log-format", "--swimlanes", "--format", "mmd"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("sequenceDiagram\n    title Event log by level\n")
    assert "participant L0 as ERROR" in out


def test_main_event_log_mermaid_gantt_file_without_lanes(tmp_path, raw_log):
    out = tmp_path / "out"
    rc = main(
        [
            str(raw_log),
            "--event-log",
            "--raw-log-format",
            "--format",
            "mmd",
            "--mermaid-style",
            "gantt",
            "-o",
            str(out),
        ]
    )
    assert rc == 0
    text = (out / "event_log_timeline.mmd").read_text()
    assert text.startswith("gantt\n") and "section Events" in text


def test_main_event_log_gantt_start_alignment_errors(raw_log, capsys):
    rc = main(
        [
            str(raw_log),
            "--event-log",
            "--raw-log-format",
            "--swimlanes",
            "--format",
            "mmd",
            "--mermaid-style",
            "gantt",
            "--align",
            "start",
        ]
    )
    assert rc == 1
    assert "absolute" in capsys.readouterr().err


def test_main_event_log_lanes_errors(tmp_path, capsys):
    assert main(["missing.log", "--event-log", "--raw-log-format", "--swimlanes"]) == 1
    assert "not found" in capsys.readouterr().err
    csv_path = tmp_path / "l.csv"
    csv_path.write_text("ts,level\n2024-01-01,INFO\n")
    rc = main([str(csv_path), "--event-log", "--log-time-column", "ts", "--lane-column", "nope"])
    assert rc == 1
    assert "lane_column" in capsys.readouterr().err
    rc = main(
        [
            str(csv_path),
            "--event-log",
            "--log-time-column",
            "ts",
            "--lane-column",
            "level",
            "--log-filter-column",
            "level",
            "--log-include",
            "ERROR",
        ]
    )
    assert rc == 1
    assert "No events" in capsys.readouterr().err


def test_main_entity_swimlanes_default_start_alignment(tmp_path, orders_csv, monkeypatch):
    import timelineviz.cli as cli

    seen = {}
    real = cli.render_swimlanes

    def spy(timeline, **kwargs):
        seen.update(kwargs, lanes=timeline.lane_order())
        return real(timeline, **kwargs)

    monkeypatch.setattr(cli, "render_swimlanes", spy)
    out = tmp_path / "out"
    rc = main(
        [
            str(orders_csv),
            "--id-column",
            "order_id",
            "--entity-name",
            "Order",
            "--swimlanes",
            "-o",
            str(out),
            "--format",
            "svg",
            "--no-show",
        ]
    )
    assert rc == 0
    assert (out / "order_swimlanes.svg").is_file()
    assert seen["align"] == "start" and seen["threshold_days"] == float("inf")
    assert seen["lanes"] == ["A", "B"]


def test_main_entity_swimlanes_explicit_threshold_and_absolute(tmp_path, orders_csv, monkeypatch):
    import timelineviz.cli as cli

    seen = {}
    monkeypatch.setattr(cli, "render_swimlanes", lambda t, **kw: seen.update(kw))
    rc = main(
        [
            str(orders_csv),
            "--id-column",
            "order_id",
            "--swimlanes",
            "--align",
            "absolute",
            "-T",
            "3",
            "--no-show",
        ]
    )
    assert rc == 0
    assert seen["align"] == "absolute" and seen["threshold_days"] == 3


def test_main_entity_swimlanes_mermaid(orders_csv, capsys):
    rc = main([str(orders_csv), "--id-column", "order_id", "--swimlanes", "--format", "mmd"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "participant L0 as A" in out and "+3h<br/>Shipped" in out


def test_main_entity_swimlanes_errors(tmp_path, capsys):
    assert main(["missing.csv", "--swimlanes"]) == 1
    assert "not found" in capsys.readouterr().err
    p = tmp_path / "n.csv"
    p.write_text("id,name\n1,x\n")
    assert main([str(p), "--swimlanes"]) == 1
    assert "No timestamp columns" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main([str(p), "--swimlanes", "--figsize", "1,2,3"])


def test_entity_swimlanes_bad_colors_and_figsize(orders_csv, capsys):
    from types import SimpleNamespace

    import timelineviz.cli as cli

    base = dict(csv_file=str(orders_csv), colors=None, figsize=None)
    assert cli._run_entity_swimlanes(SimpleNamespace(**{**base, "figsize": "1,2,3"})) == 1
    assert cli._run_entity_swimlanes(SimpleNamespace(**{**base, "colors": {"x": "1"}})) == 1


def test_main_entity_swimlanes_facts_stdout(capsys):
    rc = main(
        [
            "examples/order_fulfilment.csv",
            "--id-column",
            "order_id",
            "--swimlanes",
            "--format",
            "facts",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("# Facts: Entity swimlanes\n")
    assert "- Slowest: A-1004, 5d 23h" in out


def test_main_event_log_facts_json_file(tmp_path, raw_log):
    out = tmp_path / "out"
    rc = main(
        [
            str(raw_log),
            "--event-log",
            "--raw-log-format",
            "--swimlanes",
            "--format",
            "facts-json",
            "-o",
            str(out),
        ]
    )
    assert rc == 0
    data = json.loads((out / "event_log_swimlanes.facts.json").read_text())
    assert data["title"] == "Event log by level" and "largest_gaps" in data


def test_main_facts_brief_template(tmp_path, capsys):
    tpl = tmp_path / "t.md"
    tpl.write_text("Title: {{title}}\n\n{{facts}}\n")
    out = tmp_path / "out"
    argv = [
        "examples/order_fulfilment.csv",
        "--id-column",
        "order_id",
        "--entity-name",
        "Order",
        "--swimlanes",
        "--format",
        "facts",
        "--brief-template",
        str(tpl),
    ]
    assert main(argv + ["-o", str(out)]) == 0
    text = (out / "order_swimlanes.brief.md").read_text()
    assert text.startswith("Title: Order swimlanes\n\n# Facts: Order swimlanes\n")
    assert "Saved brief to" in capsys.readouterr().out

    assert main(argv[:-1] + [str(tmp_path / "missing.md")]) == 1
    assert "cannot read brief template" in capsys.readouterr().err
    tpl.write_text("no placeholder")
    assert main(argv) == 1
    assert "no {{facts}} placeholder" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["x.csv", "--format", "facts"],  # wide mode without --swimlanes
        ["x.yml", "--promtest", "--format", "facts-json"],
        ["x.csv", "--swimlanes", "--brief-template", "t.md"],  # needs --format facts
        ["x.csv", "--swimlanes", "--format", "facts-json", "--brief-template", "t.md"],
    ],
)
def test_parse_args_facts_errors(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)
