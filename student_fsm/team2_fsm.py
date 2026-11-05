"""STUDENT TODO — Team 2: Lite 6 workstation FSM.

Only edit THIS file. The arm is controlled through supplied joint-space
FollowJointTrajectory action calls. No gripper, MoveIt, or recovery required.
"""
from enum import Enum, auto


class State(Enum):
    START = auto()
    WAIT_FOR_R1_DOCK = auto()
    HOME_BEFORE_PICK = auto()
    R1_PICK = auto()
    HOME_AFTER_PICK = auto()
    WAIT_FOR_R2_DOCK = auto()
    R2_PLACE = auto()
    HOME_AFTER_PLACE = auto()
    COMPLETE = auto()


PLAN = ('START -> WAIT_FOR_R1_DOCK -> HOME_BEFORE_PICK -> R1_PICK -> '
        'HOME_AFTER_PICK -> WAIT_FOR_R2_DOCK -> R2_PLACE -> HOME_AFTER_PLACE -> COMPLETE')


class Team2FSM:
    def __init__(self):
        self.state = State.START

    def is_complete(self):
        return self.state == State.COMPLETE

    def step(self, api, signals):
        """One transition per call; False means waiting for another team.

        api.arm_to('HOME'), api.arm_to('R1_PICK'), api.arm_to('R2_PLACE')
        return True on action success; raise an exception on failure.

        Guards:
          WAIT_FOR_R1_DOCK: require signals.r1_at_dock
          WAIT_FOR_R2_DOCK: require signals.r2_at_dock

        Outputs:
          Set signals.pick_complete True ONLY after HOME_AFTER_PICK succeeds.
          Set signals.place_complete True ONLY after HOME_AFTER_PLACE succeeds.

        TODO T2-1: START and waiting states (return False if guard missing).
        TODO T2-2: Execute HOME -> R1_PICK -> HOME, checking each success.
        TODO T2-3: Report pick_complete and wait for Robot 2 to dock.
        TODO T2-4: Execute R2_PLACE -> HOME, checking each success.
        TODO T2-5: Report place_complete and COMPLETE.
        No retry/recovery logic is needed.
        """
        raise NotImplementedError(f'Team 2 step TODO at {self.state.name}')
