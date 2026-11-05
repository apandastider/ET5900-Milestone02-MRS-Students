#!/usr/bin/env python3
"""ROS 2 Jazzy Lite 6 motion client: MoveIt plan, optional execution.

Targets the existing /lite6/move_group server. No RViz or separate move_group needed.
This is joint-space goal planning, not Cartesian pose control.
"""
import argparse
import math
import sys

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from moveit_msgs.srv import GetMotionPlan
from moveit_msgs.action import ExecuteTrajectory
from moveit_msgs.msg import Constraints, JointConstraint, MoveItErrorCodes

JOINTS = [f'joint{i}' for i in range(1, 7)]
# Small demonstration targets, not validated against workstation collisions.
NAMED = {
    'home': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    'left': [0.2, 0.0, 0.0, 0.0, 0.0, 0.0],
    'right': [-0.2, 0.0, 0.0, 0.0, 0.0, 0.0],
}


def await_future(node, future, timeout=30.0):
    rclpy.spin_until_future_complete(node, future, timeout_sec=timeout)
    if not future.done():
        raise TimeoutError('ROS request timed out')
    if future.exception() is not None:
        raise RuntimeError(str(future.exception()))
    return future.result()


class Lite6Client(Node):
    def __init__(self):
        super().__init__('lite6_student_motion_client')
        self.last_state = None
        self.create_subscription(
            JointState, '/lite6/joint_states', self.on_state, qos_profile_sensor_data
        )
        self.planner = self.create_client(GetMotionPlan, '/lite6/plan_kinematic_path')
        self.execute_client = ActionClient(self, ExecuteTrajectory, '/lite6/execute_trajectory')

    def on_state(self, state):
        self.last_state = state

    def wait_for_state(self):
        import time
        deadline = time.monotonic() + 12.0
        while self.last_state is None or not all(j in self.last_state.name for j in JOINTS):
            if time.monotonic() >= deadline:
                raise RuntimeError('No valid /lite6/joint_states; check joint_state_broadcaster')
            rclpy.spin_once(self, timeout_sec=0.2)
        return self.last_state

    def plan(self, target):
        if not self.planner.wait_for_service(timeout_sec=10.0):
            raise RuntimeError('MoveIt planning service /lite6/plan_kinematic_path unavailable')

        current = self.wait_for_state()
        positions = dict(zip(current.name, current.position))
        print('Current joint angles:', [round(positions[j], 4) for j in JOINTS])
        print('Target joint angles: ', [round(x, 4) for x in target])

        request = GetMotionPlan.Request()
        mp = request.motion_plan_request
        mp.group_name = 'lite6'
        mp.pipeline_id = 'ompl'
        mp.num_planning_attempts = 5
        mp.allowed_planning_time = 8.0
        mp.max_velocity_scaling_factor = 0.15
        mp.max_acceleration_scaling_factor = 0.15
        mp.start_state.joint_state = current
        mp.start_state.is_diff = True
        goal = Constraints()
        for name, angle in zip(JOINTS, target):
            jc = JointConstraint()
            jc.joint_name = name
            jc.position = angle
            jc.tolerance_above = 0.01
            jc.tolerance_below = 0.01
            jc.weight = 1.0
            goal.joint_constraints.append(jc)
        mp.goal_constraints.append(goal)

        response = await_future(self, self.planner.call_async(request), timeout=20.0)
        result = response.motion_plan_response
        if result.error_code.val != MoveItErrorCodes.SUCCESS:
            raise RuntimeError(f'MoveIt planning failed: error code {result.error_code.val}')
        n = len(result.trajectory.joint_trajectory.points)
        if not n:
            raise RuntimeError('MoveIt returned an empty trajectory')
        print(f'Planning succeeded: {n} trajectory points')
        return result.trajectory

    def execute_plan(self, trajectory):
        if not self.execute_client.wait_for_server(timeout_sec=10.0):
            raise RuntimeError('MoveIt execute action /lite6/execute_trajectory unavailable')
        goal = ExecuteTrajectory.Goal()
        goal.trajectory = trajectory
        handle = await_future(self, self.execute_client.send_goal_async(goal), timeout=10.0)
        if handle is None or not handle.accepted:
            raise RuntimeError('MoveIt rejected execution goal')
        print('Executing planned trajectory...')
        completed = await_future(self, handle.get_result_async(), timeout=90.0)
        if completed.result.error_code.val != MoveItErrorCodes.SUCCESS:
            raise RuntimeError(
                f'MoveIt execution failed: code {completed.result.error_code.val}, '
                f'action status {completed.status}'
            )
        print('Execution succeeded')


def main():
    parser = argparse.ArgumentParser(description='MoveIt-planned Lite 6 joint motion')
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--goal', choices=sorted(NAMED))
    selection.add_argument('--joints', nargs=6, type=float, metavar='RAD')
    parser.add_argument('--execute', action='store_true', help='Execute after successful planning (default: plan only)')
    args = parser.parse_args()
    target = NAMED[args.goal] if args.goal else args.joints
    if not all(math.isfinite(x) for x in target):
        parser.error('Joint angles must be finite')
    rclpy.init()
    node = Lite6Client()
    try:
        traj = node.plan(target)
        if args.execute:
            node.execute_plan(traj)
        else:
            print('Plan-only mode: no robot movement. Pass --execute to move in Gazebo.')
    except (RuntimeError, TimeoutError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
