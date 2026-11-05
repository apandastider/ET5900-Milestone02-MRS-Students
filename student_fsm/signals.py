"""Instructor-provided in-process completion signals for the three team FSMs.

No ROS topics are required for the simplified course coordinator: one Python
process executes each team's step() and updates these shared flags. Motion is
still executed via real ROS 2 actions inside RobotAPI when in live mode.
"""
from dataclasses import dataclass


@dataclass
class SharedSignals:
    r1_at_dock: bool = False
    pick_complete: bool = False
    r1_cleared: bool = False
    r2_at_dock: bool = False
    place_complete: bool = False


def isolated_signals(team: int) -> SharedSignals:
    """Assume OTHER teams succeeded in a single-robot simulation.

    This is intentionally only for isolated testing. The integrated coordinator
    starts with every signal FALSE and sets them after actual action success.
    """
    s = SharedSignals()
    if team == 1:
        s.pick_complete = True
    elif team == 2:
        s.r1_at_dock = True
        s.r2_at_dock = True
    elif team == 3:
        s.r1_cleared = True
        s.place_complete = True
    else:
        raise ValueError('team must be 1, 2, or 3')
    return s
