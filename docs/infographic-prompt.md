# Example brief: executive infographic from a timelineviz chart

`timelineviz` draws the precise, to-scale chart. An image model can't place points on a scale reliably, so this brief doesn't ask it to redraw the chart. Instead it tells the same story with a weekly calendar, where every fact is a day or a printed number, not a position on an axis.

Every number below comes from the facts block for the order data, [`examples/order_fulfilment.facts.md`](../examples/order_fulfilment.facts.md):

```bash
timelineviz examples/order_fulfilment.csv --id-column order_id --entity-name Order \
  --swimlanes --format facts
```

This brief was then written by hand around a calendar concept. To skip that step, fill the generic [`brief-template.md`](brief-template.md) instead, which leaves the concept to the model:

```bash
timelineviz examples/order_fulfilment.csv --id-column order_id --entity-name Order \
  --swimlanes --format facts --brief-template docs/brief-template.md > brief.md
```

Attach `images/swimlanes_orders.png` as context, paste the brief, and check every number in the result against the facts before using it.

## Brief

```text
Attached for context only: a technical timeline of five online orders. Do NOT redraw
it, and do not draw any continuous time axis, scale, gridlines or bars whose length
stands for time.

Create one landscape 16:9 editorial infographic titled
"Order fulfilment: where the time goes".

Concept: a week-planner calendar. Time is shown only by which DAY a thing happened
and by printed durations, never by distance.

Use ONLY these facts. Do not invent numbers, causes, people, logos or brands.
Do not explain WHY anything was slow.

HERO, top two-thirds: "A-1004's week"
A horizontal row of seven paper calendar day cards, Fri 7 Mar to Thu 13 Mar
(Fri, Sat, Sun, Mon, Tue, Wed, Thu). Milestones are stickers placed in their day card,
each with an icon and time:
- Fri 7 Mar: cart icon, "Placed 16:20"
- Sat 8 Mar: card icon, "Paid 10:02"
- Sun 9 Mar: empty
- Mon 10 Mar: box icon, "Picked 09:30" and truck icon, "Shipped 17:05"
- Tue 11 Mar: empty, a small van-on-the-road doodle
- Wed 12 Mar: empty, a small van-on-the-road doodle
- Thu 13 Mar: house icon, "Delivered 15:35"
Between cards, small handwritten-style tags show the waits:
- Placed to paid: "17h 43m"
- Paid to picked: "1d 23h"
- Picked to shipped: "7h 35m"
- Shipped to delivered: "2d 23h"
Use the warm accent (#eb6834) for A-1004's stickers and tags.

COMPARISON, bottom-left: "The other four orders"
Four small ticket stubs, blue accent (#2a78d6), each with the order number, the day
placed, the day delivered and the total, as text:
- A-1001: Mon 3 Mar → Wed 5 Mar, 2d 2h
- A-1002: Tue 4 Mar → Thu 6 Mar, 1d 16h
- A-1003: Thu 6 Mar → Fri 7 Mar, 22h 43m (fastest)
- A-1005: Mon 10 Mar → Tue 11 Mar, 1d 2h
Plus one line under them: "All four were paid within 2 minutes."

STATS, bottom-right: three numbers with small labels:
"5d 23h" A-1004 total; "1d 16h" median of all five; "22h 43m" fastest (A-1003)

Bottom sentence, neutral:
"A-1004 took longest at payment, picking and delivery: 5d 23h against a 1d 16h median."

Style: warm editorial / paper-craft, off-white background (#fcfcfb), near-black text
(#0b0b0b), only the two accents above, subtle paper texture on the cards. Simple line
icons, no clip-art people, no 3D, no gradients, no stock photos. Sans-serif type with
clear hierarchy, every number legible at thumbnail size.

All text must be spelled exactly as given. If something can't be rendered legibly,
leave it out rather than approximate it.

Footer, small: "Illustrative. Synthetic data from timelineviz examples/order_fulfilment.csv".
```
