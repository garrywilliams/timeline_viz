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

def generate_sample_data(num_entities=5, entity_type="generic", 
                       timestamp_columns=None, output_file=None):
    """
    Generate sample data for timeline visualization testing.
    
    Parameters:
    -----------
    num_entities : int, default=5
        Number of entities to generate
    entity_type : str, default="generic"
        Type of entity to generate (generic, patient, order, etc.)
    timestamp_columns : list, optional
        List of timestamp column names to generate
        If None, uses default columns for the entity type
    output_file : str, optional
        Path to save the generated CSV file
        If None, returns the DataFrame without saving
        
    Returns:
    --------
    pandas.DataFrame
        DataFrame containing the generated data
    """
    # Define default timestamp columns based on entity type
    default_columns = {
        "generic": ["created_at_utc", "updated_at_utc", "completed_at_utc"],
        "patient": ["admission_start_utc", "kit_assigned_utc", "activated_utc", 
                   "first_event_utc", "first_task_utc", "discharged_utc"],
        "order": ["order_placed_utc", "payment_received_utc", "processing_started_utc", 
                 "shipped_utc", "delivered_utc"],
        "task": ["created_at_utc", "assigned_at_utc", "started_at_utc", 
                "milestone_1_at_utc", "milestone_2_at_utc", "completed_at_utc"]
    }
    
    # Use default columns if none specified
    if timestamp_columns is None:
        timestamp_columns = default_columns.get(
            entity_type.lower(), default_columns["generic"]
        )
    
    # Define ID column based on entity type
    id_column = f"{entity_type.lower()}_id" if entity_type != "generic" else "entity_id"
    
    # Create data structure
    data = []
    
    for i in range(1, num_entities + 1):
        # Base date for this entity
        base_date = datetime(2024, random.randint(1, 12), random.randint(1, 28), 
                           random.randint(8, 17), random.randint(0, 59))
        
        # Create an entity record
        entity = {
            id_column: f"{10000 + i}"
        }
        
        # Add sequential timestamps with random gaps
        current_time = base_date
        for col in timestamp_columns:
            # Randomly skip some timestamps (about 10% chance)
            if random.random() < 0.1 and col != timestamp_columns[0]:
                continue
                
            # Add random time gap (minutes to hours)
            gap = timedelta(
                minutes=random.randint(15, 120)
            )
            current_time += gap
            
            # Add milliseconds for precision
            ms = random.randint(0, 999)
            timestamp = current_time.replace(microsecond=ms*1000)
            
            # Add to entity record
            entity[col] = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
        # For some entities, add a large gap to test timeline breaks
        if i % 3 == 0 and len(timestamp_columns) > 3:
            mid_idx = len(timestamp_columns) // 2
            for j in range(mid_idx, len(timestamp_columns)):
                if timestamp_columns[j] in entity:
                    # Parse the timestamp
                    ts = datetime.strptime(entity[timestamp_columns[j]], "%Y-%m-%d %H:%M:%S.%f")
                    # Add days gap
                    ts += timedelta(days=random.randint(2, 5))
                    # Update the timestamp
                    entity[timestamp_columns[j]] = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        data.append(entity)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Save to CSV if output file specified
    if output_file:
        df.to_csv(output_file, index=False)
        print(f"Generated sample data with {num_entities} entities saved to {output_file}")
    
    return df

def detect_date_format(sample_date):
    """
    Detect the date format from a sample date string.
    
    Parameters:
    -----------
    sample_date : str
        Sample date string to analyze
        
    Returns:
    --------
    str or None
        Detected date format string for datetime.strptime, or None if not detected
    """
    # Common date formats to try
    formats = [
        '%Y-%m-%d %H:%M:%S.%f',  # 2024-01-01 12:30:45.123
        '%Y-%m-%d %H:%M:%S',     # 2024-01-01 12:30:45
        '%Y-%m-%dT%H:%M:%S.%fZ', # 2024-01-01T12:30:45.123Z (ISO format)
        '%Y-%m-%dT%H:%M:%SZ',    # 2024-01-01T12:30:45Z
        '%Y-%m-%d',              # 2024-01-01
        '%m/%d/%Y %H:%M:%S',     # 01/01/2024 12:30:45
        '%m/%d/%Y',              # 01/01/2024
        '%d-%b-%Y %H:%M:%S',     # 01-Jan-2024 12:30:45
        '%d-%b-%Y',              # 01-Jan-2024
        '%b %d, %Y %H:%M:%S',    # Jan 01, 2024 12:30:45
        '%b %d, %Y',             # Jan 01, 2024
    ]
    
    for fmt in formats:
        try:
            datetime.strptime(sample_date, fmt)
            return fmt
        except ValueError:
            continue
    
    return None

def parse_timestamps(df, column, errors='coerce'):
    """
    Parse timestamp strings to datetime objects, handling multiple formats.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing the timestamp column
    column : str
        Column name to parse
    errors : str, default='coerce'
        How to handle parsing errors:
        - 'coerce': Set failed parse to NaT
        - 'raise': Raise exception
        - 'ignore': Return original values for failed parse
        
    Returns:
    --------
    pandas.Series
        Series of datetime objects
    """
    # Make a copy of the column
    timestamp_series = df[column].copy()
    
    # Skip if already datetime
    if pd.api.types.is_datetime64_any_dtype(timestamp_series):
        return timestamp_series
    
    # Try to parse with pandas
    try:
        return pd.to_datetime(timestamp_series, errors=errors)
    except:
        # If pandas auto-detection fails, try manual format detection
        # Get the first non-null value
        sample = timestamp_series.dropna().iloc[0] if not timestamp_series.dropna().empty else None
        
        if sample:
            fmt = detect_date_format(str(sample))
            if fmt:
                # Apply the detected format
                parsed = timestamp_series.apply(
                    lambda x: datetime.strptime(str(x), fmt) if pd.notna(x) else pd.NaT
                )
                return parsed
    
    # If all else fails, return as specified by errors parameter
    if errors == 'coerce':
        return pd.Series([pd.NaT] * len(timestamp_series))
    elif errors == 'ignore':
        return timestamp_series
    else:  # 'raise'
        raise ValueError(f"Could not parse timestamps in column '{column}'")

def create_color_scheme(base_color=None, accent_color=None):
    """
    Create a complete color scheme based on provided base and accent colors.
    
    Parameters:
    -----------
    base_color : str, optional
        Hex color code for the primary color
        If None, uses Best Buy blue (#0046be)
    accent_color : str, optional
        Hex color code for the accent color
        If None, uses Best Buy yellow (#ffe000)
        
    Returns:
    --------
    dict
        Complete color scheme dictionary
    """
    # Default Best Buy colors
    if base_color is None:
        base_color = '#0046be'  # Best Buy blue
    
    if accent_color is None:
        accent_color = '#ffe000'  # Best Buy yellow
    
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
