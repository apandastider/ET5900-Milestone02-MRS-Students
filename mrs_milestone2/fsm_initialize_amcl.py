"""Publish known Gazebo start poses to AMCL. No RViz or mouse clicks needed."""
import argparse
import math
import pathlib
import time
import yaml
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--seconds', type=float, default=8.0)
    parsed = parser.parse_args(args=args)
    with pathlib.Path(parsed.config).open(encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    rclpy.init()
    node = Node('milestone2_amcl_initializer')
    node.set_parameters([
        rclpy.parameter.Parameter(
            'use_sim_time',
            rclpy.Parameter.Type.BOOL,
            True
        )
    ])
    qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.VOLATILE)
    pubs = {r: node.create_publisher(PoseWithCovarianceStamped, f'/{r}/initialpose', qos)
            for r in ('robot1', 'robot2')}
    starts = {'robot1': 'R1_HOME', 'robot2': 'R2_HOME'}
    try:
        until = time.monotonic() + parsed.seconds
        while time.monotonic() < until:
            for robot, key in starts.items():
                loc = cfg['navigation_locations'][key]
                msg = PoseWithCovarianceStamped()
                msg.header.stamp = node.get_clock().now().to_msg()
                msg.header.frame_id = cfg.get('nav_frame', 'map')
                msg.pose.pose.position.x = float(loc['x'])
                msg.pose.pose.position.y = float(loc['y'])
                yaw = float(loc['yaw'])
                msg.pose.pose.orientation.z = math.sin(yaw/2)
                msg.pose.pose.orientation.w = math.cos(yaw/2)
                msg.pose.covariance[0] = 0.04
                msg.pose.covariance[7] = 0.04
                msg.pose.covariance[35] = 0.03
                pubs[robot].publish(msg)
            rclpy.spin_once(node, timeout_sec=1.0)
        node.get_logger().info('Published initial AMCL poses. Verify map -> odom and AMCL active.')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
