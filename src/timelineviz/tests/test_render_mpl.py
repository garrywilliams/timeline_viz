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
