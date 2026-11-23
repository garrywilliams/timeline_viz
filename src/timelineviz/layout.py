"""
Pure layout for event timelines: clusters, panel geometry and label placement.

Nothing here draws. Given event times, label sizes (in points) and a figure
width, :func:`compute_layout` decides where every panel, label box and
connector goes, so the result can be unit-tested and handed to any renderer.

Units
-----
* x positions are matplotlib date numbers (days since the epoch).
* Vertical positions and all sizes are **points** (1/72 inch). The renderer
  sets each panel's y-range so that one y data unit is one point, which keeps
  label boxes, connectors and gaps in one coordinate system.

Label placement
---------------
Labels sit in horizontal *tracks* (levels) above and below the timeline.
Each label is placed greedily in time order at the lowest level where:

1. its box does not overlap another box on the same side and level;
2. its connector does not pass through a lower box on the same side;
3. its box does not cover the connector of a taller label already placed.

A box may be centred on its event or anchored to the left/right of it, and is
kept inside its panel, which lets close events share low tracks instead of
stacking. This replaces the old fixed alternate-up/down placement, which
overlapped whenever neighbouring labels were wide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

# --- Style constants (points unless noted) ---------------------------------

LABEL_FONTSIZE = 9.0
LINE_SPACING = 1.2  # matplotlib's default multi-line spacing
BOX_PAD = 0.5 * LABEL_FONTSIZE  # boxstyle "round,pad=0.5" pads by 0.5 * fontsize
FIRST_LEVEL_GAP = 26.0  # line → first label box (visible connector)
LEVEL_GAP = 8.0  # vertical gap between stacked boxes
BOX_H_GAP = 6.0  # horizontal gap between boxes in one track
VARYING_HEIGHT_CYCLE = 4  # number of stagger levels used by varying_height

# Figure furniture (inches)
MARGIN_X_IN = 0.3
BREAK_GAP_IN = 0.7
TITLE_BAND_IN = 0.55
TICK_BAND_IN = 0.55
MIN_PANEL_IN = 0.8
MAX_TICK_SPACING_IN = 1.1

ABOVE, BELOW = 1, -1


def find_clusters(dates_num, threshold_days=30):
    """
    Split sorted dates into clusters wherever the gap exceeds ``threshold_days``.

    Parameters
    ----------
    dates_num : array-like
        Sorted dates in matplotlib date-number format (days).
    threshold_days : float
        A gap larger than this starts a new cluster.

    Returns
    -------
    clusters : list of arrays
        Dates in each cluster.
    cluster_indices : list of lists
        Indices into ``dates_num`` for each cluster.
    """
    dates_num = np.asarray(dates_num, dtype=float)
    if len(dates_num) == 0:
        return [], []
    if len(dates_num) == 1:
        return [dates_num], [[0]]

    break_indices = np.where(np.diff(dates_num) > threshold_days)[0]
    clusters, cluster_indices = [], []
    start = 0
    for idx in break_indices:
        clusters.append(dates_num[start : idx + 1])
        cluster_indices.append(list(range(start, idx + 1)))
        start = idx + 1
    clusters.append(dates_num[start:])
    cluster_indices.append(list(range(start, len(dates_num))))
    return clusters, cluster_indices


@dataclass
class LabelPlacement:
    """Where one event's label box goes."""

    index: int  # event index (chronological)
    x: float  # event position (date number)
    box_lo: float  # box left edge (date number)
    box_hi: float  # box right edge (date number)
    side: int  # ABOVE (+1) or BELOW (-1)
    level: int  # track number on that side, 0 = nearest the line
    y: float  # signed distance (points) from the line to the box's near edge
    width_pt: float
    height_pt: float
    fallback: bool = False  # placed by the last-resort rule; connector may cross a box

    @property
    def box_center(self) -> float:
        return 0.5 * (self.box_lo + self.box_hi)


@dataclass
class PanelLayout:
    """One continuous time segment (a cluster) drawn as its own panel."""

    indices: list[int]
    x_lo: float
    x_hi: float
    left_in: float  # panel left edge from figure left (inches)
    width_in: float
    max_ticks: int

    @property
    def data_per_pt(self) -> float:
        return (self.x_hi - self.x_lo) / (self.width_in * 72.0)


@dataclass
class TimelineLayout:
    panels: list[PanelLayout]
    labels: list[LabelPlacement]
    above_pt: float  # space needed above the line
    below_pt: float  # space needed below the line
    fig_width_in: float
    fig_height_in: float
    gaps: list[float] = field(default_factory=list)  # days skipped at each break


def label_box_size(text: str, measure: Callable[[str], float]) -> tuple[float, float]:
    """Box (width, height) in points for a label, including padding."""
    lines = text.split("\n")
    width = max(measure(line) for line in lines) + 2 * BOX_PAD
    height = len(lines) * LABEL_FONTSIZE * LINE_SPACING + 2 * BOX_PAD
    return width, height


def _panel_x_range(cluster: np.ndarray) -> tuple[float, float]:
    lo, hi = float(cluster.min()), float(cluster.max())
    span = hi - lo
    if span == 0:
        pad = 1.0 / 24.0  # single instant: show an hour either side
    else:
        pad = span * 0.06
    return lo - pad, hi + pad


def _panel_widths(needs_pt: Sequence[float], available_in: float) -> list[float]:
    """Split ``available_in`` across panels in proportion to label space needed."""
    total = sum(needs_pt) or 1.0
    widths = [max(available_in * n / total, MIN_PANEL_IN) for n in needs_pt]
    scale = available_in / sum(widths)
    return [w * scale for w in widths]


def _box_candidates(x, w, lo, hi, margin):
    """Candidate (box_lo, box_hi) for a box of data-width ``w`` covering ``x``.

    Centred first (most natural), then extending left, then right; each is
    shifted to stay inside ``[lo, hi]`` while still covering ``x``.
    """
    raw = [
        (x - w / 2, x + w / 2),
        (x + margin - w, x + margin),
        (x - margin, x - margin + w),
    ]
    out = []
    for b_lo, b_hi in raw:
        if w <= hi - lo:
            if b_lo < lo:
                b_lo, b_hi = lo, lo + w
            elif b_hi > hi:
                b_lo, b_hi = hi - w, hi
        if b_lo <= x <= b_hi and (b_lo, b_hi) not in out:
            out.append((b_lo, b_hi))
    return out


def _fits(placed, side, level, b_lo, b_hi, x, gap):
    for p in placed:
        if p.side != side:
            continue
        if p.level == level and b_lo < p.box_hi + gap and p.box_lo < b_hi + gap:
            return False  # rule 1: overlapping box in the same track
        if p.level < level and p.box_lo <= x <= p.box_hi:
            return False  # rule 2: our connector would cross a lower box
        if p.level > level and b_lo <= p.x <= b_hi:
            return False  # rule 3: we would cover a taller label's connector
    return True


def pack_labels(
    xs: Sequence[float],
    sizes_pt: Sequence[tuple[float, float]],
    x_lo: float,
    x_hi: float,
    data_per_pt: float,
    *,
    varying_height: bool = False,
    index_offset: int = 0,
) -> list[LabelPlacement]:
    """Place label boxes for one panel. See the module docstring for the rules."""
    placed: list[LabelPlacement] = []
    level_h = max((h for _, h in sizes_pt), default=0.0) + LEVEL_GAP
    gap = BOX_H_GAP * data_per_pt
    margin = 2 * BOX_PAD * data_per_pt
    preferred = ABOVE

    for j, (x, (w_pt, h_pt)) in enumerate(zip(xs, sizes_pt)):
        w = w_pt * data_per_pt
        min_level = (j // 2) % VARYING_HEIGHT_CYCLE if varying_height else 0
        sides = (preferred, -preferred)
        cands = _box_candidates(x, w, x_lo, x_hi, margin)
        max_level = max((p.level for p in placed), default=-1) + 2

        best = None
        for level in range(min_level, max_level + 1):
            for side in sides:
                for b_lo, b_hi in cands:
                    if _fits(placed, side, level, b_lo, b_hi, x, gap):
                        best = (side, level, b_lo, b_hi)
                        break
                if best:
                    break
            if best:
                break

        fallback = best is None
        if fallback:
            # Every connector path is blocked (x is covered by boxes on both
            # sides). Stack above everything on the preferred side; the opaque
            # box hides the crossing rather than overlapping another label.
            side = preferred
            level = max((p.level for p in placed if p.side == side), default=-1) + 1
            level = max(level, min_level)
            best = (side, level, *cands[0])

        side, level, b_lo, b_hi = best
        placed.append(
            LabelPlacement(
                index=index_offset + j,
                x=float(x),
                box_lo=b_lo,
                box_hi=b_hi,
                side=side,
                level=level,
                y=side * (FIRST_LEVEL_GAP + level * level_h),
                width_pt=w_pt,
                height_pt=h_pt,
                fallback=fallback,
            )
        )
        preferred = -side
    return placed


def compute_layout(
    dates_num: Sequence[float],
    label_texts: Sequence[str],
    *,
    threshold_days: float,
    measure: Callable[[str], float],
    fig_width_in: float = 15.0,
    varying_height: bool = False,
) -> TimelineLayout:
    """Lay out a whole timeline: panels, label boxes and figure size.

    Parameters
    ----------
    dates_num : sequence of float
        Sorted event times as matplotlib date numbers.
    label_texts : sequence of str
        Label text per event (may contain newlines).
    threshold_days : float
        Gap that splits the timeline into separate panels.
    measure : callable
        ``measure(line) -> width in points`` for one line of label text.
    fig_width_in : float
        Figure width; the height is derived from the label stacks.
    varying_height : bool
        Stagger labels across several tracks even where they would fit lower.
    """
    dates = np.asarray(dates_num, dtype=float)
    clusters, cluster_indices = find_clusters(dates, threshold_days)
    sizes = [label_box_size(t, measure) for t in label_texts]

    n = len(clusters)
    available = fig_width_in - 2 * MARGIN_X_IN - (n - 1) * BREAK_GAP_IN
    needs = []
    for idx in cluster_indices:
        widths = [sizes[i][0] for i in idx]
        needs.append(max(sum(widths) / 2.0, max(widths)))
    widths_in = _panel_widths(needs, max(available, MIN_PANEL_IN * n))

    panels, labels = [], []
    left = MARGIN_X_IN
    for cluster, idx, w_in in zip(clusters, cluster_indices, widths_in):
        x_lo, x_hi = _panel_x_range(cluster)
        panel = PanelLayout(
            indices=list(idx),
            x_lo=x_lo,
            x_hi=x_hi,
            left_in=left,
            width_in=w_in,
            max_ticks=max(2, int(w_in / MAX_TICK_SPACING_IN)),
        )
        panels.append(panel)
        labels.extend(
            pack_labels(
                [dates[i] for i in idx],
                [sizes[i] for i in idx],
                x_lo,
                x_hi,
                panel.data_per_pt,
                varying_height=varying_height,
                index_offset=idx[0],
            )
        )
        left += w_in + BREAK_GAP_IN

    def extent(side):
        return max(
            (abs(p.y) + p.height_pt for p in labels if p.side == side),
            default=FIRST_LEVEL_GAP,
        )

    above = extent(ABOVE) + 6.0
    below = extent(BELOW) + 6.0
    fig_h = TITLE_BAND_IN + (above + below) / 72.0 + TICK_BAND_IN
    gaps = [float(clusters[i + 1][0] - clusters[i][-1]) for i in range(n - 1)]

    return TimelineLayout(
        panels=panels,
        labels=labels,
        above_pt=above,
        below_pt=below,
        fig_width_in=fig_width_in,
        fig_height_in=fig_h,
        gaps=gaps,
    )


def format_gap(days: float) -> str:
    """Compact duration for a timeline break, e.g. ``'3d 21h'``, ``'45m'``."""
    total_min = int(round(days * 24 * 60))
    d, rem = divmod(total_min, 24 * 60)
    h, m = divmod(rem, 60)
    if d:
        return f"{d}d {h}h" if h else f"{d}d"
    if h:
        return f"{h}h {m}m" if m else f"{h}h"
    return f"{m}m" if m else "<1m"
