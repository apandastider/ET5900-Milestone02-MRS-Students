# Install `milestone2_overlay_ws` — iRobot Create 3 Gazebo Overlay

**Course:** ET 5900 Multi-Robot Systems — Milestone 2
**Platform:** Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic
**Purpose:** Provide the modified iRobot Create 3 Gazebo packages required by the two TurtleBot 4 Lite robots in the custom manufacturing world.

> **Required for Teams 1 and 3 and instructor integration.** The course-provided source archive is attached to the GitHub **v0.1.0 release**. Do not use a generic fresh upstream clone in place of the supplied archive; it may lack the adjustments used for this milestone.

## 1. Download the supplied source overlay

**Release:** https://github.com/apandastider/ET5900-Milestone02-MRS-Students/releases/tag/v0.1.0

Download the release asset named **`milestone2_overlay_src.tar.gz`** into `~/Downloads`.

If GitHub CLI (`gh`) is installed and you have repository access, you can instead download it with:

```bash
mkdir -p ~/Downloads

gh release download v0.1.0 \
  -R apandastider/ET5900-Milestone02-MRS-Students-Students \
  --pattern milestone2_overlay_src.tar.gz \
  --dir ~/Downloads
```

For public repositories, direct download may also work:

```bash
curl -fL \
  -o ~/Downloads/milestone2_overlay_src.tar.gz \
  https://github.com/apandastider/ET5900-Milestone02-MRS-Students/releases/download/v0.1.0/milestone2_overlay_src.tar.gz
```

Use the public student repository release asset; the private instructor repository is not required.

## 2. Extract the source into the correct workspace

```bash
mkdir -p ~/milestone2_overlay_ws

tar -tzf ~/Downloads/milestone2_overlay_src.tar.gz | head -20

tar -xzf ~/Downloads/milestone2_overlay_src.tar.gz \
  -C ~/milestone2_overlay_ws
```

The archive contains a top-level `src/` folder. The result must be:

```text
~/milestone2_overlay_ws/
└── src/
    └── create3_sim/
        ├── irobot_create_common/
        └── irobot_create_gz/
```

**Do not extract it into `src/src/`.** Do not overwrite an existing, working instructor or student overlay without first backing it up.

## 3. Verify the nine overlay packages

```bash
source /opt/ros/jazzy/setup.bash
cd ~/milestone2_overlay_ws

colcon list --base-paths src
```

Expected package names:

```text
irobot_create_common_bringup
irobot_create_control
irobot_create_description
irobot_create_gz_bringup
irobot_create_gz_plugins
irobot_create_gz_sim
irobot_create_gz_toolbox
irobot_create_nodes
irobot_create_toolbox
```

## 4. Install dependencies and build

The regular TurtleBot 4 workspace should already be installed.

```bash
source /opt/ros/jazzy/setup.bash
source ~/turtlebot4_ws/install/setup.bash

cd ~/milestone2_overlay_ws

rosdep update
rosdep install --from-paths src \
  --ignore-src --rosdistro jazzy -y

colcon build --symlink-install \
  --allow-overriding irobot_create_description \
  --parallel-workers 4
```

The `--allow-overriding` flag is intentional: this overlay may replace the underlay's `irobot_create_description` with the course-tested version. If the build reports other overriding packages or unresolved dependencies, read the diagnostic instead of deleting or upgrading your existing TurtleBot workspace.

## 5. Source and verify the overlay

```bash
source /opt/ros/jazzy/setup.bash
source ~/turtlebot4_ws/install/setup.bash
source ~/milestone2_overlay_ws/install/setup.bash

ros2 pkg prefix irobot_create_description
ros2 pkg prefix irobot_create_gz_bringup
ros2 pkg prefix irobot_create_gz_plugins
```

The prefixes should point to packages found in `~/milestone2_overlay_ws/install/` where expected.

## 6. Build and run the course package

The course workspace also depends on the UFACTORY workspace. See [`INSTALL_LITE6_JAZZY.md`](INSTALL_LITE6_JAZZY.md) for that installation.

```bash
source /opt/ros/jazzy/setup.bash
source ~/turtlebot4_ws/install/setup.bash
source ~/lite6_jazzy_ws/install/setup.bash
source ~/milestone2_overlay_ws/install/setup.bash

cd ~/mrs_milestone2_ws
colcon build --symlink-install --packages-select mrs_milestone2
source install/setup.bash

cd ~/mrs_milestone2_ws/src/mrs_milestone2
```

Start only your assigned robot:

```bash
# Team 1 — Robot 1 + sensors + AMCL + Nav2
bash scripts/milestone2_team.sh team1 start

# OR Team 3 — Robot 2 + sensors + AMCL + Nav2
bash scripts/milestone2_team.sh team3 start
```

Check readiness for your team:

```bash
bash scripts/milestone2_team.sh team1 status
# or
bash scripts/milestone2_team.sh team3 status
```

**Do not also run `milestone2_start_safe.sh start`.** The instructor uses that script to start all three robots for integrated FSM evaluation.

## 7. Troubleshooting

- **Missing package:** Confirm `colcon list --base-paths src` reports all nine packages and the overlay `install/setup.bash` has been sourced.
- **No `/robot1/scan` or `/robot2/scan`:** Verify Gazebo is running the milestone world and the team script started the bridge for the correct world, `milestone2_multi_robot_transfer`.
- **No `/clock`:** Check the team launcher's clock bridge before troubleshooting AMCL or Nav2.
- **Nav2 cannot navigate:** Check `/robotN/odom`, `/robotN/scan`, `map → robotN/odom → robotN/base_link`, AMCL, and the active map server; consult the course troubleshooting guide.
- **A second robot appears unexpectedly:** Use only the team-specific launcher in a fresh session. The instructor integrated launcher deliberately starts all three robots.

## Reproducibility and licenses

The supplied archive was created from the instructor's `~/milestone2_overlay_ws/src` (nine packages; approximately **1.9 MB compressed**) and excludes Git history and compiled `build/`, `install/`, and `log/` folders. Respect the included upstream notices and licenses. If the archive is updated, give the replacement a new release version and update this guide's download link.
