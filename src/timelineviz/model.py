"""
Data model for event timelines, independent of how they are drawn.

Every input mode (wide CSV rows, long-format event logs, raw text logs) is
turned into a :class:`Timeline` of :class:`Event` objects. Renderers only ever
see a ``Timeline``, so adding a new output format never touches parsing, and
adding a new input format never touches rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import pandas as pd

from timelineviz.utils import clean_column_name, detect_timestamp_columns, parse_timestamps

DEFAULT_REMOVE_SUFFIXES = ("_utc", "_at", "_time", "_date")


# Log levels ordered most to least severe; lanes with these names sort this way.
LEVEL_ORDER = ("FATAL", "CRITICAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "TRACE")


@dataclass(frozen=True)
class Event:
    """A single point in time with a label, optionally assigned to a lane."""

    time: pd.Timestamp
    label: str
    lane: str | None = None


@dataclass
class Timeline:
    """Chronologically ordered events plus optional title / entity identity.

    Events are sorted on construction. The sort is stable, so events sharing a
    timestamp keep their input order.
    """

    events: list[Event] = field(default_factory=list)
    title: str | None = None
    entity_id: str | None = None

    def __post_init__(self):
        self.events = sorted(self.events, key=lambda e: e.time)

    def __len__(self) -> int:
        return len(self.events)

    @property
    def times(self) -> list[pd.Timestamp]:
        return [e.time for e in self.events]

    @property
    def labels(self) -> list[str]:
        return [e.label for e in self.events]

    @property
    def lanes(self) -> list[str | None]:
        return [e.lane for e in self.events]

    def lane_order(self) -> list[str | None]:
        """Distinct lanes in display order (see :func:`default_lane_order`)."""
        return default_lane_order(self.lanes)


def default_lane_order(lanes: Iterable[str | None]) -> list[str | None]:
    """Order lanes for display, top to bottom.

    If every lane is a recognised log level, lanes are ordered most severe
    first (FATAL, ERROR, WARN, INFO, DEBUG, TRACE). Otherwise lanes keep the
    order in which they first appear.
    """
    seen = list(dict.fromkeys(lanes))
    if seen and all(isinstance(lane, str) and lane.upper() in LEVEL_ORDER for lane in seen):
        return sorted(seen, key=lambda lane: LEVEL_ORDER.index(lane.upper()))
    return seen


def timeline_from_wide(
    data: pd.DataFrame | pd.Series,
    timestamp_columns: Sequence[str] | None = None,
    *,
    label_mappings: Mapping[str, str] | None = None,
    remove_suffixes: Iterable[str] | None = None,
    entity_id: str | None = None,
    title: str | None = None,
) -> Timeline:
    """Build a timeline from wide-format data: one column per milestone.

    All rows of a DataFrame are treated as one entity; every non-null value in
    each timestamp column becomes an event labelled from the column name.
    Timestamps are normalised to naive UTC.
    """
    if remove_suffixes is None:
        remove_suffixes = DEFAULT_REMOVE_SUFFIXES
    remove_suffixes = list(remove_suffixes)

    if isinstance(data, pd.Series):
        data = pd.DataFrame([data])

    if timestamp_columns is None:
        timestamp_columns = detect_timestamp_columns(data)

    events = []
    for col in timestamp_columns or []:
        if col not in data.columns:
            continue
        present = data.loc[data[col].notna(), [col]]
        if present.empty:
            continue
        if label_mappings and col in label_mappings:
            label = label_mappings[col]
        else:
            label = clean_column_name(col, remove_suffixes)
        for ts in parse_timestamps(present, col, normalize_tz=True):
            events.append(Event(ts, label))

    return Timeline(events, title=title, entity_id=entity_id)


def load_dataframe(data) -> pd.DataFrame:
    """Accept a DataFrame or a CSV path."""
    if isinstance(data, str):
        return pd.read_csv(data)
    if isinstance(data, pd.DataFrame):
        return data
    raise ValueError(f"data must be a DataFrame or path to CSV, not {type(data)}")


def timeline_from_event_log(
    data,
    timestamp_column: str,
    *,
    label_column: str | None = None,
    filter_column: str | None = None,
    include_values: Sequence | None = None,
    exclude_values: Sequence | None = None,
    lane_column: str | None = None,
    entity_id: str | None = None,
    title: str | None = None,
) -> Timeline:
    """Build a timeline from long-format data: one row per event.

    Rows are filtered on ``filter_column`` (``include_values`` /
    ``exclude_values``), rows with unparseable timestamps are dropped, and the
    rest become events labelled from ``label_column`` (or ``Event 1``, …).
    With ``lane_column`` (e.g. ``level`` or ``service``) each event is put in
    the lane named by that column, for :func:`~timelineviz.render_swimlanes`.

    Raises
    ------
    ValueError
        For a missing column or a filter list without ``filter_column``.
    """
    df = load_dataframe(data)

    for name, col in (
        ("timestamp_column", timestamp_column),
        ("label_column", label_column),
        ("filter_column", filter_column),
        ("lane_column", lane_column),
    ):
        if col is not None and col not in df.columns:
            raise ValueError(f"{name} {col!r} not found in columns")

    working = df
    if include_values is not None:
        if filter_column is None:
            raise ValueError("filter_column is required when include_values is set")
        working = working[working[filter_column].isin(include_values)]
    if exclude_values is not None:
        if filter_column is None:
            raise ValueError("filter_column is required when exclude_values is set")
        working = working[~working[filter_column].isin(exclude_values)]

    if working.empty:
        return Timeline([], title=title, entity_id=entity_id)

    ts = parse_timestamps(working, timestamp_column, normalize_tz=True, errors="coerce")
    working = working.assign(_event_ts=ts)
    working = working[working["_event_ts"].notna()].sort_values("_event_ts", kind="stable")

    if label_column is not None:
        labels = working[label_column].astype(str).tolist()
    else:
        labels = [f"Event {i + 1}" for i in range(len(working))]

    if lane_column is not None:
        lanes = [None if pd.isna(v) else str(v) for v in working[lane_column]]
    else:
        lanes = [None] * len(working)

    events = [Event(t, lab, lane) for t, lab, lane in zip(working["_event_ts"], labels, lanes)]
    return Timeline(events, title=title, entity_id=entity_id)


def timeline_from_wide_entities(
    data,
    timestamp_columns: Sequence[str] | None = None,
    id_column: str | None = None,
    *,
    max_entities: int | None = None,
    label_mappings: Mapping[str, str] | None = None,
    remove_suffixes: Iterable[str] | None = None,
    title: str | None = None,
) -> Timeline:
    """Build one timeline with a lane per entity, from wide-format data.

    Each entity (``id_column`` value, or row when ``id_column`` is None) becomes
    a lane holding that entity's milestones, so several entities can be compared
    side by side with :func:`~timelineviz.render_swimlanes` (typically with
    ``align="start"`` so every lane starts at its own first event).
    """
    df = load_dataframe(data)
    if id_column is not None and id_column not in df.columns:
        raise ValueError(f"id_column {id_column!r} not found in columns")
    if timestamp_columns is None:
        timestamp_columns = detect_timestamp_columns(df)

    if id_column is None:
        groups = [(f"row_{i}", df.iloc[[i]]) for i in range(len(df))]
    else:
        groups = [(str(key), df[df[id_column] == key]) for key in df[id_column].dropna().unique()]
    if max_entities:
        groups = groups[:max_entities]

    events = []
    for lane, rows in groups:
        single = timeline_from_wide(
            rows,
            timestamp_columns,
            label_mappings=label_mappings,
            remove_suffixes=remove_suffixes,
        )
        events.extend(Event(e.time, e.label, lane) for e in single.events)
    return Timeline(events, title=title)
