import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory

ROBOTS = [
    ("robot1", -25.0, 25.0),
    ("robot2", 25.0, 25.0),
    ("robot3", -25.0, -25.0),
    ("robot4", 25.0, -25.0),
]

def generate_launch_description():
    share = get_package_share_directory("nvidia_inventory_swarm")
    world = os.path.join(share, "worlds", "inventory_warehouse.world")
    gz_launch = os.path.join(get_package_share_directory("ros_gz_sim"), "launch", "gz_sim.launch.py")
    actions = [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gz_launch),
        launch_arguments={"gz_args": f"-r -v 3 {world}"}.items(),
    )]
    for i, (name, x, y) in enumerate(ROBOTS):
        model = os.path.join(share, "models", f"{name}.sdf")
        actions.append(TimerAction(period=4.0 + i * 1.5, actions=[Node(
            package="ros_gz_sim", executable="create", name=f"spawn_{name}",
            arguments=["-world", "inventory_warehouse", "-file", model, "-name", name,
                       "-x", str(x), "-y", str(y), "-z", "0"], output="screen")]))
        actions.append(Node(package="ros_gz_bridge", executable="parameter_bridge", name=f"bridge_{name}",
            arguments=[f"/{name}/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
                       f"/{name}/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
                       f"/{name}/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image"], output="screen"))
        actions.append(TimerAction(period=8.0 + i * 1.0, actions=[Node(
            package="nvidia_inventory_swarm", executable="nemotron_vla_node", namespace=name,
            name="nemotron_vla_node", parameters=[{"image_topic": "camera/image_raw",
                "result_topic": "inventory_result"}], output="screen")]))
    actions.append(TimerAction(period=12.0, actions=[Node(
        package="nvidia_inventory_swarm", executable="grid_dispatcher", name="grid_dispatcher",
        output="screen", parameters=[{"waypoints_per_robot": 20, "linear_speed": 0.8,
            "position_tolerance": 0.8, "control_rate_hz": 10.0, "start_delay_sec": 3.0}])]))
    return LaunchDescription(actions)
