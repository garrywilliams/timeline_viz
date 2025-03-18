import pytest
from pathlib import Path
import pandas as pd
from datetime import datetime
import json
import sys
from cli import main, parse_args

def test_parse_args_basic():
    # Test minimal arguments
    args = parse_args(['data.csv'])
    assert args.csv_file == 'data.csv'
    assert args.detect_timestamps is False
    assert args.output_dir is None
    assert args.figsize == '15,5'  # Default value
    
    # Test with output directory
    args = parse_args(['data.csv', '--output-dir', 'output'])
    assert args.output_dir == 'output'
    
    # Test with timestamp columns
    args = parse_args(['data.csv', '--timestamp-columns', 'created_at', 'updated_at'])
    assert args.timestamp_columns == ['created_at', 'updated_at']

def test_parse_args_validation():
    # Test invalid figure size
    with pytest.raises(SystemExit):
        parse_args(['data.csv', '--figsize', 'invalid'])
    
    # Test invalid JSON in colors
    with pytest.raises(SystemExit):
        parse_args(['data.csv', '--colors', 'invalid json'])
    
    # Test invalid JSON in label mappings
    with pytest.raises(SystemExit):
        parse_args(['data.csv', '--label-mappings', 'invalid json'])
    
    # Test missing required argument
    with pytest.raises(SystemExit):
        parse_args([])

def test_parse_args_numeric_options():
    # Test numeric options
    args = parse_args([
        'data.csv',
        '--max-entities', '10',
        '--threshold-days', '5',
        '--point-size', '12',
        '--dpi', '300'
    ])
    assert args.max_entities == 10
    assert args.threshold_days == 5
    assert args.point_size == 12
    assert args.dpi == 300

def test_main_basic_functionality(tmp_path):
    # Create a test CSV file
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame({
        'id': [1],
        'timestamp': ['2024-01-01']
    })
    df.to_csv(csv_path, index=False)
    
    # Test basic functionality
    output_dir = tmp_path / "output"
    result = main([
        str(csv_path),
        '--output-dir', str(output_dir),
        '--timestamp-columns', 'timestamp',
        '--no-show'
    ])
    assert result == 0
    assert output_dir.exists()
    assert len(list(output_dir.glob('*.png'))) > 0

def test_main_error_handling(tmp_path):
    # Test file not found
    result = main(['nonexistent.csv'])
    assert result == 1
    
    # Test invalid CSV
    invalid_file = tmp_path / "invalid.csv"
    invalid_file.write_text("not,a,valid,csv\nfile")
    result = main([str(invalid_file)])
    assert result == 1
    
    # Test no timestamp columns found
    no_timestamps = tmp_path / "no_timestamps.csv"
    pd.DataFrame({'id': [1], 'name': ['test']}).to_csv(no_timestamps, index=False)
    result = main([
        str(no_timestamps),
        '--detect-timestamps'
    ])
    assert result == 1

def test_main_with_all_options(tmp_path):
    # Create test CSV
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame({
        'id': [1],
        'created': ['2024-01-01 10:00:00'],  # Use full datetime
        'updated': ['2024-01-02 15:30:00']
    })
    df.to_csv(csv_path, index=False)
    
    # Create output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Full color scheme
    color_scheme = {
        'line': '#FF0000',
        'point_edge': '#FF0000',
        'point_face': '#00FF00',
        'connector': '#FF0000',
        'label_bg': '#FFFFFF',
        'label_edge': '#FF0000',
        'slashes': '#FF0000',
        'title': '#FF0000'
    }
    
    # Test with all options
    result = main([
        str(csv_path),
        '--output-dir', str(output_dir),
        '--timestamp-columns', 'created', 'updated',
        '--id-column', 'id',
        '--entity-name', 'Test',
        '--max-entities', '1',
        '--threshold-days', '5',
        '--figsize', '15,5',
        '--point-size', '10',
        '--colors', json.dumps(color_scheme),
        '--label-mappings', '{"created":"Created At"}',
        '--remove-suffixes', '_utc',
        '--dpi', '300',
        '--no-show'
    ])
    assert result == 0
    assert output_dir.exists()
    assert len(list(output_dir.glob('*.png'))) > 0

def test_main_auto_detection(tmp_path):
    # Create test CSV with detectable timestamp columns
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame({
        'id': [1],
        'created_at': ['2024-01-01'],
        'updated_at': ['2024-01-02']
    })
    df.to_csv(csv_path, index=False)
    
    # Test auto-detection
    result = main([
        str(csv_path),
        '--detect-timestamps',
        '--no-show'
    ])
    assert result == 0

def test_main_invalid_options(tmp_path):
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({'id': [1]}).to_csv(csv_path, index=False)
    
    # Test invalid max_entities
    result = main([
        str(csv_path),
        '--max-entities', '-1'
    ])
    assert result == 1
    
    # Test invalid threshold_days
    result = main([
        str(csv_path),
        '--threshold-days', '0'
    ])
    assert result == 1
    
    # Test invalid point_size
    result = main([
        str(csv_path),
        '--point-size', '-5'
    ])
    assert result == 1

def test_main_output_handling(tmp_path):
    # Test output directory creation
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({
        'id': [1],
        'timestamp': ['2024-01-01']
    }).to_csv(csv_path, index=False)
    
    output_dir = tmp_path / "nonexistent"
    result = main([
        str(csv_path),
        '--output-dir', str(output_dir),
        '--timestamp-columns', 'timestamp',
        '--no-show'
    ])
    assert result == 0
    assert output_dir.exists()

def test_parse_args_comprehensive():
    # Test all options
    args = parse_args([
        'data.csv',
        '--output-dir', 'output',
        '--timestamp-columns', 'created_at', 'updated_at',
        '--id-column', 'order_id',
        '--entity-name', 'Order',
        '--detect-timestamps',
        '--max-entities', '10',
        '--threshold-days', '5',
        '--point-size', '12',
        '--dpi', '300',
        '--no-show',
        '--colors', '{"line":"#FF0000"}',
        '--label-mappings', '{"created_at":"Created"}',
        '--remove-suffixes', '_utc', '_at'
    ])
    assert args.csv_file == 'data.csv'
    assert args.output_dir == 'output'
    assert args.timestamp_columns == ['created_at', 'updated_at']
    assert args.id_column == 'order_id'
    assert args.entity_name == 'Order'
    assert args.detect_timestamps is True
    assert args.max_entities == 10
    assert args.threshold_days == 5
    assert args.point_size == 12
    assert args.dpi == 300
    assert args.no_show is True
    assert isinstance(args.colors, dict)
    assert isinstance(args.label_mappings, dict)
    assert args.remove_suffixes == ['_utc', '_at']

def test_cli_invalid_json(tmp_path):
    # Create a test CSV file
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({
        'id': [1],
        'timestamp': ['2024-01-01']
    }).to_csv(csv_path, index=False)
    
    # Test invalid JSON in colors
    with pytest.raises(SystemExit):
        parse_args([
            str(csv_path),
            '--colors', 'invalid json'
        ])
    
    # Test invalid JSON in label mappings
    with pytest.raises(SystemExit):
        parse_args([
            str(csv_path),
            '--label-mappings', 'invalid json'
        ])

def test_cli_figure_size():
    # Test valid figure size
    args = parse_args(['data.csv', '--figsize', '10,5'])
    assert args.figsize == '10,5'
    
    # Test invalid figure size format
    with pytest.raises(SystemExit):
        parse_args(['data.csv', '--figsize', 'invalid'])

def test_cli_with_all_options(tmp_path):
    # Create a test CSV file
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({
        'id': [1],
        'timestamp': ['2024-01-01']
    }).to_csv(csv_path, index=False)
    
    # Create output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Full color scheme with all required keys
    color_scheme = {
        'line': '#FF0000',
        'point_edge': '#FF0000',
        'point_face': '#00FF00',
        'connector': '#FF0000',
        'label_bg': '#FFFFFF',
        'label_edge': '#FF0000',
        'slashes': '#FF0000',
        'title': '#FF0000'
    }
    
    # Test with all options specified
    result = main([
        str(csv_path),
        '--output-dir', str(output_dir),
        '--timestamp-columns', 'timestamp',
        '--id-column', 'id',
        '--entity-name', 'Test',
        '--max-entities', '1',
        '--threshold-days', '5',
        '--figsize', '15,5',
        '--point-size', '10',
        '--colors', json.dumps(color_scheme),
        '--label-mappings', '{"timestamp":"Time"}',
        '--remove-suffixes', '_utc',
        '--dpi', '300',
        '--no-show'
    ])
    assert result == 0 

def test_main_invalid_json_handling(tmp_path):
    # Create test CSV
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({'id': [1], 'ts': ['2024-01-01']}).to_csv(csv_path, index=False)
    
    # Test invalid JSON in colors - should exit with error code 2 (argparse error)
    with pytest.raises(SystemExit) as exc_info:
        main([
            str(csv_path),
            '--colors', 'invalid json',
            '--timestamp-columns', 'ts'
        ])
    assert exc_info.value.code == 2
    
    # Test invalid JSON in label mappings
    with pytest.raises(SystemExit) as exc_info:
        main([
            str(csv_path),
            '--label-mappings', 'invalid json',
            '--timestamp-columns', 'ts'
        ])
    assert exc_info.value.code == 2

def test_main_invalid_numeric_options(tmp_path):
    # Create test CSV
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({'id': [1], 'ts': ['2024-01-01']}).to_csv(csv_path, index=False)
    
    # Test invalid DPI format - should exit with error code 2 (argparse error)
    with pytest.raises(SystemExit) as exc_info:
        main([
            str(csv_path),
            '--dpi', 'not_a_number',  # Changed from -100 to non-numeric value
            '--timestamp-columns', 'ts',
            '--no-show'
        ])
    assert exc_info.value.code == 2
    
    # Test invalid figure size
    with pytest.raises(SystemExit) as exc_info:
        main([
            str(csv_path),
            '--figsize', 'invalid,size',
            '--timestamp-columns', 'ts',
            '--no-show'
        ])
    assert exc_info.value.code == 2 

def test_main_with_detect_timestamps(tmp_path):
    # Create test CSV with timestamp-like columns
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame({
        'id': [1],
        'created_at': ['2024-01-01'],
        'updated_at': ['2024-01-02'],
        'description': ['text']  # Changed from not_a_date to avoid detection
    })
    df.to_csv(csv_path, index=False)
    
    # Create output directory
    output_dir = tmp_path / "output"
    
    # Test with detect_timestamps
    result = main([
        str(csv_path),
        '--detect-timestamps',
        '--output-dir', str(output_dir),
        '--no-show'
    ])
    assert result == 0
    assert output_dir.exists()
    assert len(list(output_dir.glob('*.png'))) > 0

def test_main_with_invalid_paths(tmp_path):
    # Test with invalid output directory permissions
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({'ts': ['2024-01-01']}).to_csv(csv_path, index=False)
    
    output_dir = tmp_path / "readonly"
    output_dir.mkdir()
    output_dir.chmod(0o444)  # Read-only
    
    result = main([
        str(csv_path),
        '--output-dir', str(output_dir),
        '--timestamp-columns', 'ts',
        '--no-show'
    ])
    assert result == 1 

def test_main_color_scheme_validation(tmp_path):
    # Create test CSV
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({'ts': ['2024-01-01']}).to_csv(csv_path, index=False)
    
    # Test missing required color keys
    incomplete_colors = {
        'line': '#FF0000'  # Missing other required keys
    }
    
    result = main([
        str(csv_path),
        '--colors', json.dumps(incomplete_colors),
        '--timestamp-columns', 'ts',
        '--no-show'
    ])
    assert result == 1
    
    # Test invalid color values
    invalid_colors = {
        'line': '#FF0000',
        'point_edge': '#FF0000',
        'point_face': 'not-a-color',  # Invalid color
        'connector': '#FF0000',
        'label_bg': '#FFFFFF',
        'label_edge': '#FF0000',
        'slashes': '#FF0000',
        'title': '#FF0000'
    }
    
    result = main([
        str(csv_path),
        '--colors', json.dumps(invalid_colors),
        '--timestamp-columns', 'ts',
        '--no-show'
    ])
    assert result == 1

def test_main_no_timestamp_columns(tmp_path):
    # Create test CSV with no timestamp columns
    csv_path = tmp_path / "test.csv"
    df = pd.DataFrame({
        'id': [1],
        'name': ['test'],
        'value': [100]
    })
    df.to_csv(csv_path, index=False)
    
    # Test with no timestamp columns and no detection
    result = main([
        str(csv_path),
        '--no-show'
    ])
    assert result == 1

def test_main_label_mappings_validation(tmp_path):
    # Create test CSV
    csv_path = tmp_path / "test.csv"
    pd.DataFrame({
        'ts': ['2024-01-01'],
        'other_ts': ['2024-01-02']
    }).to_csv(csv_path, index=False)
    
    # Test label mapping for non-existent column
    invalid_mappings = {
        'nonexistent': 'Label',
        'ts': 'Timestamp'
    }
    
    result = main([
        str(csv_path),
        '--label-mappings', json.dumps(invalid_mappings),
        '--timestamp-columns', 'ts',
        '--no-show'
    ])
    assert result == 1 

def test_main_invalid_figsize_format():
    # Test completely invalid format
    with pytest.raises(SystemExit) as exc_info:
        main(['data.csv', '--figsize', 'not-a-size'])
    assert exc_info.value.code == 2
    
    # Test wrong number of values
    with pytest.raises(SystemExit) as exc_info:
        main(['data.csv', '--figsize', '10,5,2'])
    assert exc_info.value.code == 2
    
    # Test non-numeric values
    with pytest.raises(SystemExit) as exc_info:
        main(['data.csv', '--figsize', 'a,b'])
    assert exc_info.value.code == 2 

def test_main_invalid_csv_format(tmp_path):
    # Create an invalid CSV file
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text("not,a,valid\ncsv,file\nwith,wrong,columns")
    
    # Test with invalid CSV format
    result = main([
        str(csv_path),
        '--timestamp-columns', 'ts',
        '--no-show'
    ])
    assert result == 1 

def test_main_file_not_found():
    # Test with non-existent file
    result = main(['nonexistent.csv', '--no-show'])
    assert result == 1

def test_main_figure_size_parsing():
    # Test with invalid figure size format
    with pytest.raises(SystemExit) as exc_info:
        main(['data.csv', '--figsize', 'invalid'])
    assert exc_info.value.code == 2 