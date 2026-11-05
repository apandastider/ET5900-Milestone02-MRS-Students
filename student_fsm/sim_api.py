"""Fake robot action adapter: --simulate checks student FSM logic without ROS/Gazebo.

A simulated 'success' is NOT evidence of actual robot navigation or motion.
"""

class SimRobotAPI:
    def navigate(self, robot, location_name):
        if robot not in {'robot1', 'robot2'}:
            raise ValueError(f'Unsupported robot: {robot}')
        print(f'[SIM] Nav2 {robot} -> {location_name}: SUCCEEDED', flush=True)
        return True

    def arm_to(self, pose_name):
        if pose_name not in {'HOME', 'R1_PICK', 'R2_PLACE'}:
            raise ValueError(f'Unsupported Lite 6 pose: {pose_name}')
        print(f'[SIM] Lite 6 -> {pose_name}: SUCCEEDED', flush=True)
        return True
