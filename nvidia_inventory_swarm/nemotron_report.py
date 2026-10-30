
import os
import time
import requests
import json
from datetime import datetime

# NVIDIA Nemotron configuration
API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = os.getenv(
    "NVIDIA_MODEL",
    "nvidia/nemotron-3-nano-30b-a3b"
)

# Current simulated warehouse inventory
inventory = {
    "project": "NemoSwarm-Grid",
    "total_boards": 100,
    "green_boards": 50,
    "red_boards": 50,
    "inspection_status": "Completed",
    "inspection_method": "Gazebo simulation inventory data"
}


def generate_report():

    print("\n==========================================")
    print("       NEMOSWARM-GRID INSPECTION")
    print("==========================================")
    print("Waiting 20 seconds for inspection...")
    
    for remaining in range(20, 0, -1):
        print(f"\rGenerating report in {remaining:02d} seconds...",
              end="", flush=True)
        time.sleep(1)

    print("\n\nInventory data collected:")
    print(json.dumps(inventory, indent=4))

    api_key = os.getenv("NVIDIA_API_KEY")

    if not api_key:
        print("\nERROR: NVIDIA_API_KEY is not configured.")
        return

    prompt = f"""
    You are the AI warehouse inspection analyst of NemoSwarm-Grid.

    Analyse this warehouse inventory:

    {json.dumps(inventory, indent=2)}

    Generate a professional inspection report.

    Include:
    1. Total boards: 100
    2. Green boards: 50
    3. Red boards: 50
    4. Inventory distribution percentages.
    5. Inspection completion status.
    6. Final conclusion.

    Use only the supplied inventory data.
    Do not invent measurements or observations.
    """

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an industrial warehouse inventory analyst."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 1000,
        "stream": False
    }

    try:
        print("\nConnecting to NVIDIA Nemotron...")

        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=120
        )

        response.raise_for_status()

        result = response.json()
        report = result["choices"][0]["message"]["content"]

        print("\n==========================================")
        print("       NVIDIA NEMOTRON AI REPORT")
        print("==========================================\n")

        print(report)

        print("\n==========================================")
        print("       INSPECTION REPORT COMPLETED")
        print("==========================================")

    except requests.exceptions.RequestException as error:
        print("\nNVIDIA API request failed:")
        print(error)


if __name__ == "__main__":
    generate_report()
