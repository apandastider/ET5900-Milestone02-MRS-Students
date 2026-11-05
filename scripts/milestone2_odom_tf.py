#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from tf2_msgs.msg import TFMessage

class OdomTFRelay(Node):
    def __init__(self):
        super().__init__('milestone2_odom_tf_relay')

        self.tf_publishers = {}

        for robot in ['robot1', 'robot2']:
            self.tf_publishers[robot] = self.create_publisher(
                TFMessage, f'/{robot}/tf', 100
            )

            self.create_subscription(
                Odometry,
                f'/{robot}/odom',
                lambda msg, r=robot: self.forward(r, msg),
                qos_profile_sensor_data
            )

        self.get_logger().info('Odometry TF relay started for both robots')

    def forward(self, robot, msg):
        if (msg.header.frame_id != f'{robot}/odom' or
                msg.child_frame_id != f'{robot}/base_link'):
            return

        transform = TransformStamped()
        transform.header = msg.header
        transform.child_frame_id = msg.child_frame_id

        transform.transform.translation.x = msg.pose.pose.position.x
        transform.transform.translation.y = msg.pose.pose.position.y
        transform.transform.translation.z = msg.pose.pose.position.z
        transform.transform.rotation = msg.pose.pose.orientation

        self.tf_publishers[robot].publish(
            TFMessage(transforms=[transform])
        )

def main():
    rclpy.init()
    node = OdomTFRelay()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
