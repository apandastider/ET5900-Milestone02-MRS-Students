#!/usr/bin/env python3
"""Publish one team's AMCL initial pose from the shared FSM YAML."""
import argparse
import math
import time
from pathlib import Path
import yaml
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from geometry_msgs.msg import PoseWithCovarianceStamped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--robot', required=True, choices=['robot1', 'robot2'])
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    name = 'R1_HOME' if args.robot == 'robot1' else 'R2_HOME'
    loc = cfg['navigation_locations'][name]
    yaw = float(loc['yaw'])

    rclpy.init()
    node = Node(f'{args.robot}_team_amcl_initializer')
    # Jazzy may auto-declare use_sim_time. Never declare the same parameter twice.
    if node.has_parameter('use_sim_time'):
        node.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])
    else:
        node.declare_parameter('use_sim_time', True)
    clock_deadline = time.monotonic() + 10.0
    while node.get_clock().now().nanoseconds == 0 and time.monotonic() < clock_deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if node.get_clock().now().nanoseconds == 0:
        node.destroy_node()
        rclpy.shutdown()
        raise RuntimeError('No advancing ROS simulation clock for initial pose')
    pub = node.create_publisher(PoseWithCovarianceStamped,
                                f'/{args.robot}/initialpose', 10)
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.pose.pose.position.x = float(loc['x'])
    msg.pose.pose.position.y = float(loc['y'])
    msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
    msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
    msg.pose.covariance[0] = 0.25
    msg.pose.covariance[7] = 0.25
    msg.pose.covariance[35] = 0.1
    try:
        # ROS discovery + repeated publishing; no dependence on the other robot.
        end = time.monotonic() + 10.0
        while time.monotonic() < end:
            msg.header.stamp = node.get_clock().now().to_msg()
            pub.publish(msg)
            rclpy.spin_once(node, timeout_sec=0.1)
        node.get_logger().info(f'Initialized {args.robot} from {name}: '
                               f'x={loc["x"]}, y={loc["y"]}, yaw={yaw}')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
