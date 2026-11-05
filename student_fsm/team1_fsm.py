"""STUDENT TODO — Team 1: Robot 1 transport FSM.

Only edit THIS file. Complete the state transitions in step().
No retries or recovery are required. An unsuccessful action must STOP.

The instructor's central coordinator calls step() repeatedly and may leave
Team 1 waiting at the workstation while Team 2 completes its pick motion.
"""
from enum import Enum, auto


class State(Enum):
    START = auto()
    NAVIGATE_TO_DOCK = auto()
    WAIT_FOR_PICK = auto()
    NAVIGATE_TO_CLEAR = auto()
    COMPLETE = auto()


PLAN = 'START -> NAVIGATE_TO_DOCK -> WAIT_FOR_PICK -> NAVIGATE_TO_CLEAR -> COMPLETE'


class Team1FSM:
    def __init__(self):
        self.state = State.START

    def is_complete(self):
        return self.state == State.COMPLETE

    def step(self, api, signals):
        """Perform ONE state transition; return True if progressed, False if waiting.

        api.navigate('robot1', 'R1_DOCK') returns True on success and raises on failure.
        api.navigate('robot1', 'R1_CLEAR') likewise.

        Signals written only after action SUCCESS:
          signals.r1_at_dock = True
          signals.r1_cleared = True

        WAIT_FOR_PICK guard:
          signals.pick_complete must become True before leaving this state.

        TODO T1-1: START -> NAVIGATE_TO_DOCK.
        TODO T1-2: Call Nav2 at NAVIGATE_TO_DOCK; set r1_at_dock on success.
        TODO T1-3: Implement WAIT_FOR_PICK (return False until pick_complete).
        TODO T1-4: Call Nav2 at NAVIGATE_TO_CLEAR; set r1_cleared on success.
        TODO T1-5: End in COMPLETE and print transitions.
        No recovery logic, no retry loops, no waiting on ROS topics.
        """
        raise NotImplementedError(f'Team 1 step TODO at {self.state.name}')
