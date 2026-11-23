"""
Plain-text facts about a :class:`~timelineviz.model.Timeline`.

A chart shows the shape of the data; a facts block states it exactly, in a form
a person can check and a language model can copy without drifting. Use it to
brief a writer or an image model (see :func:`fill_brief`), or to paste exact
numbers into an incident write-up.

For each lane the facts list every event with its date, weekday and time, the
time since the lane started and since the previous event. Then:

* **entity lanes** (orders, patients, ...) get a comparison: median, fastest and
  slowest elapsed time, the longest single stage, and a table of each stage
  (``Placed → Paid``) shared by two or more lanes;
* **log-level lanes** or a single lane get the largest quiet periods instead.

Durations are rounded to their two most significant units (``1d 23h`` for
1 day 23 hours 27 minutes, ``1d 2h`` for 1 day 1 hour 59 minutes).
"""

from __future__ import annotations

import json
import re
import statistics

import pandas as pd

from timelineviz.model import LEVEL_ORDER, Timeline, default_lane_order

FACTS_FORMATS = ("markdown", "json")
_SINGLE_LANE_NAME = "Events"
_LARGEST_GAPS = 3
_SHORT_LABEL = 30  # longer labels (log messages) are not repeated in "N after X"
_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _seconds(a: pd.Timestamp, b: pd.Timestamp) -> float:
    return (b - a).total_seconds()


_UNITS = ((86400, "d"), (3600, "h"), (60, "m"), (1, "s"))


def _dur(seconds: float) -> str:
    """Duration rounded to its two most significant units: ``1d 2h``, ``4h 27m``, ``37s``.

    Rounding (not truncation) so 1 day 1 hour 59 minutes reads ``1d 2h``.
    """
    total = abs(seconds)
    if total < 0.5:
        return "0s"
    lead = next(i for i, (size, _) in enumerate(_UNITS) if total >= size or size == 1)
    step = _UNITS[min(lead + 1, len(_UNITS) - 1)][0]
    rem = int(total / step + 0.5) * step  # round half up to the second unit
    parts = []
    for size, unit in _UNITS:
        value, rem = divmod(rem, size)
        if value or parts:
            parts.append((value, unit))
    return " ".join(f"{v}{u}" for v, u in parts[:2] if v)


def _lane_name(lane) -> str:
    return _SINGLE_LANE_NAME if lane is None else str(lane)


def _one_line(text) -> str:
    return " ".join(str(text).split())


def _is_log_levels(order) -> bool:
    return all(isinstance(lane, str) and lane.upper() in LEVEL_ORDER for lane in order)


def timeline_facts(
    timeline: Timeline,
    *,
    lane_order=None,
    compare_lanes: bool | None = None,
    title: str | None = None,
) -> dict:
    """Collect exact facts about a timeline as a JSON-serialisable dict.

    Parameters
    ----------
    timeline : Timeline
        Events; ``Event.lane`` groups them (``None`` = one ``Events`` lane).
    lane_order : list, optional
        Lanes in output order. Defaults as for
        :func:`~timelineviz.render_swimlanes`.
    compare_lanes : bool, optional
        Include the lane comparison (median / fastest / slowest / stages).
        Default: on when there are two or more lanes that are not log levels.
        When off, the largest quiet periods across the timeline are listed.
    title : str, optional
        Overrides ``timeline.title``.

    Returns
    -------
    dict
        Times are ISO 8601 strings; every duration has ``seconds`` and ``text``.
    """
    if not timeline.events:
        raise ValueError("timeline has no events")
    order = list(lane_order) if lane_order is not None else default_lane_order(timeline.lanes)
    if compare_lanes is None:
        compare_lanes = len(order) > 1 and not _is_log_levels(order)

    times = timeline.times
    first, last = times[0], times[-1]
    facts = {
        "title": title if title is not None else timeline.title,
        "event_count": len(timeline.events),
        "lane_count": len(order),
        "start": first.isoformat(),
        "end": last.isoformat(),
        "span": {"seconds": _seconds(first, last), "text": _dur(_seconds(first, last))},
        "lanes": [],
    }

    for lane in order:
        evs = [e for e in timeline.events if e.lane == lane]
        if not evs:
            continue
        start = evs[0].time
        events = []
        for i, e in enumerate(evs):
            item = {
                "label": str(e.label),
                "time": e.time.isoformat(),
                "since_start": {
                    "seconds": _seconds(start, e.time),
                    "text": _dur(_seconds(start, e.time)),
                },
            }
            if i:
                gap = _seconds(evs[i - 1].time, e.time)
                item["since_previous"] = {"seconds": gap, "text": _dur(gap)}
            events.append(item)
        elapsed = _seconds(start, evs[-1].time)
        facts["lanes"].append(
            {
                "name": _lane_name(lane),
                "event_count": len(evs),
                "start": start.isoformat(),
                "end": evs[-1].time.isoformat(),
                "elapsed": {"seconds": elapsed, "text": _dur(elapsed)},
                "events": events,
            }
        )

    if compare_lanes:
        comparison = _comparison(facts["lanes"])
        if comparison:
            facts["comparison"] = comparison
    else:
        facts["largest_gaps"] = _largest_gaps(timeline)
    return facts


def _comparison(lanes: list[dict]) -> dict | None:
    """Median / fastest / slowest / stages over lanes with at least two events."""
    timed = [lane for lane in lanes if lane["event_count"] > 1]
    if len(timed) < 2:
        return None

    # min/max keep the first of equal values, so lane order breaks ties.
    fastest = min(timed, key=lambda lane: lane["elapsed"]["seconds"])
    slowest = max(timed, key=lambda lane: lane["elapsed"]["seconds"])
    median = statistics.median(lane["elapsed"]["seconds"] for lane in timed)

    stages: dict[tuple[str, str], list[tuple[str, float]]] = {}
    longest_stage = None
    for lane in timed:
        evs = lane["events"]
        for prev, cur in zip(evs, evs[1:]):
            secs = cur["since_previous"]["seconds"]
            stages.setdefault((prev["label"], cur["label"]), []).append((lane["name"], secs))
            if longest_stage is None or secs > longest_stage["seconds"]:
                longest_stage = {
                    "lane": lane["name"],
                    "from": prev["label"],
                    "to": cur["label"],
                    "seconds": secs,
                    "text": _dur(secs),
                }

    shared = []
    for (frm, to), values in stages.items():
        if len(values) < 2:
            continue
        lo = min(values, key=lambda v: v[1])
        hi = max(values, key=lambda v: v[1])
        med = statistics.median(v[1] for v in values)
        shared.append(
            {
                "from": frm,
                "to": to,
                "lanes": len(values),
                "median": {"seconds": med, "text": _dur(med)},
                "longest": {"lane": hi[0], "seconds": hi[1], "text": _dur(hi[1])},
                "shortest": {"lane": lo[0], "seconds": lo[1], "text": _dur(lo[1])},
            }
        )

    return {
        "lanes_compared": len(timed),
        "median_elapsed": {"seconds": median, "text": _dur(median)},
        "fastest": {"lane": fastest["name"], **fastest["elapsed"]},
        "slowest": {"lane": slowest["name"], **slowest["elapsed"]},
        "longest_stage": longest_stage,
        "stages": shared,
    }


def _largest_gaps(timeline: Timeline) -> list[dict]:
    """The longest stretches with no events, longest first."""
    evs = timeline.events
    gaps = []
    for a, b in zip(evs, evs[1:]):
        secs = _seconds(a.time, b.time)
        if secs > 0:
            gaps.append((secs, a, b))
    gaps.sort(key=lambda g: -g[0])
    return [
        {
            "seconds": secs,
            "text": _dur(secs),
            "after": {
                "label": str(a.label),
                "lane": _lane_name(a.lane),
                "time": a.time.isoformat(),
            },
            "before": {
                "label": str(b.label),
                "lane": _lane_name(b.lane),
                "time": b.time.isoformat(),
            },
        }
        for secs, a, b in gaps[:_LARGEST_GAPS]
    ]


def to_facts(
    timeline: Timeline,
    *,
    format: str = "markdown",
    lane_order=None,
    compare_lanes: bool | None = None,
    title: str | None = None,
) -> str:
    """Render :func:`timeline_facts` as Markdown (default) or JSON text."""
    if format not in FACTS_FORMATS:
        raise ValueError(f"format must be one of {FACTS_FORMATS}, not {format!r}")
    facts = timeline_facts(
        timeline, lane_order=lane_order, compare_lanes=compare_lanes, title=title
    )
    if format == "json":
        return json.dumps(facts, indent=2, ensure_ascii=False) + "\n"
    return _markdown(facts)


def _when(iso: str, seconds: bool) -> str:
    t = pd.Timestamp(iso)
    clock = t.strftime("%H:%M:%S" if seconds else "%H:%M")
    return f"{t:%a} {t.day} {t:%b %Y} {clock}"


def _cell(text: str) -> str:
    return _one_line(text).replace("|", "\\|")


def _markdown(facts: dict) -> str:
    seconds = facts["span"]["seconds"] < 86400  # sub-day timelines need the seconds
    w = lambda iso: _when(iso, seconds)  # noqa: E731
    lanes = facts["lanes"]
    heading = _one_line(facts["title"]) if facts["title"] else "Timeline"
    out = [
        f"# Facts: {heading}",
        "",
        f"- Events: {facts['event_count']} in {facts['lane_count']} "
        + ("lane" if facts["lane_count"] == 1 else "lanes"),
        f"- From {w(facts['start'])} to {w(facts['end'])} ({facts['span']['text']})",
        "- Durations are elapsed time, rounded to the two largest units "
        "(1d 23h is 1 day 23 hours to the nearest hour).",
        "",
    ]

    for lane in lanes:
        out.append(f"## {_one_line(lane['name'])}")
        out.append("")
        if lane["event_count"] > 1:
            out.append(
                f"Elapsed {lane['elapsed']['text']}, {w(lane['start'])} to {w(lane['end'])}."
            )
            out.append("")
        prev = None
        for e in lane["events"]:
            label = _one_line(e["label"])
            if prev is None:
                start_note = " (start)" if lane["event_count"] > 1 else ""
                out.append(f"- {label}: {w(e['time'])}{start_note}")
            else:
                out.append(
                    f"- {label}: {w(e['time'])}, +{e['since_start']['text']} "
                    f"({e['since_previous']['text']} after {prev})"
                )
            prev = label if len(label) <= _SHORT_LABEL else "previous"
        out.append("")

    comparison = facts.get("comparison")
    if comparison:
        c = comparison
        out += [
            f"## Comparison of {c['lanes_compared']} lanes",
            "",
            f"- Median elapsed: {c['median_elapsed']['text']}",
            f"- Fastest: {_one_line(c['fastest']['lane'])}, {c['fastest']['text']}",
            f"- Slowest: {_one_line(c['slowest']['lane'])}, {c['slowest']['text']}",
        ]
        ls = c["longest_stage"]
        out.append(
            f"- Longest single stage: {_one_line(ls['lane'])}, "
            f"{_one_line(ls['from'])} → {_one_line(ls['to'])}, {ls['text']}"
        )
        out.append("")
        if c["stages"]:
            out += [
                "| Stage | Lanes | Median | Longest | Shortest |",
                "|---|---|---|---|---|",
            ]
            for s in c["stages"]:
                out.append(
                    f"| {_cell(s['from'])} → {_cell(s['to'])} | {s['lanes']} "
                    f"| {s['median']['text']} "
                    f"| {_cell(s['longest']['lane'])}, {s['longest']['text']} "
                    f"| {_cell(s['shortest']['lane'])}, {s['shortest']['text']} |"
                )
            out.append("")

    gaps = facts.get("largest_gaps")
    if gaps:
        out += ["## Largest gaps", ""]
        for g in gaps:
            a, b = g["after"], g["before"]
            out.append(
                f"- {g['text']}: after {_one_line(a['label'])} ({_one_line(a['lane'])}, "
                f"{w(a['time'])}) until {_one_line(b['label'])} ({_one_line(b['lane'])}, "
                f"{w(b['time'])})"
            )
        out.append("")

    return "\n".join(out).rstrip("\n") + "\n"


def fill_brief(template: str, facts: str, *, title: str | None = None) -> str:
    """Fill a brief template with a facts block.

    ``{{facts}}`` is replaced by ``facts`` (typically :func:`to_facts` output)
    and ``{{title}}`` by ``title``. Any other ``{{name}}`` is an error, so a
    typo is never sent to a model verbatim.
    """
    values = {"facts": facts.rstrip("\n"), "title": title or ""}
    names = {m.group(1) for m in _PLACEHOLDER_RE.finditer(template)}
    if "facts" not in names:
        raise ValueError("brief template has no {{facts}} placeholder")
    unknown = sorted(names - values.keys())
    if unknown:
        raise ValueError(f"unknown placeholder(s) in brief template: {', '.join(unknown)}")
    return _PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], template)
