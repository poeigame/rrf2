from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.parser_service import safe_parse_rrf_bytes


def parse_file(path: Path) -> dict:
    data = path.read_bytes()
    result = safe_parse_rrf_bytes(
        data,
        filename=path.name,
        mode="decoded",
        include_events=False,
        include_aggregates=True,
    )
    if result["errors"]:
        return {"file": path.name, "errors": result["errors"]}

    aggregates = result.get("aggregates") or {}
    damage = aggregates.get("damage_overview") or {}
    skills = aggregates.get("skill_usage") or []
    top_skills = sorted(skills, key=lambda s: s.get("total_damage", 0), reverse=True)[:10]

    return {
        "file": path.name,
        "event_type_counts": result.get("summary", {}).get("event_type_counts", {}),
        "total_skill_damage": damage.get("total_skill_damage", 0),
        "overall_skill_dps": damage.get("overall_skill_dps", 0),
        "overall_skill_uses_per_second": damage.get("overall_skill_uses_per_second", 0),
        "top_skills": [
            {
                "skill_id": s.get("skill_id"),
                "uses": s.get("uses"),
                "hits": s.get("hits"),
                "total_damage": s.get("total_damage"),
                "dps": s.get("dps"),
                "uses_per_second": s.get("uses_per_second"),
            }
            for s in top_skills
        ],
    }


def load_rrf_files(input_dir: Path) -> list[Path]:
    return sorted(p for p in input_dir.glob("*.rrf") if p.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate/compare parser parity fingerprints.")
    parser.add_argument("input_dir", type=Path, help="Directory with .rrf files")
    parser.add_argument("--baseline", type=Path, default=None, help="Baseline fingerprint JSON to compare")
    parser.add_argument("--output", type=Path, default=Path("parity_fingerprint.json"), help="Output fingerprint JSON")
    args = parser.parse_args()

    files = load_rrf_files(args.input_dir)
    if not files:
        print("No .rrf files found")
        return 1

    fingerprint = {"files": [parse_file(path) for path in files]}
    args.output.write_text(json.dumps(fingerprint, indent=2), encoding="utf-8")
    print(f"Wrote fingerprint to {args.output}")

    if not args.baseline:
        return 0

    if not args.baseline.exists():
        print(f"Baseline file not found: {args.baseline}")
        return 1

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    if baseline == fingerprint:
        print("Parity check OK: baseline matches.")
        return 0

    print("Parity check FAILED: baseline differs.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
