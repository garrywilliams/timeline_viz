# Example brief: executive infographic from a timelineviz chart

A worked example of turning a `timelineviz` chart into a stakeholder infographic with a multimodal image model. Attach the chart image and paste the brief below. Check every number in the result against the source data before using it.

## Brief

```text
Attach: images/swimlanes_orders.png

Create a single executive infographic, landscape 16:9, titled
"Order fulfilment: where the time goes". It is a stakeholder summary of the attached
timeline chart, which shows five online orders, one lane each, aligned so every order
starts at 0 at the moment it was placed.

Use ONLY these facts. Do not invent numbers, causes, customer names, logos or brands.

Orders (time measured from the moment each order was placed):
- A-1001, placed Mon 3 Mar 09:12: paid immediately, picked +4h 28m, shipped +7h 52m, delivered +2d 2h
- A-1002, placed Tue 4 Mar 21:47: paid +1m, picked +10h 28m, shipped +18h 42m, delivered +1d 16h
- A-1003, placed Thu 6 Mar 11:03: paid immediately, picked +54m, shipped +6h 1m, delivered +22h 43m (fastest)
- A-1004, placed Fri 7 Mar 16:20: paid +17h 42m, picked +2d 17h, shipped +3d 0h 44m, delivered +5d 23h (slowest)
- A-1005, placed Mon 10 Mar 08:05: paid immediately, picked +1h 6m, shipped +4h 34m, delivered +1d 2h

Headline numbers:
- Median placed-to-delivered: 1d 16h
- Median excluding A-1004: 1d 9h
- Slowest order: A-1004 at 5d 23h, about 3.5x the median

Layout:
1. Left two-thirds: a clean, simplified redraw of the swimlane chart. Five horizontal
   lanes labelled A-1001 to A-1005, a shared elapsed-time axis from 0 to +6d, and a
   small marker for each milestone (Placed, Paid, Picked, Shipped, Delivered). Emphasise
   A-1004 and keep the other four lanes muted. Use a short text annotation beside
   A-1004's gaps, e.g. "Payment +17h 42m" and "Picked +2d 17h". Do not speculate on why.
2. Right third: three stat tiles stacked vertically, showing "1d 16h median delivery",
   "22h 43m fastest (A-1003)" and "5d 23h slowest (A-1004)".
3. Bottom strip: one neutral sentence: "Four of five orders were delivered within about
   two days; A-1004 waited longest for payment and picking."

Style:
- Flat, modern, lots of whitespace, off-white background (#fcfcfb), near-black text
  (#0b0b0b), one accent blue (#2a78d6) for the normal lanes and one warm accent
  (#eb6834) only for A-1004. No gradients, 3D, drop shadows, stock photos or clip-art
  people. Simple line icons are fine (cart, card, box, truck, house) for the five
  milestone types.
- Sans-serif type, clear hierarchy, every number legible at thumbnail size.
- All text must be spelled exactly as given above. If a label can't be rendered
  legibly, leave it out rather than approximate it.

Footer, small: "Illustrative. Synthetic data from timelineviz examples/order_fulfilment.csv".
```
