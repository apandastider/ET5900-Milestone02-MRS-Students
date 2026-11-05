#!/usr/bin/env python3
"""Read-only AMCL/map validation for one isolated TurtleBot 4 team.

Requires ROS 2 Jazzy, rclpy, PyYAML, and the installed milestone world map.
"""
import argparse
import math
import sys
import time
from pathlib import Path

import yaml
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy


def pgm_dimensions(path: Path):
    with path.open('rb') as fh:
        tokens = []
        while len(tokens) < 4:
            line = fh.readline()
            if not line:
                raise ValueError('Incomplete PGM header')
            line = line.split(b'#', 1)[0]
            tokens.extend(line.split())
        if tokens[0] not in (b'P2', b'P5'):
            raise ValueError('Unsupported map image format (expect PGM)')
        return int(tokens[1]), int(tokens[2])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--robot', required=True, choices=('robot1', 'robot2'))
    p.add_argument('--map', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=10.0)
    p.add_argument('--near-home', type=float, default=None,
                   help='Require pose within this many meters of configured HOME')
    args = p.parse_args()
    meta = yaml.safe_load(args.map.read_text())
    res = float(meta['resolution'])
    ox, oy = map(float, meta['origin'][:2])
    image = Path(meta['image'])
    if not image.is_absolute():
        image = args.map.parent / image
    width, height = pgm_dimensions(image)
    xmax = ox + width * res
    ymax = oy + height * res
    home_key = 'R1_HOME' if args.robot == 'robot1' else 'R2_HOME'
    home = yaml.safe_load(args.config.read_text())['navigation_locations'][home_key]

    rclpy.init()
    node = Node(f'{args.robot}_amcl_sanity_check')
    latest = []
    pose_qos = QoSProfile(
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )
    pose_sub = node.create_subscription(
        PoseWithCovarianceStamped, f'/{args.robot}/amcl_pose',
        latest.append, pose_qos,
    )
    try:
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline and not latest:
            rclpy.spin_once(node, timeout_sec=0.25)
        if not latest:
            print(f'FAIL: no /{args.robot}/amcl_pose', file=sys.stderr)
            return 2
        pos = latest[-1].pose.pose.position
        x, y = float(pos.x), float(pos.y)
        inside = ox <= x <= xmax and oy <= y <= ymax
        distance = math.hypot(x-float(home['x']), y-float(home['y']))
        print(f'{args.robot}: AMCL=({x:.3f},{y:.3f}); '
              f'map x=[{ox:.3f},{xmax:.3f}], y=[{oy:.3f},{ymax:.3f}]; '
              f'distance from {home_key}={distance:.3f} m')
        if not inside:
            print('FAIL: localization pose outside map', file=sys.stderr)
            return 1
        if args.near_home is not None and distance > args.near_home:
            print('FAIL: localization pose too far from configured HOME', file=sys.stderr)
            return 1
        print('PASS: localization sanity check')
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
