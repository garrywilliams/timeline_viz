import json

import pandas as pd
import pytest

from timelineviz import Event, Timeline, fill_brief, timeline_facts, to_facts
from timelineviz.facts import _dur
from timelineviz.model import timeline_from_wide_entities

ORDERS = "examples/order_fulfilment.csv"


def T(s):
    return pd.Timestamp(s)


@pytest.mark.parametrize(
    "seconds,text",
    [
        (0, "0s"),
        (0.4, "0s"),
        (37, "37s"),
        (92, "1m 32s"),
        (16020, "4h 27m"),
        (86400 + 3600 + 3561, "1d 2h"),  # rounds up, not truncated to 1d 1h
        (86370, "1d"),  # 23h 59m 30s carries into a whole day
        (59.6, "1m"),
        (7 * 86400, "7d"),
    ],
)
def test_dur_rounds_to_two_units(seconds, text):
    assert _dur(seconds) == text


@pytest.fixture
def orders():
    return timeline_from_wide_entities(ORDERS, id_column="order_id", title="Orders")


def test_entity_facts_match_source(orders):
    f = timeline_facts(orders)
    assert f["event_count"] == 25 and f["lane_count"] == 5
    a1004 = next(lane for lane in f["lanes"] if lane["name"] == "A-1004")
    assert a1004["elapsed"]["text"] == "5d 23h"
    assert [e["label"] for e in a1004["events"]] == [
        "Placed",
        "Paid",
        "Picked",
        "Shipped",
        "Delivered",
    ]
    assert "since_previous" not in a1004["events"][0]
    assert a1004["events"][1]["since_previous"]["text"] == "17h 43m"

    c = f["comparison"]
    assert c["median_elapsed"]["text"] == "1d 16h"
    assert (c["fastest"]["lane"], c["fastest"]["text"]) == ("A-1003", "22h 43m")
    assert (c["slowest"]["lane"], c["slowest"]["text"]) == ("A-1004", "5d 23h")
    assert c["longest_stage"]["from"] == "Shipped" and c["longest_stage"]["to"] == "Delivered"
    stages = {(s["from"], s["to"]): s for s in c["stages"]}
    assert stages[("Picked", "Shipped")]["longest"]["lane"] == "A-1002"
    assert stages[("Placed", "Paid")]["lanes"] == 5
    assert "largest_gaps" not in f


def test_markdown_facts(orders):
    md = to_facts(orders)
    assert md.startswith("# Facts: Orders\n")
    assert "- Paid: Sat 8 Mar 2025 10:02, +17h 43m (17h 43m after Placed)" in md
    assert "Elapsed 1d 2h, Mon 10 Mar 2025 08:05 to Tue 11 Mar 2025 10:05." in md
    assert "| Shipped → Delivered | 5 | 21h 40m | A-1004, 2d 23h | A-1003, 16h 42m |" in md
    assert "- Fastest: A-1003, 22h 43m" in md


def test_json_facts_round_trip(orders):
    data = json.loads(to_facts(orders, format="json"))
    assert data == timeline_facts(orders)


def test_log_levels_get_gaps_not_comparison():
    t = Timeline(
        [
            Event(T("2024-01-01 09:00:00"), "boot", "INFO"),
            Event(T("2024-01-01 09:00:05"), "x | y", "ERROR"),
            Event(T("2024-01-01 11:00:05"), "done", "INFO"),
            Event(T("2024-01-01 11:00:05"), "same time", "INFO"),
        ]
    )
    f = timeline_facts(t)
    assert "comparison" not in f
    assert [lane["name"] for lane in f["lanes"]] == ["ERROR", "INFO"]
    gaps = f["largest_gaps"]
    assert len(gaps) == 2  # the zero-length gap is skipped
    assert gaps[0]["text"] == "2h" and gaps[0]["after"]["lane"] == "ERROR"
    md = to_facts(t)
    assert "09:00:05" in md  # sub-day timelines keep seconds
    assert "## Largest gaps" in md
    assert "- x | y: Mon 1 Jan 2024 09:00:05\n" in md  # single-event lane: no "(start)"


def test_single_lane_and_long_labels():
    long = "a very long log message that keeps going and going"
    t = Timeline(
        [Event(T("2024-01-01"), long), Event(T("2024-01-03"), "next"), Event(T("2024-01-04"), "z")]
    )
    md = to_facts(t)
    assert "# Facts: Timeline" in md
    assert "## Events" in md and "Events: 3 in 1 lane\n" in md
    assert "(2d after previous)" in md
    assert "(1d after next)" in md


def test_comparison_overrides_and_lane_order(orders):
    assert "comparison" not in timeline_facts(orders, compare_lanes=False)
    f = timeline_facts(orders, lane_order=["A-1005", "A-1001"], title="Two")
    assert [lane["name"] for lane in f["lanes"]] == ["A-1005", "A-1001"]
    assert f["title"] == "Two"
    # a lane in lane_order with no events is skipped
    assert len(timeline_facts(orders, lane_order=["A-1001", "nope"])["lanes"]) == 1


def test_comparison_needs_two_timed_lanes():
    t = Timeline(
        [
            Event(T("2024-01-01"), "a", "x"),
            Event(T("2024-01-02"), "b", "x"),
            Event(T("2024-01-03"), "a", "y"),
        ]
    )
    assert "comparison" not in timeline_facts(t, compare_lanes=True)
    md = to_facts(t, compare_lanes=True)
    assert "Comparison" not in md and "Largest gaps" not in md


def test_unshared_stages_are_not_tabled():
    t = Timeline(
        [
            Event(T("2024-01-01"), "a", "x"),
            Event(T("2024-01-02"), "b", "x"),
            Event(T("2024-01-03"), "c", "y"),
            Event(T("2024-01-05"), "d", "y"),
        ]
    )
    c = timeline_facts(t)["comparison"]
    assert c["stages"] == []
    assert "| Stage |" not in to_facts(t)


def test_errors():
    with pytest.raises(ValueError, match="no events"):
        timeline_facts(Timeline([]))
    with pytest.raises(ValueError, match="format"):
        to_facts(Timeline([Event(T("2024-01-01"), "a")]), format="yaml")


def test_fill_brief():
    assert fill_brief("T={{ title }}\n{{facts}}", "F\n", title="X") == "T=X\nF"
    assert fill_brief("{{facts}}", "F") == "F"
    with pytest.raises(ValueError, match="no \\{\\{facts\\}\\}"):
        fill_brief("nothing here", "F")
    with pytest.raises(ValueError, match="unknown placeholder"):
        fill_brief("{{facts}} {{fcats}}", "F")
