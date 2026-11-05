from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    tb4_nav = get_package_share_directory('turtlebot4_navigation')
    nav_launch = PathJoinSubstitution([tb4_nav, 'launch', 'nav2.launch.py'])

    robot1_nav = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(nav_launch),
        launch_arguments={
            'namespace': 'robot1',
            'use_sim_time': 'true',
        }.items(),
    )

    robot2_nav = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(nav_launch),
        launch_arguments={
            'namespace': 'robot2',
            'use_sim_time': 'true',
        }.items(),
    )

    return LaunchDescription([robot1_nav, robot2_nav])
