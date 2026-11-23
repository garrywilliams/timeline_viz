"""
Public plotting API for event timelines.

These functions keep their long-standing signatures but are now thin wrappers:
input is turned into a :class:`~timelineviz.model.Timeline`, laid out by
:mod:`timelineviz.layout` and drawn by :mod:`timelineviz.render_mpl`.
"""

import os

import pandas as pd

from timelineviz.layout import find_clusters
from timelineviz.model import (
    Event,
    Timeline,
    load_dataframe,
    timeline_from_event_log,
    timeline_from_wide,
)
from timelineviz.render_mpl import format_timestamp, render_timeline
from timelineviz.utils import clean_column_name, create_color_scheme, detect_timestamp_columns

# Default colour scheme (blue line, yellow points). Kept for backwards compatibility.
DEFAULT_COLOR_SCHEME = create_color_scheme()

__all__ = [
    "DEFAULT_COLOR_SCHEME",
    "clean_column_name",
    "find_clusters",
    "format_timestamp",
    "plot_event_log_timeline",
    "plot_multiple_timelines",
    "plot_timeline",
]


def _plot_sorted_events(
    timestamps,
    labels,
    *,
    entity_id=None,
    threshold_days=30,
    figsize=None,
    point_size=8,
    date_rotation=0,
    color_scheme=None,
    title=None,
    title_default_prefix="Timeline",
    show_plot=True,
    output_file=None,
    dpi=150,
    varying_height=False,
):
    """Render chronologically sorted timestamps with per-point labels."""
    if not timestamps or not labels or len(timestamps) != len(labels):
        print("No valid events to plot")
        return None, None

    if title is None:
        title = title_default_prefix
        if entity_id:
            title += f" - Entity {entity_id}"

    timeline = Timeline(
        [Event(t, lab) for t, lab in zip(timestamps, labels)],
        title=title,
        entity_id=entity_id,
    )
    return render_timeline(
        timeline,
        threshold_days=threshold_days,
        figsize=figsize,
        point_size=point_size,
        date_rotation=date_rotation,
        color_scheme=color_scheme,
        varying_height=varying_height,
        output_file=output_file,
        dpi=dpi,
        show_plot=show_plot,
    )


def plot_timeline(
    data,
    timestamp_columns=None,
    entity_id=None,
    threshold_days=30,
    figsize=None,
    point_size=8,
    date_rotation=0,
    color_scheme=None,
    title=None,
    label_mappings=None,
    remove_suffixes=None,
    show_plot=True,
    output_file=None,
    dpi=150,
    varying_height=False,
):
    """
    Plot a timeline of events based on timestamp columns.

    Parameters
    ----------
    data : pandas.DataFrame or pandas.Series
        Data containing timestamp columns. A Series is one row. All rows of a
        DataFrame are treated as a single entity: every non-null value in each
        timestamp column becomes a point.
    timestamp_columns : list, optional
        Columns to plot. If None, timestamp columns are auto-detected by name.
    entity_id : str, optional
        Entity ID shown in the default title.
    threshold_days : float, default=30
        Gaps longer than this split the timeline into panels, with a break mark
        labelled with the time skipped.
    figsize : tuple, optional
        ``None`` (default) sizes the figure to fit its labels at 15in wide.
        ``(width, None)`` fixes only the width; ``(width, height)`` fixes both.
    point_size : int, default=8
        Marker size of event points.
    date_rotation : int, default=0
        Rotation of the time-axis tick labels.
    color_scheme : dict, optional
        Colour overrides; any subset of the keys in ``DEFAULT_COLOR_SCHEME``.
    title : str, optional
        Plot title. Defaults to ``"Timeline - Entity {id}"``.
    label_mappings : dict, optional
        Column name → display label.
    remove_suffixes : list, optional
        Suffixes stripped from column names to make labels
        (default ``_utc``, ``_at``, ``_time``, ``_date``).
    show_plot : bool, default=True
        Show the figure (GUI backends); otherwise it is closed after saving.
    output_file : str, optional
        Save path; the extension picks the format (``.png``, ``.svg``, ``.pdf``).
    dpi : int, default=150
        Resolution for raster output.
    varying_height : bool, default=False
        Stagger labels over several heights even where they would fit lower.
        Labels never overlap either way.

    Returns
    -------
    fig : matplotlib.figure.Figure
    axs : list of matplotlib.axes.Axes
        One axes per time panel. ``(None, None)`` if there is nothing to plot.
    """
    if timestamp_columns is None:
        frame = pd.DataFrame([data]) if isinstance(data, pd.Series) else data
        timestamp_columns = detect_timestamp_columns(frame)
    if not timestamp_columns:
        print("No timestamp columns found or specified")
        return None, None

    timeline = timeline_from_wide(
        data,
        timestamp_columns,
        label_mappings=label_mappings,
        remove_suffixes=remove_suffixes,
        entity_id=entity_id,
    )
    if not timeline.events:
        print(f"No valid timestamps found for entity {entity_id}")
        return None, None

    return _plot_sorted_events(
        timeline.times,
        timeline.labels,
        entity_id=entity_id,
        threshold_days=threshold_days,
        figsize=figsize,
        point_size=point_size,
        date_rotation=date_rotation,
        color_scheme=color_scheme,
        title=title,
        title_default_prefix="Timeline",
        show_plot=show_plot,
        output_file=output_file,
        dpi=dpi,
        varying_height=varying_height,
    )


def plot_event_log_timeline(
    data,
    timestamp_column,
    label_column=None,
    filter_column=None,
    include_values=None,
    exclude_values=None,
    entity_id=None,
    threshold_days=30,
    figsize=None,
    point_size=8,
    date_rotation=0,
    color_scheme=None,
    title=None,
    show_plot=True,
    output_file=None,
    dpi=150,
    varying_height=False,
):
    """
    Plot a timeline from long-format (log-style) data: one timestamp column, many rows.

    Each row becomes one point on the timeline. Use ``filter_column`` with
    ``include_values`` / ``exclude_values`` to drop noise (for example only
    ``ERROR`` and ``WARN`` lines, or exclude ``DEBUG``).

    Parameters
    ----------
    data : str or pandas.DataFrame
        CSV path or DataFrame.
    timestamp_column : str
        Column containing event times.
    label_column : str, optional
        Column whose values are shown as event labels. If omitted, labels are
        ``Event 1``, ``Event 2``, … in time order.
    filter_column : str, optional
        Column used with ``include_values`` / ``exclude_values`` (e.g. ``level``,
        ``event_type``). Required if either filter list is provided.
    include_values : list, optional
        Keep only rows where ``filter_column`` is in this list.
    exclude_values : list, optional
        Drop rows where ``filter_column`` is in this list.
    entity_id : str, optional
        Shown in the default title after "Event log - Entity …".
    threshold_days, figsize, point_size, date_rotation, color_scheme, title,
    show_plot, output_file, dpi, varying_height
        Same as :func:`plot_timeline`.

    Returns
    -------
    fig, axs
        Same as :func:`plot_timeline`.
    """
    timeline = timeline_from_event_log(
        data,
        timestamp_column,
        label_column=label_column,
        filter_column=filter_column,
        include_values=include_values,
        exclude_values=exclude_values,
        entity_id=entity_id,
    )
    if not timeline.events:
        print("No events left after filtering and parsing timestamps")
        return None, None

    if threshold_days <= 0:
        raise ValueError("threshold_days must be positive")

    return _plot_sorted_events(
        timeline.times,
        timeline.labels,
        entity_id=entity_id,
        threshold_days=threshold_days,
        figsize=figsize,
        point_size=point_size,
        date_rotation=date_rotation,
        color_scheme=color_scheme,
        title=title,
        title_default_prefix="Event log",
        show_plot=show_plot,
        output_file=output_file,
        dpi=dpi,
        varying_height=varying_height,
    )


def plot_multiple_timelines(
    data,
    timestamp_columns=None,
    id_column=None,
    detect_timestamps=False,
    output_dir=None,
    max_entities=None,
    threshold_days=1,
    figsize=None,
    point_size=10,
    color_scheme=None,
    show_plots=True,
    dpi=150,
    label_mappings=None,
    remove_suffixes=None,
    entity_name="Entity",
    varying_height=False,
    output_format="png",
):
    """
    Plot timelines for multiple entities from a DataFrame or CSV file.

    Parameters
    ----------
    data : str or pandas.DataFrame
        Path to a CSV file or a DataFrame.
    timestamp_columns : list, optional
        Columns containing timestamps.
    id_column : str, optional
        Entity identifier column. If None, each row is its own entity.
    detect_timestamps : bool, default=False
        Also auto-detect timestamp columns by name.
    output_dir : str, optional
        Directory to save images to.
    max_entities : int, optional
        Plot at most this many entities.
    threshold_days : float, default=1
        Gap that splits a timeline into panels.
    figsize, point_size, color_scheme, dpi, label_mappings, remove_suffixes, varying_height
        See :func:`plot_timeline`.
    show_plots : bool, default=True
        Show each figure.
    entity_name : str, default='Entity'
        Entity noun used in titles and filenames (e.g. 'Patient', 'Order').
    output_format : str, default='png'
        File extension for saved images, e.g. ``'png'``, ``'svg'``, ``'pdf'``.

    Returns
    -------
    list of str
        IDs of entities that were plotted.
    """
    df = load_dataframe(data)

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if detect_timestamps:
        detected_columns = detect_timestamp_columns(df)
        if not detected_columns:
            print("No timestamp columns detected in the CSV file")
            return []
        if timestamp_columns:
            timestamp_columns = list(dict.fromkeys(list(timestamp_columns) + detected_columns))
        else:
            timestamp_columns = detected_columns

    if not timestamp_columns:
        print("No timestamp columns specified or detected")
        return []

    if threshold_days <= 0:
        raise ValueError("threshold_days must be positive")

    entity_ids = df.index.tolist() if id_column is None else df[id_column].unique()
    if max_entities:
        entity_ids = entity_ids[:max_entities]

    ext = output_format.lstrip(".").lower()
    processed_entities = []

    for entity_id in entity_ids:
        if id_column:
            entity_data = df[df[id_column] == entity_id]
            entity_id_str = str(entity_id)
        else:
            entity_data = df.iloc[[entity_id]]
            entity_id_str = f"row_{entity_id}"

        if len(entity_data) == 0:
            print(f"No data found for {entity_name.lower()} {entity_id}")
            continue

        output_file = None
        if output_dir:
            safe_id = "".join(c if c.isalnum() else "_" for c in entity_id_str)
            output_file = os.path.join(
                output_dir, f"{entity_name.lower()}_{safe_id}_timeline.{ext}"
            )

        fig, _axs = plot_timeline(
            entity_data,
            timestamp_columns,
            entity_id=entity_id_str,
            threshold_days=threshold_days,
            figsize=figsize,
            point_size=point_size,
            color_scheme=color_scheme,
            title=f"{entity_name} Timeline - {entity_id_str}",
            label_mappings=label_mappings,
            remove_suffixes=remove_suffixes,
            show_plot=show_plots,
            output_file=output_file,
            dpi=dpi,
            varying_height=varying_height,
        )

        if fig is not None:
            processed_entities.append(entity_id_str)
            if output_file:
                print(f"Saved timeline for {entity_name.lower()} {entity_id_str} to {output_file}")

    return processed_entities
