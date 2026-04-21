from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.skill_names import SKILL_NAME_FILE, update_skill_names


def _extract_skill_ids_from_report(path: Path) -> set[int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    skill_ids: set[int] = set()

    for item in (data.get("skill_summary") or []):
        value = item.get("skill_id")
        if isinstance(value, int):
            skill_ids.add(value)

    for entry in (data.get("skill_by_player") or []):
        for item in (entry.get("skill_summary") or []):
            value = item.get("skill_id")
            if isinstance(value, int):
                skill_ids.add(value)

    aggregates = data.get("aggregates") or {}
    for item in (aggregates.get("skill_summary") or []):
        value = item.get("skill_id")
        if isinstance(value, int):
            skill_ids.add(value)

    return skill_ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync skill names from Divine Pride API to data/skill_names.json")
    parser.add_argument("--api-key", default=os.getenv("DIVINE_PRIDE_API_KEY", ""), help="Divine Pride API key")
    parser.add_argument("--skills", nargs="*", type=int, default=[], help="Skill IDs to fetch")
    parser.add_argument("--report-json", type=Path, default=None, help="Path to parser JSON output to extract skill IDs")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    api_key = (args.api_key or "").strip()
    if not api_key:
        print("Missing API key. Use --api-key or set DIVINE_PRIDE_API_KEY")
        return 2

    skill_ids: set[int] = set(args.skills)
    if args.report_json is not None:
        if not args.report_json.exists():
            print(f"Report file not found: {args.report_json}")
            return 2
        skill_ids.update(_extract_skill_ids_from_report(args.report_json))

    if not skill_ids:
        print("No skill IDs provided. Use --skills or --report-json")
        return 1

    updated = update_skill_names(sorted(skill_ids), api_key=api_key, timeout=args.timeout)
    print(f"Updated {len(updated)} skill names.")
    print(f"Output: {SKILL_NAME_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
