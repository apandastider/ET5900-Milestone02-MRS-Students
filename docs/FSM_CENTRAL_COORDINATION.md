# How the central coordinator connects the three team FSMs

The instructor provides the coordinator: `student_fsm/run_integrated.py`.
Its job is to schedule each team's `step()` method and route completion signals
between the teams. Students **read and explain** this code; they do not write it.

## Why we need WAIT states

This simplified model uses a **single shared workstation**. Robot 2 must not
enter it before Robot 1 has cleared. Robot 1 must not leave until the Lite 6
pick pose is completed. Robot 2 must not depart until placement has finished.

```text
Team 1 (robot1)         Team 2 (Lite 6)        Team 3 (robot2)
START                  WAIT_R1_DOCK           WAIT_R1_CLEAR
  |                          |                     |
Nav2 -> R1_DOCK              |                     |
  | -- r1_at_dock=True ----> |                     |
WAIT_PICK                HOME/PICK/HOME             |
  | <--- pick_complete ----- |                     |
Nav2 -> R1_CLEAR              |                     |
  | ------ r1_cleared ----------------------------> |
COMPLETE                 WAIT_R2_DOCK          Nav2 -> R2_DOCK
                             | <--- r2_at_dock --- |
                          PLACE/HOME           WAIT_PLACE
                             | -- place_complete->|
                             |               Nav2 -> DEST
                          COMPLETE              COMPLETE
```

## Shared completion signals

All flags start `False` when the full coordinator runs.

| Signal | Set by | Unlocks |
|---|---|---|
| `r1_at_dock` | Team 1 after Nav2 success | Team 2 pick sequence |
| `pick_complete` | Team 2 after HOME/PICK/HOME success | Team 1 clearance |
| `r1_cleared` | Team 1 after Nav2 success | Team 3 entering workstation |
| `r2_at_dock` | Team 3 after Nav2 success | Team 2 place sequence |
| `place_complete` | Team 2 after PLACE/HOME success | Team 3 destination |

The coordinator calls each FSM in a round-robin loop. If a `step()` performs an
action successfully, it advances the FSM. If it is WAITING, the `step()` simply
returns `False`; no extra ROS node or interprocess messaging is required.

**These flags are Python data shared inside ONE coordinator process, not ROS 2
topics or services.** This choice keeps the milestone focused on FSM concepts.
ROS actions still control the real robots in live mode.

## Student discussion questions

1. Why does Team 3 have to wait for `r1_cleared` rather than `r1_at_dock`?
2. Why should a signal be set *after* action success and not when the goal is sent?
3. How does the central coordinator know an FSM is waiting rather than failed?
4. What could happen if `pick_complete` were set before the arm returned HOME?
5. How would ROS topics/actions replace the shared Python flags in a distributed system?

## Try it without ROS

```bash
python3 student_fsm/run_integrated.py --demo
```

`--demo` is an illustrative trace that does **not** execute student FSM code.
After all teams implement their FSMs, `--simulate` executes real state
transitions against a **fake success API**, without moving robots:

```bash
python3 student_fsm/run_integrated.py --simulate
```

For a complete real run, start all three robots with the integrated launcher
and execute the coordinator without `--simulate`. The instructor should run
this test first because the integrated startup has not been revalidated from
a clean, headless session.
