# Install `lite6_jazzy_ws` — UFACTORY Lite 6

**Course:** ET 5900 Multi-Robot Systems — Milestone 2
**Platform:** Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic
**Purpose:** Build the UFACTORY Lite 6 ROS 2 packages used by Team 2 and the instructor's integrated simulation.

> **Scope:** Milestone 2 controls the Lite 6 through predefined joint-space trajectories. The milestone does **not** require a gripper, object transfer, MoveIt planning, or RViz. The upstream UFACTORY workspace includes additional packages; they are not all used by the assignment.

## 1. Install prerequisites

These commands assume ROS 2 Jazzy and Gazebo Harmonic are already installed.

```bash
source /opt/ros/jazzy/setup.bash

sudo apt update
sudo apt install -y \
  python3-colcon-common-extensions \
  python3-rosdep \
  ros-jazzy-moveit \
  ros-jazzy-ros-gz \
  ros-jazzy-gz-ros2-control \
  ros-jazzy-ros2-control \
  ros-jazzy-ros2-controllers
```

If `rosdep` has not been initialized on this computer, run `sudo rosdep init` once; otherwise skip it. Then:

```bash
rosdep update
```

## 2. Download UFACTORY's Jazzy source

```bash
mkdir -p ~/lite6_jazzy_ws/src
cd ~/lite6_jazzy_ws/src

git clone --recursive -b jazzy \
  https://github.com/xArm-Developer/xarm_ros2.git
```

If `xarm_ros2` was already cloned, **do not overwrite it**. Instead, check the current branch and submodules:

```bash
cd ~/lite6_jazzy_ws/src/xarm_ros2
git branch --show-current
git submodule status
```

The `--recursive` option is necessary for upstream submodules.

## 3. Install package dependencies

```bash
source /opt/ros/jazzy/setup.bash
cd ~/lite6_jazzy_ws

rosdep install --from-paths src \
  --ignore-src --rosdistro jazzy -y
```

**If `rosdep` reports unresolved `sdformat14` or `gz-sim8` keys:** this is a known issue with some Jazzy versions of the upstream project. Verify Gazebo Harmonic and the corresponding Gazebo/ROS vendor packages are installed. Do not edit `package.xml` or replace ROS dependencies blindly; ask the instructor for the tested dependency workaround before continuing.

## 4. Build the workspace

```bash
source /opt/ros/jazzy/setup.bash
cd ~/lite6_jazzy_ws

colcon build --symlink-install --parallel-workers 4

source install/setup.bash
```

On lower-memory computers, reduce `--parallel-workers` to `2` or `1`.

## 5. Verify installation

```bash
source /opt/ros/jazzy/setup.bash
source ~/lite6_jazzy_ws/install/setup.bash

ros2 pkg prefix xarm_description
ros2 pkg prefix xarm_gazebo
ros2 pkg prefix xarm_moveit_config
```

Each command should print a package installation prefix without an error.

For Milestone 2, the Lite 6 is spawned into the **course manufacturing world** by the course launcher. Do **not** launch `lite6_beside_table_gazebo.launch.py` or `lite6_moveit_gazebo.launch.py` at the same time as the course launcher: those are separate upstream demos and can create a second simulation.

## 6. Source this workspace in a new terminal

```bash
source /opt/ros/jazzy/setup.bash
source ~/turtlebot4_ws/install/setup.bash
source ~/lite6_jazzy_ws/install/setup.bash
source ~/milestone2_overlay_ws/install/setup.bash
source ~/mrs_milestone2_ws/install/setup.bash
```

The other workspaces must be installed before their `source` commands are used. Build order and all workspace requirements are described in the repository's main `README.md`.

## 7. Team 2: Start only Lite 6

After installing the course repository in `~/mrs_milestone2_ws/src/mrs_milestone2` and building the course package:

```bash
cd ~/mrs_milestone2_ws/src/mrs_milestone2

bash scripts/milestone2_team.sh team2 start
bash scripts/milestone2_team.sh team2 status
```

Check the arm action/controller if needed:

```bash
ros2 action list | grep follow_joint_trajectory
ros2 control list_controllers -c /lite6/controller_manager
```

Expected course controller: `lite6_traj_controller` (active). Check the actual action name shown by `ros2 action list`; controller and action namespaces can differ depending on the launch configuration.

**Important:** Do not run `milestone2_start_safe.sh` afterward. That script is for the instructor's **full three-robot** integration.

## Reference

- UFACTORY ROS 2 source and upstream instructions: https://github.com/xArm-Developer/xarm_ros2

**Instructor reproducibility note:** The latest `jazzy` branch may change. Before release, record the exact commit tested on the instructor computer:

```bash
git -C ~/lite6_jazzy_ws/src/xarm_ros2 rev-parse HEAD
```

Students can then be directed to checkout that precise commit if reproducibility requires it.
