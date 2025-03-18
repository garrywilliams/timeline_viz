"""
Timeline Visualization Library
==============================

A Python library for visualizing event timelines from CSV data.

Main functionality:
- Plot event timelines from any timestamp data
- Process multiple rows/entities from CSV files
- Customizable timeline appearance
- Handle time gaps with broken timelines

Example usage:
-------------
from timeline_viz import plot_timeline, plot_multiple_timelines

# Plot a timeline from a DataFrame row
import pandas as pd
df = pd.read_csv("events.csv")
plot_timeline(df.iloc[0], ['created_at', 'updated_at', 'completed_at'])

# Plot multiple timelines from a CSV file
plot_multiple_timelines("events.csv", 
                      timestamp_columns=['created_at', 'updated_at', 'completed_at'], 
                      id_column='entity_id',
                      output_dir="timeline_images")

# Auto-detect timestamp columns ending with "_utc"
plot_multiple_timelines("events.csv", 
                      detect_timestamps=True,
                      id_column='entity_id')
"""

__version__ = '0.1.0'

from timeline import (
    plot_timeline,
    plot_multiple_timelines,
    find_clusters,
    format_timestamp
)

__all__ = [
    'plot_timeline',
    'plot_multiple_timelines',
    'find_clusters',
    'format_timestamp'
]