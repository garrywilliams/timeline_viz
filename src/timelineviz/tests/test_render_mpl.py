import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from timelineviz.model import Event, Timeline
from timelineviz.render_mpl import (
    _escape_mathtext,
    _parse_figsize,
    measure_text_pt,
    render_timeline,
)


def make_timeline(times, labels=None, title="T"):
    labels = labels or [f"Event number {i}" for i in range(len(times))]
    return Timeline([Event(pd.Timestamp(t), lab) for t, lab in zip(times, labels)], title=title)


def draw(fig):
    """Draw on an Agg canvas (show_plot=False closes the figure's own manager)."""
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    return canvas.get_renderer()


def rendered_label_boxes(fig, axs):
    renderer = draw(fig)
    return [t.get_bbox_patch().get_window_extent(renderer) for ax in axs for t in ax.texts]


def test_rendered_label_boxes_do_not_overlap():
    # Dense burst of long labels: the case that overlapped before the layout engine.
    times = pd.date_range("2024-06-01 09:00:00", periods=10, freq="3s")
    labels = [f"service.component{i} something notable happened here" for i in range(10)]
    fig, axs = render_timeline(make_timeline(times, labels), show_plot=False)
    boxes = rendered_label_boxes(fig, axs)
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert not a.overlaps(b), "rendered label boxes overlap"
    plt.close(fig)


def test_rendered_labels_stay_inside_figure():
    times = pd.date_range("2024-06-01", periods=6, freq="1min")
    fig, axs = render_timeline(make_timeline(times), show_plot=False)
    w, h = fig.canvas.get_width_height()
    for box in rendered_label_boxes(fig, axs):
        assert box.x0 >= -1 and box.x1 <= w + 1
        assert box.y0 >= -1 and box.y1 <= h + 1
    plt.close(fig)


def test_breaks_create_panels_with_gap_labels():
    times = ["2024-01-01 10:00", "2024-01-01 11:00", "2024-01-05 09:00"]
    fig, axs = render_timeline(make_timeline(times), threshold_days=1, show_plot=False)
    assert len(axs) == 2
    gap_texts = [t.get_text() for t in fig.texts if t.get_text().startswith("+")]
    assert gap_texts == ["+3d 22h"]
    plt.close(fig)


def test_title_override_and_absent_title():
    fig, _ = render_timeline(make_timeline(["2024-01-01"]), title="Custom", show_plot=False)
    assert [t.get_text() for t in fig.texts] == ["Custom"]
    plt.close(fig)
    fig, _ = render_timeline(make_timeline(["2024-01-01"], title=None), show_plot=False)
    assert fig.texts == []
    plt.close(fig)


@pytest.mark.parametrize("ext", ["png", "svg", "pdf"])
def test_output_format_follows_extension(tmp_path, ext):
    out = tmp_path / f"timeline.{ext}"
    fig, _ = render_timeline(
        make_timeline(["2024-01-01", "2024-01-02"]), output_file=str(out), show_plot=False
    )
    data = out.read_bytes()
    magic = {"png": b"\x89PNG", "svg": b"<?xml", "pdf": b"%PDF"}[ext]
    assert data.startswith(magic)


def test_figsize_modes():
    assert _parse_figsize(None) == (15.0, None)
    assert _parse_figsize((10, None)) == (10.0, None)
    assert _parse_figsize((10, 4)) == (10.0, 4.0)

    t = make_timeline(pd.date_range("2024-01-01", periods=4, freq="1h"))
    fig, _ = render_timeline(t, figsize=(9, None), show_plot=False)
    w, h = fig.get_size_inches()
    assert w == 9 and h > 1
    plt.close(fig)
    fig, _ = render_timeline(t, figsize=(9, 4), show_plot=False)
    assert tuple(fig.get_size_inches()) == (9, 4)
    plt.close(fig)


def test_dollar_signs_render_literally():
    assert _escape_mathtext("cost $5 then $6") == r"cost \$5 then \$6"
    fig, axs = render_timeline(
        make_timeline(["2024-01-01"], ["charged $5 and $6"]), show_plot=False
    )
    draw(fig)  # would raise / render math if '$...$' were parsed as mathtext
    assert axs[0].texts[0].get_text().startswith(r"charged \$5")
    plt.close(fig)


def test_measure_text_pt_scales_with_length():
    assert measure_text_pt("") == 0.0
    assert measure_text_pt("abcdefgh") > measure_text_pt("abcd") > 0


def test_date_rotation_applied():
    fig, axs = render_timeline(
        make_timeline(["2024-01-01 10:00", "2024-01-01 12:00"]),
        date_rotation=30,
        show_plot=False,
    )
    draw(fig)
    assert all(lab.get_rotation() == 30 for lab in axs[0].get_xticklabels())
    plt.close(fig)


# --- swimlanes -------------------------------------------------------------


def lane_timeline(rows, title="Lanes"):
    return Timeline([Event(pd.Timestamp(t), lab, lane) for t, lab, lane in rows], title=title)


LEVEL_ROWS = [
    ("2024-06-01 10:00:00", "boot", "INFO"),
    ("2024-06-01 10:00:05", "slow disk", "WARN"),
    ("2024-06-01 10:00:07", "write failed", "ERROR"),
    ("2024-06-01 10:00:09", "retrying", "INFO"),
]


def test_swimlanes_level_order_names_and_status_colours():
    from matplotlib.colors import to_hex

    from timelineviz.render_mpl import LEVEL_COLORS, render_swimlanes

    fig, axs = render_swimlanes(lane_timeline(LEVEL_ROWS), show_plot=False)
    names = [t.get_text() for t in fig.texts if t.get_text() in {"ERROR", "WARN", "INFO"}]
    assert names == ["ERROR", "WARN", "INFO"]  # most severe on top
    lane_names = {t.get_text(): t.get_position()[1] for t in fig.texts}
    assert lane_names["ERROR"] > lane_names["WARN"] > lane_names["INFO"]
    faces = {to_hex(ln.get_markerfacecolor()) for ln in axs[0].lines if ln.get_marker() == "o"}
    assert faces == {LEVEL_COLORS["ERROR"], LEVEL_COLORS["WARN"], LEVEL_COLORS["INFO"]}
    plt.close(fig)


def test_swimlanes_labels_do_not_overlap_across_lanes():
    from timelineviz.render_mpl import render_swimlanes

    rows = [
        (f"2024-06-01 10:00:{s:02d}", f"something long happened number {s}", lane)
        for s, lane in zip(range(0, 40, 3), ["svc-a", "svc-b", "svc-c"] * 5)
    ]
    fig, axs = render_swimlanes(lane_timeline(rows), show_plot=False)
    boxes = rendered_label_boxes(fig, axs)
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert not a.overlaps(b)
    plt.close(fig)


def test_swimlanes_start_alignment_uses_offsets():
    from timelineviz.render_mpl import lane_offsets_days, render_swimlanes

    rows = [
        ("2024-01-01 09:00", "Placed", "A"),
        ("2024-01-01 10:30", "Shipped", "A"),
        ("2024-03-05 14:00", "Placed", "B"),
        ("2024-03-05 14:45", "Shipped", "B"),
    ]
    t = lane_timeline(rows)
    assert lane_offsets_days(t) == pytest.approx([0, 1.5 / 24, 0, 0.75 / 24])
    fig, axs = render_swimlanes(t, align="start", show_plot=False)
    assert len(axs) == 1  # months apart in absolute time, but aligned there is no gap
    texts = [tx.get_text() for tx in axs[0].texts]
    assert any(tx.startswith("Shipped\n+1h 30m") for tx in texts)
    draw(fig)
    ticks = [lab.get_text() for lab in axs[0].get_xticklabels() if lab.get_text()]
    assert ticks[0] == "0" and all(tk.startswith("+") for tk in ticks[1:])
    plt.close(fig)


def test_swimlanes_breaks_drawn_on_every_lane():
    from timelineviz.render_mpl import render_swimlanes

    rows = [
        ("2024-01-01 10:00", "a", "X"),
        ("2024-01-01 11:00", "b", "Y"),
        ("2024-01-04 10:00", "c", "X"),
    ]
    fig, axs = render_swimlanes(lane_timeline(rows), threshold_days=1, show_plot=False)
    assert len(axs) == 2
    slashes = [a for a in fig.artists if a.get_xdata()[0] != a.get_xdata()[-1]]
    assert len(slashes) == 2 * 2  # two strokes per lane, two lanes
    assert [t.get_text() for t in fig.texts if t.get_text().startswith("+")] == ["+2d 23h"]
    plt.close(fig)


def test_swimlane_colours_categorical_then_grey_and_overrides():
    from timelineviz.render_mpl import (
        LANE_PALETTE,
        OVERFLOW_LANE_COLOR,
        default_lane_colors,
        render_swimlanes,
    )

    lanes = [f"lane{i}" for i in range(10)]
    colors = default_lane_colors(lanes)
    assert [colors[k] for k in lanes[:8]] == list(LANE_PALETTE)
    assert colors["lane8"] == colors["lane9"] == OVERFLOW_LANE_COLOR

    fig, axs = render_swimlanes(
        lane_timeline(LEVEL_ROWS),
        lane_order=["INFO", "WARN", "ERROR"],
        lane_colors={"INFO": "#123456"},
        show_plot=False,
    )
    from matplotlib.colors import to_hex

    faces = [to_hex(ln.get_markerfacecolor()) for ln in axs[0].lines if ln.get_marker() == "o"]
    assert faces[0] == "#123456"  # first lane drawn is INFO, overridden
    plt.close(fig)


def test_swimlanes_validation_and_long_lane_names():
    from timelineviz.render_mpl import _lane_name, render_swimlanes

    with pytest.raises(ValueError, match="align"):
        render_swimlanes(lane_timeline(LEVEL_ROWS), align="sideways", show_plot=False)
    assert _lane_name(None) == "(none)"
    assert _lane_name("x" * 40).endswith("…") and len(_lane_name("x" * 40)) == 24


def test_offset_tick_formatting():
    from timelineviz.render_mpl import _offset_tick

    assert _offset_tick(-0.5) == ""  # padding left of zero shows no tick label
    assert _offset_tick(0) == "0"
    assert _offset_tick(1.5) == "+1d 12h"
