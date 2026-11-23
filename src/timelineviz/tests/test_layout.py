import random

import numpy as np
import pytest

from timelineviz.layout import (
    ABOVE,
    BELOW,
    BOX_H_GAP,
    FIRST_LEVEL_GAP,
    MARGIN_X_IN,
    compute_layout,
    find_clusters,
    format_gap,
    label_box_size,
    pack_labels,
)


def fixed_width(line):
    """Deterministic stand-in for font metrics: 5pt per character."""
    return 5.0 * len(line)


def assert_packing_invariants(labels, data_per_pt):
    gap = BOX_H_GAP * data_per_pt
    for a in labels:
        assert a.box_lo <= a.x <= a.box_hi, "box must cover its own event"
        for b in labels:
            if a is b or a.side != b.side:
                continue
            if a.level == b.level:
                overlap = a.box_lo < b.box_hi + gap and b.box_lo < a.box_hi + gap
                assert not overlap, f"boxes {a.index} and {b.index} overlap"
            if b.level < a.level and not a.fallback:
                assert not (b.box_lo <= a.x <= b.box_hi), (
                    f"connector of {a.index} crosses box {b.index}"
                )


# --- find_clusters ---------------------------------------------------------


def test_find_clusters_splits_on_gaps():
    clusters, idx = find_clusters([0.0, 0.5, 10.0, 10.2, 30.0], threshold_days=2)
    assert idx == [[0, 1], [2, 3], [4]]
    assert [list(c) for c in clusters] == [[0.0, 0.5], [10.0, 10.2], [30.0]]


def test_find_clusters_empty_and_single():
    assert find_clusters([], 1) == ([], [])
    clusters, idx = find_clusters([5.0], 1)
    assert idx == [[0]] and list(clusters[0]) == [5.0]


# --- format_gap ------------------------------------------------------------


@pytest.mark.parametrize(
    "days,expected",
    [
        (3 + 21 / 24, "3d 21h"),
        (2.0, "2d"),
        (5 / 24 + 30 / 1440, "5h 30m"),
        (1 / 24, "1h"),
        (45 / 1440, "45m"),
        (10 / 86400, "<1m"),
    ],
)
def test_format_gap(days, expected):
    assert format_gap(days) == expected


# --- label sizing ----------------------------------------------------------


def test_label_box_size_uses_widest_line_and_line_count():
    w1, h1 = label_box_size("abcd\nab", fixed_width)
    w2, h2 = label_box_size("abcd", fixed_width)
    assert w1 == w2 == 20 + 9  # widest line + 2 * BOX_PAD
    assert h1 > h2


# --- pack_labels -----------------------------------------------------------


def test_sparse_labels_alternate_on_first_track():
    xs = [0.0, 10.0, 20.0, 30.0]
    placed = pack_labels(xs, [(50, 30)] * 4, -1, 31, data_per_pt=0.01)
    assert [p.level for p in placed] == [0, 0, 0, 0]
    assert [p.side for p in placed] == [ABOVE, BELOW, ABOVE, BELOW]
    assert all(abs(p.y) == FIRST_LEVEL_GAP for p in placed)


def test_close_labels_never_overlap_and_climb_tracks():
    xs = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    placed = pack_labels(xs, [(200, 30)] * 6, -1, 2, data_per_pt=0.01)
    assert_packing_invariants(placed, 0.01)
    assert max(p.level for p in placed) >= 1


def test_boxes_stay_inside_panel():
    placed = pack_labels([0.0, 9.9], [(300, 30)] * 2, 0.0, 10.0, data_per_pt=0.01)
    for p in placed:
        assert 0.0 <= p.box_lo and p.box_hi <= 10.0


def test_varying_height_staggers_even_when_space_allows():
    xs = [float(i) * 10 for i in range(8)]
    plain = pack_labels(xs, [(50, 30)] * 8, -1, 80, data_per_pt=0.01)
    staggered = pack_labels(xs, [(50, 30)] * 8, -1, 80, data_per_pt=0.01, varying_height=True)
    assert {p.level for p in plain} == {0}
    assert len({p.level for p in staggered}) > 1
    assert_packing_invariants(staggered, 0.01)


@pytest.mark.parametrize("seed", range(40))
def test_random_inputs_respect_invariants(seed):
    rng = random.Random(seed)
    n = rng.randint(2, 25)
    xs = sorted(rng.uniform(0, 100) for _ in range(n))
    sizes = [(rng.uniform(40, 400), rng.choice([30.0, 41.0])) for _ in range(n)]
    dpp = rng.choice([0.02, 0.05, 0.1])
    placed = pack_labels(xs, sizes, -5, 105, data_per_pt=dpp)
    assert len(placed) == n
    assert_packing_invariants(placed, dpp)


# --- compute_layout --------------------------------------------------------


def test_compute_layout_panels_fill_width_and_record_gaps():
    dates = [0.0, 0.01, 5.0, 5.02]
    layout = compute_layout(
        dates, ["a\nx", "b\nx", "c\nx", "d\nx"], threshold_days=1, measure=fixed_width
    )
    assert len(layout.panels) == 2
    assert layout.gaps == pytest.approx([4.99])
    right_edge = layout.panels[-1].left_in + layout.panels[-1].width_in
    assert right_edge == pytest.approx(layout.fig_width_in - MARGIN_X_IN)
    for a, b in zip(layout.panels, layout.panels[1:]):
        assert a.left_in + a.width_in < b.left_in


def test_compute_layout_height_grows_with_label_stacks():
    sparse = compute_layout(
        np.arange(4) * 1.0, ["e\nt"] * 4, threshold_days=10, measure=fixed_width
    )
    crowded = compute_layout(
        np.arange(12) * 0.001, ["x" * 60 + "\nt"] * 12, threshold_days=10, measure=fixed_width
    )
    assert crowded.fig_height_in > sparse.fig_height_in
    assert crowded.above_pt > sparse.above_pt


def test_compute_layout_single_event_has_nonzero_range():
    layout = compute_layout([100.0], ["only\nt"], threshold_days=1, measure=fixed_width)
    (panel,) = layout.panels
    assert panel.x_lo < 100.0 < panel.x_hi
    (label,) = layout.labels
    assert label.side in (ABOVE, BELOW)
