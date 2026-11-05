#!/usr/bin/env bash
# Milestone 2 release-candidate launcher. Additive: does not modify original startup.
# Modes: status (read-only), start (bring up missing components). It never kills processes.
set -Eeo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="$(cd "$ROOT/../.." && pwd)"
ORIGINAL="$ROOT/scripts/milestone2_start.sh"
BASE="$WS/.milestone2_runtime"
LOGS="$BASE/logs"; PIDS="$BASE/pids"
WORLD="milestone2_multi_robot_transfer"
if [[ -f "$ROOT/maps/milestone2_map.yaml" ]]; then
  DEFAULT_MAP="$ROOT/maps/milestone2_map.yaml"
else
  DEFAULT_MAP="$ROOT/maps/milestone2_map.yaml"
fi
MAP="${MRS_MAP:-$DEFAULT_MAP}"
CFG="$ROOT/config"
ENV_FILE="$BASE/source_env.bash"
mkdir -p "$LOGS" "$PIDS"

cat > "$ENV_FILE" <<'EOF'
source /opt/ros/jazzy/setup.bash
for w in turtlebot4_ws lite6_jazzy_ws milestone2_overlay_ws; do
  if [[ -f "$HOME/$w/install/setup.bash" ]]; then
    source "$HOME/$w/install/setup.bash"
  fi
done
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/install/setup.bash"
EOF
source "$ENV_FILE"

log() { printf '%s\n' "$*"; }
node_exists() { ros2 node list 2>/dev/null | grep -Fx "$1" >/dev/null; }
topic_live() { timeout 8 ros2 topic echo "$1" --once >/dev/null 2>&1; }
lifecycle_active() { [[ "$(timeout 8 ros2 lifecycle get "$1" 2>/dev/null || true)" == 'active [3]' ]]; }
world_exists() { gz service -l 2>/dev/null | grep -Fx "/world/$WORLD/control" >/dev/null; }
clock_publishers() {
  local count
  count="$(timeout 8 ros2 topic info /clock 2>/dev/null | awk '/^Publisher count:/ {print $3; exit}' || true)"
  [[ "$count" =~ ^[0-9]+$ ]] || count=0
  printf '%s\n' "$count"
}
one_clock_live() { [[ "$(clock_publishers)" == 1 ]] && topic_live /clock; }
owned_original_world() {
  local p="$PIDS/world.pid" pid cmd pgid sid
  [[ -f "$p" ]] || return 1
  pid="$(cat "$p")"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null || return 1
  cmd="$(ps -o args= -p "$pid" 2>/dev/null || true)"
  pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
  sid="$(ps -o sid= -p "$pid" | tr -d ' ')"
  [[ "$pgid" == "$pid" && "$sid" == "$pid" && "$cmd" == *'world.launch.py'* ]]
}
model_exists() {
  # Match the model name, not substrings such as lite6_station_label.
  gz model --list 2>/dev/null | grep -Fx -- "    - $1" >/dev/null ||
    gz model --list 2>/dev/null | sed -n 's/^[[:space:]]*-[[:space:]]*//p' | grep -Fx -- "$1" >/dev/null
}

wait_for() {
  local label="$1" count="$2"; shift 2
  local i
  for ((i=0; i<count; i++)); do
    if "$@"; then log "READY: $label"; return 0; fi
    sleep 2
  done
  log "NOT READY: $label (no components were stopped)" >&2
  return 1
}

# Test for a valid TF result, not merely a registered TF publisher.
tf_ready() {
  local r="$1" source="$2" target="$3" output
  output="$(timeout 8 ros2 run tf2_ros tf2_echo "$source" "$target" \
    --ros-args -r "/tf:=/$r/tf" -r "/tf_static:=/$r/tf_static" 2>&1 || true)"
  [[ "$output" == *'At time '* ]]
}

start_bg() {
  local name="$1"; shift
  local pidfile="$PIDS/safe_${name}.pid"
  local pid
  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile")"
    if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
      log "REUSE: $name (PID $pid)"
      return 0
    fi
  fi
  log "START: $name"
  setsid bash -c 'source "$1"; shift; exec "$@"' _ "$ENV_FILE" "$@" \
    > "$LOGS/safe_${name}.log" 2>&1 </dev/null &
  echo "$!" > "$pidfile"
}

controller_active() {
  local robot="$1" required="$2" output
  output="$(timeout 15 ros2 control list_controllers -c "/$robot/controller_manager" 2>/dev/null || true)"
  printf '%s\n' "$output" | grep -E "^${required}[[:space:]]+.*active" >/dev/null
}

status() {
  log '=== Milestone 2 diagnostics (READ ONLY) ==='
  if world_exists; then log 'OK: Gazebo world'; else log 'MISSING: Gazebo world'; fi
  if one_clock_live; then log 'OK: /clock (one publisher)'; else
    log "PROBLEM: /clock publisher count=$(clock_publishers)"
  fi
  for r in robot1 robot2; do
    if topic_live "/$r/odom"; then log "OK: /$r/odom"; else log "MISSING: /$r/odom"; fi
    if topic_live "/$r/scan"; then log "OK: /$r/scan"; else log "MISSING: /$r/scan"; fi
    if tf_ready "$r" "$r/odom" "$r/base_link"; then log "OK: $r odom->base TF"; else log "MISSING: $r odom->base TF"; fi
    if tf_ready "$r" map "$r/base_link"; then log "OK: $r map->base TF"; else log "MISSING: $r map->base TF"; fi
    for n in map_server amcl bt_navigator; do
      if lifecycle_active "/$r/$n"; then log "OK: /$r/$n active"; else log "NOT ACTIVE: /$r/$n"; fi
    done
  done
  if controller_active robot1 diffdrive_controller; then log 'OK: robot1 controller'; else log 'NOT ACTIVE: robot1 controller'; fi
  if controller_active robot2 diffdrive_controller; then log 'OK: robot2 controller'; else log 'NOT ACTIVE: robot2 controller'; fi
  if controller_active lite6 lite6_traj_controller; then log 'OK: Lite 6 controller'; else log 'NOT ACTIVE: Lite 6 controller'; fi
  if [[ -f "$MAP" ]]; then log "OK: map $MAP"; else log "MISSING: map $MAP"; fi
}

start() {
  if [[ ! -f "$ORIGINAL" ]]; then log "Missing $ORIGINAL" >&2; return 1; fi
  if [[ ! -f "$MAP" ]]; then log "Missing map $MAP" >&2; return 1; fi
  if [[ ! -f "$ROOT/scripts/milestone2_odom_tf.py" ]]; then
    log 'Missing scripts/milestone2_odom_tf.py (copy bundled helper first)' >&2
    return 1
  fi
  for r in robot1 robot2; do
    [[ -f "$CFG/${r}_localization.yaml" && -f "$CFG/${r}_nav2.yaml" ]] || {
      log "Missing ${r} localization/Nav2 YAML" >&2; return 1;
    }
  done

  # 1. One Gazebo world, do not create a second instance.
  local existing_clocks
  existing_clocks="$(clock_publishers)"
  if world_exists; then
    if ! owned_original_world; then
      log 'ERROR: existing world is not owned by this student runtime' >&2
      return 1
    fi
    log 'REUSE: student Gazebo world'
  else
    if [[ "$existing_clocks" != 0 ]]; then
      log "ERROR: $existing_clocks old /clock publisher(s); stop them first." >&2
      return 1
    fi
    bash "$ORIGINAL" world
  fi
  wait_for 'Gazebo world' 30 world_exists

  # 2. Only world.launch.py supplies /clock; never create another bridge.
  existing_clocks="$(clock_publishers)"
  if [[ "$existing_clocks" -gt 1 ]]; then
    log "ERROR: $existing_clocks /clock publishers; stop duplicate bridges." >&2
    return 1
  fi
  wait_for 'a single /clock publisher' 20 one_clock_live

  # 3. Spawn the two bases and the arm only if their models are absent.
  for r in robot1 robot2; do
    if model_exists "$r/turtlebot4"; then log "REUSE: $r model"; else bash "$ORIGINAL" "$r"; fi
  done
  if model_exists lite6; then log 'REUSE: Lite 6 model'; else bash "$ORIGINAL" lite6; fi
  for r in robot1 robot2 lite6; do
    wait_for "/$r/controller_manager" 40 node_exists "/$r/controller_manager"
  done

  # 4. Controller activation can remain in the original (previously fixed) routine.
  if controller_active robot1 diffdrive_controller && \
     controller_active robot2 diffdrive_controller && \
     controller_active lite6 lite6_traj_controller; then
    log 'REUSE: all controllers already active'
  else
    bash "$ORIGINAL" controllers
  fi
  wait_for 'robot1 diffdrive controller' 20 controller_active robot1 diffdrive_controller
  wait_for 'robot2 diffdrive controller' 20 controller_active robot2 diffdrive_controller
  wait_for 'Lite 6 trajectory controller' 20 controller_active lite6 lite6_traj_controller

  for r in robot1 robot2; do
    wait_for "/$r/odom" 15 topic_live "/$r/odom"
  done

  # 5. Use custom LiDAR bridge for THIS world only when no valid scan is flowing.
  for r in robot1 robot2; do
    if topic_live "/$r/scan"; then
      log "REUSE: /$r/scan"
    else
      start_bg "${r}_scan_bridge" ros2 run ros_gz_bridge parameter_bridge \
        "/world/$WORLD/model/$r/turtlebot4/link/rplidar_link/sensor/rplidar/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" \
        --ros-args \
        -r "/world/$WORLD/model/$r/turtlebot4/link/rplidar_link/sensor/rplidar/scan:=/$r/scan" \
        -r "__node:=${r}_scan_bridge"
    fi
    wait_for "/$r/scan" 15 topic_live "/$r/scan"
  done

  # 6. Fallback relay only when an odometry TF actually fails to appear.
  if tf_ready robot1 robot1/odom robot1/base_link && \
     tf_ready robot2 robot2/odom robot2/base_link; then
    log 'REUSE: native odometry TF for both robots'
  elif node_exists /milestone2_odom_tf_relay; then
    log 'REUSE: existing odometry TF relay'
  else
    start_bg odom_tf_relay python3 "$ROOT/scripts/milestone2_odom_tf.py"
  fi
  for r in robot1 robot2; do
    wait_for "$r odom->base TF" 12 tf_ready "$r" "$r/odom" "$r/base_link"
    wait_for "$r odom->LiDAR TF" 12 tf_ready "$r" "$r/odom" "$r/turtlebot4/rplidar_link/rplidar"
  done

  # 7. Omit charging dock models, not R1_DOCK/R2_DOCK visual pads.
  if [[ "${MRS_REMOVE_CHARGING_DOCKS:-1}" == 1 ]]; then
    for r in robot1 robot2; do
      if model_exists "$r/standard_dock"; then
        log "REMOVE: $r charging dock model"
        gz service -s "/world/$WORLD/remove" \
          --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean \
          --timeout 3000 --req "name: \"$r/standard_dock\", type: MODEL" || true
      fi
    done
  fi

  # 8. Localization BEFORE Nav2. Never create duplicate localization nodes.
  for r in robot1 robot2; do
    if node_exists "/$r/amcl" && node_exists "/$r/map_server"; then
      log "REUSE: $r localization nodes"
    else
      start_bg "${r}_localization" ros2 launch turtlebot4_navigation localization.launch.py \
        "namespace:=/$r" use_sim_time:=true "map:=$MAP" \
        "params:=$CFG/${r}_localization.yaml"
    fi
    wait_for "$r map_server active" 25 lifecycle_active "/$r/map_server"
    wait_for "$r amcl active" 25 lifecycle_active "/$r/amcl"
  done

  # 9. Do not reset a working AMCL estimate during an idempotent start.
  if tf_ready robot1 map robot1/base_link && \
     tf_ready robot2 map robot2/base_link; then
    log 'REUSE: both valid map->base TF chains; no initial-pose reset'
  else
    MAP="$MAP" bash "$ORIGINAL" amcl
    for r in robot1 robot2; do
      timeout 8 ros2 service call "/$r/request_nomotion_update" std_srvs/srv/Empty '{}' \
        >/dev/null 2>&1 || true
    done
  fi
  for r in robot1 robot2; do
    wait_for "$r map->base TF" 12 tf_ready "$r" map "$r/base_link"
  done

  # 10. Nav2 LAST; do not start a duplicate navigator if one already exists.
  for r in robot1 robot2; do
    if node_exists "/$r/bt_navigator"; then
      log "REUSE: $r Nav2 nodes"
    else
      start_bg "${r}_nav2" ros2 launch turtlebot4_navigation nav2.launch.py \
        "namespace:=/$r" use_sim_time:=true "params_file:=$CFG/${r}_nav2.yaml"
    fi
    wait_for "$r Nav2 navigator active" 25 lifecycle_active "/$r/bt_navigator"
  done
  log 'SUCCESS: both robot navigation stacks active. No running processes were stopped.'
}

case "${1:-status}" in
  status) status ;;
  start) start ;;
  *) echo "Usage: bash scripts/milestone2_start_safe.sh [status|start]" >&2; exit 2 ;;
esac
