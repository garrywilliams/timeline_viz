"""
Mermaid output for :class:`~timelineviz.model.Timeline` objects.

Mermaid diagrams are plain text that GitHub, GitLab, Notion, Obsidian and many
docs tools render natively, so a timeline can live in a README, PR or incident
write-up without an image. Two styles:

* ``"sequence"`` - a ``sequenceDiagram`` with one participant per lane and a
  note per event in time order. Shows *ordering* and hand-offs between lanes;
  long gaps become an explicit "+3d 2h later" note. Works with ``align="start"``.
* ``"gantt"`` - a ``gantt`` chart with one section per lane and a milestone per
  event on a real (proportional) time axis. Needs ``align="absolute"``.
"""

from __future__ import annotations

import re

import matplotlib.dates as mdates

from timelineviz.layout import format_gap, format_offset
from timelineviz.model import Timeline, default_lane_order

MERMAID_STYLES = ("sequence", "gantt")
_SINGLE_LANE_NAME = "Events"


_SEQ_ESCAPES = {"#": "#35;", ";": "#59;", "<": "#lt;", ">": "#gt;", "\n": " "}
_SEQ_ESCAPE_RE = re.compile("[#;<>\n]")


def _seq_text(text: str) -> str:
    """Escape text for sequenceDiagram notes / participant aliases (entity codes).

    One pass, so the ``;`` inside an inserted ``#35;`` is never escaped again.
    """
    return _SEQ_ESCAPE_RE.sub(lambda m: _SEQ_ESCAPES[m.group()], str(text))


def _gantt_text(text: str) -> str:
    """Make text safe as a gantt task / section name.

    ``:`` separates a task's name from its metadata, so it is swapped for the
    look-alike ``꞉`` (U+A789); ``;`` and ``#`` would end or break the line.
    """
    return (
        str(text).replace(":", "꞉").replace(";", ",").replace("#", "♯").replace("\n", " ").strip()
    ) or "-"


def _time_text(times, t) -> str:
    """Clock time only when every event is on one day, else date and time."""
    same_day = len({x.date() for x in times}) == 1
    return t.strftime("%H:%M:%S") if same_day else t.strftime("%Y-%m-%d %H:%M:%S")


def to_mermaid(
    timeline: Timeline,
    *,
    style: str = "sequence",
    align: str = "absolute",
    lane_order=None,
    threshold_days: float | None = None,
    title: str | None = None,
) -> str:
    """Render a timeline as Mermaid source.

    Parameters
    ----------
    timeline : Timeline
        Events; ``Event.lane`` picks the participant / section. Events with no
        lane go in a single ``Events`` lane.
    style : {'sequence', 'gantt'}
        See the module docstring.
    align : {'absolute', 'start'}
        ``'start'`` orders and labels events by time since their lane's first
        event (``sequence`` only).
    lane_order : list, optional
        Lanes in display order (left→right for ``sequence``, top→bottom for
        ``gantt``). Defaults as for :func:`~timelineviz.render_swimlanes`.
    threshold_days : float, optional
        ``sequence`` only: insert a "+gap later" note spanning all lanes where
        consecutive events are further apart than this.
    title : str, optional
        Overrides ``timeline.title``.

    Returns
    -------
    str
        Mermaid source, without a surrounding ```` ```mermaid ```` fence.
    """
    if style not in MERMAID_STYLES:
        raise ValueError(f"style must be one of {MERMAID_STYLES}, not {style!r}")
    if align not in ("absolute", "start"):
        raise ValueError(f"align must be 'absolute' or 'start', not {align!r}")
    if not timeline.events:
        raise ValueError("timeline has no events")
    heading = title if title is not None else timeline.title
    order = list(lane_order) if lane_order is not None else default_lane_order(timeline.lanes)

    if style == "gantt":
        if align != "absolute":
            raise ValueError(
                "Mermaid gantt charts need absolute times; use style='sequence' with align='start'"
            )
        return _gantt(timeline, order, heading)
    return _sequence(timeline, order, heading, align, threshold_days)


def _sequence(timeline, order, heading, align, threshold_days):
    alias = {lane: f"L{i}" for i, lane in enumerate(order)}
    lines = ["sequenceDiagram"]
    if heading:
        lines.append(f"    title {_seq_text(heading)}")
    for lane in order:
        name = _SINGLE_LANE_NAME if lane is None else lane
        lines.append(f"    participant {alias[lane]} as {_seq_text(name)}")

    nums = list(mdates.date2num(timeline.times))
    if align == "start":
        start = {}
        for lane, x in zip(timeline.lanes, nums):
            start[lane] = min(start.get(lane, x), x)
        keyed = [(x - start[e.lane], i) for i, (e, x) in enumerate(zip(timeline.events, nums))]
    else:
        keyed = [(x, i) for i, x in enumerate(nums)]
    keyed.sort()

    span = f"{alias[order[0]]},{alias[order[-1]]}" if len(order) > 1 else alias[order[0]]
    prev = None
    for x, i in keyed:
        e = timeline.events[i]
        if prev is not None and threshold_days is not None and x - prev > threshold_days:
            gap = format_offset(x - prev) if align == "start" else format_gap(x - prev)
            lines.append(f"    Note over {span}: +{gap} later")
        when = f"+{format_offset(x)}" if align == "start" else _time_text(timeline.times, e.time)
        lines.append(f"    Note over {alias[e.lane]}: {_seq_text(when)}<br/>{_seq_text(e.label)}")
        prev = x
    return "\n".join(lines) + "\n"


def _gantt(timeline, order, heading):
    times = timeline.times
    span_days = (max(times) - min(times)).total_seconds() / 86400
    if span_days <= 1:
        axis = "%H:%M"
    elif span_days <= 60:
        axis = "%m-%d %H:%M"
    else:
        axis = "%Y-%m-%d"

    lines = ["gantt"]
    if heading:
        lines.append(f"    title {_gantt_text(heading)}")
    lines += ["    dateFormat YYYY-MM-DD HH:mm:ss.SSS", f"    axisFormat {axis}"]
    for lane in order:
        lines.append(f"    section {_gantt_text(_SINGLE_LANE_NAME if lane is None else lane)}")
        for e in timeline.events:
            if e.lane != lane:
                continue
            stamp = e.time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            lines.append(f"    {_gantt_text(e.label)} : milestone, {stamp}, 0d")
    return "\n".join(lines) + "\n"


def write_mermaid(text: str, output_file: str) -> None:
    """Write Mermaid source; ``.md`` files get a ```` ```mermaid ```` fence."""
    body = f"```mermaid\n{text}```\n" if output_file.endswith(".md") else text
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"Saved Mermaid diagram to {output_file}")
