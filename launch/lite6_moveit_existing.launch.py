#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from uf_ros_lib.moveit_configs_builder import MoveItConfigsBuilder
from uf_ros_lib.uf_robot_utils import generate_ros2_control_params_temp_file


def launch_setup(context, *args, **kwargs):

    # Match the existing Lite 6 Gazebo robot.
    robot_type = LaunchConfiguration('robot_type', default='lite')
    dof = LaunchConfiguration('dof', default='6')
    prefix = LaunchConfiguration('prefix', default='')
    hw_ns = LaunchConfiguration('hw_ns', default='xarm')

    controller_yaml = os.path.join(
        get_package_share_directory('xarm_controller'),
        'config',
        'lite6_controllers.yaml'
    )

    control_params = generate_ros2_control_params_temp_file(
        controller_yaml,
        prefix='',
        add_gripper=True,
        add_bio_gripper=False,
        ros_namespace='lite6',
        update_rate=1000,
        use_sim_time=True,
        robot_type='lite'
    )

    moveit_config = MoveItConfigsBuilder(
        context=context,
        controllers_name='fake_controllers',
        dof=dof,
        robot_type=robot_type,
        prefix=prefix,
        hw_ns=hw_ns,
        limited=LaunchConfiguration('limited', default=True),
        effort_control=LaunchConfiguration('effort_control', default=False),
        velocity_control=LaunchConfiguration('velocity_control', default=False),
        model1300=LaunchConfiguration('model1300', default=False),
        robot_sn=LaunchConfiguration('robot_sn', default=''),
        attach_to=LaunchConfiguration('attach_to', default='world'),
        attach_xyz=LaunchConfiguration('attach_xyz', default='"0 0.15 0"'),
        attach_rpy=LaunchConfiguration('attach_rpy', default='"0 0 -1.5708"'),
        mesh_suffix=LaunchConfiguration('mesh_suffix', default='stl'),
        kinematics_suffix=LaunchConfiguration('kinematics_suffix', default=''),
        ros2_control_plugin='gz_ros2_control/GazeboSimSystem',
        ros2_control_params=control_params,
        gripper_version=LaunchConfiguration('gripper_version', default='G1'),
        add_gripper=LaunchConfiguration('add_gripper', default=True),
        add_vacuum_gripper=LaunchConfiguration('add_vacuum_gripper', default=False),
        add_bio_gripper=LaunchConfiguration('add_bio_gripper', default=False),
        add_realsense_d435i=LaunchConfiguration('add_realsense_d435i', default=False),
        add_d435i_links=LaunchConfiguration('add_d435i_links', default=True),
    ).to_moveit_configs()

    config = moveit_config.to_dict()

    # Use the already-running arm controller, not fake execution.
    config['moveit_controller_manager'] = (
        'moveit_simple_controller_manager/MoveItSimpleControllerManager'
    )

    config['moveit_simple_controller_manager'] = {
        'controller_names': ['lite6_traj_controller'],
        'lite6_traj_controller': {
            'type': 'FollowJointTrajectory',
            'action_ns': 'follow_joint_trajectory',
            'default': True,
            'joints': [
                'joint1', 'joint2', 'joint3',
                'joint4', 'joint5', 'joint6'
            ]
        }
    }

    config['trajectory_execution'] = {
        'allowed_execution_duration_scaling': 1.5,
        'allowed_goal_duration_margin': 1.0,
        'allowed_start_tolerance': 0.05
    }

    config['use_sim_time'] = True

    move_group = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        namespace='lite6',
        output='screen',
        parameters=[
            config,
            {
                'publish_robot_description': True,
                'publish_robot_description_semantic': True
            }
        ],
        remappings=[
            ('/tf', '/tf'),
            ('/tf_static', '/tf_static')
        ]
    )

    rviz_config = os.path.join(
        get_package_share_directory('xarm_moveit_config'),
        'rviz',
        'moveit.rviz'
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        namespace='lite6',
        name='rviz',
        output='screen',

        # Start with an empty display configuration.
        # We will add MotionPlanning manually.
        parameters=[
            config,
            {'use_sim_time': True},
        ],

        remappings=[
            ('/tf', '/tf'),
            ('/tf_static', '/tf_static'),
            ('/joint_states', '/lite6/joint_states'),

            ('/move_action', '/lite6/move_action'),
            ('/execute_trajectory', '/lite6/execute_trajectory'),

            ('/query_planner_interface',
             '/lite6/query_planner_interface'),

            ('/get_planning_scene',
             '/lite6/get_planning_scene'),

            ('/apply_planning_scene',
             '/lite6/apply_planning_scene'),

            ('/get_cartesian_path',
             '/lite6/get_cartesian_path'),

            ('/monitored_planning_scene',
             '/lite6/monitored_planning_scene'),
        ],
    )

    return [move_group]


def generate_launch_description():
    return LaunchDescription([
        OpaqueFunction(function=launch_setup)
    ])
