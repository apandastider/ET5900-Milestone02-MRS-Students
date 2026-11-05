
#!/usr/bin/env python3

import os
from pathlib import Path
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
import yaml

from launch import LaunchDescription
from launch.actions import OpaqueFunction, RegisterEventHandler
from launch.event_handlers import OnProcessStart
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node

from uf_ros_lib.uf_robot_utils import (
    get_xacro_content,
    generate_ros2_control_params_temp_file,
)


WORLD = "milestone2_multi_robot_transfer"


def launch_setup(context, *args, **kwargs):

    # --------------------------------------------------
    # 1. Lite 6 configuration
    # --------------------------------------------------

    robot_type = LaunchConfiguration("robot_type", default="lite")
    dof = LaunchConfiguration("dof", default="6")
    prefix = LaunchConfiguration("prefix", default="")
    hw_ns = LaunchConfiguration("hw_ns", default="ufactory")

    ros_namespace = "lite6"

    add_gripper = LaunchConfiguration(
        "add_gripper", default="true"
    )

    # --------------------------------------------------
    # 2. Generate ROS 2 controller configuration
    # --------------------------------------------------

    controller_yaml = os.path.join(
        get_package_share_directory("xarm_controller"),
        "config",
        "lite6_controllers.yaml",
    )

    control_params = generate_ros2_control_params_temp_file(
        controller_yaml,
        prefix="",
        add_gripper=True,
        add_bio_gripper=False,
        ros_namespace=ros_namespace,
        update_rate=1000,
        use_sim_time=True,
        robot_type="lite",
    )

    # Add the missing Lite 6 parallel gripper controller
# to the generated Gazebo ros2_control configuration.

    with open(control_params, "r") as f:
        controller_config = yaml.safe_load(f)

    lite6_config = controller_config["lite6"]

    # Register controller type
    lite6_config["controller_manager"]["ros__parameters"][
        "lite_gripper_traj_controller"
    ] = {
        "type": "joint_trajectory_controller/JointTrajectoryController"
    }

    # Configure actuated finger joint
    lite6_config["lite_gripper_traj_controller"] = {
        "ros__parameters": {
            "joints": ["finger_joint1"],
            "command_interfaces": ["position", "velocity"],
            "state_interfaces": ["position", "velocity"],
            "state_publish_rate": 25.0,
            "action_monitor_rate": 10.0,
            "constraints": {
                "goal_time": 0.5,
                "stopped_velocity_tolerance": 0.05,
                "finger_joint1": {
                    "trajectory": 1.0,
                    "goal": 0.05
                }
            }
        }
    }

    with open(control_params, "w") as f:
        yaml.safe_dump(controller_config, f)

    # --------------------------------------------------
    # 3. Generate Lite 6 URDF
    # --------------------------------------------------

    robot_description = get_xacro_content(
        context,
        xacro_file=(
            Path(get_package_share_directory("xarm_description"))
            / "urdf"
            / "xarm_device.urdf.xacro"
        ),
        robot_type=robot_type,
        dof=dof,
        prefix=prefix,
        hw_ns=hw_ns,
        limited=LaunchConfiguration(
            "limited", default="false"
        ),
        effort_control=LaunchConfiguration(
            "effort_control", default="false"
        ),
        velocity_control=LaunchConfiguration(
            "velocity_control", default="false"
        ),
        model1300=LaunchConfiguration(
            "model1300", default="false"
        ),
        robot_sn=LaunchConfiguration(
            "robot_sn", default=""
        ),
        attach_to=LaunchConfiguration(
            "attach_to", default="world"
        ),
        attach_xyz=LaunchConfiguration(
            "attach_xyz", default='"0 0.15 0"'
        ),
        attach_rpy=LaunchConfiguration(
            "attach_rpy", default='"0 0 -1.5708"'
        ),
        kinematics_suffix=LaunchConfiguration(
            "kinematics_suffix", default=""
        ),
        ros2_control_plugin="gz_ros2_control/GazeboSimSystem",
        ros2_control_params=control_params,
        gripper_version=LaunchConfiguration(
            "gripper_version", default="G1"
        ),
        add_gripper=add_gripper,
        add_vacuum_gripper=LaunchConfiguration(
            "add_vacuum_gripper", default="false"
        ),
        add_bio_gripper=LaunchConfiguration(
            "add_bio_gripper", default="false"
        ),
        add_realsense_d435i=LaunchConfiguration(
            "add_realsense_d435i", default="false"
        ),
        add_d435i_links=LaunchConfiguration(
            "add_d435i_links", default="true"
        ),
        add_other_geometry=LaunchConfiguration(
            "add_other_geometry", default="false"
        ),
        geometry_type=LaunchConfiguration(
            "geometry_type", default="box"
        ),
        geometry_mass=LaunchConfiguration(
            "geometry_mass", default="0.1"
        ),
        geometry_height=LaunchConfiguration(
            "geometry_height", default="0.1"
        ),
        geometry_radius=LaunchConfiguration(
            "geometry_radius", default="0.1"
        ),
        geometry_length=LaunchConfiguration(
            "geometry_length", default="0.1"
        ),
        geometry_width=LaunchConfiguration(
            "geometry_width", default="0.1"
        ),
        geometry_mesh_filename=LaunchConfiguration(
            "geometry_mesh_filename", default=""
        ),
        geometry_mesh_origin_xyz=LaunchConfiguration(
            "geometry_mesh_origin_xyz", default='"0 0 0"'
        ),
        geometry_mesh_origin_rpy=LaunchConfiguration(
            "geometry_mesh_origin_rpy", default='"0 0 0"'
        ),
        geometry_mesh_tcp_xyz=LaunchConfiguration(
            "geometry_mesh_tcp_xyz", default='"0 0 0"'
        ),
        geometry_mesh_tcp_rpy=LaunchConfiguration(
            "geometry_mesh_tcp_rpy", default='"0 0 0"'
        ),
    )

    # --------------------------------------------------
    # 4. Configure Gazebo ROS 2 control plugin
    # --------------------------------------------------

    root = ET.fromstring(robot_description)

    plugins = [
        p for p in root.findall(".//gazebo/plugin")
        if "gz_ros2_control" in p.get("filename", "")
    ]

    if len(plugins) != 1:
        raise RuntimeError(
            "Expected one gz_ros2_control plugin; "
            f"found {len(plugins)}"
        )

    plugin = plugins[0]

    # Controller manager ROS namespace
    ros_tag = plugin.find("ros")

    if ros_tag is None:
        ros_tag = ET.SubElement(plugin, "ros")

    namespace_tag = ros_tag.find("namespace")

    if namespace_tag is None:
        namespace_tag = ET.SubElement(
            ros_tag, "namespace"
        )

    namespace_tag.text = "/lite6"

    # Robot description parameter
    robot_param = plugin.find("robot_param")

    if robot_param is None:
        robot_param = ET.SubElement(
            plugin, "robot_param"
        )

    robot_param.text = "robot_description"

    # Robot state publisher name
    robot_param_node = plugin.find(
        "robot_param_node"
    )

    if robot_param_node is None:
        robot_param_node = ET.SubElement(
            plugin, "robot_param_node"
        )

    robot_param_node.text = (
        "/lite6/robot_state_publisher"
    )

    # Convert XML back into URDF
    robot_description = ET.tostring(
        root,
        encoding="unicode"
    )

    # Save generated URDF for debugging
    with open(
        "/tmp/milestone2_lite6.urdf", "w"
    ) as f:
        f.write(robot_description)

    # --------------------------------------------------
    # 5. Robot state publisher
    # --------------------------------------------------

    state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        namespace=ros_namespace,
        output="screen",
        parameters=[
            {"use_sim_time": True},
            {"robot_description": robot_description},
        ],
        remappings=[
            ("tf", "/tf"),
            ("tf_static", "/tf_static"),
        ],
    )

    # --------------------------------------------------
    # 6. Spawn Lite 6 in EXISTING Gazebo world
    # --------------------------------------------------

    spawn_lite6 = Node(
        package="ros_gz_sim",
        executable="create",
        output="screen",
        arguments=[
            "-world", WORLD,
            "-topic", "/lite6/robot_description",
            "-name", "lite6",
            "-x", "0.0",
            "-y", "0.0",
            "-z", "0.76",
            "-Y", "0.0",
        ],
        parameters=[
            {"use_sim_time": True}
        ],
    )

    # --------------------------------------------------
    # 7. Launch robot and spawn entity
    # --------------------------------------------------

    return [
        state_publisher,

        RegisterEventHandler(
            OnProcessStart(
                target_action=state_publisher,
                on_start=[spawn_lite6],
            )
        ),
    ]


def generate_launch_description():

    return LaunchDescription([
        OpaqueFunction(
            function=launch_setup
        )
    ])
