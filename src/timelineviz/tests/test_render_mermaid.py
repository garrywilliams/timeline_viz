import pandas as pd
import pytest

from timelineviz.model import Event, Timeline
from timelineviz.render_mermaid import to_mermaid, write_mermaid


def tl(rows, title="T"):
    return Timeline([Event(pd.Timestamp(t), lab, lane) for t, lab, lane in rows], title=title)


ROWS = [
    ("2024-06-01 10:00:00", "boot", "INFO"),
    ("2024-06-01 10:00:05", "slow disk", "WARN"),
    ("2024-06-01 10:00:07", "write failed", "ERROR"),
]


def test_sequence_participants_in_severity_order_and_notes_in_time_order():
    text = to_mermaid(tl(ROWS))
    lines = text.splitlines()
    assert lines[0] == "sequenceDiagram"
    assert lines[1] == "    title T"
    assert lines[2:5] == [
        "    participant L0 as ERROR",
        "    participant L1 as WARN",
        "    participant L2 as INFO",
    ]
    assert lines[5:] == [
        "    Note over L2: 10:00:00<br/>boot",
        "    Note over L1: 10:00:05<br/>slow disk",
        "    Note over L0: 10:00:07<br/>write failed",
    ]


def test_sequence_gap_note_and_full_dates_across_days():
    rows = [("2024-06-01 10:00", "a", "X"), ("2024-06-04 12:00", "b", "Y")]
    text = to_mermaid(tl(rows), threshold_days=1)
    assert "    Note over L0,L1: +3d 2h later" in text
    assert "2024-06-04 12:00:00<br/>b" in text


def test_sequence_start_alignment_orders_by_offset():
    rows = [
        ("2024-01-01 09:00", "Placed", "A"),
        ("2024-01-01 12:00", "Shipped", "A"),
        ("2024-03-01 09:00", "Placed", "B"),
        ("2024-03-01 10:00", "Shipped", "B"),
    ]
    notes = [ln for ln in to_mermaid(tl(rows), align="start").splitlines() if "Note" in ln]
    assert notes == [
        "    Note over L0: +0s<br/>Placed",
        "    Note over L1: +0s<br/>Placed",
        "    Note over L1: +1h<br/>Shipped",
        "    Note over L0: +3h<br/>Shipped",
    ]


def test_sequence_escapes_special_characters_and_single_lane():
    rows = [("2024-01-01 10:00", "a;b #1 <x>", None)]
    text = to_mermaid(tl(rows, title=None))
    assert "title" not in text
    assert "participant L0 as Events" in text
    assert "a#59;b #35;1 #lt;x#gt;" in text


def test_gantt_sections_milestones_and_safe_names():
    rows = ROWS + [("2024-06-01 10:00:09", "retry: attempt #2; ok", "INFO")]
    text = to_mermaid(tl(rows), style="gantt")
    lines = text.splitlines()
    assert lines[:4] == [
        "gantt",
        "    title T",
        "    dateFormat YYYY-MM-DD HH:mm:ss.SSS",
        "    axisFormat %H:%M",
    ]
    assert lines.index("    section ERROR") < lines.index("    section INFO")
    assert "    boot : milestone, 2024-06-01 10:00:00.000, 0d" in lines
    assert "    retry꞉ attempt ♯2, ok : milestone, 2024-06-01 10:00:09.000, 0d" in lines


@pytest.mark.parametrize(
    "rows,axis",
    [
        ([("2024-01-01", "a", None), ("2024-01-20", "b", None)], "%m-%d %H:%M"),
        ([("2024-01-01", "a", None), ("2024-09-01", "b", None)], "%Y-%m-%d"),
    ],
)
def test_gantt_axis_format_follows_span(rows, axis):
    assert f"axisFormat {axis}" in to_mermaid(tl(rows), style="gantt")


def test_validation():
    with pytest.raises(ValueError, match="style"):
        to_mermaid(tl(ROWS), style="pie")
    with pytest.raises(ValueError, match="align"):
        to_mermaid(tl(ROWS), align="middle")
    with pytest.raises(ValueError, match="absolute"):
        to_mermaid(tl(ROWS), style="gantt", align="start")
    with pytest.raises(ValueError, match="no events"):
        to_mermaid(Timeline([]))


def test_write_mermaid_fences_markdown(tmp_path):
    text = to_mermaid(tl(ROWS))
    write_mermaid(text, str(tmp_path / "d.mmd"))
    write_mermaid(text, str(tmp_path / "d.md"))
    assert (tmp_path / "d.mmd").read_text() == text
    assert (tmp_path / "d.md").read_text() == f"```mermaid\n{text}```\n"
