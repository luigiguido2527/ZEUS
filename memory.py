import json
from pathlib import Path


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if data is not None else default
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def default_memory():
    return {"user_name": "User", "facts": []}
