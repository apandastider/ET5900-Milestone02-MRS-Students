import os
import shutil
import subprocess

REQUIRED_ROS_PACKAGES = [
    'turtlebot4_gz_bringup',
    'turtlebot4_navigation',
    'nav2_bringup',
    'ros_gz_sim',
    'ros_gz_bridge',
]

RECOMMENDED_LITE6_PACKAGES = [
    'xarm_moveit_config',
    'xarm_gazebo',
]


def ros_pkg_exists(name):
    try:
        subprocess.run(
            ['ros2', 'pkg', 'prefix', name],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def main():
    print('=== ET 5900 Milestone 2 prerequisite check ===')
    print('ROS_DISTRO =', os.environ.get('ROS_DISTRO', '<not sourced>'))

    if shutil.which('gz'):
        print('[OK] gz command found')
    else:
        print('[MISSING] gz command not found')

    for pkg in REQUIRED_ROS_PACKAGES:
        print(('[OK]      ' if ros_pkg_exists(pkg) else '[MISSING] ') + pkg)

    for pkg in RECOMMENDED_LITE6_PACKAGES:
        print(('[OK]      ' if ros_pkg_exists(pkg) else '[CHECK]   ') + pkg)

    print('\nExpected course target: ROS 2 Jazzy + Gazebo Harmonic.')
    print('Lite 6 packages may live in the instructor-provided source workspace.')


if __name__ == '__main__':
    main()
