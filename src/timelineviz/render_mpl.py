"""
Matplotlib renderer for :class:`~timelineviz.model.Timeline` objects.

Draws what :func:`timelineviz.layout.compute_layout` decided. Output format
follows the file extension (``.png``, ``.svg``, ``.pdf``, …).
"""

from __future__ import annotations

from functools import lru_cache

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

from timelineviz.layout import (
    LABEL_FONTSIZE,
    TICK_BAND_IN,
    TITLE_BAND_IN,
    compute_layout,
    format_gap,
)
from timelineviz.model import Timeline
from timelineviz.utils import resolve_color_scheme, show_or_close

DEFAULT_FIG_WIDTH_IN = 15.0
AXIS_TEXT_COLOR = "#555555"
AXIS_LINE_COLOR = "#bbbbbb"


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
        Events to draw (must be non-empty).
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
    dates = mdates.date2num(timeline.times)
    texts = [f"{_escape_mathtext(e.label)}\n{format_timestamp(e.time)}" for e in timeline.events]

    fig_w, fig_h_fixed = _parse_figsize(figsize)
    layout = compute_layout(
        dates,
        texts,
        threshold_days=threshold_days,
        measure=measure_text_pt,
        fig_width_in=fig_w,
        varying_height=varying_height,
    )
    fig_h = fig_h_fixed if fig_h_fixed is not None else layout.fig_height_in
    axes_h = max(fig_h - TITLE_BAND_IN - TICK_BAND_IN, 0.5)

    fig = plt.figure(figsize=(fig_w, fig_h))
    axs = []
    labels_by_index = {p.index: p for p in layout.labels}
    bottom = TICK_BAND_IN / fig_h
    height = axes_h / fig_h

    for panel in layout.panels:
        ax = fig.add_axes([panel.left_in / fig_w, bottom, panel.width_in / fig_w, height])
        axs.append(ax)
        ax.set_xlim(panel.x_lo, panel.x_hi)
        ax.set_ylim(-layout.below_pt, layout.above_pt)

        ax.axhline(0, color=cs["line"], linewidth=2.0, zorder=1)
        for i in panel.indices:
            p = labels_by_index[i]
            near, far = p.y, p.y + p.side * p.height_pt
            ax.plot([p.x, p.x], [0, near], "-", color=cs["connector"], lw=1.2, alpha=0.8, zorder=2)
            ax.text(
                p.box_center,
                (near + far) / 2,
                texts[i],
                ha="center",
                va="center",
                fontsize=LABEL_FONTSIZE,
                linespacing=1.2,
                zorder=4,
                bbox=dict(boxstyle="round,pad=0.5", fc=cs["label_bg"], ec=cs["label_edge"], lw=1.0),
            )
        panel_dates = [dates[i] for i in panel.indices]
        ax.plot(
            panel_dates,
            [0] * len(panel_dates),
            "o",
            color=cs["point_edge"],
            markersize=point_size,
            markerfacecolor=cs["point_face"],
            markeredgewidth=1.5,
            zorder=5,
        )

        locator = mdates.AutoDateLocator(minticks=2, maxticks=panel.max_ticks)
        ax.xaxis.set_major_locator(locator)
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

    _draw_breaks(fig, axs, layout, cs)

    heading = title if title is not None else timeline.title
    if heading:
        fig.text(
            0.3 / fig_w,
            1 - 0.12 / fig_h,
            heading,
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


def _draw_breaks(fig, axs, layout, cs):
    """Slash marks between panels at the timeline's height, labelled with the gap."""
    if len(axs) < 2:
        return
    fig_w, fig_h = fig.get_size_inches()
    # y of the timeline (data y = 0) in figure coordinates
    y_line = axs[0].transData.transform((0, 0))[1]
    y_fig = fig.transFigure.inverted().transform((0, y_line))[1]
    slash_h = 0.22 / fig_h
    slash_w = 0.07 / fig_w
    for left_ax, right_ax, gap_days in zip(axs, axs[1:], layout.gaps):
        x_mid = (left_ax.get_position().x1 + right_ax.get_position().x0) / 2
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
            y_fig - slash_h / 2 - 0.06 / fig_h,
            f"+{format_gap(gap_days)}",
            ha="center",
            va="top",
            fontsize=8,
            color=AXIS_TEXT_COLOR,
        )
