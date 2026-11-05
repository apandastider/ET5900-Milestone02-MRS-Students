#!/usr/bin/env bash
# ET 5900 — Lightweight Milestone 2 bringup (no RViz, MoveIt or visual transfer).
# Supports: ./start.sh [all|world|robot1|robot2|bridges|lite6|controllers|nav|amcl|status|stop]
set -Eeo pipefail
BASE="${HOME}/.mrs_milestone2_integrated"
LOGS="$BASE/logs"; PIDS="$BASE/pids"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CFG="${CFG:-$HOME/mrs_milestone2_ws/src/mrs_milestone2/config/milestone2_locations_and_poses.yaml}"
MAP="${MAP:-$HOME/mrs_milestone2_ws/maps/milestone2_map.yaml}"
WORLD=milestone2_multi_robot_transfer
# Use official Lite6 launch instead if your custom one fails, for example:
# LITE6_COMMAND='ros2 launch /absolute/path/to/lite6_beside_table_gazebo.launch.py' ./start.sh lite6
LITE6_COMMAND="${LITE6_COMMAND:-ros2 launch mrs_milestone2 lite6_spawn.launch.py}"
mkdir -p "$LOGS" "$PIDS"

# Source in this script AND new child shells. This never modifies ROS packages.
ENV_FILE="$BASE/source_env.bash"
cat > "$ENV_FILE" <<'EOT'
source /opt/ros/jazzy/setup.bash
source "$HOME/turtlebot4_ws/install/setup.bash"
source "$HOME/lite6_jazzy_ws/install/setup.bash"
source "$HOME/milestone2_overlay_ws/install/setup.bash"
source "$HOME/mrs_milestone2_ws/install/setup.bash"
EOT
for f in /opt/ros/jazzy/setup.bash "$HOME/turtlebot4_ws/install/setup.bash" \
  "$HOME/lite6_jazzy_ws/install/setup.bash" "$HOME/milestone2_overlay_ws/install/setup.bash" \
  "$HOME/mrs_milestone2_ws/install/setup.bash"; do
  [[ -f "$f" ]] || { echo "Missing workspace setup: $f" >&2; exit 1; }
done
# shellcheck disable=SC1090
source "$ENV_FILE"

start_bg() {
  local name="$1"; shift
  local cmd="$*"
  local pidfile="$PIDS/$name.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "SKIP: $name is already launched by this script"
    return
  fi
  echo "START $name: $cmd"
  # Each group can be stopped independently. Only processes started here are affected.
  setsid bash -c 'source "$1"; shift; exec "$@"' _ "$ENV_FILE" bash -lc "source '$ENV_FILE'; $cmd" \
    >"$LOGS/$name.log" 2>&1 < /dev/null &
  echo "$!" > "$pidfile"
}

# Bound readiness waits instead of assuming particular machine speed.
wait_for() {
  local description="$1"; shift
  local i
  for ((i=0;i<40;i++)); do
    if timeout 7 "$@" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  echo "WARNING: timeout waiting for $description. Inspect $LOGS/" >&2
  return 1
}

world() {
  if timeout 7 gz model --list 2>/dev/null | grep -q 'Available models:'; then
    echo 'ERROR: An existing Gazebo world is already active. Stop it first to avoid duplicates.' >&2
    echo 'Inspect: pgrep -af "gz sim"' >&2
    return 1
  fi
  start_bg world ros2 launch mrs_milestone2 world.launch.py
}
robot1() {
  start_bg robot1 ros2 launch turtlebot4_gz_bringup turtlebot4_spawn.launch.py \
    model:=lite namespace:=robot1 x:=-3.0 y:=-1.6 z:=0.0 yaw:=0.0 \
    slam:=false localization:=false nav2:=false rviz:=false
}
robot2() {
  start_bg robot2 ros2 launch turtlebot4_gz_bringup turtlebot4_spawn.launch.py \
    model:=lite namespace:=robot2 x:=3.0 y:=-1.6 z:=0.0 yaw:=3.14159 \
    slam:=false localization:=false nav2:=false rviz:=false
}
bridges() {
  for robot in robot1 robot2; do
    local topic="/world/$WORLD/model/$robot/turtlebot4/link/rplidar_link/sensor/rplidar/scan"
    # Use the known custom-world topic. If your Gazebo path differs, check `gz topic -l | grep scan`.
    start_bg "${robot}_scan" ros2 run ros_gz_bridge parameter_bridge \
      "'${topic}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan'" \
      --ros-args -r "'${topic}:=/${robot}/scan'" -r "__node:=${robot}_scan_bridge"
  done
}
lite6() { start_bg lite6 "$LITE6_COMMAND"; }

controller_manager_for_arm() {
  if ros2 service list 2>/dev/null | grep -Fx '/lite6/controller_manager/list_controllers' >/dev/null; then
    echo /lite6/controller_manager
  elif ros2 service list 2>/dev/null | grep -Fx '/controller_manager/list_controllers' >/dev/null; then
    echo /controller_manager
  else
    return 1
  fi
}

ensure_controller() {
  local cm="$1" name="$2"
  local result
  result="$(timeout 12 ros2 control list_controllers -c "$cm" 2>&1)" || {
    echo "Could not list controllers at $cm" >&2; return 1;
  }
  if grep -E "^${name}[[:space:]]" <<<"$result" | grep -q 'active'; then
    echo "ACTIVE: $cm $name"; return 0
  fi
  if grep -E "^${name}[[:space:]]" <<<"$result" | grep -q 'inactive'; then
    timeout 30 ros2 control switch_controllers -c "$cm" --activate "$name"
  else
    timeout 35 ros2 run controller_manager spawner "$name" -c "$cm" --controller-manager-timeout 15
  fi
}
controllers() {
  for robot in robot1 robot2; do
    local cm="/$robot/controller_manager"
    if ros2 service list | grep -Fx "${cm}/list_controllers">/dev/null; then
      ensure_controller "$cm" joint_state_broadcaster || true
      ensure_controller "$cm" diffdrive_controller || true
    else
      echo "WARNING: No controller manager for $robot. See $LOGS/$robot.log" >&2
    fi
  done
  local cm
  cm="$(controller_manager_for_arm)" || {
    echo 'ERROR: Lite 6 controller_manager unavailable; start Lite 6 first.' >&2; return 1;
  }
  echo "Lite 6 manager: $cm"
  ensure_controller "$cm" joint_state_broadcaster
  ensure_controller "$cm" lite6_traj_controller
  echo 'Confirm the Lite 6 action name via: ros2 action list | grep follow_joint_trajectory'
}

nav() {
  local config_dir="$HOME/mrs_milestone2_ws/src/mrs_milestone2/config"

  if [[ ! -f "$MAP" ]]; then
    echo "ERROR: map missing: $MAP" >&2
    return 1
  fi

  for robot in robot1 robot2; do
    start_bg "${robot}_localization" \
      ros2 launch turtlebot4_navigation localization.launch.py \
      "namespace:=/$robot" \
      use_sim_time:=true \
      "map:=$MAP" \
      "params:=$config_dir/${robot}_localization.yaml"
  done

  for robot in robot1 robot2; do
    start_bg "${robot}_nav2" \
      ros2 launch turtlebot4_navigation nav2.launch.py \
      "namespace:=/$robot" \
      use_sim_time:=true \
      "params_file:=$config_dir/${robot}_nav2.yaml"
  done
}
amcl() {
  [[ -f "$CFG" ]] || { echo "Missing config: $CFG" >&2; return 1; }
  if ! python3 -c "import mrs_milestone2.fsm_initialize_amcl" >/dev/null 2>&1; then
    echo 'ERROR: build and source ~/mrs_milestone2_ws first.' >&2; return 1
  fi
  for robot in robot1 robot2; do
    echo "Checking $robot map server is active..."
    local i s=''
    for ((i=0;i<35;i++)); do
      s="$(timeout 5 ros2 lifecycle get "/$robot/map_server" 2>/dev/null || true)"
      [[ "$s" == *'active [3]'* ]] && break
      sleep 2
    done
    if [[ "$s" != *'active [3]'* ]]; then
      # Attempt a single standard lifecycle transition for a stalled map_server.
      # This does not overwrite the saved map or any navigation parameters.
      echo "Map server for $robot is '$s'; attempting normal lifecycle activation..."
      if [[ "$s" == *'unconfigured [1]'* ]]; then
        timeout 12 ros2 lifecycle set "/$robot/map_server" configure || true
      fi
      timeout 12 ros2 lifecycle set "/$robot/map_server" activate || true
      s="$(timeout 6 ros2 lifecycle get "/$robot/map_server" 2>/dev/null || true)"
    fi
    if [[ "$s" != *'active [3]'* ]]; then
      echo "ERROR: $robot map server not active: $s" >&2
      echo "Check $LOGS/${robot}_localization.log and the YAML map path." >&2
      return 1
    fi
  done
  echo 'Publishing both AMCL initial poses (no RViz)...'
  python3 -m mrs_milestone2.fsm_initialize_amcl --config "$CFG" --seconds 12
}
status() {
  echo '=== Launched components ==='
  for file in "$PIDS"/*.pid; do
    [[ -f "$file" ]] || continue
    local pid; pid="$(cat "$file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "RUNNING $(basename "$file" .pid) $pid"
    else
      echo "STOPPED $(basename "$file" .pid)"
    fi
  done
  echo '=== Controllers ==='
  ros2 action list 2>/dev/null | grep -E 'navigate_to_pose|follow_joint_trajectory' || true
  echo "Logs in $LOGS"
}
stop_all() {
  for file in "$PIDS"/*.pid; do
    [[ -f "$file" ]] || continue
    local pid; pid="$(cat "$file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "STOP $(basename "$file" .pid): $pid"
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
  done
  echo 'Stopped processes recorded by this script. Inspect any independently started processes separately.'
}
all() {
  world
  echo 'Waiting briefly for Gazebo to initialize...'
  sleep 7
  robot1; sleep 7
  robot2; sleep 7
  bridges
  lite6; sleep 8
  controllers
  nav
  echo 'Waiting for Nav2 / AMCL lifecycle startup...'
  amcl
  status
}

case "${1:-all}" in
  all) all;;
  world) world;;
  robot1) robot1;;
  robot2) robot2;;
  bridges) bridges;;
  lite6) lite6;;
  controllers) controllers;;
  nav) nav;;
  amcl) amcl;;
  status) status;;
  stop) stop_all;;
  *) echo 'Usage: start.sh [all|world|robot1|robot2|bridges|lite6|controllers|nav|amcl|status|stop]'; exit 2;;
esac
