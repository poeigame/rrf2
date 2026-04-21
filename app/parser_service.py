from __future__ import annotations

import hashlib
import time
from datetime import timezone
from typing import Any

from app.decoders import decode_packet
from app.packet_stream import PacketStream
from app.replay_reader import (
    ReplayParseError,
    extract_main_packet_chunks,
    extract_replay_metadata,
    parse_replay,
)
from app.state import ParseState


def _hex(data: bytes) -> str:
    return data.hex()


def parse_rrf_bytes(
    file_bytes: bytes,
    *,
    filename: str,
    mode: str,
    include_events: bool,
    include_aggregates: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    replay = parse_replay(file_bytes)
    replay_meta = extract_replay_metadata(replay)
    chunks = extract_main_packet_chunks(replay)

    state = ParseState(
        replay_last_map=(replay_meta.get("last_map") or None),
        replay_last_zeny=replay_meta.get("last_zeny") if isinstance(replay_meta.get("last_zeny"), int) else None,
        map_name=(replay_meta.get("last_map") or None),
        zeny=replay_meta.get("last_zeny") if isinstance(replay_meta.get("last_zeny"), int) else None,
    )

    if isinstance(replay_meta.get("player_aid"), int):
        state.mark_player_seen(
            gid=int(replay_meta["player_aid"]),
            tick_ms=0,
            name=replay_meta.get("player_name") if isinstance(replay_meta.get("player_name"), str) else None,
            class_id=None,
        )

    events: list[dict[str, Any]] = []
    stream = PacketStream(chunks)

    while stream.can_read:
        packet = stream.current_packet

        if mode == "raw":
            if include_events:
                event = {
                    "event_type": "raw_packet",
                    "packet_id": packet.id,
                    "packet_header": f"0x{(packet.header or 0):04x}",
                    "tick_ms": int(stream.delay_ms),
                    "interval_ms": int(stream.interval_ms),
                    "length": packet.length,
                    "bytes_hex": _hex(packet.data),
                }
                events.append(event)
                state.count_event(event["event_type"])
        else:
            event = decode_packet(packet, stream, state)
            if event is not None:
                state.count_event(str(event["event_type"]))
                if include_events:
                    events.append(event)

        stream.next_packet()

    parse_duration_ms = int((time.perf_counter() - started) * 1000)
    metadata = {
        "source_file": filename,
        "source_sha1": hashlib.sha1(file_bytes).hexdigest(),
        "replay_version": replay.version,
        "replay_date": replay.date.replace(tzinfo=timezone.utc).isoformat(),
        "file_size_bytes": len(file_bytes),
        "packet_count": len(chunks),
        "container_count": len(replay.chunk_containers),
        "player_aid": replay_meta.get("player_aid"),
        "player_name": replay_meta.get("player_name"),
        "parse_duration_ms": parse_duration_ms,
    }

    summary = {
        "mode": mode,
        "events_included": include_events,
        "aggregates_included": include_aggregates,
        "recognized_event_count": sum(state.event_type_counts.values()),
        "returned_event_count": len(events) if include_events else 0,
        "event_type_counts": state.event_type_counts,
    }

    aggregates = None
    if include_aggregates:
        aggregate_input = events if include_events else []
        aggregates = state.build_aggregates(aggregate_input)
        damage_overview = aggregates.get("damage_overview", {})
        top_skills = aggregates.get("skill_summary", [])
        players = aggregates.get("player_mapping", [])
        summary["overall_skill_dps"] = damage_overview.get("overall_skill_dps")
        summary["overall_skill_hits_per_second"] = damage_overview.get("overall_skill_hits_per_second")
        summary["player_count"] = len(players)
        summary["players"] = [
            {"player_aid": p.get("player_aid"), "player_name": p.get("player_name")}
            for p in players
            if isinstance(p.get("player_aid"), int)
        ]
        summary["top_skills"] = top_skills[:10]

    return {
        "metadata": metadata,
        "summary": summary,
        "events": events if include_events else None,
        "aggregates": aggregates,
        "warnings": state.warnings,
        "errors": [],
    }


def safe_parse_rrf_bytes(
    file_bytes: bytes,
    *,
    filename: str,
    mode: str,
    include_events: bool,
    include_aggregates: bool,
) -> dict[str, Any]:
    try:
        return parse_rrf_bytes(
            file_bytes,
            filename=filename,
            mode=mode,
            include_events=include_events,
            include_aggregates=include_aggregates,
        )
    except ReplayParseError as exc:
        return {
            "metadata": {"source_file": filename},
            "summary": {"mode": mode},
            "events": None,
            "aggregates": None,
            "warnings": [],
            "errors": [str(exc)],
        }
