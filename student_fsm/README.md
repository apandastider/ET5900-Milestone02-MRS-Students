# Student FSM source files

- Edit exactly one of `team1_fsm.py`, `team2_fsm.py`, `team3_fsm.py`.
- The provided `State` enums define the intended states. Write the `step(api, signals)` method.
- The provided `robot_api.py` sends ROS 2 Nav2 / FollowJointTrajectory goals and checks success.
- `signals.py` defines the shared Boolean handoff flags. Only the central coordinator shares them across all teams; isolated runs emulate completed external team work.
- `run_team.py` runs one team. `run_integrated.py` schedules all three teams in one process; **read it but do not edit it**.
- `waiting_demo.py` demonstrates the WAIT state without any ROS installation.

Use `--dry-run` for a printed plan, `--simulate` to check your completed FSM logic with fake success, and live mode only after the simulation is ready. No recovery or retries are required; on failure stop.

Use `python3 student_fsm/run_integrated.py --demo` to watch a real toy WAIT guard and the intended robot handoff trace before writing your team code.
