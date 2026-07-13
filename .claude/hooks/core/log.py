import json
import os
from typing import Any


def append_json_log(filename: str, data: dict[str, Any]) -> None:
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, filename)
    log_data: list = []
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                log_data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            log_data = []
    log_data.append(data)
    with open(path, "w") as f:
        json.dump(log_data, f, indent=2)
