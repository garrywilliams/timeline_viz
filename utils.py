"""
Utility functions for timeline visualization.

This module provides helper functions for data preprocessing, 
column detection, and other utilities.
"""

import pandas as pd
import re
import os
from datetime import datetime, timedelta
import numpy as np
import random
from dateutil import parser
import pytz



def generate_sample_data(num_entities=5, entity_type="generic", 
                       timestamp_columns=None, output_file=None):
    """Generate sample data for testing."""
    if timestamp_columns is None:
        timestamp_columns = ['created_at_utc', 'updated_at_utc']
        
    # Create DataFrame with specified columns
    data = []
    current_time = datetime.now()
    
    for i in range(num_entities):
        entity = {
            f'{entity_type}_id': f'{i+1:03d}'
        }
        
        # Add timestamps
        for col in timestamp_columns:
            entity[col] = current_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            current_time += timedelta(minutes=random.randint(15, 120))
            
        data.append(entity)
    
    df = pd.DataFrame(data)
    
    if output_file:
        df.to_csv(output_file, index=False)
        
    return df

def detect_date_format(date_string):
    """
    Detect the format of a date string.
    
    Parameters:
    -----------
    date_string : str
        String containing a date
        
    Returns:
    --------
    str or None
        Format string if detected, None if not a valid date
    """
    if not isinstance(date_string, str):
        return None
        
    common_formats = [
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%Y%m%d'
    ]
    
    for fmt in common_formats:
        try:
            datetime.strptime(date_string, fmt)
            return fmt
        except ValueError:
            continue
    
    return None



def parse_timestamps(df, column, normalize_tz=False, errors='raise'):
    """
    Parse timestamp column in a DataFrame.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing the timestamp column
    column : str
        Name of column containing timestamps
    normalize_tz : bool, default=False
        If True, converts timezone-aware timestamps to timezone-naive
    errors : str, default='raise'
        How to handle parsing errors:
        - 'raise': raise exception
        - 'coerce': set invalid values to NaT
        - 'ignore': return original values
        
    Returns:
    --------
    pandas.Series
        Series with parsed timestamps
    """
    timestamp_series = df[column]
    
    if errors == 'ignore':
        return timestamp_series
        
    # Try to parse timestamps
    ts_series = pd.to_datetime(timestamp_series, errors=errors)
    
    # Handle timezone normalization
    if normalize_tz and not ts_series.isna().all():
        # Only check timezone if we have valid timestamps
        if ts_series.dt.tz is not None:
            ts_series = ts_series.dt.tz_localize(None)
    
    return ts_series

def create_color_scheme(base_color=None, accent_color=None):
    """Create a color scheme for timeline visualization."""
    # Convert color names to hex first
    if base_color and not base_color.startswith('#'):
        from matplotlib.colors import to_hex
        try:
            base_color = to_hex(base_color)
        except ValueError:
            raise ValueError(f"Invalid color name: {base_color}")

    if accent_color and not accent_color.startswith('#'):
        from matplotlib.colors import to_hex
        try:
            accent_color = to_hex(accent_color)
        except ValueError:
            raise ValueError(f"Invalid color name: {accent_color}")

    # Then validate hex format
    if base_color:
        if not re.match(r'^#[0-9A-Fa-f]{6}$', base_color):
            raise ValueError(f"Invalid hex color format: {base_color}")
    
    if accent_color:
        if not re.match(r'^#[0-9A-Fa-f]{6}$', accent_color):
            raise ValueError(f"Invalid hex color format: {accent_color}")
    
    # Default Best Buy colors
    if base_color is None:
        base_color = '#0046be'  # Best Buy blue
    elif not base_color.startswith('#'):
        # Convert color names to hex
        from matplotlib.colors import to_hex
        base_color = to_hex(base_color)
    
    if accent_color is None:
        accent_color = '#ffe000'  # Best Buy yellow
    elif not accent_color.startswith('#'):
        from matplotlib.colors import to_hex
        accent_color = to_hex(accent_color)
    
    # Create color scheme
    return {
        'line': base_color,          # Timeline
        'point_edge': base_color,    # Point border
        'point_face': accent_color,  # Point fill
        'connector': base_color,     # Connector lines
        'label_bg': '#f5f5f5',      # Light gray - label background
        'label_edge': base_color,    # Label border
        'slashes': base_color,       # Timeline breaks
        'title': base_color          # Title
    }

def detect_timestamp_columns(columns):
    """Detect columns that might contain timestamp data based on naming patterns."""
    timestamp_patterns = ['_utc', '_at', '_time', '_date', 'timestamp', 'datetime']
    start_patterns = ['date', 'time']
    
    detected = []
    for col in columns:
        col_lower = col.lower()
        # Check suffixes
        if any(col_lower.endswith(pattern) for pattern in timestamp_patterns):
            detected.append(col)
        # Check contains
        elif any(pattern in col_lower for pattern in ['timestamp', 'datetime']):
            detected.append(col)
        # Check prefixes
        elif any(col_lower.startswith(pattern) for pattern in start_patterns):
            detected.append(col)
            
        # Don't include columns with 'invalid' in the name
        if 'invalid' in col_lower:
            detected.remove(col) if col in detected else None
    
    return detected

def validate_timestamps(timestamp_columns, df_columns):
    """Validate that all specified timestamp columns exist in the dataframe."""
    missing = [col for col in timestamp_columns if col not in df_columns]
    if missing:
        raise ValueError(f"Timestamp columns not found in data: {missing}")
    return True

def clean_column_name(column_name, remove_suffixes=None):
    """
    Convert column names to human-readable labels.
    
    Parameters:
    -----------
    column_name : str
        Original column name
    remove_suffixes : list of str, optional
        Suffixes to remove from column names (e.g., ['_utc', '_at'])
        
    Returns:
    --------
    str
        Clean, human-readable label
    """
    clean_name = column_name
    
    # Remove specified suffixes
    if remove_suffixes:
        for suffix in remove_suffixes:
            if clean_name.endswith(suffix):
                clean_name = clean_name[:-len(suffix)]
                break
    
    # Replace underscores and hyphens with spaces
    clean_name = clean_name.replace('_', ' ').replace('-', ' ')
    
    # Title case the result
    return clean_name.title()
