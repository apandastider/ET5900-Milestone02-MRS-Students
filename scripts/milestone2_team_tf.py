#!/usr/bin/env python3
"""Single-robot odometry TF fallback for isolated Milestone 2 team labs.

Start only if the native odom -> base TF is not already available.
"""
import argparse
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from tf2_msgs.msg import TFMessage
from geometry_msgs.msg import TransformStamped


class OdomRelay(Node):
    def __init__(self, robot):
        super().__init__(f'{robot}_team_odom_tf_relay')
        self.robot = robot
        self.tf_publisher = self.create_publisher(TFMessage, f'/{robot}/tf', 100)
        self.create_subscription(
            Odometry, f'/{robot}/odom', self.on_odom, qos_profile_sensor_data
        )
        self.get_logger().info(f'Fallback TF relay for {robot} started')

    def on_odom(self, msg):
        if (msg.header.frame_id != f'{self.robot}/odom' or
                msg.child_frame_id != f'{self.robot}/base_link'):
            return
        t = TransformStamped()
        t.header = msg.header
        t.child_frame_id = msg.child_frame_id
        t.transform.translation.x = msg.pose.pose.position.x
        t.transform.translation.y = msg.pose.pose.position.y
        t.transform.translation.z = msg.pose.pose.position.z
        t.transform.rotation = msg.pose.pose.orientation
        self.tf_publisher.publish(TFMessage(transforms=[t]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--robot', required=True, choices=['robot1', 'robot2'])
    args = parser.parse_args()
    rclpy.init()
    node = OdomRelay(args.robot)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
