#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/jazzy/setup.bash

for w in turtlebot4_ws lite6_jazzy_ws milestone2_overlay_ws mrs_milestone2_ws; do
  if [[ -f "$HOME/$w/install/setup.bash" ]]; then
    source "$HOME/$w/install/setup.bash"
  fi
done

check_topic() {
  if timeout 10 ros2 topic echo "$1" --once >/dev/null 2>&1; then
    echo "OK: $1"
  else
    echo "FAIL: $1"
  fi
}

echo "=== SIMULATION CLOCK ==="
check_topic /clock

for robot in robot1 robot2; do
  echo "=== $robot ==="
  check_topic /$robot/odom
  check_topic /$robot/scan

  ros2 lifecycle get /$robot/map_server || true
  ros2 lifecycle get /$robot/amcl || true
  ros2 lifecycle get /$robot/bt_navigator || true
done

echo "=== NAVIGATION AND ARM ACTIONS ==="
ros2 action list | grep -E \
'navigate_to_pose|follow_joint_trajectory' || true

echo "=== CONTROLLERS ==="
for robot in robot1 robot2 lite6; do
  echo "$robot:"
  timeout 25 ros2 control list_controllers \
    -c /$robot/controller_manager || \
    echo "WARNING: $robot controller query unavailable"
done
