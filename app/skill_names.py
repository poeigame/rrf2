from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent.parent
SKILL_NAME_FILE = BASE_DIR / "data" / "skill_names.json"
API_URL = "https://www.divine-pride.net/api/database/Skill/{skill_id}?apiKey={api_key}"


def _normalize_mapping(raw: object) -> dict[int, str]:
    mapping: dict[int, str] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            try:
                skill_id = int(key)
            except Exception:
                continue
            if isinstance(value, str) and value.strip():
                mapping[skill_id] = value.strip()
    return mapping


@lru_cache(maxsize=1)
def _load_skill_name_map() -> dict[int, str]:
    if not SKILL_NAME_FILE.exists():
        return {}

    try:
        raw = json.loads(SKILL_NAME_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return _normalize_mapping(raw)


def _save_skill_name_map(mapping: dict[int, str]) -> None:
    SKILL_NAME_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {str(k): v for k, v in sorted(mapping.items(), key=lambda x: x[0])}
    SKILL_NAME_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _load_skill_name_map.cache_clear()


def fetch_skill_name(skill_id: int, api_key: str, timeout: float = 10.0) -> str | None:
    url = API_URL.format(skill_id=skill_id, api_key=api_key)
    request = Request(url, headers={"User-Agent": "rrf-parser/1.0"})
    try:
        with urlopen(request, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    name = data.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def update_skill_names(skill_ids: Iterable[int], api_key: str, timeout: float = 10.0) -> dict[int, str]:
    mapping = dict(_load_skill_name_map())
    updated: dict[int, str] = {}

    for skill_id in sorted({int(s) for s in skill_ids if isinstance(s, int) or str(s).isdigit()}):
        if skill_id in mapping:
            continue
        name = fetch_skill_name(skill_id=skill_id, api_key=api_key, timeout=timeout)
        if not name:
            continue
        mapping[skill_id] = name
        updated[skill_id] = name

    if updated:
        _save_skill_name_map(mapping)

    return updated



def get_skill_name(skill_id: int) -> str:
    mapping = _load_skill_name_map()
    if skill_id in mapping:
        return mapping[skill_id]

    api_key = os.getenv("DIVINE_PRIDE_API_KEY", "").strip()
    if api_key:
        updated = update_skill_names([skill_id], api_key=api_key)
        if skill_id in updated:
            return updated[skill_id]

    return f"skill_{skill_id}"
