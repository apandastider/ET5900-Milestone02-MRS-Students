"""Provided ROS 2 action interface for ET5900 student FSMs.

Students edit ONLY team1_fsm.py, team2_fsm.py or team3_fsm.py.
This module handles ROS 2 action mechanics, not the FSM state transitions.
Execute in a sourced ROS 2 Jazzy shell. Not tested against your robot setup.
"""
from __future__ import annotations

import math
from pathlib import Path
import yaml


def _find_key(obj, key):
    """Find a named goal nested in the instructor-supplied YAML configuration."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = _find_key(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_key(value, key)
            if found is not None:
                return found
    return None


class RobotAPI:
    """Ready-to-use helpers. Calls return True on action success; else raise."""

    def __init__(self, config_path: str, node_name: str = 'student_fsm'):
        import rclpy
        from rclpy.node import Node
        from rclpy.parameter import Parameter

        self._rclpy = rclpy
        if not rclpy.ok():
            rclpy.init()
        self.node = Node(node_name)
        self.node.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.cfg = yaml.safe_load(Path(config_path).read_text(encoding='utf8'))
        if not isinstance(self.cfg, dict):
            raise ValueError('Expected a YAML dictionary in configuration')

    def close(self):
        self.node.destroy_node()
        if self._rclpy.ok():
            self._rclpy.shutdown()

    def _await(self, future, timeout_sec=180.0):
        self._rclpy.spin_until_future_complete(self.node, future, timeout_sec=timeout_sec)
        if not future.done():
            raise TimeoutError(f'ROS action exceeded {timeout_sec}s waiting for response')
        error = future.exception()
        if error:
            raise error
        return future.result()

    def navigate(self, robot: str, location_name: str) -> bool:
        """Send a Nav2 NavigateToPose action and confirm SUCCESS.

        robot must be 'robot1' or 'robot2'.
        """
        from action_msgs.msg import GoalStatus
        from nav2_msgs.action import NavigateToPose
        from rclpy.action import ActionClient

        if robot not in ('robot1', 'robot2'):
            raise ValueError(f'Unsupported robot: {robot}')
        loc = _find_key(self.cfg, location_name)
        if not isinstance(loc, dict):
            raise KeyError(f'Cannot find navigation location {location_name!r}')
        x, y = float(loc['x']), float(loc['y'])
        yaw = float(loc.get('yaw', 0.0))

        client = ActionClient(self.node, NavigateToPose, f'/{robot}/navigate_to_pose')
        if not client.wait_for_server(timeout_sec=20.0):
            raise RuntimeError(f'Nav2 action server for {robot} unavailable')

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.node.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.z = math.sin(yaw / 2)
        goal.pose.pose.orientation.w = math.cos(yaw / 2)

        self.node.get_logger().info(f'{robot} -> {location_name} ({x:.2f},{y:.2f},{yaw:.2f})')
        handle = self._await(client.send_goal_async(goal), timeout_sec=30.0)
        if not handle.accepted:
            raise RuntimeError(f'Nav2 rejected {robot} goal {location_name}')
        outcome = self._await(handle.get_result_async(), timeout_sec=240.0)
        if outcome.status != GoalStatus.STATUS_SUCCEEDED:
            raise RuntimeError(f'{robot} navigation to {location_name} failed: '
                               f'status={outcome.status}, result={outcome.result}')
        return True

    def arm_to(self, pose_name: str) -> bool:
        """Send the configured Lite 6 6-joint pose as FollowJointTrajectory.

        Requires active lite6_traj_controller; predefined joint-space poses only.
        """
        from action_msgs.msg import GoalStatus
        from builtin_interfaces.msg import Duration
        from control_msgs.action import FollowJointTrajectory
        from rclpy.action import ActionClient
        from trajectory_msgs.msg import JointTrajectoryPoint

        arm_cfg = self.cfg.get('lite6', {})
        poses = arm_cfg.get('poses', {})
        if pose_name not in poses:
            raise KeyError(f'Lite 6 pose {pose_name!r} is not in lite6.poses')
        joints = [float(v) for v in poses[pose_name]]
        if len(joints) != 6:
            raise ValueError(f'{pose_name} must contain six joint angles')
        names = arm_cfg.get('joint_names', [f'joint{i}' for i in range(1, 7)])
        duration = float(arm_cfg.get('motion_duration_seconds', 10.0))
        if duration <= 0:
            raise ValueError('Motion duration must be positive')

        possible_actions = (
            '/lite6_traj_controller/follow_joint_trajectory',
            '/lite6/lite6_traj_controller/follow_joint_trajectory',
        )
        client = None
        for action_name in possible_actions:
            candidate = ActionClient(self.node, FollowJointTrajectory, action_name)
            if candidate.wait_for_server(timeout_sec=3.0):
                client = candidate
                break
            candidate.destroy()
        if client is None:
            raise RuntimeError('Lite 6 FollowJointTrajectory server unavailable; '
                               'check `ros2 action list -t`')

        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = list(names)
        pt = JointTrajectoryPoint()
        pt.positions = joints
        seconds = int(duration)
        pt.time_from_start = Duration(sec=seconds, nanosec=int(round((duration-seconds)*1e9)))
        goal.trajectory.points = [pt]
        goal.goal_time_tolerance = Duration(sec=4)
        self.node.get_logger().info(f'Lite 6 -> {pose_name} ({duration:.1f}s)')
        handle = self._await(client.send_goal_async(goal), timeout_sec=30.0)
        if not handle.accepted:
            raise RuntimeError(f'Lite 6 rejected {pose_name}')
        outcome = self._await(handle.get_result_async(), timeout_sec=max(60, duration + 30))
        if outcome.status != GoalStatus.STATUS_SUCCEEDED or outcome.result.error_code != 0:
            raise RuntimeError(f'Lite 6 failed {pose_name}: '
                               f'status={outcome.status}, result={outcome.result}')
        return True
