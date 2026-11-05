#!/usr/bin/env bash
# ET 5900 Milestone 2: isolated, non-destructive Team 1 / 2 / 3 bringup.
# Usage: bash scripts/milestone2_team.sh team1|team2|team3 [start|status|stop]
# Team 1: robot1 + Nav2. Team 2: Lite6. Team 3: robot2 + Nav2.
# Does NOT start the other team's robots; does NOT stop existing processes.
set -Eeo pipefail

TEAM="${1:-}"
MODE="${2:-start}"
if [[ ! "$TEAM" =~ ^team[123]$ || ! "$MODE" =~ ^(start|status|stop)$ ]]; then
  echo 'Usage: bash scripts/milestone2_team.sh team1|team2|team3 [start|status|stop]' >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIGINAL="$ROOT/scripts/milestone2_start.sh"
WORLD=milestone2_multi_robot_transfer
CFG="$ROOT/config"
MAP="${MRS_MAP:-$ROOT/maps/milestone2_map.yaml}"
BASE="$HOME/.mrs_milestone2_integrated"
LOGS="$BASE/logs"; PIDS="$BASE/pids"
ENV_FILE="$BASE/source_env.bash"
mkdir -p "$LOGS" "$PIDS"

# Follow exactly the same workspace ordering used by the verified integrated launcher.
if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<'EOF'
source /opt/ros/jazzy/setup.bash
for w in turtlebot4_ws lite6_jazzy_ws milestone2_overlay_ws mrs_milestone2_ws; do
  if [[ -f "$HOME/$w/install/setup.bash" ]]; then
    source "$HOME/$w/install/setup.bash"
  fi
done
EOF
fi
source "$ENV_FILE"

log() { echo "$*"; }
node_exists() { ros2 node list 2>/dev/null | grep -Fx "$1" >/dev/null; }
topic_live() { timeout 8 ros2 topic echo "$1" --once >/dev/null 2>&1; }
lifecycle_active() { [[ "$(timeout 8 ros2 lifecycle get "$1" 2>/dev/null || true)" == 'active [3]' ]]; }
world_exists() { gz service -l 2>/dev/null | grep -Fx "/world/$WORLD/control" >/dev/null; }
model_exists() {
  gz model --list 2>/dev/null | sed -n 's/^[[:space:]]*-[[:space:]]*//p' | grep -Fx "$1" >/dev/null
}
controller_active() {
  local r="$1" c="$2" output
  output="$(timeout 20 ros2 control list_controllers -c "/$r/controller_manager" 2>/dev/null || true)"
  printf '%s\n' "$output" | grep -E "^${c}[[:space:]]+.*active" >/dev/null
}
tf_ready() {
  local r="$1" source="$2" target="$3" output
  output="$(timeout 8 ros2 run tf2_ros tf2_echo "$source" "$target" \
    --ros-args -r "/tf:=/$r/tf" -r "/tf_static:=/$r/tf_static" 2>&1 || true)"
  [[ "$output" == *'At time '* ]]
}
wait_for() {
  local what="$1" tries="$2"; shift 2
  local i
  for ((i=0;i<tries;i++)); do
    if "$@"; then log "READY: $what"; return 0; fi
    sleep 2
  done
  log "NOT READY: $what; details in $LOGS" >&2
  return 1
}
start_bg() {
  local name="$1"; shift
  local pidfile="$PIDS/team_${TEAM}_${name}.pid" pid
  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile")"
    if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
      log "REUSE: $name (PID $pid)"; return 0
    fi
  fi
  log "START: $name"
  setsid bash -c 'source "$1"; shift; exec "$@"' _ "$ENV_FILE" "$@" \
    >"$LOGS/team_${TEAM}_${name}.log" 2>&1 </dev/null &
  echo "$!" > "$pidfile"
}

# Stop is intentionally scoped to the entire Milestone 2 session: the world
# is shared, and stopping one robot alone is NOT a clean team-isolation test.
stop_all() {
  echo 'STOP: requesting shutdown of all recorded Milestone 2 processes.'
  echo 'NOTE: this resets the shared world and may affect other running teams.'
  # Team/safe wrappers create their own process groups with setsid.
  # Validate the session leader before signalling to avoid a reused PID.
  local f pid pgid sid
  for f in "$PIDS"/team_*.pid "$PIDS"/safe_*.pid; do
    [[ -f "$f" ]] || continue
    pid="$(cat "$f")"
    if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
      pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
      sid="$(ps -o sid= -p "$pid" | tr -d ' ')"
      if [[ "$pgid" == "$pid" && "$sid" == "$pid" ]]; then
        echo "STOP: $(basename "$f") (process group $pid)"
        kill -TERM -- "-$pid" 2>/dev/null || true
      else
        echo "SKIP: $f has PID $pid but is not an owned session leader"
      fi
    fi
    rm -f "$f"
  done
  # Original launcher tracks the Gazebo world and robot spawn launchers.
  bash "$ORIGINAL" stop
  sleep 2
  if world_exists; then
    echo 'WARNING: Gazebo world still exists; inspect manual terminals before starting another team.' >&2
    return 1
  fi
  echo 'STOPPED: Milestone 2 recorded processes; world absent.'
}

if [[ "$TEAM" == team2 ]]; then ROBOT=lite6
elif [[ "$TEAM" == team1 ]]; then ROBOT=robot1
else ROBOT=robot2; fi

status() {
  log "=== $TEAM / $ROBOT readiness (read only) ==="
  world_exists && log 'OK: world' || log 'MISSING: world'
  topic_live /clock && log 'OK: clock' || log 'MISSING: clock'
  if [[ "$TEAM" == team2 ]]; then
    model_exists lite6 && log 'OK: Lite 6 model' || log 'MISSING: Lite 6 model'
    controller_active lite6 lite6_traj_controller && log 'OK: Lite 6 trajectory controller' || log 'MISSING: Lite 6 controller'
  else
    model_exists "$ROBOT/turtlebot4" && log "OK: $ROBOT model" || log "MISSING: $ROBOT model"
    topic_live "/$ROBOT/odom" && log 'OK: odom' || log 'MISSING: odom'
    topic_live "/$ROBOT/scan" && log 'OK: LiDAR' || log 'MISSING: LiDAR'
    tf_ready "$ROBOT" map "$ROBOT/base_link" && log 'OK: map-to-base TF' || log 'MISSING: map-to-base TF'
    lifecycle_active "/$ROBOT/amcl" && log 'OK: AMCL' || log 'MISSING: AMCL'
    lifecycle_active "/$ROBOT/bt_navigator" && log 'OK: Nav2' || log 'MISSING: Nav2'
  fi
}

ensure_controller() {
  local r="$1" c="$2"
  if controller_active "$r" "$c"; then
    log "REUSE: $r $c controller"
  else
    log "ACTIVATE: $r $c"
    timeout 65 ros2 run controller_manager spawner "$c" \
      -c "/$r/controller_manager" --controller-manager-timeout 40
  fi
  wait_for "$r $c controller" 15 controller_active "$r" "$c"
}

start() {
  local fresh_spawn=0
  [[ -f "$ORIGINAL" ]] || { log "Missing $ORIGINAL" >&2; exit 1; }
  [[ -f "$ROOT/scripts/milestone2_team_tf.py" ]] || { log 'Missing scripts/milestone2_team_tf.py' >&2; exit 1; }
  [[ -f "$ROOT/scripts/milestone2_team_amcl.py" ]] || { log 'Missing scripts/milestone2_team_amcl.py' >&2; exit 1; }
  [[ -f "$ROOT/scripts/milestone2_team_pose_check.py" ]] || { log 'Missing scripts/milestone2_team_pose_check.py' >&2; exit 1; }
  if [[ "$TEAM" != team2 ]]; then
    [[ -f "$MAP" && -f "$CFG/${ROBOT}_localization.yaml" && -f "$CFG/${ROBOT}_nav2.yaml" ]] || {
      log 'Missing map or per-robot navigation YAML (copy the validated files into the repository)' >&2; exit 1;
    }
  fi

  if world_exists; then log 'REUSE: Gazebo world'; else bash "$ORIGINAL" world; fi
  wait_for 'Gazebo world' 30 world_exists

  if topic_live /clock; then
    log 'REUSE: /clock'
  else
    start_bg clock_bridge ros2 run ros_gz_bridge parameter_bridge \
      "/world/$WORLD/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock" \
      --ros-args -r "/world/$WORLD/clock:=/clock" -r __node:=milestone2_clock_bridge
  fi
  wait_for '/clock delivering messages' 12 topic_live /clock

  # Spawn ONE team's robot only; reuse anything already in this Gazebo instance.
  if [[ "$TEAM" == team2 ]]; then
    if model_exists lite6; then log 'REUSE: Lite 6'; else bash "$ORIGINAL" lite6; fi
    wait_for '/lite6/controller_manager' 40 node_exists /lite6/controller_manager
    ensure_controller lite6 joint_state_broadcaster
    ensure_controller lite6 lite6_traj_controller
    log 'SUCCESS: Team 2 Lite 6 only; no Nav2 and no TurtleBots started by this script.'
    return 0
  fi

  if model_exists "$ROBOT/turtlebot4"; then
    log "REUSE: $ROBOT"
  else
    bash "$ORIGINAL" "$ROBOT"
    fresh_spawn=1
  fi
  wait_for "/$ROBOT/controller_manager" 40 node_exists "/$ROBOT/controller_manager"
  ensure_controller "$ROBOT" joint_state_broadcaster
  ensure_controller "$ROBOT" diffdrive_controller
  wait_for "/$ROBOT/odom" 20 topic_live "/$ROBOT/odom"

  # Stock TB4 bridge targets /world/warehouse; our world requires this path.
  if topic_live "/$ROBOT/scan"; then
    log "REUSE: /$ROBOT/scan"
  else
    start_bg "${ROBOT}_scan_bridge" ros2 run ros_gz_bridge parameter_bridge \
      "/world/$WORLD/model/$ROBOT/turtlebot4/link/rplidar_link/sensor/rplidar/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" \
      --ros-args \
      -r "/world/$WORLD/model/$ROBOT/turtlebot4/link/rplidar_link/sensor/rplidar/scan:=/$ROBOT/scan" \
      -r "__node:=${ROBOT}_scan_bridge"
  fi
  wait_for "/$ROBOT/scan" 20 topic_live "/$ROBOT/scan"

  # Use native TF when it works; fallback only if missing. Never create duplicate relays.
  if tf_ready "$ROBOT" "$ROBOT/odom" "$ROBOT/base_link"; then
    log "REUSE: $ROBOT native odometry TF"
  elif node_exists /milestone2_odom_tf_relay || node_exists "/${ROBOT}_team_odom_tf_relay"; then
    log 'REUSE: existing odometry TF relay'
  else
    start_bg "${ROBOT}_odom_tf" python3 "$ROOT/scripts/milestone2_team_tf.py" --robot "$ROBOT"
  fi
  wait_for "$ROBOT odom-to-base TF" 15 tf_ready "$ROBOT" "$ROBOT/odom" "$ROBOT/base_link"
  wait_for "$ROBOT odom-to-LiDAR TF" 15 tf_ready "$ROBOT" "$ROBOT/odom" "$ROBOT/turtlebot4/rplidar_link/rplidar"

  # Remove only the simulation charging dock, not the teaching station pads.
  if [[ "${MRS_REMOVE_CHARGING_DOCKS:-1}" == 1 ]] && model_exists "$ROBOT/standard_dock"; then
    gz service -s "/world/$WORLD/remove" \
      --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 3000 \
      --req "name: \"$ROBOT/standard_dock\", type: MODEL" || true
  fi

  # Localization for this team only. Do NOT use original 'nav' or 'amcl' modes:
  # both assume robot1 + robot2 exist simultaneously.
  if node_exists "/$ROBOT/amcl" && node_exists "/$ROBOT/map_server"; then
    log "REUSE: $ROBOT localization"
  else
    start_bg "${ROBOT}_localization" ros2 launch turtlebot4_navigation localization.launch.py \
      "namespace:=/$ROBOT" use_sim_time:=true "map:=$MAP" \
      "params:=$CFG/${ROBOT}_localization.yaml"
  fi
  wait_for "$ROBOT map_server active" 25 lifecycle_active "/$ROBOT/map_server"
  wait_for "$ROBOT AMCL active" 25 lifecycle_active "/$ROBOT/amcl"

  # TF existence alone does not imply a valid AMCL pose. On a fresh robot
  # spawn, always initialize once. On reuse, reinitialize ONLY if AMCL is
  # missing or outside the map. Never reset a robot simply because it moved.
  local amcl_check=(python3 "$ROOT/scripts/milestone2_team_pose_check.py"
    --robot "$ROBOT" --map "$MAP"
    --config "$CFG/milestone2_locations_and_poses.yaml")
  if (( fresh_spawn )) || ! "${amcl_check[@]}"; then
    log "INIT: $ROBOT AMCL from configured HOME"
    python3 "$ROOT/scripts/milestone2_team_amcl.py" \
      --robot "$ROBOT" --config "$CFG/milestone2_locations_and_poses.yaml"
    timeout 10 ros2 service call "/$ROBOT/request_nomotion_update" \
      std_srvs/srv/Empty '{}' >/dev/null 2>&1 || true
    wait_for "$ROBOT corrected AMCL near HOME" 10 \
      "${amcl_check[@]}" --near-home 1.2
  else
    log "REUSE: $ROBOT AMCL estimate is inside map"
  fi
  wait_for "$ROBOT map-to-base TF" 20 tf_ready "$ROBOT" map "$ROBOT/base_link"

  if node_exists "/$ROBOT/bt_navigator"; then
    log "REUSE: $ROBOT Nav2"
  else
    start_bg "${ROBOT}_nav2" ros2 launch turtlebot4_navigation nav2.launch.py \
      "namespace:=/$ROBOT" use_sim_time:=true \
      "params_file:=$CFG/${ROBOT}_nav2.yaml"
  fi
  wait_for "$ROBOT Nav2 navigator active" 35 lifecycle_active "/$ROBOT/bt_navigator"
  log "SUCCESS: $TEAM ready; only $ROBOT was requested by this script."
}

case "$MODE" in
  status) status ;;
  start) start ;;
  stop) stop_all ;;
esac
