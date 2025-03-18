"""
Core timeline visualization functionality.

This module contains the main functions for creating generic timeline visualizations
for any type of timestamp data.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import pandas as pd
import os
import re
from utils import parse_timestamps, detect_timestamp_columns

# Default color scheme - Best Buy brand colors
DEFAULT_COLOR_SCHEME = {
    'line': '#0046be',          # Best Buy blue - timeline
    'point_edge': '#0046be',    # Best Buy blue - point border
    'point_face': '#ffe000',    # Best Buy yellow - point fill
    'connector': '#0046be',     # Best Buy blue - connector lines
    'label_bg': '#f5f5f5',      # Light gray - label background
    'label_edge': '#0046be',    # Best Buy blue - label border
    'slashes': '#0046be',       # Best Buy blue - timeline breaks
    'title': '#0046be'          # Best Buy blue - title
}

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

def find_clusters(dates_num, threshold_days=30):
    """
    Find clusters of timestamps based on time gaps.
    
    Parameters:
    -----------
    dates_num : array-like
        Dates in matplotlib numerical format
    threshold_days : float
        Number of days gap to consider as a break in timeline
        
    Returns:
    --------
    clusters : list of arrays
        List of clusters of dates
    cluster_indices : list of lists
        List of lists of indices corresponding to original dates
    """
    if len(dates_num) <= 1:
        return [dates_num], [[0]] if len(dates_num) == 1 else [[], []]
    
    # Convert threshold to numerical date units (days)
    threshold = threshold_days
    
    # Calculate gaps between consecutive dates
    gaps = np.diff(dates_num)
    
    # Find indices where gaps exceed threshold
    break_indices = np.where(gaps > threshold)[0]
    
    # Create clusters
    clusters = []
    cluster_indices = []
    start_idx = 0
    
    for idx in break_indices:
        cluster_dates = dates_num[start_idx:idx + 1]
        clusters.append(cluster_dates)
        cluster_indices.append(list(range(start_idx, idx + 1)))
        start_idx = idx + 1
    
    # Add final cluster
    clusters.append(dates_num[start_idx:])
    cluster_indices.append(list(range(start_idx, len(dates_num))))
    
    return clusters, cluster_indices

def format_timestamp(dt):
    """
    Format timestamp for label display with milliseconds.
    
    Parameters:
    -----------
    dt : datetime
        Datetime object to format
        
    Returns:
    --------
    str
        Formatted timestamp string with milliseconds
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # truncate to milliseconds

def plot_timeline(data, timestamp_columns=None, entity_id=None, 
                threshold_days=30, figsize=(15, 5), point_size=8, date_rotation=45, 
                color_scheme=None, title=None, label_mappings=None,
                remove_suffixes=None, show_plot=True, output_file=None, dpi=150):
    """
    Plot a timeline of events based on timestamp columns.
    
    Parameters:
    -----------
    data : pandas.DataFrame or pandas.Series
        Data containing timestamp columns
    timestamp_columns : list, optional
        List of column names containing timestamps to include in timeline
        If None, will attempt to auto-detect timestamp columns
    entity_id : str, optional
        ID of entity for plot title
    threshold_days : float, default=30
        Number of days gap to consider as a break in timeline
    figsize : tuple, default=(15, 5)
        Size of the figure in inches
    point_size : int, default=8
        Size of the event points
    date_rotation : int, default=45
        Rotation angle for date labels
    color_scheme : dict, optional
        Custom color scheme. If None, uses default Best Buy colors
    title : str, optional
        Custom title for the plot. If None, uses "Timeline - Entity {id}"
    label_mappings : dict, optional
        Custom mappings from column names to display labels
    remove_suffixes : list, optional
        List of suffixes to remove from column names when creating labels
    show_plot : bool, default=True
        Whether to display the plot
    output_file : str, optional
        Path to save the plot image. If None, image is not saved
    dpi : int, default=150
        Resolution for saved image
        
    Returns:
    --------
    fig : matplotlib.figure.Figure
        The figure object containing the timeline
    axs : list of matplotlib.axes.Axes
        The axes objects in the figure
    """
    # Use default color scheme if none provided
    if color_scheme is None:
        color_scheme = DEFAULT_COLOR_SCHEME
    
    # Default suffixes to remove when creating labels
    if remove_suffixes is None:
        remove_suffixes = ['_utc', '_at', '_time', '_date']
        
    # Convert Series to DataFrame if necessary
    if isinstance(data, pd.Series):
        data = pd.DataFrame([data])
    
    # Auto-detect timestamp columns if not specified
    if timestamp_columns is None:
        timestamp_columns = detect_timestamp_columns(data)
    
    if not timestamp_columns:
        print("No timestamp columns found or specified")
        return None, None
    
    # Filter to include only columns that exist and have non-null values
    valid_columns = []
    timestamps = []
    labels = []
    
    for col in timestamp_columns:
        if col in data.columns and pd.notna(data[col].iloc[0]):
            valid_columns.append(col)
            # Parse the timestamp, ensuring consistent timezone handling
            ts = parse_timestamps(data, col, normalize_tz=True).iloc[0]
            timestamps.append(ts)
            
            # Get label for the column
            if label_mappings and col in label_mappings:
                # Use custom label mapping if provided
                label = label_mappings[col]
            else:
                # Otherwise clean the column name
                label = clean_column_name(col, remove_suffixes)
            
            labels.append(label)
        
    if not timestamps:
        print(f"No valid timestamps found for entity {entity_id}")
        return None, None
    
    # Sort timestamps chronologically
    sorted_indices = np.argsort(timestamps)
    timestamps = [timestamps[i] for i in sorted_indices]
    labels = [labels[i] for i in sorted_indices]
    
    # Convert timestamps to matplotlib date numbers
    dates_num = mdates.date2num(timestamps)
    
    # Find clusters
    clusters, cluster_indices = find_clusters(dates_num, threshold_days)
    n_clusters = len(clusters)
    
    if n_clusters == 0:
        print(f"No valid clusters to plot for entity {entity_id}")
        return None, None
    
    # Create figure with wider spacing between subplots
    fig, axs = plt.subplots(1, n_clusters, figsize=figsize, 
                           gridspec_kw={'width_ratios': [len(c) for c in clusters]})
    if n_clusters == 1:
        axs = [axs]
    
    plt.subplots_adjust(wspace=0.1)  # Adjust spacing between subplots
    
    # Plot each cluster
    for i, (ax, cluster, indices) in enumerate(zip(axs, clusters, cluster_indices)):
        # Calculate padding for x limits
        time_range = max(cluster) - min(cluster)
        padding = time_range * 0.15 if len(cluster) > 1 else 0.1
        
        # Set x limits with padding
        ax.set_xlim(min(cluster) - padding, max(cluster) + padding)
        
        # Plot central timeline with brand color
        ax.axhline(y=0, color=color_scheme['line'], linewidth=2.0, zorder=1)
        
        # Plot points with brand colors
        ax.plot(cluster, np.zeros_like(cluster), 'o', 
                color=color_scheme['point_edge'], markersize=point_size, 
                markerfacecolor=color_scheme['point_face'], 
                markeredgewidth=1.5, zorder=3)
        
        # Add labels with alternating heights and connecting lines
        for j, (date_num, idx) in enumerate(zip(cluster, indices)):
            date = mdates.num2date(date_num)
            col_label = labels[idx]
            time_label = format_timestamp(date)
            label = f"{col_label}\n{time_label}"
            
            y_offset = 0.4 if j % 2 == 0 else -0.4
            text_y = y_offset * 2
            
            # Add connecting line
            ax.plot([date_num, date_num], [0, text_y], '-', 
                   color=color_scheme['connector'], linewidth=1.2, alpha=0.8, zorder=2)
            
            # Add text label with background
            bbox_props = dict(
                boxstyle="round,pad=0.5",
                fc=color_scheme['label_bg'],
                ec=color_scheme['label_edge'],
                alpha=0.9
            )
            
            ax.annotate(label, 
                       xy=(date_num, text_y),
                       xytext=(0, 5 if y_offset > 0 else -5),
                       textcoords='offset points',
                       ha='center',
                       va='bottom' if y_offset > 0 else 'top',
                       bbox=bbox_props,
                       fontsize=9)
        
        # Format x-axis to show time
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax.set_xticks([min(cluster), max(cluster)])
        
        ax.spines['bottom'].set_position(('data', 0))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=date_rotation, ha='right')
        
        ax.set_ylim(-1.2, 1.2)
        ax.set_yticks([])
        
        # Remove spines
        ax.spines['left'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
    
    # Draw break markers directly on the figure after tight_layout is applied
    plt.tight_layout()
    
    # Add custom break markers between subplots
    for i in range(n_clusters - 1):
        # Get positions of adjacent subplots
        right_pos = axs[i].get_position().x1
        left_pos = axs[i+1].get_position().x0
        mid_pos = (right_pos + left_pos) / 2
        
        # Parameters for slash positioning
        y_center = 0.5  # Center point in y-direction (figure coordinates)
        slash_height = 0.05  # Height of slash in figure coordinates
        slash_gap = 0.015  # Gap between slashes
        
        # Draw two parallel slashes for each break - with steeper angle
        for offset in [-slash_gap/2, slash_gap/2]:
            x_mid = mid_pos + offset
            
            # Draw the slash with steeper angle
            slash = plt.Line2D(
                [x_mid - slash_height/6, x_mid + slash_height/6],  # x-coords - narrower for steeper angle
                [y_center - slash_height/2, y_center + slash_height/2],  # y-coords
                transform=fig.transFigure,
                color=color_scheme['slashes'],
                linewidth=2.5,
                solid_capstyle='round',
                clip_on=False,
                zorder=10
            )
            fig.add_artist(slash)
    
    # Add title
    if title is None:
        title = 'Timeline'
        if entity_id:
            title += f' - Entity {entity_id}'
    
    plt.suptitle(title, fontsize=16, fontweight='bold', x=0.02, ha='left', 
                color=color_scheme.get('title', '#0046be'))
    
    # Save or show the figure
    if output_file:
        fig.savefig(output_file, bbox_inches='tight', dpi=dpi)
        print(f"Saved timeline to {output_file}")
    
    if show_plot:
        # Only try to show if using an interactive backend
        if plt.get_backend().lower() in ['tkagg', 'qt5agg', 'macosx', 'wx', 'gtk3agg']:
            plt.show()
    else:
        plt.close(fig)
    
    return fig, axs

def plot_multiple_timelines(data, timestamp_columns=None, id_column=None, 
                         detect_timestamps=False, output_dir=None, max_entities=None,
                         threshold_days=1, figsize=(15, 5), point_size=10,
                         color_scheme=None, show_plots=True, dpi=150,
                         label_mappings=None, remove_suffixes=None,
                         entity_name='Entity'):
    """
    Plot timelines for multiple entities from a DataFrame or CSV file.
    
    Parameters:
    -----------
    data : str or pandas.DataFrame
        Either a path to CSV file or a pandas DataFrame containing event data
    timestamp_columns : list, optional
        List of column names containing timestamps to include in timeline
    id_column : str, optional
        Column name for entity identifier. If None, uses row index
    detect_timestamps : bool, default=False
        If True, automatically detect timestamp columns
    output_dir : str, optional
        Directory to save timeline images. If None, doesn't save images
    max_entities : int, optional
        Maximum number of entities to plot. If None, plots all entities
    threshold_days : float, default=1
        Number of days gap to consider as a break in timeline
    figsize : tuple, default=(15, 5)
        Size of the figure in inches
    point_size : int, default=10
        Size of the event points
    color_scheme : dict, optional
        Custom color scheme. If None, uses default Best Buy colors
    show_plots : bool, default=True
        Whether to display the plots
    dpi : int, default=150
        Resolution for saved images
    label_mappings : dict, optional
        Custom mappings from column names to display labels
    remove_suffixes : list, optional
        List of suffixes to remove from column names when creating labels
    entity_name : str, default='Entity'
        Name to use for entities in titles (e.g., 'Patient', 'Order', 'User')
        
    Returns:
    --------
    processed_entities : list
        List of entity IDs that were successfully processed
    """
    # Handle input data
    if isinstance(data, str):
        df = pd.read_csv(data)
    elif isinstance(data, pd.DataFrame):
        df = data
    else:
        raise ValueError(f"data must be a DataFrame or path to CSV, not {type(data)}")
    
    # Create output directory if it doesn't exist
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Identify timestamp columns if needed
    if detect_timestamps:
        detected_columns = detect_timestamp_columns(df)
        if not detected_columns:
            print("No timestamp columns detected in the CSV file")
            return []
        
        if timestamp_columns:
            # Combine specified and detected columns
            timestamp_columns = list(set(timestamp_columns + detected_columns))
        else:
            timestamp_columns = detected_columns
    
    if not timestamp_columns:
        print("No timestamp columns specified or detected")
        return []
    
    # Use row index as entity ID if no id_column specified
    entity_ids = df.index.tolist() if id_column is None else df[id_column].unique()
    
    # Limit the number of entities if specified
    if max_entities:
        entity_ids = entity_ids[:max_entities]
    
    processed_entities = []
    
    # Validate threshold_days
    if threshold_days <= 0:
        raise ValueError("threshold_days must be positive")
    
    # Plot for each entity
    for entity_id in entity_ids:
        # Filter to get this entity's data
        if id_column:
            entity_data = df[df[id_column] == entity_id]
            entity_id_str = str(entity_id)
        else:
            entity_data = df.iloc[[entity_id]]
            entity_id_str = f"row_{entity_id}"
        
        # Skip if no data
        if len(entity_data) == 0:
            print(f"No data found for {entity_name.lower()} {entity_id}")
            continue
        
        # Generate output file path if needed
        output_file = None
        if output_dir:
            safe_id = "".join(c if c.isalnum() else "_" for c in entity_id_str)
            output_file = os.path.join(output_dir, f"{entity_name.lower()}_{safe_id}_timeline.png")
        
        # Custom title with entity name
        title = f"{entity_name} Timeline - {entity_id_str}"
        
        # Plot the timeline
        fig, axs = plot_timeline(
            entity_data, 
            timestamp_columns, 
            entity_id=entity_id_str,
            threshold_days=threshold_days,
            figsize=figsize,
            point_size=point_size,
            color_scheme=color_scheme,
            title=title,
            label_mappings=label_mappings,
            remove_suffixes=remove_suffixes,
            show_plot=show_plots,
            output_file=output_file,
            dpi=dpi
        )
        
        if fig is not None:
            processed_entities.append(entity_id_str)
            
            if output_file:
                print(f"Saved timeline for {entity_name.lower()} {entity_id_str} to {output_file}")
            
            if not show_plots:
                plt.close(fig)
    
    return processed_entities