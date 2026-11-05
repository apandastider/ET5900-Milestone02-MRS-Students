# ET 5900 Milestone 2 — Student FSM assignment

**Goal:** Implement one simple finite-state machine per team. Students only
edit their assigned `student_fsm/teamN_fsm.py` file. The Gazebo world, map,
Nav2/AMCL, Lite 6 trajectory controller, ROS action helper, and integrated
coordinator are provided. No recovery, retries, gripper, or MoveIt required.

| Team | Your state-machine job | Required robot motions |
|---|---|---|
| 1 | Deliver to workstation, **WAIT for Team 2 pickup**, clear station | R1_DOCK → R1_CLEAR |
| 2 | **WAIT for Robot 1**, perform pick motion, **WAIT for Robot 2**, perform place motion | HOME → R1_PICK → HOME → R2_PLACE → HOME |
| 3 | **WAIT until Robot 1 clears**, dock, **WAIT for placement**, deliver | R2_DOCK → R2_DESTINATION |

## Student TODOs

1. Use the provided `State` enumeration and set `self.state` explicitly.
2. In `step(api, signals)`, do **one transition per call**.
3. Use the provided `api.navigate()` or `api.arm_to()` for motions.
4. Advance only after action success. Set shared completion signals **after**
   the relevant motion finishes, not before.
5. A WAIT state returns `False` until the specified shared signal is `True`.
   When a guard becomes true, transition and return `True`.
6. Return `True` whenever the state advances; end in `COMPLETE`.
7. On action failure, **stop and report**. No recovery logic is required.

The action helper raises exceptions on rejected, aborted, or timed-out goals.
Do not catch and convert these to successful FSM transitions.

## How coordination works

The provided `student_fsm/run_integrated.py` repeatedly calls `step()` for all
three teams in a **single Python process**. It maintains one `SharedSignals`
object. A team in WAIT makes no motion and advances only after a completion
flag from another team. The coordinator is supplied; **students do not code it**.

Read [Coordination explanation](FSM_CENTRAL_COORDINATION.md).

## Test commands (run inside the course package directory)

```bash
# No robots, prints plan and a complete example of the waiting concept
python3 student_fsm/run_integrated.py --demo
python3 student_fsm/run_team.py --team 1 --dry-run

# After completing Team 1 FSM: run logic without ROS
python3 student_fsm/run_team.py --team 1 --simulate

# After starting Team 1-only Gazebo: run actual motion
python3 student_fsm/run_team.py --team 1

# After all three teams have completed: test shared state logic without ROS
python3 student_fsm/run_integrated.py --simulate
```

Use `--team 2` or `--team 3` for other groups. In **isolated** tests only,
external team completion flags are mocked. The integrated run has no mocked
signals and enforces the real logical order.

## Submission

Each team submits its completed `teamN_fsm.py`, a terminal execution log, and a
brief explanation of its states, waiting condition(s), and successful actions.
Students **do not** submit or edit the coordinator or helper API.
