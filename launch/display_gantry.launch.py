import os

from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from launch_ros.parameter_descriptions import ParameterValue

def generate_launch_description():

    package_path = get_package_share_directory('nvidia_inventory_swarm')
    urdf_path = os.path.join(package_path, 'urdf', 'gantry_robot.urdf')

    with open(urdf_path, 'r') as file:
        robot_description = file.read()

    robot_description = ParameterValue(robot_description, value_type=str)

    return LaunchDescription([

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': robot_description,
                'publish_robot_description': True
            }]
        ),

        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            output='screen'
        ),

        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen'
        )
    ])