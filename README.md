# NemoSwarm-Grid — ROS 2 + Gazebo Harmonic baseline

This package targets **Ubuntu 22.04 + ROS 2 Humble + Gazebo Harmonic**. It creates a 100 m × 100 m warehouse floor, spawns four simulated differential-drive inspection robots, bridges camera/velocity/odometry topics to ROS 2, and runs a waypoint dispatcher plus an inventory vision node.

## Important honest limitations

- The camera and robot motion are simulated. The Nemotron node uses an explicit `MOCK` result unless `NVIDIA_API_KEY` is configured and the selected NVIDIA endpoint/model is available to your account.
- The generated robot is a differential-drive base with a gantry-shaped frame; it is not a true Cartesian gantry mechanism.
- Each robot is assigned 20 sparse sample waypoints in a 50 m × 50 m quadrant. This is a demo sampling route, not full dense shelf-level inventory coverage.
- Camera topic is `/robotN/camera/image_raw`; velocity is `/robotN/cmd_vel`; odometry is `/robotN/odom`; audit result is `/robotN/inventory_result`; shared status is `/grid_status`.

## Dependencies

Already present on the intended machine according to the user's checks: ROS 2 Humble, Gazebo Harmonic, `ros_gz_sim`, `ros_gz_bridge`, OpenCV, `cv_bridge`, and the Python OpenAI SDK.

## Build

```bash
source /opt/ros/humble/setup.bash
mkdir -p ~/nemoswarm_ws/src
cp -r ~/nvidia_inventory_swarm/nvidia_inventory_swarm ~/nemoswarm_ws/src/
cd ~/nemoswarm_ws
colcon build --symlink-install
source install/setup.bash
```

If `colcon` is not installed, install it with `sudo apt install python3-colcon-common-extensions`.

## Run

```bash
source /opt/ros/humble/setup.bash
source ~/nemoswarm_ws/install/setup.bash
ros2 launch nvidia_inventory_swarm swarm_audit.launch.py
```

The launch file starts Gazebo Harmonic, spawns four robots from SDF model files, starts ROS/Gazebo bridges, then starts the audit nodes and dispatcher. Initial simulation may take several seconds to load.

## NVIDIA API mode (optional)

```bash
export NVIDIA_API_KEY='YOUR_KEY_HERE'
```

Set the key in the same terminal before launching. Do not commit or share the key. Confirm the model identifier `nvidia/nemotron-nano-12b-v2-vl` is available to your NVIDIA API account; change the `model` parameter if needed. Without a valid key/model, the node publishes an explicitly labeled `MOCK` result.
