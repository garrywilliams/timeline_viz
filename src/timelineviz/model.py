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


@dataclass(frozen=True)
class Event:
    """A single point in time with a label."""

    time: pd.Timestamp
    label: str


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
    entity_id: str | None = None,
    title: str | None = None,
) -> Timeline:
    """Build a timeline from long-format data: one row per event.

    Rows are filtered on ``filter_column`` (``include_values`` /
    ``exclude_values``), rows with unparseable timestamps are dropped, and the
    rest become events labelled from ``label_column`` (or ``Event 1``, …).

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

    events = [Event(t, lab) for t, lab in zip(working["_event_ts"], labels)]
    return Timeline(events, title=title, entity_id=entity_id)
