import pytest
from datetime import datetime, timedelta
import pandas as pd
import pytz
import os
from utils import (
    detect_timestamp_columns,
    validate_timestamps,
    create_color_scheme,
    clean_column_name,
    detect_date_format,
    generate_sample_data,
    parse_timestamps
)

def test_create_color_scheme():
    # Test default colors
    colors = create_color_scheme()
    assert colors['line'] == '#0046be'
    assert colors['point_face'] == '#ffe000'
    
    # Test custom colors
    custom = create_color_scheme(base_color='#FF0000', accent_color='#00FF00')
    assert custom['line'] == '#FF0000'
    assert custom['point_face'] == '#00FF00'
    assert all(key in custom for key in ['line', 'point_edge', 'connector', 'label_bg'])

def test_clean_column_name():
    # Test basic cleaning
    assert clean_column_name('test_column') == 'Test Column'
    assert clean_column_name('test-column') == 'Test Column'
    
    # Test suffix removal
    assert clean_column_name('created_at_utc', remove_suffixes=['_utc']) == 'Created At'
    assert clean_column_name('updated_at', remove_suffixes=['_at']) == 'Updated'
    
    # Test multiple suffixes
    suffixes = ['_utc', '_at', '_time']
    assert clean_column_name('event_time', remove_suffixes=suffixes) == 'Event'

def test_detect_date_format():
    # Test various date formats
    assert detect_date_format('2024-01-01') == '%Y-%m-%d'
    assert detect_date_format('01/02/2024') == '%m/%d/%Y'
    assert detect_date_format('2024-01-01 10:30:00') == '%Y-%m-%d %H:%M:%S'
    assert detect_date_format('invalid_date') is None

def test_detect_timestamp_columns():
    columns = [
        'id', 'name', 
        'created_at', 'updated_at',
        'timestamp_field',
        'date_modified',
        'some_time_utc'
    ]
    detected = detect_timestamp_columns(columns)
    assert 'created_at' in detected
    assert 'updated_at' in detected
    assert 'timestamp_field' in detected
    assert 'date_modified' in detected
    assert 'some_time_utc' in detected
    assert 'id' not in detected
    assert 'name' not in detected

def test_validate_timestamps():
    valid_columns = ['created_at', 'updated_at']
    invalid_columns = ['created_at', 'nonexistent_column']
    df_columns = ['id', 'created_at', 'updated_at']
    
    assert validate_timestamps(valid_columns, df_columns) == True
    with pytest.raises(ValueError):
        validate_timestamps(invalid_columns, df_columns)

def test_generate_sample_data():
    # Test default parameters
    df = generate_sample_data(num_entities=3)
    assert len(df) == 3
    assert 'generic_id' in df.columns
    assert 'created_at_utc' in df.columns
    
    # Test custom entity type
    df = generate_sample_data(num_entities=2, entity_type="patient")
    assert len(df) == 2
    assert 'patient_id' in df.columns
    
    # Test custom timestamp columns
    custom_columns = ['start_time', 'end_time']
    df = generate_sample_data(
        num_entities=1, 
        timestamp_columns=custom_columns
    )
    assert all(col in df.columns for col in custom_columns)
    
    # Test output file
    output_file = "test_sample.csv"
    try:
        df = generate_sample_data(num_entities=1, output_file=output_file)
        assert os.path.exists(output_file)
    finally:
        if os.path.exists(output_file):
            os.remove(output_file)

def test_parse_timestamps():
    # Create test DataFrame
    df = pd.DataFrame({
        'ts1': ['2024-01-01 10:00:00', '2024-01-02 15:30:00'],
        'ts2': ['2024-01-01T10:00:00Z', '2024-01-02T15:30:00Z'],
        'ts3': [datetime.now(), datetime.now()],
        'not_ts': ['invalid', 'data']
    })
    
    # Test basic parsing
    result = parse_timestamps(df, 'ts1')
    assert isinstance(result, pd.Series)
    assert pd.api.types.is_datetime64_any_dtype(result)
    
    # Test timezone handling
    result = parse_timestamps(df, 'ts2', normalize_tz=True)
    assert result.dt.tz is None
    
    # Test multiple formats
    result = parse_timestamps(df, 'ts3')
    assert pd.api.types.is_datetime64_any_dtype(result)
    
    # Test error handling - raise
    with pytest.raises(ValueError):
        parse_timestamps(df, 'not_ts', errors='raise')
    
    # Test error handling - coerce
    result = parse_timestamps(df, 'not_ts', errors='coerce')
    assert result.isna().all()
    
    # Test error handling - ignore
    result = parse_timestamps(df, 'not_ts', errors='ignore')
    assert result.equals(df['not_ts'])
    
    # Test invalid column
    with pytest.raises(KeyError):
        parse_timestamps(df, 'nonexistent_column')

def test_detect_timestamp_columns_with_data():
    # Test with actual DataFrame
    df = pd.DataFrame({
        'id': [1, 2],
        'created_at': ['2024-01-01', '2024-01-02'],
        'name': ['test1', 'test2'],
        'updated_at': ['2024-01-01 10:00', '2024-01-02 11:00'],
        'invalid_date': ['not a date', 'still not a date']
    })
    
    detected = detect_timestamp_columns(df.columns)
    assert 'created_at' in detected
    assert 'updated_at' in detected
    assert 'id' not in detected
    assert 'name' not in detected
    assert 'invalid_date' not in detected

def test_validate_timestamps_edge_cases():
    # Test empty lists
    assert validate_timestamps([], []) == True
    
    # Test single column
    assert validate_timestamps(['col'], ['col']) == True
    
    # Test case sensitivity
    with pytest.raises(ValueError):
        validate_timestamps(['Created_At'], ['created_at'])
    
    # Test duplicate columns
    assert validate_timestamps(['col', 'col'], ['col']) == True

def test_detect_timestamp_columns_comprehensive():
    # Test with various column names and patterns
    columns = [
        'id',
        'created_at',
        'updated_at_utc',
        'timestamp_field',
        'date_modified',
        'some_time_utc',
        'datetime_column',
        'date_only',
        'time_only',
        'name',
        'description',
        'invalid_date'
    ]
    
    detected = detect_timestamp_columns(columns)
    
    # Should be detected
    assert all(col in detected for col in [
        'created_at',
        'updated_at_utc',
        'timestamp_field',
        'date_modified',
        'some_time_utc',
        'datetime_column',
        'date_only',
        'time_only'
    ])
    
    # Should not be detected
    assert all(col not in detected for col in [
        'id',
        'name',
        'description'
    ])

def test_detect_timestamp_columns_edge_cases():
    # Test empty list
    assert detect_timestamp_columns([]) == []
    
    # Test None input
    with pytest.raises(TypeError):
        detect_timestamp_columns(None)
    
    # Test non-list input
    with pytest.raises(TypeError):
        detect_timestamp_columns(123)

def test_validate_timestamps_comprehensive():
    # Test various scenarios
    df_columns = ['id', 'created_at', 'updated_at', 'completed_at']
    
    # Valid cases
    assert validate_timestamps(['created_at'], df_columns)
    assert validate_timestamps(['created_at', 'updated_at'], df_columns)
    assert validate_timestamps(df_columns, df_columns)
    assert validate_timestamps([], df_columns)
    
    # Invalid cases
    with pytest.raises(ValueError):
        validate_timestamps(['nonexistent'], df_columns)
    
    with pytest.raises(ValueError):
        validate_timestamps(['created_at', 'nonexistent'], df_columns)
    
    # Edge cases
    with pytest.raises(TypeError):
        validate_timestamps(None, df_columns)
    
    with pytest.raises(TypeError):
        validate_timestamps(['created_at'], None)

def test_create_color_scheme_edge_cases():
    # Test with invalid hex color format
    with pytest.raises(ValueError):
        create_color_scheme(base_color='#ZZ0000')
    
    # Test with invalid color name
    with pytest.raises(ValueError):
        create_color_scheme(accent_color='not-a-color')
    
    # Test with empty string
    with pytest.raises(ValueError):
        create_color_scheme(base_color='')

def test_detect_date_format_comprehensive():
    # Test various date formats
    test_cases = {
        '2024-01-01': '%Y-%m-%d',
        '2024-01-01 10:30:00': '%Y-%m-%d %H:%M:%S',
        '01/02/2024': '%m/%d/%Y',  # US format
        '2024-01-01T10:30:00Z': '%Y-%m-%dT%H:%M:%SZ',
        '20240101': '%Y%m%d',
        'not a date': None
    }
    
    for date_string, expected_format in test_cases.items():
        assert detect_date_format(date_string) == expected_format

def test_parse_timestamps_comprehensive():
    # Test various timestamp scenarios
    df = pd.DataFrame({
        'valid_iso': ['2024-01-01T10:30:00Z', '2024-01-02T11:30:00Z'],
        'valid_date': ['2024-01-01', '2024-01-02'],
        'valid_datetime': ['2024-01-01 10:30:00', '2024-01-02 11:30:00'],
        'mixed_valid': ['2024-01-01', '2024-01-02 11:30:00'],
        'invalid': ['not a date', 'also not a date'],
        'mixed_invalid': ['2024-01-01', 'not a date']
    })
    
    # Test valid columns
    for col in ['valid_iso', 'valid_date', 'valid_datetime']:
        result = parse_timestamps(df, col)
        assert pd.api.types.is_datetime64_any_dtype(result)
        
    # Test with errors='coerce'
    result = parse_timestamps(df, 'mixed_invalid', errors='coerce')
    assert pd.api.types.is_datetime64_any_dtype(result)
    assert pd.isna(result.iloc[1])
    
    # Test with errors='raise'
    with pytest.raises((ValueError, pd._libs.tslibs.parsing.DateParseError)):
        parse_timestamps(df, 'invalid', errors='raise')

def test_parse_timestamps_edge_cases():
    # Test empty DataFrame with column
    df = pd.DataFrame({'col': []})
    result = parse_timestamps(df, 'col')
    assert len(result) == 0
    
    # Test with invalid column
    df = pd.DataFrame({'other_col': [1]})
    with pytest.raises(KeyError):
        parse_timestamps(df, 'nonexistent_col')
    
    # Test with all null values
    df = pd.DataFrame({'col': [None, None]})
    result = parse_timestamps(df, 'col', errors='coerce')
    assert pd.isna(result).all()

def test_detect_date_format_edge_cases():
    # Test None input
    assert detect_date_format(None) is None
    
    # Test empty string
    assert detect_date_format('') is None
    
    # Test invalid types
    assert detect_date_format(123) is None
    assert detect_date_format([]) is None

def test_parse_timestamps_timezone_handling():
    # Test with timezone-aware timestamps
    df = pd.DataFrame({
        'ts': [
            '2024-01-01T10:00:00+00:00',  # UTC
            '2024-01-02T15:30:00+00:00'   # UTC
        ]
    })
    
    # Test without timezone normalization
    result = parse_timestamps(df, 'ts', normalize_tz=False)
    assert result.dt.tz is not None  # Should preserve timezone
    
    # Test with timezone normalization
    result = parse_timestamps(df, 'ts', normalize_tz=True)
    assert result.dt.tz is None  # Should be timezone-naive
    
    # Test with mixed timezone data
    df = pd.DataFrame({
        'ts': [
            '2024-01-01T10:00:00+00:00',  # With timezone
            '2024-01-02T15:30:00+00:00'   # With timezone
        ]
    })
    result = parse_timestamps(df, 'ts', normalize_tz=True)
    assert result.dt.tz is None  # Should all be timezone-naive
    
    # Test with all naive timestamps
    df = pd.DataFrame({
        'ts': [
            '2024-01-01 10:00:00',  # Without timezone
            '2024-01-02 15:30:00'   # Without timezone
        ]
    })
    result = parse_timestamps(df, 'ts', normalize_tz=True)
    assert result.dt.tz is None  # Should remain timezone-naive

def test_create_color_scheme_color_names():
    # Test with color names instead of hex
    colors = create_color_scheme(
        base_color='red',
        accent_color='blue'
    )
    assert colors['line'].startswith('#')  # Should convert to hex
    assert colors['point_face'].startswith('#')
    
    # Test with mixed hex and names
    colors = create_color_scheme(
        base_color='#FF0000',
        accent_color='blue'
    )
    assert colors['line'] == '#FF0000'
    assert colors['point_face'].startswith('#') 