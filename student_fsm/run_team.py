#!/usr/bin/env python3
"""Student single-team runner: dry plan, logic-only simulation, or live ROS action."""
import argparse
from pathlib import Path
from signals import isolated_signals
from sim_api import SimRobotAPI
from team1_fsm import Team1FSM, PLAN as PLAN1
from team2_fsm import Team2FSM, PLAN as PLAN2
from team3_fsm import Team3FSM, PLAN as PLAN3

FSM_CLASSES = {1: Team1FSM, 2: Team2FSM, 3: Team3FSM}
PLANS = {1: PLAN1, 2: PLAN2, 3: PLAN3}


def main():
    p = argparse.ArgumentParser(description='Run a single-team FSM')
    p.add_argument('--team', required=True, type=int, choices=(1, 2, 3))
    p.add_argument('--config', default=str(Path(__file__).resolve().parents[1] /
                                           'config/milestone2_locations_and_poses.yaml'))
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--dry-run', action='store_true', help='Print plan only; no code/actions')
    modes.add_argument('--simulate', action='store_true', help='Run team FSM using mock success; no ROS')
    a = p.parse_args()

    print(f'Team {a.team} PLAN: {PLANS[a.team]}', flush=True)
    if a.dry_run:
        print('DRY-RUN: plan only, no student FSM steps or robot motions.')
        return 0

    if a.simulate:
        api = SimRobotAPI()
    else:
        from robot_api import RobotAPI
        api = RobotAPI(a.config, node_name=f'team{a.team}_student_fsm')
    fsm = FSM_CLASSES[a.team]()
    signals = isolated_signals(a.team)
    try:
        for tick in range(40):
            if fsm.is_complete():
                print(f'Team {a.team}: COMPLETE after {tick} ticks', flush=True)
                return 0
            previous = fsm.state
            progressed = fsm.step(api, signals)
            if not isinstance(progressed, bool):
                raise RuntimeError('step() must return True (progress) or False (waiting)')
            if not progressed:
                raise RuntimeError(f'Team {a.team} unexpectedly waiting at {fsm.state.name} '
                                   'in isolated mode; check team waiting guard')
            if previous == fsm.state:
                raise RuntimeError(f'Team {a.team} returned progress without changing state')
        raise RuntimeError('FSM exceeded 40 transitions; check state logic')
    except (RuntimeError, TimeoutError, NotImplementedError) as exc:
        print(f'Team {a.team} STOPPED: {exc}', flush=True)
        return 1
    finally:
        if not a.simulate:
            api.close()


if __name__ == '__main__':
    raise SystemExit(main())
