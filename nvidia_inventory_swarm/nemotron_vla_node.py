#!/usr/bin/env python3
"""Capture camera frames and request zero-shot NVIDIA Nemotron visual counts.

Set NVIDIA_API_KEY before launching to enable the remote model. The API URL and
model are parameters because NVIDIA's supported endpoint/model identifiers may
vary by account. Without credentials, or on request failure, the node emits an
explicit MOCK result; it never represents mock counts as model predictions.
"""
import base64
import json
import os
import re
import threading
import time
from typing import Optional

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String

SYSTEM_PROMPT = (
    "You are an industrial inventory auditing vision AI. Analyze this image cell "
    "and accurately count the distinct NVIDIA hardware modules based strictly on "
    "their color profile: Emerald Green boards (Jetson Nano), Matte Dark Grey/Silver "
    "assemblies (Orin Nano), Jet Black cages (AGX Xavier), and Metallic Silver/Copper "
    "modules (AGX Orin Industrial). Output the response strictly as a structured "
    "summary: 'Green: X, Grey: Y, Black: Z, Silver: W'."
)
RESULT_RE = re.compile(
    r"Green\s*:\s*(\d+)\s*,\s*Grey\s*:\s*(\d+)\s*,\s*Black\s*:\s*(\d+)\s*,\s*Silver\s*:\s*(\d+)",
    re.IGNORECASE,
)


class NemotronVlaNode(Node):
    def __init__(self):
        super().__init__("nemotron_vla_node")
        self.declare_parameter("image_topic", "camera/image_raw")
        self.declare_parameter("result_topic", "inventory_result")
        self.declare_parameter("grid_status_topic", "/grid_status")
        self.declare_parameter("api_base_url", "https://integrate.api.nvidia.com/v1")
        self.declare_parameter("model", "nvidia/nemotron-nano-12b-v2-vl")
        self.declare_parameter("request_timeout_sec", 12.0)
        self.declare_parameter("max_image_width", 1280)
        self.declare_parameter("mock_counts", "Green: 0, Grey: 0, Black: 0, Silver: 0")
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.request_in_flight = False
        self.last_frame_time = 0.0
        self.last_digest = None
        self.result_pub = self.create_publisher(String, self.get_parameter("result_topic").value, 10)
        self.status_pub = self.create_publisher(String, self.get_parameter("grid_status_topic").value, 20)
        self.image_sub = self.create_subscription(
            Image, self.get_parameter("image_topic").value, self.image_callback, 10
        )
        self.get_logger().info(f"Listening for images on {self.get_parameter('image_topic').value}")
        if not os.environ.get("NVIDIA_API_KEY"):
            self.get_logger().warning("NVIDIA_API_KEY missing: audit requests will use explicit MOCK fallback.")

    def image_callback(self, msg):
        now = time.monotonic()
        if now - self.last_frame_time < 0.5:
            return
        self.last_frame_time = now
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            max_width = int(self.get_parameter("max_image_width").value)
            if frame.shape[1] > max_width:
                scale = max_width / float(frame.shape[1])
                frame = cv2.resize(frame, (max_width, int(frame.shape[0] * scale)))
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                raise RuntimeError("OpenCV failed to encode image")
            image_b64 = base64.b64encode(encoded.tobytes()).decode("ascii")
        except Exception as exc:
            self.get_logger().error(f"Frame conversion failed: {exc}")
            return

        with self.lock:
            if self.request_in_flight:
                return
            self.request_in_flight = True
        thread = threading.Thread(target=self.audit_worker, args=(image_b64,), daemon=True)
        thread.start()

    def audit_worker(self, image_b64):
        try:
            result, source = self.call_nemotron(image_b64)
        except Exception as exc:
            self.get_logger().warning(f"Vision request failed; using mock fallback: {exc}")
            result, source = self.mock_result(), "MOCK"
        finally:
            with self.lock:
                self.request_in_flight = False
        payload = {
            "robot": self.get_namespace().strip("/") or "robot",
            "result": result,
            "source": source,
            "timestamp_unix": time.time(),
        }
        out = String()
        out.data = json.dumps(payload)
        self.result_pub.publish(out)
        status = String()
        status.data = json.dumps({
            "robot": payload["robot"], "state": "audit_result",
            "detail": f"{source}: {result}", "stamp_monotonic": time.monotonic()
        })
        self.status_pub.publish(status)
        self.get_logger().info(f"{source} inventory result: {result}")

    def call_nemotron(self, image_b64):
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            return self.mock_result(), "MOCK"
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the openai Python package to enable NVIDIA API calls") from exc

        client = OpenAI(
            base_url=self.get_parameter("api_base_url").value,
            api_key=api_key,
            timeout=float(self.get_parameter("request_timeout_sec").value),
            max_retries=0,
        )
        model = self.get_parameter("model").value
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=100,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "Audit this inspection image. Return only the required summary."},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image_b64}},
                ]},
            ],
        )
        content = response.choices[0].message.content or ""
        match = RESULT_RE.search(content)
        if not match:
            raise ValueError(f"Model response did not match required count format: {content[:160]!r}")
        normalized = f"Green: {int(match.group(1))}, Grey: {int(match.group(2))}, Black: {int(match.group(3))}, Silver: {int(match.group(4))}"
        return normalized, "NVIDIA_API"

    def mock_result(self):
        value = str(self.get_parameter("mock_counts").value)
        match = RESULT_RE.fullmatch(value.strip())
        if not match:
            return "Green: 0, Grey: 0, Black: 0, Silver: 0"
        return f"Green: {int(match.group(1))}, Grey: {int(match.group(2))}, Black: {int(match.group(3))}, Silver: {int(match.group(4))}"


def main(args=None):
    rclpy.init(args=args)
    node = NemotronVlaNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
