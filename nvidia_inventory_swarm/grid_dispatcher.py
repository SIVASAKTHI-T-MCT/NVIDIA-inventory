#!/usr/bin/env python3
"""Dispatch non-overlapping grid sweeps to four simulated robots.

The 100 m x 100 m floor is divided into four 50 m x 50 m quadrants.
Each robot receives 20 sparse sample waypoints in its assigned quadrant.
The shared /grid_status topic carries JSON status messages. The broker is
centralized in this executable for deterministic demo behavior; robots publish
completion/status events to the shared topic.
"""
import json
import math
import time
from typing import Dict, List, Tuple

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import String


ROBOTS = ("robot1", "robot2", "robot3", "robot4")
FLOOR_MIN, FLOOR_MAX = -50.0, 50.0
QUADRANTS = {
    "robot1": (-50.0, 0.0, 0.0, 50.0),    # x_min, x_max, y_min, y_max
    "robot2": (0.0, 50.0, 0.0, 50.0),
    "robot3": (-50.0, 0.0, -50.0, 0.0),
    "robot4": (0.0, 50.0, -50.0, 0.0),
}


def sparse_waypoints(bounds: Tuple[float, float, float, float], count: int = 20):
    """Return a deterministic serpentine sample track within a rectangle."""
    xmin, xmax, ymin, ymax = bounds
    rows = 4
    cols = math.ceil(count / rows)
    xs = [xmin + (i + 0.5) * (xmax - xmin) / cols for i in range(cols)]
    ys = [ymin + (j + 0.5) * (ymax - ymin) / rows for j in range(rows)]
    points = []
    for row, y in enumerate(ys):
        row_xs = xs if row % 2 == 0 else list(reversed(xs))
        for x in row_xs:
            points.append((x, y))
            if len(points) == count:
                return points
    return points


class GridDispatcher(Node):
    def __init__(self):
        super().__init__("grid_dispatcher")
        self.declare_parameter("waypoints_per_robot", 20)
        self.declare_parameter("linear_speed", 0.8)
        self.declare_parameter("position_tolerance", 0.25)
        self.declare_parameter("control_rate_hz", 10.0)
        self.declare_parameter("start_delay_sec", 3.0)

        self.speed = float(self.get_parameter("linear_speed").value)
        self.tolerance = float(self.get_parameter("position_tolerance").value)
        self.start_delay = float(self.get_parameter("start_delay_sec").value)
        n = int(self.get_parameter("waypoints_per_robot").value)
        if n < 1:
            raise ValueError("waypoints_per_robot must be >= 1")

        self.paths: Dict[str, List[Tuple[float, float]]] = {
            name: sparse_waypoints(QUADRANTS[name], n) for name in ROBOTS
        }
        self.index = {name: 0 for name in ROBOTS}
        self.position = {name: [0.0, 0.0] for name in ROBOTS}
        self.yaw = {name: 0.0 for name in ROBOTS}
        self.have_odom = {name: False for name in ROBOTS}
        self.odom_subs = {
            name: self.create_subscription(Odometry, f"/{name}/odom",
                                           lambda msg, robot=name: self.odom_callback(robot, msg), 10)
            for name in ROBOTS
        }
        self.started_at = time.monotonic()
        self.done = set()
        self.claimed = {name: name for name in ROBOTS}
        self.cmd_pubs = {
            name: self.create_publisher(Twist, f"/{name}/cmd_vel", 10)
            for name in ROBOTS
        }
        self.status_pub = self.create_publisher(String, "/grid_status", 50)
        self.status_sub = self.create_subscription(String, "/grid_status", self.status_callback, 50)
        hz = float(self.get_parameter("control_rate_hz").value)
        self.timer = self.create_timer(1.0 / max(hz, 1.0), self.control_tick)
        self.get_logger().info("NemoSwarm dispatcher initialized with 4 non-overlapping 50 m x 50 m quadrants.")
        for name, path in self.paths.items():
            self.get_logger().info(f"{name}: assigned {len(path)} sample waypoints.")

    def odom_callback(self, robot, msg):
        self.position[robot][0] = msg.pose.pose.position.x
        self.position[robot][1] = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.yaw[robot] = math.atan2(siny_cosp, cosy_cosp)
        self.have_odom[robot] = True

    def publish_status(self, robot, state, waypoint=None, detail=""):
        msg = String()
        msg.data = json.dumps({
            "robot": robot, "state": state, "waypoint_index": waypoint,
            "detail": detail, "stamp_monotonic": time.monotonic()
        })
        self.status_pub.publish(msg)

    def status_callback(self, msg):
        try:
            data = json.loads(msg.data)
        except (ValueError, TypeError):
            self.get_logger().warning("Ignoring malformed /grid_status message")
            return
        robot = data.get("robot")
        state = data.get("state")
        if robot in ROBOTS and state == "complete":
            self.done.add(robot)

    def control_tick(self):
        if time.monotonic() - self.started_at < self.start_delay:
            return
        for name in ROBOTS:
            if name in self.done:
                self.stop_robot(name)
                continue
            if not self.have_odom[name]:
                self.stop_robot(name)
                self.publish_status(name, "waiting_for_odom", None, "waiting for Gazebo odometry bridge")
                continue
            path = self.paths[name]
            idx = self.index[name]
            if idx >= len(path):
                self.stop_robot(name)
                self.done.add(name)
                self.publish_status(name, "complete", idx, "all assigned waypoints visited")
                continue
            tx, ty = path[idx]
            px, py = self.position[name]
            dx, dy = tx - px, ty - py
            distance = math.hypot(dx, dy)
            cmd = Twist()
            if distance <= self.tolerance:
                self.index[name] += 1
                self.publish_status(name, "waypoint_complete", idx, f"x={tx:.2f},y={ty:.2f}")
                self.get_logger().info(f"{name} completed waypoint {idx + 1}/{len(path)}")
                if self.index[name] >= len(path):
                    self.publish_status(name, "complete", self.index[name], "sweep finished")
                    self.done.add(name)
                continue
            # Closed-loop differential-drive control using Gazebo odometry.
            desired_yaw = math.atan2(dy, dx)
            current_yaw = self.yaw[name]
            yaw_error = math.atan2(math.sin(desired_yaw-current_yaw), math.cos(desired_yaw-current_yaw))
            cmd.angular.z = max(-0.7, min(0.7, 1.8 * yaw_error))
            if abs(yaw_error) < 0.35:
                cmd.linear.x = min(self.speed, 0.6 * distance)
            self.cmd_pubs[name].publish(cmd)
            self.publish_status(name, "moving", idx, f"target=({tx:.2f},{ty:.2f})")
        if len(self.done) == len(ROBOTS):
            self.get_logger().info("All four robot assignments completed.")
            for name in ROBOTS:
                self.stop_robot(name)
            self.timer.cancel()

    def stop_robot(self, name):
        self.cmd_pubs[name].publish(Twist())


def main(args=None):
    rclpy.init(args=args)
    node = GridDispatcher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        for name in ROBOTS:
            node.stop_robot(name)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
