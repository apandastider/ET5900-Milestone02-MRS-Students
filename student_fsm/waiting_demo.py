"""Tiny runnable WAIT-state demonstration (NOT an implementation of any team FSM)."""
from enum import Enum, auto

class State(Enum):
    WAIT_FOR_PERMISSION = auto()
    PROCEED = auto()
    COMPLETE = auto()

class ExampleFSM:
    def __init__(self):
        self.state = State.WAIT_FOR_PERMISSION

    def step(self, permission):
        if self.state == State.WAIT_FOR_PERMISSION:
            if not permission:
                print('Example FSM: WAIT — permission is False (no movement)', flush=True)
                return False
            self.state = State.PROCEED
            print('Example FSM: permission received -> PROCEED', flush=True)
            return True
        if self.state == State.PROCEED:
            self.state = State.COMPLETE
            print('Example FSM: PROCEED -> COMPLETE', flush=True)
            return True
        return False

def demo():
    print('ACTUAL WAIT-STATE DEMO (no ROS, no robot motion):', flush=True)
    fsm = ExampleFSM()
    assert not fsm.step(permission=False)
    assert not fsm.step(permission=False)
    print('Central coordinator: received a completion signal from another team', flush=True)
    assert fsm.step(permission=True)
    assert fsm.step(permission=True)
    print('Example FSM finished', flush=True)

if __name__ == '__main__':
    demo()
