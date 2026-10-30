
from setuptools import setup, find_packages
from glob import glob
import os

package_name = "nvidia_inventory_swarm"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),

        # Robot meshes
        (
            os.path.join("share", package_name, "meshes"),
            glob("meshes/*.stl"),
        ),

        # Gazebo models
        (
            os.path.join("share", package_name, "models"),
            glob("models/*"),
        ),

        # URDF
        (
            os.path.join("share", package_name, "urdf"),
            glob("urdf/*.urdf"),
        ),

        # Launch files
        (
            os.path.join("share", package_name, "launch"),
            glob("launch/*.launch.py"),
        ),

        # Gazebo worlds
        (
            os.path.join("share", package_name, "worlds"),
            glob("worlds/*.world"),
        ),

        # Configuration
        (
            os.path.join("share", package_name, "config"),
            glob("config/*"),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="NemoSwarm-Grid Team",
    maintainer_email="maintainer@example.com",
    description="Four-agent simulated inventory auditing swarm using ROS 2, Gazebo Harmonic, and NVIDIA Nemotron vision.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "grid_dispatcher = nvidia_inventory_swarm.grid_dispatcher:main",
            "nemotron_vla_node = nvidia_inventory_swarm.nemotron_vla_node:main",
        ],
    },
)
