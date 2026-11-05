"""STUDENT TODO — Team 3: Robot 2 receiving / delivery FSM.

Only edit THIS file. WAIT states demonstrate shared-workstation coordination.
No retries or recovery are required.
"""
from enum import Enum, auto


class State(Enum):
    START = auto()
    WAIT_FOR_R1_CLEAR = auto()
    NAVIGATE_TO_DOCK = auto()
    WAIT_FOR_PLACE = auto()
    NAVIGATE_TO_DESTINATION = auto()
    COMPLETE = auto()


PLAN = ('START -> WAIT_FOR_R1_CLEAR -> NAVIGATE_TO_DOCK -> '
        'WAIT_FOR_PLACE -> NAVIGATE_TO_DESTINATION -> COMPLETE')


class Team3FSM:
    def __init__(self):
        self.state = State.START

    def is_complete(self):
        return self.state == State.COMPLETE

    def step(self, api, signals):
        """One state transition; return True on progress, False while waiting.

        api.navigate('robot2', 'R2_DOCK')
        api.navigate('robot2', 'R2_DESTINATION')
        Both return True for success; raise on unsuccessful action.

        Guards:
          WAIT_FOR_R1_CLEAR: require signals.r1_cleared
          WAIT_FOR_PLACE: require signals.place_complete

        Outputs:
          Set signals.r2_at_dock after successful R2_DOCK arrival.

        TODO T3-1: START and WAIT_FOR_R1_CLEAR guard.
        TODO T3-2: Navigate to R2_DOCK and report arrival.
        TODO T3-3: WAIT_FOR_PLACE guard.
        TODO T3-4: Navigate to R2_DESTINATION, check result and COMPLETE.
        No retries, no recovery.
        """
        raise NotImplementedError(f'Team 3 step TODO at {self.state.name}')
