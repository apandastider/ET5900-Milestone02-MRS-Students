#!/usr/bin/env python3
"""Initialize fresh robot AMCL at exactly the pose used by the spawn launcher.

No Gazebo model-pose parsing. NEVER use to reinitialize a moved robot.
"""
import argparse
import math
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--robot', choices=('robot1', 'robot2'), required=True)
    p.add_argument('--x', type=float, required=True)
    p.add_argument('--y', type=float, required=True)
    p.add_argument('--yaw', type=float, required=True)
    a = p.parse_args()
    if not all(math.isfinite(n) for n in (a.x, a.y, a.yaw)):
        p.error('spawn pose must be finite')
    rclpy.init()
    node = Node(f'{a.robot}_student_spawn_pose_initializer')
    if not node.has_parameter('use_sim_time'):
        node.declare_parameter('use_sim_time', True)
    else:
        node.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])

    qos = QoSProfile(depth=1,
                     reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)
    pub = node.create_publisher(PoseWithCovarianceStamped,
                                f'/{a.robot}/initialpose', qos)
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.pose.pose.position.x = a.x
    msg.pose.pose.position.y = a.y
    msg.pose.pose.orientation.z = math.sin(a.yaw / 2.0)
    msg.pose.pose.orientation.w = math.cos(a.yaw / 2.0)
    msg.pose.covariance[0] = 0.25
    msg.pose.covariance[7] = 0.25
    msg.pose.covariance[35] = 0.1
    try:
        deadline = time.monotonic() + 10.0
        while node.get_clock().now().nanoseconds == 0 and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        if node.get_clock().now().nanoseconds == 0:
            raise RuntimeError('No simulated /clock')
        deadline = time.monotonic() + 7.0
        while time.monotonic() < deadline:
            msg.header.stamp = node.get_clock().now().to_msg()
            pub.publish(msg)
            rclpy.spin_once(node, timeout_sec=0.2)
        print(f'INIT: {a.robot} initialpose x={a.x:.3f}, y={a.y:.3f}, yaw={a.yaw:.3f}', flush=True)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
