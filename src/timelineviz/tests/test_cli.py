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
    assert args.figsize == "15,5"  # Default value

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

    # Test missing required color keys
    incomplete_colors = {
        "line": "#FF0000"  # Missing other required keys
    }

    result = main(
        [
            str(csv_path),
            "--colors",
            json.dumps(incomplete_colors),
            "--timestamp-columns",
            "ts",
            "--no-show",
        ]
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


def test_main_event_log_incomplete_colors(tmp_path):
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
    args = SimpleNamespace(figsize="1,2,3", colors=None)
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
