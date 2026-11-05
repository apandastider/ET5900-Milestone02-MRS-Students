#!/usr/bin/env bash
set -e

source /opt/ros/jazzy/setup.bash

cd "$(dirname "$0")/../../../../" 2>/dev/null || true

echo "Build from your workspace root instead:"
echo "  colcon build --symlink-install --packages-select mrs_milestone2"
echo "  source install/setup.bash"
echo "  ros2 run mrs_milestone2 check_prerequisites"
