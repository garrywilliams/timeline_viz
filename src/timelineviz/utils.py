"""
Utility functions for timeline visualization.

This module provides helper functions for data preprocessing,
column detection, and other utilities.
"""

import random
import re
from datetime import datetime, timedelta

import pandas as pd


def generate_sample_data(
    num_entities=5, entity_type="generic", timestamp_columns=None, output_file=None
):
    """Generate sample data for testing."""
    if timestamp_columns is None:
        timestamp_columns = ["created_at_utc", "updated_at_utc"]

    # Create DataFrame with specified columns
    data = []
    current_time = datetime.now()

    for i in range(num_entities):
        entity = {f"{entity_type}_id": f"{i + 1:03d}"}

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
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y%m%d",
    ]

    for fmt in common_formats:
        try:
            datetime.strptime(date_string, fmt)
            return fmt
        except ValueError:
            continue

    return None


def parse_timestamps(df, column, normalize_tz=False, errors="raise"):
    """
    Parse timestamp column in a DataFrame.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing the timestamp column
    column : str
        Name of column containing timestamps
    normalize_tz : bool, default=False
        If True, convert every timestamp to UTC and return timezone-naive values.
        Values carrying an offset (``+01:00``, ``Z``) are converted to UTC first, so
        rows with different offsets stay in true chronological order. Naive values
        are assumed to already be UTC and are left unchanged.
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

    if errors == "ignore":
        return timestamp_series

    if normalize_tz:
        # utc=True converts offset-aware values to UTC (and copes with mixed
        # offsets in one column); naive values are treated as UTC. Dropping the
        # tz afterwards keeps the UTC wall-clock rather than the local one.
        ts_series = pd.to_datetime(timestamp_series, errors=errors, utc=True)
        return ts_series.dt.tz_localize(None)

    return pd.to_datetime(timestamp_series, errors=errors)


def create_color_scheme(base_color=None, accent_color=None):
    """Create a color scheme for timeline visualization."""
    if base_color == "":
        raise ValueError("Invalid color name: ")
    if accent_color == "":
        raise ValueError("Invalid color name: ")

    # Convert color names to hex first
    if base_color and not base_color.startswith("#"):
        from matplotlib.colors import to_hex

        try:
            base_color = to_hex(base_color)
        except ValueError:
            raise ValueError(f"Invalid color name: {base_color}")

    if accent_color and not accent_color.startswith("#"):
        from matplotlib.colors import to_hex

        try:
            accent_color = to_hex(accent_color)
        except ValueError:
            raise ValueError(f"Invalid color name: {accent_color}")

    # Then validate hex format
    if base_color:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", base_color):
            raise ValueError(f"Invalid hex color format: {base_color}")

    if accent_color:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", accent_color):
            raise ValueError(f"Invalid hex color format: {accent_color}")

    # Default Best Buy colors
    if base_color is None:
        base_color = "#0046be"  # Best Buy blue

    if accent_color is None:
        accent_color = "#ffe000"  # Best Buy yellow

    # Create color scheme
    return {
        "line": base_color,  # Timeline
        "point_edge": base_color,  # Point border
        "point_face": accent_color,  # Point fill
        "connector": base_color,  # Connector lines
        "label_bg": "#f5f5f5",  # Light gray - label background
        "label_edge": base_color,  # Label border
        "slashes": base_color,  # Timeline breaks
        "title": base_color,  # Title
    }


def resolve_color_scheme(overrides=None):
    """Merge a (possibly partial) colour override dict onto the default scheme.

    ``line`` and ``point_face`` act as base / accent colours: every other key
    derived from them follows them unless that key is overridden too. Any other
    key can be overridden on its own. Values may be hex strings or matplotlib
    colour names; they are normalised to ``#rrggbb``.

    Raises
    ------
    ValueError
        If a key is not a known colour slot or a value is not a valid colour.
    """
    from matplotlib.colors import to_hex

    overrides = dict(overrides or {})
    scheme = create_color_scheme(
        base_color=overrides.get("line"), accent_color=overrides.get("point_face")
    )
    unknown = sorted(set(overrides) - set(scheme))
    if unknown:
        raise ValueError(f"Unknown color keys: {unknown}. Valid keys: {sorted(scheme)}")
    for key, value in overrides.items():
        try:
            scheme[key] = to_hex(value)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid color for {key!r}: {value!r}") from None
    return scheme


def detect_timestamp_columns(columns):
    """Detect columns that might contain timestamp data based on naming patterns."""
    timestamp_patterns = ["_utc", "_at", "_time", "_date", "timestamp", "datetime"]
    start_patterns = ["date", "time"]

    detected = []
    for col in columns:
        col_lower = col.lower()
        # Check suffixes
        if any(col_lower.endswith(pattern) for pattern in timestamp_patterns):
            detected.append(col)
        # Check contains
        elif any(pattern in col_lower for pattern in ["timestamp", "datetime"]):
            detected.append(col)
        # Check prefixes
        elif any(col_lower.startswith(pattern) for pattern in start_patterns):
            detected.append(col)

        # Don't include columns with 'invalid' in the name
        if "invalid" in col_lower:
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
                clean_name = clean_name[: -len(suffix)]
                break

    # Replace underscores and hyphens with spaces
    clean_name = clean_name.replace("_", " ").replace("-", " ")

    # Title case the result
    return clean_name.title()


# Matplotlib's built-in non-interactive (file-only) backends.
_NON_INTERACTIVE_BACKENDS = frozenset({"agg", "cairo", "pdf", "pgf", "ps", "svg", "template"})


def is_gui_backend(backend):
    """Return True if ``backend`` opens a window, so ``plt.show()`` is needed.

    Covers every GUI backend name (``qtagg``, ``qt5agg``, ``tkagg``, ``macosx``,
    ``gtk4agg``, ``wxagg``, …) without a hard-coded allowlist that goes stale.
    Notebook / third-party ``module://`` backends (e.g. Jupyter inline) display
    figures themselves, so they are not treated as GUI backends.
    """
    name = backend.lower()
    return not name.startswith("module://") and name not in _NON_INTERACTIVE_BACKENDS


def show_or_close(fig, show_plot):
    """Show ``fig`` on a GUI backend when requested, otherwise close it.

    With ``show_plot=True`` on a non-GUI backend (scripts using Agg, Jupyter
    inline) the figure is left open, which is what lets notebooks render it.
    """
    import matplotlib.pyplot as plt

    if not show_plot:
        plt.close(fig)
    elif is_gui_backend(plt.get_backend()):
        plt.show()
