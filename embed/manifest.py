import json
import os


def load_manifest(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_manifest(path: str, mapping: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, sort_keys=True, indent=2)


def diff(current: dict, previous: dict) -> dict:
    to_upsert = sorted(k for k, v in current.items() if previous.get(k) != v)
    to_delete = sorted(k for k in previous if k not in current)
    return {"to_upsert": to_upsert, "to_delete": to_delete}
