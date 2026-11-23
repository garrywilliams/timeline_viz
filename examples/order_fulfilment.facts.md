# Facts: Order swimlanes

- Events: 25 in 5 lanes
- From Mon 3 Mar 2025 09:12 to Thu 13 Mar 2025 15:35 (10d 6h)
- Durations are elapsed time, rounded to the two largest units (1d 23h is 1 day 23 hours to the nearest hour).

## A-1001

Elapsed 2d 2h, Mon 3 Mar 2025 09:12 to Wed 5 Mar 2025 11:22.

- Placed: Mon 3 Mar 2025 09:12 (start)
- Paid: Mon 3 Mar 2025 09:12, +37s (37s after Placed)
- Picked: Mon 3 Mar 2025 13:40, +4h 28m (4h 27m after Paid)
- Shipped: Mon 3 Mar 2025 17:05, +7h 53m (3h 25m after Picked)
- Delivered: Wed 5 Mar 2025 11:22, +2d 2h (1d 18h after Shipped)

## A-1002

Elapsed 1d 16h, Tue 4 Mar 2025 21:47 to Thu 6 Mar 2025 14:10.

- Placed: Tue 4 Mar 2025 21:47 (start)
- Paid: Tue 4 Mar 2025 21:49, +1m 32s (1m 32s after Placed)
- Picked: Wed 5 Mar 2025 08:15, +10h 28m (10h 27m after Paid)
- Shipped: Wed 5 Mar 2025 16:30, +18h 43m (8h 14m after Picked)
- Delivered: Thu 6 Mar 2025 14:10, +1d 16h (21h 40m after Shipped)

## A-1003

Elapsed 22h 43m, Thu 6 Mar 2025 11:03 to Fri 7 Mar 2025 09:47.

- Placed: Thu 6 Mar 2025 11:03 (start)
- Paid: Thu 6 Mar 2025 11:04, +25s (25s after Placed)
- Picked: Thu 6 Mar 2025 11:58, +54m 36s (54m 11s after Paid)
- Shipped: Thu 6 Mar 2025 17:05, +6h 1m (5h 6m after Picked)
- Delivered: Fri 7 Mar 2025 09:47, +22h 43m (16h 42m after Shipped)

## A-1004

Elapsed 5d 23h, Fri 7 Mar 2025 16:20 to Thu 13 Mar 2025 15:35.

- Placed: Fri 7 Mar 2025 16:20 (start)
- Paid: Sat 8 Mar 2025 10:02, +17h 43m (17h 43m after Placed)
- Picked: Mon 10 Mar 2025 09:30, +2d 17h (1d 23h after Paid)
- Shipped: Mon 10 Mar 2025 17:05, +3d 1h (7h 35m after Picked)
- Delivered: Thu 13 Mar 2025 15:35, +5d 23h (2d 23h after Shipped)

## A-1005

Elapsed 1d 2h, Mon 10 Mar 2025 08:05 to Tue 11 Mar 2025 10:05.

- Placed: Mon 10 Mar 2025 08:05 (start)
- Paid: Mon 10 Mar 2025 08:06, +22s (22s after Placed)
- Picked: Mon 10 Mar 2025 09:12, +1h 7m (1h 6m after Paid)
- Shipped: Mon 10 Mar 2025 12:40, +4h 34m (3h 28m after Picked)
- Delivered: Tue 11 Mar 2025 10:05, +1d 2h (21h 25m after Shipped)

## Comparison of 5 lanes

- Median elapsed: 1d 16h
- Fastest: A-1003, 22h 43m
- Slowest: A-1004, 5d 23h
- Longest single stage: A-1004, Shipped → Delivered, 2d 23h

| Stage | Lanes | Median | Longest | Shortest |
|---|---|---|---|---|
| Placed → Paid | 5 | 37s | A-1004, 17h 43m | A-1005, 22s |
| Paid → Picked | 5 | 4h 27m | A-1004, 1d 23h | A-1003, 54m 11s |
| Picked → Shipped | 5 | 5h 6m | A-1002, 8h 14m | A-1001, 3h 25m |
| Shipped → Delivered | 5 | 21h 40m | A-1004, 2d 23h | A-1003, 16h 42m |
