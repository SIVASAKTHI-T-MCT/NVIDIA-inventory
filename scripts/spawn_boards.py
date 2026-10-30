#!/usr/bin/env python3
import random
import json
import subprocess
import time
from pathlib import Path

random.seed(42)

ROOT = Path.home() / "nemoswarm_ws/src/nvidia_inventory_swarm"
records = []
positions = []

# 50 green + 50 red boards
colours = ["green"] * 50 + ["red"] * 50
random.shuffle(colours)

for i, colour in enumerate(colours, 1):
    # Keep boards separated by at least 5 units.
    for attempt in range(1000):
        x = random.uniform(-43, 43)
        y = random.uniform(-43, 43)

        if all((x-px)**2 + (y-py)**2 >= 25 for px, py in positions):
            positions.append((x, y))
            break
    else:
        raise RuntimeError("Could not find a free board position")

    name = f"board_{i:03d}"
    rgb = "0.0 0.8 0.1 1" if colour == "green" else "0.9 0.05 0.05 1"

    sdf = f"""<sdf version="1.9">
    <model name="{name}">
      <static>false</static>
      <pose>{x} {y} 2.5 0 0 0</pose>
      <link name="link">
        <visual name="visual">
          <geometry><box><size>4 3 0.3</size></box></geometry>
          <material><ambient>{rgb}</ambient><diffuse>{rgb}</diffuse></material>
        </visual>
        <collision name="collision">
  <geometry><box><size>4 3 0.3</size></box></geometry>
  <surface>
    <friction>
      <ode>
        <mu>0.8</mu>
        <mu2>0.8</mu2>
      </ode>
    </friction>
  </surface>
</collision>
      </link>
    </model>
    </sdf>"""

    request = "sdf: " + json.dumps(sdf)
    result = subprocess.run([
        "gz", "service",
        "-s", "/world/inventory_warehouse/create",
        "--reqtype", "gz.msgs.EntityFactory",
        "--reptype", "gz.msgs.Boolean",
        "--timeout", "3000",
        "--req", request
    ], capture_output=True, text=True)

    records.append({
        "id": name, "colour": colour,
        "x": round(x, 3), "y": round(y, 3), "z": 0.30
    })

    if i % 10 == 0:
        print(f"Requested {i}/100 boards")

    time.sleep(0.05)

(ROOT / "config/board_inventory.json").write_text(
    json.dumps(records, indent=2)
)

print("Finished. Inventory metadata saved.")