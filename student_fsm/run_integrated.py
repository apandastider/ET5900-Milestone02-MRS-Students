#!/usr/bin/env python3
"""Instructor-provided coordinator: orchestrates ALL THREE student FSMs.

Runs all teams in ONE Python process, exchanging shared completion flags.
Each student's step() returns True for a completed transition, or False while
waiting. No recovery/retry logic and no inter-process ROS messaging are needed.
Real physical moves occur only in live mode using the ROS 2 action helper.
"""
import argparse
from pathlib import Path
from signals import SharedSignals
from team1_fsm import Team1FSM, PLAN as PLAN1
from team2_fsm import Team2FSM, PLAN as PLAN2
from team3_fsm import Team3FSM, PLAN as PLAN3
from sim_api import SimRobotAPI

DEMO = (
    'TEAM 2: WAIT_FOR_R1_DOCK (robot1_at_dock=False)',
    'TEAM 3: WAIT_FOR_R1_CLEAR (r1_cleared=False)',
    'TEAM 1: Navigate R1_DOCK -> signal r1_at_dock',
    'TEAM 2: HOME -> R1_PICK -> HOME -> signal pick_complete',
    'TEAM 1: WAIT_FOR_PICK released -> navigate R1_CLEAR -> signal r1_cleared',
    'TEAM 3: WAIT_FOR_R1_CLEAR released -> navigate R2_DOCK -> signal r2_at_dock',
    'TEAM 2: WAIT_FOR_R2_DOCK released -> R2_PLACE -> HOME -> signal place_complete',
    'TEAM 3: WAIT_FOR_PLACE released -> navigate R2_DESTINATION',
    'ALL TEAMS: COMPLETE',
)


def run(api, max_rounds=50):
    """Round-robin cooperative scheduling with actual action result gating."""
    teams = [('TEAM 2', Team2FSM()), ('TEAM 3', Team3FSM()), ('TEAM 1', Team1FSM())]
    signals = SharedSignals()  # all FALSE: NO fake inter-team acknowledgments
    idle_rounds = 0
    for round_number in range(1, max_rounds + 1):
        made_progress = False
        print(f'--- Coordinator round {round_number} ---', flush=True)
        for name, fsm in teams:
            if fsm.is_complete():
                continue
            before = fsm.state
            changed = fsm.step(api, signals)
            if not isinstance(changed, bool):
                raise RuntimeError(f'{name}.step() must return a Boolean')
            if changed:
                if fsm.state == before:
                    raise RuntimeError(f'{name} claimed progress but state remained {before.name}')
                made_progress = True
                print(f'{name}: {before.name} -> {fsm.state.name}', flush=True)
            else:
                if fsm.state != before:
                    raise RuntimeError(f'{name} changed state while reporting WAIT')
                print(f'{name}: WAIT in {fsm.state.name}', flush=True)
        if all(fsm.is_complete() for _, fsm in teams):
            print('CENTRAL COORDINATOR: ALL THREE TEAMS COMPLETE', flush=True)
            return 0
        idle_rounds = 0 if made_progress else idle_rounds + 1
        if idle_rounds >= 3:
            raise RuntimeError('No FSM progressed for 3 rounds; missing coordination signal '
                               'or incomplete student transition (no retry required).')
    raise RuntimeError('Exceeded 50 coordinator rounds; inspect FSM transitions')


def main():
    p = argparse.ArgumentParser(description='Run all three student FSMs with a supplied coordinator')
    p.add_argument('--config', default=str(Path(__file__).resolve().parents[1] /
                                           'config/milestone2_locations_and_poses.yaml'))
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Print expected integration plan only')
    mode.add_argument('--demo', action='store_true', help='Print illustrative WAIT/guard trace, no code/actions')
    mode.add_argument('--simulate', action='store_true', help='Execute completed student FSM logic with fake actions')
    a = p.parse_args()

    if a.dry_run:
        print('Team 1:', PLAN1)
        print('Team 2:', PLAN2)
        print('Team 3:', PLAN3)
        print('DRY-RUN: no student FSM steps or robot actions executed.')
        return 0
    if a.demo:
        from waiting_demo import demo
        demo()
        print('\nILLUSTRATIVE INTEGRATED HANDOFF SEQUENCE:')
        for line in DEMO:
            print('  ' + line)
        print('This demo does not execute the team FSM TODOs or move robots.')
        return 0

    if a.simulate:
        api = SimRobotAPI()
    else:
        # Real mode needs ALL THREE robots, AMCL/Nav2 and Lite6 controller ready.
        from robot_api import RobotAPI
        api = RobotAPI(a.config, node_name='student_integration_coordinator')
    try:
        return run(api)
    except (RuntimeError, TimeoutError, NotImplementedError) as exc:
        print(f'CENTRAL COORDINATOR STOPPED: {exc}', flush=True)
        return 1
    finally:
        if not a.simulate:
            api.close()


if __name__ == '__main__':
    raise SystemExit(main())
