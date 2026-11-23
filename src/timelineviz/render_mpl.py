"""
Matplotlib renderer for :class:`~timelineviz.model.Timeline` objects.

Draws what :func:`timelineviz.layout.compute_layout` decided. Two entry points
share one drawing routine:

* :func:`render_timeline` - a single timeline styled by ``color_scheme``.
* :func:`render_swimlanes` - one lane per ``Event.lane`` (log level, service,
  entity, ...), on a shared absolute time axis or aligned to each lane's start.

Output format follows the file extension (``.png``, ``.svg``, ``.pdf``, ...).
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from functools import lru_cache

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.colors import to_hex, to_rgb
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from matplotlib.ticker import FuncFormatter

from timelineviz.layout import (
    LABEL_FONTSIZE,
    MARGIN_X_IN,
    TICK_BAND_IN,
    TITLE_BAND_IN,
    compute_layout,
    format_gap,
    format_offset,
)
from timelineviz.model import Timeline, default_lane_order
from timelineviz.utils import resolve_color_scheme, show_or_close

DEFAULT_FIG_WIDTH_IN = 15.0
AXIS_TEXT_COLOR = "#555555"
AXIS_LINE_COLOR = "#bbbbbb"
TEXT_COLOR = "#0b0b0b"
LANE_BAND_COLOR = "#f4f4f2"
LANE_NAME_FONTSIZE = 10.0
LANE_NAME_MAX_CHARS = 24

# Categorical lane colours, assigned in this fixed order and never cycled
# (validated light-mode categorical palette; CVD-safe on adjacent pairs).
LANE_PALETTE = (
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#6250d6",  # violet
    "#e34948",  # red
)
OVERFLOW_LANE_COLOR = "#8a8985"  # lanes past the eighth: identity comes from the lane name

# Log levels take status colours so severity reads at a glance.
LEVEL_COLORS = {
    "FATAL": "#d03b3b",  # critical
    "CRITICAL": "#d03b3b",
    "ERROR": "#d03b3b",
    "WARN": "#fab219",  # warning
    "WARNING": "#fab219",
    "INFO": "#2a78d6",
    "DEBUG": "#8a8985",  # neutral
    "TRACE": "#8a8985",
}

ALIGN_MODES = ("absolute", "start")


@lru_cache(maxsize=4096)
def measure_text_pt(line: str, fontsize: float = LABEL_FONTSIZE) -> float:
    """Rendered width of one line of text in points (default font, no mathtext)."""
    if not line:
        return 0.0
    path = TextPath((0, 0), line, size=fontsize, prop=FontProperties(size=fontsize))
    return float(path.get_extents().width)


def format_timestamp(dt) -> str:
    """Timestamp for labels, to the millisecond."""
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _escape_mathtext(text: str) -> str:
    """Stop '$' in labels (log messages, prices) being parsed as mathtext."""
    return text.replace("$", r"\$")


def _parse_figsize(figsize):
    """``None`` → auto; ``(w, None)`` → fixed width, auto height; ``(w, h)`` → fixed."""
    if figsize is None:
        return DEFAULT_FIG_WIDTH_IN, None
    width, height = figsize
    return float(width), (None if height is None else float(height))


def _darken(color: str, factor: float = 0.72) -> str:
    h, lightness, s = colorsys.rgb_to_hls(*to_rgb(color))
    return to_hex(colorsys.hls_to_rgb(h, lightness * factor, s))


def default_lane_colors(lane_order) -> dict:
    """Colour per lane: status colours for log levels, else categorical in order."""
    if lane_order and all(
        isinstance(lane, str) and lane.upper() in LEVEL_COLORS for lane in lane_order
    ):
        return {lane: LEVEL_COLORS[lane.upper()] for lane in lane_order}
    return {
        lane: LANE_PALETTE[i] if i < len(LANE_PALETTE) else OVERFLOW_LANE_COLOR
        for i, lane in enumerate(lane_order)
    }


@dataclass
class _LaneStyle:
    point_face: str
    point_edge: str
    line: str
    line_width: float
    line_alpha: float
    connector: str
    label_edge: str


def _lane_name(name) -> str:
    text = "(none)" if name is None else str(name)
    if len(text) > LANE_NAME_MAX_CHARS:
        text = text[: LANE_NAME_MAX_CHARS - 1] + "…"
    return _escape_mathtext(text)


def render_timeline(
    timeline: Timeline,
    *,
    threshold_days: float = 30,
    figsize=None,
    point_size: float = 8,
    date_rotation: float = 0,
    color_scheme=None,
    varying_height: bool = False,
    title: str | None = None,
    output_file: str | None = None,
    dpi: int = 150,
    show_plot: bool = True,
):
    """Draw a timeline and optionally save it.

    Parameters
    ----------
    timeline : Timeline
        Events to draw (must be non-empty). Lanes are ignored; use
        :func:`render_swimlanes` to draw them.
    threshold_days : float
        Gaps longer than this split the timeline into panels with a break mark
        labelled with the time skipped.
    figsize : tuple or None
        ``None`` (default) sizes the figure to its content at 15in wide.
        ``(width, None)`` fixes the width only. ``(width, height)`` fixes both;
        labels keep their size, so a short figure may crowd them.
    point_size, date_rotation, color_scheme, varying_height, dpi, show_plot
        See :func:`timelineviz.plot_timeline`.
    title : str, optional
        Overrides ``timeline.title``.
    output_file : str, optional
        Save path; the extension picks the format.

    Returns
    -------
    fig : matplotlib.figure.Figure
    axs : list of matplotlib.axes.Axes, one per panel
    """
    cs = resolve_color_scheme(color_scheme)
    style = _LaneStyle(
        point_face=cs["point_face"],
        point_edge=cs["point_edge"],
        line=cs["line"],
        line_width=2.0,
        line_alpha=1.0,
        connector=cs["connector"],
        label_edge=cs["label_edge"],
    )
    xs = list(mdates.date2num(timeline.times))
    texts = [f"{_escape_mathtext(e.label)}\n{format_timestamp(e.time)}" for e in timeline.events]
    return _render(
        xs,
        texts,
        lanes=None,
        lane_order=[None],
        lane_styles={None: style},
        show_lane_names=False,
        offset_axis=False,
        cs=cs,
        threshold_days=threshold_days,
        figsize=figsize,
        point_size=point_size,
        date_rotation=date_rotation,
        varying_height=varying_height,
        title=title if title is not None else timeline.title,
        output_file=output_file,
        dpi=dpi,
        show_plot=show_plot,
    )


def lane_offsets_days(timeline: Timeline) -> list[float]:
    """Days since the first event of each event's own lane."""
    nums = mdates.date2num(timeline.times)
    start = {}
    for lane, x in zip(timeline.lanes, nums):
        start[lane] = min(start.get(lane, x), x)
    return [float(x - start[lane]) for lane, x in zip(timeline.lanes, nums)]


def render_swimlanes(
    timeline: Timeline,
    *,
    align: str = "absolute",
    lane_order=None,
    lane_colors=None,
    threshold_days: float = 30,
    figsize=None,
    point_size: float = 8,
    date_rotation: float = 0,
    color_scheme=None,
    varying_height: bool = False,
    title: str | None = None,
    output_file: str | None = None,
    dpi: int = 150,
    show_plot: bool = True,
):
    """Draw one horizontal lane per ``Event.lane``.

    Parameters
    ----------
    timeline : Timeline
        Events with ``lane`` set (e.g. from ``timeline_from_event_log(...,
        lane_column="level")`` or ``timeline_from_wide_entities``).
    align : {'absolute', 'start'}
        ``'absolute'``: all lanes share one clock-time axis (logs, services).
        ``'start'``: each lane is shifted so its first event is at ``0`` and the
        axis shows elapsed time - for comparing entities that happened on
        different dates (patients, orders).
    lane_order : list, optional
        Lanes top to bottom. Defaults to severity order for log levels, else
        first appearance.
    lane_colors : dict, optional
        Lane → colour overrides. Defaults: status colours for log levels,
        otherwise a fixed categorical order (lanes past the eighth are grey;
        the lane name always identifies the lane).
    threshold_days, figsize, point_size, date_rotation, varying_height, title,
    output_file, dpi, show_plot
        As for :func:`render_timeline`. Breaks are shared by all lanes.
    color_scheme : dict, optional
        ``label_bg``, ``slashes`` and ``title`` apply; lane colours replace the
        point / line colours.

    Returns
    -------
    fig, axs
        As for :func:`render_timeline`.
    """
    if align not in ALIGN_MODES:
        raise ValueError(f"align must be one of {ALIGN_MODES}, not {align!r}")
    cs = resolve_color_scheme(color_scheme)
    order = list(lane_order) if lane_order is not None else default_lane_order(timeline.lanes)
    colors = {**default_lane_colors(order), **(lane_colors or {})}
    styles = {
        lane: _LaneStyle(
            point_face=colors[lane],
            point_edge=_darken(colors[lane]),
            line=colors[lane],
            line_width=1.6,
            line_alpha=0.55,
            connector=colors[lane],
            label_edge=colors[lane],
        )
        for lane in order
    }

    if align == "start":
        xs = lane_offsets_days(timeline)
        texts = [
            f"{_escape_mathtext(e.label)}\n+{format_offset(x)}  ·  {e.time:%Y-%m-%d %H:%M:%S}"
            for e, x in zip(timeline.events, xs)
        ]
    else:
        xs = list(mdates.date2num(timeline.times))
        texts = [
            f"{_escape_mathtext(e.label)}\n{format_timestamp(e.time)}" for e in timeline.events
        ]

    return _render(
        xs,
        texts,
        lanes=timeline.lanes,
        lane_order=order,
        lane_styles=styles,
        show_lane_names=True,
        offset_axis=align == "start",
        cs=cs,
        threshold_days=threshold_days,
        figsize=figsize,
        point_size=point_size,
        date_rotation=date_rotation,
        varying_height=varying_height,
        title=title if title is not None else timeline.title,
        output_file=output_file,
        dpi=dpi,
        show_plot=show_plot,
    )


def _offset_tick(x, _pos=None) -> str:
    if x < -1e-9:
        return ""
    if abs(x) < 1e-9:
        return "0"
    return "+" + format_offset(x)


def _render(
    xs,
    texts,
    *,
    lanes,
    lane_order,
    lane_styles,
    show_lane_names,
    offset_axis,
    cs,
    threshold_days,
    figsize,
    point_size,
    date_rotation,
    varying_height,
    title,
    output_file,
    dpi,
    show_plot,
):
    fig_w, fig_h_fixed = _parse_figsize(figsize)
    names = [_lane_name(lane) for lane in lane_order]
    gutter_in = 0.0
    if show_lane_names:
        widest = max(measure_text_pt(n, LANE_NAME_FONTSIZE) for n in names)
        gutter_in = (widest + 22.0) / 72.0  # swatch + padding

    layout = compute_layout(
        xs,
        texts,
        threshold_days=threshold_days,
        measure=measure_text_pt,
        fig_width_in=fig_w,
        varying_height=varying_height,
        lanes=lanes,
        lane_order=lane_order,
        gutter_in=gutter_in,
    )
    fig_h = fig_h_fixed if fig_h_fixed is not None else layout.fig_height_in
    axes_h = max(fig_h - TITLE_BAND_IN - TICK_BAND_IN, 0.5)
    total_pt = layout.total_height_pt

    fig = plt.figure(figsize=(fig_w, fig_h))
    bottom = TICK_BAND_IN / fig_h
    height = axes_h / fig_h
    labels_by_index = {p.index: p for p in layout.labels}
    lane_keys = list(lanes) if lanes is not None else [None] * len(xs)
    axs = []

    for panel in layout.panels:
        ax = fig.add_axes([panel.left_in / fig_w, bottom, panel.width_in / fig_w, height])
        axs.append(ax)
        ax.set_xlim(panel.x_lo, panel.x_hi)
        ax.set_ylim(0, total_pt)

        for k, lane in enumerate(layout.lanes):
            style = lane_styles[lane_order[k]]
            if len(layout.lanes) > 1 and k % 2 == 0:
                lo = lane.baseline_pt - lane.below_pt
                ax.axhspan(lo, lo + lane.height_pt, color=LANE_BAND_COLOR, zorder=0, lw=0)
            ax.axhline(
                lane.baseline_pt,
                color=style.line,
                linewidth=style.line_width,
                alpha=style.line_alpha,
                zorder=1,
            )

        for i in panel.indices:
            p = labels_by_index[i]
            lane = layout.lanes[p.lane]
            style = lane_styles[lane_order[p.lane]]
            base = lane.baseline_pt
            near, far = base + p.y, base + p.y + p.side * p.height_pt
            ax.plot(
                [p.x, p.x], [base, near], "-", color=style.connector, lw=1.2, alpha=0.8, zorder=2
            )
            ax.text(
                p.box_center,
                (near + far) / 2,
                texts[i],
                ha="center",
                va="center",
                fontsize=LABEL_FONTSIZE,
                linespacing=1.2,
                color=TEXT_COLOR,
                zorder=4,
                bbox=dict(boxstyle="round,pad=0.5", fc=cs["label_bg"], ec=style.label_edge, lw=1.0),
            )

        for k, lane in enumerate(layout.lanes):
            members = [i for i in panel.indices if lane_keys[i] == lane_order[k]]
            if not members:
                continue
            style = lane_styles[lane_order[k]]
            ax.plot(
                [xs[i] for i in members],
                [lane.baseline_pt] * len(members),
                "o",
                color=style.point_edge,
                markersize=point_size,
                markerfacecolor=style.point_face,
                markeredgewidth=1.5,
                zorder=5,
            )

        locator = mdates.AutoDateLocator(minticks=2, maxticks=panel.max_ticks)
        ax.xaxis.set_major_locator(locator)
        if offset_axis:
            ax.xaxis.set_major_formatter(FuncFormatter(_offset_tick))
        else:
            ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.tick_params(axis="x", colors=AXIS_TEXT_COLOR, labelsize=8, length=3)
        if date_rotation:
            for lab in ax.get_xticklabels():
                lab.set_rotation(date_rotation)
                lab.set_ha("right")
        ax.xaxis.get_offset_text().set(color=AXIS_TEXT_COLOR, fontsize=8)
        ax.grid(axis="x", color=AXIS_LINE_COLOR, alpha=0.35, lw=0.8, zorder=0)
        ax.set_yticks([])
        for side in ("left", "right", "top"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(AXIS_LINE_COLOR)
        ax.patch.set_alpha(0)

    if show_lane_names:
        for k, lane in enumerate(layout.lanes):
            y_fig = bottom + height * lane.baseline_pt / total_pt
            x_dot = MARGIN_X_IN / fig_w
            fig.add_artist(
                plt.Line2D(
                    [x_dot],
                    [y_fig],
                    marker="o",
                    markersize=7,
                    color=lane_styles[lane_order[k]].point_face,
                    markeredgecolor=lane_styles[lane_order[k]].point_edge,
                    transform=fig.transFigure,
                )
            )
            fig.text(
                x_dot + 0.16 / fig_w,
                y_fig,
                names[k],
                ha="left",
                va="center",
                fontsize=LANE_NAME_FONTSIZE,
                fontweight="bold",
                color=TEXT_COLOR,
            )

    _draw_breaks(fig, axs, layout, cs, offset_axis)

    if title:
        fig.text(
            MARGIN_X_IN / fig_w,
            1 - 0.12 / fig_h,
            title,
            ha="left",
            va="top",
            fontsize=16,
            fontweight="bold",
            color=cs["title"],
        )

    if output_file:
        fig.savefig(output_file, dpi=dpi, bbox_inches="tight", pad_inches=0.15)
        print(f"Saved timeline to {output_file}")

    show_or_close(fig, show_plot)
    return fig, axs


def _draw_breaks(fig, axs, layout, cs, offset_axis=False):
    """Slash marks between panels on every lane line, labelled with the gap."""
    if len(axs) < 2:
        return
    fig_w, fig_h = fig.get_size_inches()
    to_fig = fig.transFigure.inverted()
    slash_h = 0.22 / fig_h
    slash_w = 0.07 / fig_w
    for left_ax, right_ax, gap_days in zip(axs, axs[1:], layout.gaps):
        x_mid = (left_ax.get_position().x1 + right_ax.get_position().x0) / 2
        y_bottom_lane = None
        for lane in layout.lanes:
            y_disp = left_ax.transData.transform((left_ax.get_xlim()[0], lane.baseline_pt))[1]
            y_fig = to_fig.transform((0, y_disp))[1]
            y_bottom_lane = y_fig if y_bottom_lane is None else min(y_bottom_lane, y_fig)
            for dx in (-0.05 / fig_w, 0.05 / fig_w):
                fig.add_artist(
                    plt.Line2D(
                        [x_mid + dx - slash_w / 2, x_mid + dx + slash_w / 2],
                        [y_fig - slash_h / 2, y_fig + slash_h / 2],
                        transform=fig.transFigure,
                        color=cs["slashes"],
                        linewidth=2.5,
                        solid_capstyle="round",
                        zorder=10,
                    )
                )
        fig.text(
            x_mid,
            y_bottom_lane - slash_h / 2 - 0.06 / fig_h,
            f"+{format_offset(gap_days) if offset_axis else format_gap(gap_days)}",
            ha="center",
            va="top",
            fontsize=8,
            color=AXIS_TEXT_COLOR,
        )
