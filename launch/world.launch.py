import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():

    this_pkg = get_package_share_directory('mrs_milestone2')
    ros_gz_sim = get_package_share_directory('ros_gz_sim')

    world = os.path.join(
        this_pkg,
        'worlds',
        'milestone2_multi_robot_transfer.sdf'
    )

    gz_launch = PathJoinSubstitution(
        [ros_gz_sim, 'launch', 'gz_sim.launch.py']
    )

    return LaunchDescription([

        # Gazebo resource paths
        SetEnvironmentVariable(
            name='GZ_SIM_RESOURCE_PATH',
            value=':'.join([
                os.path.dirname(
                    get_package_share_directory('turtlebot4_description')
                ),
                os.path.dirname(
                    get_package_share_directory('irobot_create_description')
                ),
                os.environ.get('GZ_SIM_RESOURCE_PATH', '')
            ])
        ),

        # Start the Milestone 2 Gazebo world
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gz_launch),
            launch_arguments={
                'gz_args': f'{world} -r -s -v 4' if not os.environ.get('DISPLAY') else f'{world} -r -v 4'
            }.items(),
        ),

        # Gazebo -> ROS 2 simulation clock bridge
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='milestone2_clock_bridge',
            arguments=[
                '/world/milestone2_multi_robot_transfer/clock'
                '@rosgraph_msgs/msg/Clock[gz.msgs.Clock'
            ],
            remappings=[
                (
                    '/world/milestone2_multi_robot_transfer/clock',
                    '/clock'
                )
            ],
            output='screen'
        ),

    ])