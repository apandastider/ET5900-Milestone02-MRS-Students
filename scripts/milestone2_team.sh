#!/usr/bin/env bash
# ET5900 student launcher - clean-session design, version 1.0
# The world is SHARED but this launcher starts only the selected team's robot.
# start: start fresh OR verify fully healthy existing owned session.
#       NEVER repair or adopt a partial session (prevents duplicate bridges/nodes).
# stop: stop ONLY process groups tracked in the student workspace.
# status: read-only ROS/Gazebo checks.
set -Eeo pipefail

TEAM="${1:-}"
MODE="${2:-start}"
if [[ ! "$TEAM" =~ ^team[123]$ || ! "$MODE" =~ ^(start|stop|status)$ ]]; then
  echo 'Usage: bash scripts/milestone2_team.sh team1|team2|team3 start|status|stop' >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="$(cd "$ROOT/../.." && pwd)"
BASE="$WS/.milestone2_runtime"
PIDS="$BASE/pids"
LOGS="$BASE/logs"
ENV_FILE="$BASE/source_env.bash"
CFG="$ROOT/config"
MAP="$ROOT/maps/milestone2_map.yaml"
WORLD=milestone2_multi_robot_transfer
mkdir -p "$PIDS" "$LOGS"

# Always source THIS student checkout, never ~/mrs_milestone2_ws by name.
cat > "$ENV_FILE" <<'ENV'
source /opt/ros/jazzy/setup.bash
for w in turtlebot4_ws lite6_jazzy_ws milestone2_overlay_ws; do
  if [[ -f "$HOME/$w/install/setup.bash" ]]; then
    source "$HOME/$w/install/setup.bash"
  fi
done
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/install/setup.bash"
ENV
if [[ ! -f "$WS/install/setup.bash" ]]; then
  echo "ERROR: student package is not built: $WS/install/setup.bash" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$ENV_FILE"

if [[ "$TEAM" == team1 ]]; then ROBOT=robot1
elif [[ "$TEAM" == team3 ]]; then ROBOT=robot2
else ROBOT=lite6; fi

log() { echo "$*"; }
node_exists() { timeout 8 ros2 node list 2>/dev/null | grep -Fx "$1" >/dev/null; }
topic_live() { timeout 10 ros2 topic echo "$1" --once >/dev/null 2>&1; }
active() { [[ "$(timeout 8 ros2 lifecycle get "$1" 2>/dev/null || true)" == 'active [3]' ]]; }
clock_count() {
  local n
  n="$(timeout 8 ros2 topic info /clock 2>/dev/null | awk '/^Publisher count:/ {print $3;exit}' || true)"
  [[ "$n" =~ ^[0-9]+$ ]] || n=0
  echo "$n"
}
one_clock() { [[ "$(clock_count)" == 1 ]] && topic_live /clock; }
world_exists() { gz service -l 2>/dev/null | grep -Fx "/world/$WORLD/control" >/dev/null; }
any_world() { gz service -l 2>/dev/null | grep -Eq '^/world/[^/]+/control$'; }
model_exists() { gz model --list 2>/dev/null | sed -n 's/^[[:space:]]*-[[:space:]]*//p' | grep -Fx "$1" >/dev/null; }
controller_active() {
  local cm="$1" controller="$2" output
  output="$(timeout 12 ros2 control list_controllers -c "$cm" 2>/dev/null || true)"
  grep -Eq "^${controller}[[:space:]]+.*active" <<<"$output"
}
tf_ready() {
  local ns="$1" parent="$2" child="$3" output
  output="$(timeout 8 ros2 run tf2_ros tf2_echo "$parent" "$child" \
      --ros-args -r "/tf:=/$ns/tf" -r "/tf_static:=/$ns/tf_static" 2>&1 || true)"
  [[ "$output" == *'At time '* ]]
}
wait_for() {
  local label="$1" tries="$2"; shift 2
  local i
  for ((i=0;i<tries;i++)); do
    if "$@"; then log "READY: $label"; return 0; fi
    sleep 2
  done
  log "ERROR: not ready: $label (logs: $LOGS)" >&2
  return 1
}

# Inspect pidfiles; do not trust PIDs without checking process-group ownership.
leader_owned() {
  local file="$1" pid pgid sid cmd label
  [[ -f "$file" ]] || return 1
  pid="$(cat "$file")"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null || return 1
  pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')"
  sid="$(ps -o sid= -p "$pid" 2>/dev/null | tr -d ' ')"
  [[ "$pid" == "$pgid" && "$pid" == "$sid" ]] || return 1
  cmd="$(ps -o args= -p "$pid" 2>/dev/null || true)"
  label="$(basename "$file" .pid)"
  case "$label" in
    world)                  [[ "$cmd" == *world.launch.py* ]];;
    robot1|robot2)          [[ "$cmd" == *turtlebot4_spawn.launch.py* ]];;
    lite6)                  [[ "$cmd" == *lite6_spawn.launch.py* ]];;
    *_localization)         [[ "$cmd" == *localization.launch.py* ]];;
    *_nav2)                 [[ "$cmd" == *nav2.launch.py* ]];;
    *_scan_bridge|*_clock_bridge) [[ "$cmd" == *parameter_bridge* ]];;
    *_odom_tf)              [[ "$cmd" == *milestone2_team_tf.py* ]];;
    *)                      return 1;;
  esac
}
owned_world() { leader_owned "$PIDS/world.pid"; }

launch_bg() {
  local name="$1"; shift
  local file="$PIDS/$name.pid"
  if [[ -e "$file" ]]; then
    if leader_owned "$file"; then
      log "ERROR: $name is already running; use status or stop before a clean start." >&2
      return 1
    fi
    log "ERROR: stale/unverifiable PID file $file; refusing unsafe reuse." >&2
    return 1
  fi
  log "START: $name: $*"
  setsid bash -c 'source "$1"; shift; exec "$@"' _ "$ENV_FILE" "$@" \
    >"$LOGS/$name.log" 2>&1 </dev/null &
  echo "$!" > "$file"
}

# One clean command for the user; child group shutdown is scoped to this WS.
stop_session() {
  local f pid count=0
  for f in "$PIDS"/*.pid; do
    [[ -f "$f" ]] || continue
    if leader_owned "$f"; then
      pid="$(cat "$f")"
      log "STOP: $(basename "$f" .pid), process group $pid"
      kill -TERM -- "-$pid" 2>/dev/null || true
      ((count+=1))
    else
      pid="$(cat "$f")"
      if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
        log "ERROR: unverified LIVE PID file $f; not touching this process." >&2
        return 1
      fi
    fi
  done
  sleep 5
  for f in "$PIDS"/*.pid; do
    [[ -f "$f" ]] || continue
    if leader_owned "$f"; then
      log "ERROR: still running: $f. Inspect before retrying." >&2
      return 1
    fi
    rm -f "$f"
  done
  if world_exists || [[ "$(clock_count)" != 0 ]]; then
    log 'ERROR: Gazebo world or /clock remains after stop. Some process is untracked.' >&2
    log 'Inspect processes; do not launch another world on top of it.' >&2
    return 1
  fi
  log "STOPPED: student simulation ($count owned process groups)."
}

# Exactly one healthy, currently owned student session may be reused.
healthy() {
  owned_world && world_exists && one_clock || return 1
  if [[ "$TEAM" == team2 ]]; then
    model_exists lite6 || return 1
    local cm
    cm="$(arm_manager)" || return 1
    controller_active "$cm" lite6_traj_controller || return 1
  else
    model_exists "$ROBOT/turtlebot4" &&
    controller_active "/$ROBOT/controller_manager" joint_state_broadcaster &&
    controller_active "/$ROBOT/controller_manager" diffdrive_controller &&
    topic_live "/$ROBOT/odom" && topic_live "/$ROBOT/scan" &&
    active "/$ROBOT/amcl" &&
    active "/$ROBOT/controller_server" &&
    active "/$ROBOT/planner_server" &&
    active "/$ROBOT/bt_navigator" &&
    tf_ready "$ROBOT" map "$ROBOT/base_link"
  fi
}
arm_manager() {
  if timeout 8 ros2 service list 2>/dev/null | grep -Fx '/lite6/controller_manager/list_controllers' >/dev/null; then
    echo /lite6/controller_manager
  elif timeout 8 ros2 service list 2>/dev/null | grep -Fx '/controller_manager/list_controllers' >/dev/null; then
    echo /controller_manager
  else return 1; fi
}

status() {
  log "=== $TEAM ($ROBOT) read-only status ==="
  if owned_world && world_exists; then log 'OK: student world owned'; else log 'NOT READY: student world not owned/running'; fi
  log "CLOCK: $(clock_count) publisher(s) (required: 1)"
  if healthy; then log "PASS: $TEAM fully ready"; else log "NOT READY: $TEAM requires a clean startup"; return 1; fi
}

start_fresh() {
  [[ -f "$ROOT/launch/world.launch.py" && -f "$MAP" ]] || { log 'ERROR: world or map missing' >&2; return 1; }
  [[ -f "$CFG/milestone2_locations_and_poses.yaml" ]] || { log 'ERROR: locations config missing' >&2; return 1; }
  if [[ "$TEAM" != team2 ]]; then
    [[ -f "$CFG/${ROBOT}_nav2.yaml" && -f "$CFG/${ROBOT}_localization.yaml" ]] || {
      log "ERROR: missing $ROBOT Nav2/localization YAML" >&2; return 1;
    }
  fi
  if compgen -G "$PIDS/*.pid" >/dev/null; then
    log 'ERROR: an existing student PID session is partially running or stale.' >&2
    log "First run: bash scripts/milestone2_team.sh $TEAM stop" >&2
    return 1
  fi
  if any_world || [[ "$(clock_count)" != 0 ]]; then
    log 'ERROR: another Gazebo world or ROS clock exists. Refusing duplicate simulation.' >&2
    log "Check: gz service -l | grep '/world/'; ros2 topic info /clock -v" >&2
    return 1
  fi
  if node_exists "/$ROBOT/controller_manager" || node_exists "/$ROBOT/amcl" ||
     node_exists "/$ROBOT/bt_navigator" ||
     { [[ "$TEAM" == team2 ]] && node_exists /controller_manager; }; then
    log "ERROR: untracked /$ROBOT ROS nodes already exist. Do not mix sessions." >&2
    return 1
  fi

  launch_bg world ros2 launch mrs_milestone2 world.launch.py
  wait_for 'Gazebo world' 45 world_exists
  # world.launch.py owns clock; never add another bridge.
  wait_for '/clock exactly one live publisher' 35 one_clock

  if [[ "$TEAM" == team2 ]]; then
    launch_bg lite6 ros2 launch mrs_milestone2 lite6_spawn.launch.py
    wait_for "Lite6 Gazebo model" 40 model_exists lite6
    local cm
    for ((i=0;i<40;i++)); do
      cm="$(arm_manager || true)"
      [[ -n "$cm" ]] && break
      sleep 2
    done
    [[ -n "$cm" ]] || { log 'ERROR: Lite6 controller manager not found' >&2; return 1; }
    log "READY: arm controller manager $cm"
    for controller in joint_state_broadcaster lite6_traj_controller; do
      if ! controller_active "$cm" "$controller"; then
        log "START: Lite6 controller $controller"
        timeout 70 ros2 run controller_manager spawner "$controller"           -c "$cm" --controller-manager-timeout 40 || return 1
      fi
      wait_for "Lite6 $controller active" 20 controller_active "$cm" "$controller"
    done
    log 'SUCCESS: Team 2 ready. Test FollowJointTrajectory action separately.'
    return 0
  fi

  # Fresh model. HOME coordinates are explicit and known: NO live-pose parser.
  local spawn_x spawn_y spawn_yaw
  if [[ "$ROBOT" == robot1 ]]; then
    spawn_x=-3.0 spawn_y=-1.6 spawn_yaw=0.0
    launch_bg robot1 ros2 launch turtlebot4_gz_bringup turtlebot4_spawn.launch.py \
      model:=lite namespace:=robot1 "x:=$spawn_x" "y:=$spawn_y" z:=0.0 "yaw:=$spawn_yaw" \
      slam:=false localization:=false nav2:=false rviz:=false
  else
    spawn_x=3.0 spawn_y=-1.6 spawn_yaw=3.14159
    launch_bg robot2 ros2 launch turtlebot4_gz_bringup turtlebot4_spawn.launch.py \
      model:=lite namespace:=robot2 "x:=$spawn_x" "y:=$spawn_y" z:=0.0 "yaw:=$spawn_yaw" \
      slam:=false localization:=false nav2:=false rviz:=false
  fi
  wait_for "$ROBOT model" 40 model_exists "$ROBOT/turtlebot4"

  # Remove stock TurtleBot charging dock; retain manufacturing station pads.
  local dock="$ROBOT/standard_dock" reply attempt
  for ((attempt=1; attempt<=15; attempt++)); do
    if model_exists "$dock"; then
      reply="$(timeout 8 gz service -s "/world/$WORLD/remove" \
        --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean \
        --timeout 3000 --req "name: \\"$dock\\", type: MODEL" 2>&1 || true)"
      if [[ "$reply" == *"data: true"* ]]; then
        log "READY: removed charging dock $dock"
      else
        log "WARN: could not remove charging dock $dock"
      fi
      break
    fi
    sleep 1
  done
  wait_for "$ROBOT controller manager" 40 node_exists "/$ROBOT/controller_manager"
  # Stock TurtleBot spawn handles controller loading. Do not spawn twice.
  wait_for "$ROBOT joint_state_broadcaster active" 45 controller_active "/$ROBOT/controller_manager" joint_state_broadcaster
  wait_for "$ROBOT diffdrive_controller active" 45 controller_active "/$ROBOT/controller_manager" diffdrive_controller
  wait_for "$ROBOT odometry" 30 topic_live "/$ROBOT/odom"

  # Explicit Gazebo topic matches this custom world; stock bridge points to /warehouse.
  local scan="/world/$WORLD/model/$ROBOT/turtlebot4/link/rplidar_link/sensor/rplidar/scan"
  launch_bg "${ROBOT}_scan_bridge" ros2 run ros_gz_bridge parameter_bridge \
    "${scan}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" \
    --ros-args -r "${scan}:=/$ROBOT/scan" -r "__node:=${ROBOT}_scan_bridge"
  wait_for "$ROBOT LiDAR" 30 topic_live "/$ROBOT/scan"

  if ! tf_ready "$ROBOT" "$ROBOT/odom" "$ROBOT/base_link"; then
    launch_bg "${ROBOT}_odom_tf" python3 "$ROOT/scripts/milestone2_team_tf.py" --robot "$ROBOT"
  fi
  wait_for "$ROBOT odom-to-base TF" 20 tf_ready "$ROBOT" "$ROBOT/odom" "$ROBOT/base_link"
  wait_for "$ROBOT odom-to-lidar TF" 20 tf_ready "$ROBOT" "$ROBOT/odom" "$ROBOT/turtlebot4/rplidar_link/rplidar"

  # Start one robot's AMCL only, after sensors & TF are healthy.
  launch_bg "${ROBOT}_localization" ros2 launch turtlebot4_navigation localization.launch.py \
    "namespace:=/$ROBOT" use_sim_time:=true "map:=$MAP" \
    "params:=$CFG/${ROBOT}_localization.yaml"
  wait_for "$ROBOT map_server active" 40 active "/$ROBOT/map_server"
  wait_for "$ROBOT AMCL active" 40 active "/$ROBOT/amcl"

  local i
  for ((i=1;i<=3;i++)); do
    log "INIT: $ROBOT AMCL from its FRESH spawn pose ($i/3)"
    timeout 25 python3 "$ROOT/scripts/milestone2_student_amcl_seed.py" \
      --robot "$ROBOT" --x "$spawn_x" --y "$spawn_y" --yaw "$spawn_yaw"
    timeout 10 ros2 service call "/$ROBOT/request_nomotion_update" \
      std_srvs/srv/Empty '{}' >/dev/null 2>&1 || true
    if python3 "$ROOT/scripts/milestone2_team_pose_check.py" \
      --robot "$ROBOT" --map "$MAP" \
      --config "$CFG/milestone2_locations_and_poses.yaml" \
      --near-home 1.2 --timeout 12; then break; fi
  done
  [[ "$i" -le 3 ]] || { log "ERROR: $ROBOT AMCL failed. See $LOGS/${ROBOT}_localization.log" >&2; return 1; }
  wait_for "$ROBOT map-to-base TF" 20 tf_ready "$ROBOT" map "$ROBOT/base_link"

  launch_bg "${ROBOT}_nav2" ros2 launch turtlebot4_navigation nav2.launch.py \
    "namespace:=/$ROBOT" use_sim_time:=true "params_file:=$CFG/${ROBOT}_nav2.yaml"
  wait_for "$ROBOT Nav2 controller active" 45 active "/$ROBOT/controller_server"
  wait_for "$ROBOT Nav2 planner active" 45 active "/$ROBOT/planner_server"
  wait_for "$ROBOT Nav2 BT Navigator active" 45 active "/$ROBOT/bt_navigator"
  [[ "$(clock_count)" == 1 ]] || { log 'ERROR: new duplicate clock publisher detected' >&2; return 1; }
  log "SUCCESS: $TEAM ready; one robot and one clock."
}

case "$MODE" in
  stop) stop_session ;;
  status) status ;;
  start)
    if world_exists; then
      if healthy; then
        log "SUCCESS: $TEAM already fully healthy; nothing started or modified."
      else
        log 'ERROR: existing Gazebo session is incomplete, unowned, or belongs to another team.' >&2
        log "No automatic partial repair. To reset YOUR student session: bash scripts/milestone2_team.sh $TEAM stop" >&2
        exit 1
      fi
    else
      start_fresh
    fi
  ;;
esac
