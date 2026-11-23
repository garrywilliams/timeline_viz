import pandas as pd
import pytest

from timelineviz.model import (
    Event,
    Timeline,
    load_dataframe,
    timeline_from_event_log,
    timeline_from_wide,
)


def ts(s):
    return pd.Timestamp(s)


def test_timeline_sorts_events_stably():
    t = Timeline(
        [
            Event(ts("2024-01-02"), "b"),
            Event(ts("2024-01-01"), "a"),
            Event(ts("2024-01-02"), "c"),
        ]
    )
    assert t.labels == ["a", "b", "c"]
    assert t.times == [ts("2024-01-01"), ts("2024-01-02"), ts("2024-01-02")]
    assert len(t) == 3


def test_timeline_from_wide_series_labels_and_utc():
    row = pd.Series(
        {
            "id": 1,
            "created_utc": "2024-01-01T10:00:00+01:00",
            "shipped_at": "2024-01-01 10:30:00",
            "cancelled_at": None,
        }
    )
    t = timeline_from_wide(row, ["created_utc", "shipped_at", "cancelled_at"], entity_id="1")
    assert t.labels == ["Created", "Shipped"]  # 09:00Z then 10:30Z; null skipped
    assert t.times[0] == ts("2024-01-01 09:00:00")
    assert t.entity_id == "1"


def test_timeline_from_wide_label_mappings_and_detection():
    df = pd.DataFrame({"order_id": [7], "created_at": ["2024-01-01"], "note": ["x"]})
    t = timeline_from_wide(df, label_mappings={"created_at": "Order placed"})
    assert t.labels == ["Order placed"]


def test_timeline_from_wide_ignores_missing_columns():
    df = pd.DataFrame({"a_at": ["2024-01-01"]})
    assert timeline_from_wide(df, ["nope"]).events == []


def test_timeline_from_event_log_filters_and_drops_bad_times():
    df = pd.DataFrame(
        {
            "ts": ["2024-01-01 10:02", "not a time", "2024-01-01 10:01", "2024-01-01 10:03"],
            "level": ["ERROR", "ERROR", "WARN", "DEBUG"],
            "msg": ["boom", "bad", "careful", "noise"],
        }
    )
    t = timeline_from_event_log(
        df, "ts", label_column="msg", filter_column="level", exclude_values=["DEBUG"]
    )
    assert t.labels == ["careful", "boom"]


def test_timeline_from_event_log_default_labels_and_empty():
    df = pd.DataFrame({"ts": ["2024-01-01", "2024-01-02"], "level": ["A", "B"]})
    assert timeline_from_event_log(df, "ts").labels == ["Event 1", "Event 2"]
    empty = timeline_from_event_log(df, "ts", filter_column="level", include_values=["Z"])
    assert empty.events == []


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"timestamp_column": "missing"}, "timestamp_column"),
        ({"timestamp_column": "ts", "label_column": "missing"}, "label_column"),
        ({"timestamp_column": "ts", "filter_column": "missing"}, "filter_column"),
        ({"timestamp_column": "ts", "include_values": ["A"]}, "filter_column is required"),
        ({"timestamp_column": "ts", "exclude_values": ["A"]}, "filter_column is required"),
    ],
)
def test_timeline_from_event_log_validation(kwargs, match):
    df = pd.DataFrame({"ts": ["2024-01-01"]})
    with pytest.raises(ValueError, match=match):
        timeline_from_event_log(df, **kwargs)


def test_load_dataframe(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a\n1\n")
    assert list(load_dataframe(str(p)).columns) == ["a"]
    with pytest.raises(ValueError):
        load_dataframe(42)
