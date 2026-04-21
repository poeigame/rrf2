from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Callable

from app.packet_stream import PacketStream
from app.replay_reader import Chunk
from app.state import ParseState


@dataclass
class PacketView:
    packet: Chunk
    stream: PacketStream

    def base_event(self, event_type: str) -> dict[str, object]:
        return {
            "event_type": event_type,
            "packet_id": self.packet.id,
            "packet_header": f"0x{(self.packet.header or 0):04x}",
            "tick_ms": int(self.stream.delay_ms),
            "interval_ms": int(self.stream.interval_ms),
        }


DecoderFn = Callable[[PacketView, ParseState], dict[str, object] | None]


def _u16(data: bytes, offset: int) -> int | None:
    if offset + 2 > len(data):
        return None
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int | None:
    if offset + 4 > len(data):
        return None
    return struct.unpack_from("<I", data, offset)[0]


def _i32(data: bytes, offset: int) -> int | None:
    if offset + 4 > len(data):
        return None
    return struct.unpack_from("<i", data, offset)[0]


def _decode_map_name(data: bytes, offset: int = 2, length: int = 16) -> str | None:
    if offset + length > len(data):
        return None
    raw = data[offset : offset + length]
    raw = raw.split(b"\x00", 1)[0]
    if not raw:
        return None
    for encoding in ("cp949", "euc-kr", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return None


def _decode_string(data: bytes, offset: int, length: int | None = None) -> str | None:
    if offset >= len(data):
        return None
    chunk = data[offset:] if length is None else data[offset : offset + length]
    chunk = chunk.split(b"\x00", 1)[0]
    if not chunk:
        return None
    for encoding in ("utf-8", "cp874", "cp949", "euc-kr", "latin-1"):
        try:
            return chunk.decode(encoding)
        except Exception:
            continue
    return None


def _decode_pos3(data: bytes, offset: int) -> tuple[int, int, int] | None:
    if offset + 3 > len(data):
        return None
    a, b, c = data[offset], data[offset + 1], data[offset + 2]
    x = (a << 2) | ((b & 0xC0) >> 6)
    y = ((b & 0x3F) << 4) | ((c & 0xF0) >> 4)
    direction = c & 0x0F
    return x, y, direction


def decode_skill_damage(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 31:
        return None
    skill_id = _u16(data, 2)
    source_id = _u32(data, 4)
    target_id = _u32(data, 8)
    attack_motion = _i32(data, 16)
    attacked_motion = _i32(data, 20)
    damage = _i32(data, 24)
    level = _u16(data, 28)
    div = _u16(data, 30)
    action_type = data[32] if len(data) > 32 else None

    if None in (skill_id, source_id, target_id, attack_motion, attacked_motion, damage, level, div):
        return None

    tick_ms = int(view.stream.delay_ms)
    state.record_skill_damage_for_source(
        source_id=int(source_id),
        skill_id=int(skill_id),
        damage=int(damage),
        level=int(level),
        tick_ms=tick_ms,
    )

    event = view.base_event("skill_damage")
    event.update(
        {
            "skill_id": int(skill_id),
            "skill_level": int(level),
            "source_id": int(source_id),
            "target_id": int(target_id),
            "attack_motion_ms": int(attack_motion),
            "attacked_motion_ms": int(attacked_motion),
            "damage": int(damage),
            "div": int(div),
            "action_type": int(action_type) if action_type is not None else None,
        }
    )
    return event


def decode_nodamage_09cb(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 17:
        return None
    skill_id = _u16(data, 2)
    level = _i32(data, 4)
    target_id = _u32(data, 8)
    source_id = _u32(data, 12)
    result = data[16]
    if None in (skill_id, level, target_id, source_id):
        return None

    state.record_skill_use_for_source(
        source_id=int(source_id),
        skill_id=int(skill_id),
        tick_ms=int(view.stream.delay_ms),
    )

    event = view.base_event("skill_use")
    event.update(
        {
            "variant": "0x09cb",
            "skill_id": int(skill_id),
            "skill_level": int(level),
            "source_id": int(source_id),
            "target_id": int(target_id),
            "result": int(result),
            "has_damage": False,
        }
    )
    return event


def decode_nodamage_011a(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 15:
        return None
    skill_id = _u16(data, 2)
    level = _u16(data, 4)
    target_id = _u32(data, 6)
    source_id = _u32(data, 10)
    result = data[14]
    if None in (skill_id, level, target_id, source_id):
        return None

    state.record_skill_use_for_source(
        source_id=int(source_id),
        skill_id=int(skill_id),
        tick_ms=int(view.stream.delay_ms),
    )

    event = view.base_event("skill_use")
    event.update(
        {
            "variant": "0x011a",
            "skill_id": int(skill_id),
            "skill_level": int(level),
            "source_id": int(source_id),
            "target_id": int(target_id),
            "result": int(result),
            "has_damage": False,
        }
    )
    return event


def decode_ground_skill(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 18:
        return None
    skill_id = _u16(data, 2)
    source_id = _u32(data, 4)
    level = _u16(data, 8)
    x = struct.unpack_from("<h", data, 10)[0]
    y = struct.unpack_from("<h", data, 12)[0]
    start_time = _u32(data, 14)
    if None in (skill_id, source_id, level, start_time):
        return None

    event = view.base_event("ground_skill")
    event.update(
        {
            "skill_id": int(skill_id),
            "source_id": int(source_id),
            "skill_level": int(level),
            "x": int(x),
            "y": int(y),
            "start_time": int(start_time),
        }
    )
    return event


def decode_status_change(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 9:
        return None
    status_index = _u16(data, 2)
    target_id = _u32(data, 4)
    status_state = data[8]
    if None in (status_index, target_id):
        return None

    event = view.base_event("status_update")
    event.update(
        {
            "status_index": int(status_index),
            "target_id": int(target_id),
            "state": int(status_state),
            "state_text": "ended" if status_state == 0 else "updated",
        }
    )
    return event


def decode_zeny_update(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 8:
        return None
    stat_type = _u16(data, 2)
    value = _i32(data, 4)
    if stat_type is None or value is None:
        return None
    if stat_type != 20:
        return None

    previous = state.zeny if state.zeny is not None else state.replay_last_zeny
    state.zeny = int(value)

    event = view.base_event("currency_update")
    event.update(
        {
            "currency": "zeny",
            "previous": int(previous) if previous is not None else None,
            "current": int(value),
            "delta": int(value - previous) if previous is not None else None,
        }
    )
    return event


def decode_status_param_update(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 8:
        return None
    stat_type = _u16(data, 2)
    value = _i32(data, 4)
    if stat_type is None or value is None:
        return None

    if stat_type == 5:
        state.current_hp = int(value)
        key = "hp"
    elif stat_type == 7:
        state.current_sp = int(value)
        key = "sp"
    else:
        return None

    event = view.base_event("resource_update")
    event.update({"resource": key, "value": int(value)})
    return event


def decode_map_change_0091(view: PacketView, state: ParseState) -> dict[str, object] | None:
    name = _decode_map_name(view.packet.data)
    if not name:
        return None
    map_name = name.replace(".gat", "")
    state.mark_map_change(map_name)
    event = view.base_event("map_change")
    event.update({"map_name": map_name, "variant": "0x0091"})
    return event


def decode_map_change_0ac7(view: PacketView, state: ParseState) -> dict[str, object] | None:
    name = _decode_map_name(view.packet.data)
    if not name:
        return None
    map_name = name.replace(".gat", "")
    state.mark_map_change(map_name)
    event = view.base_event("map_change")
    event.update({"map_name": map_name, "variant": "0x0ac7"})
    return event


def decode_unit_dead(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 7:
        return None
    gid = _u32(data, 2)
    dead_type = data[6]
    if gid is None:
        return None
    if dead_type != 1:
        return None

    tick_ms = int(view.stream.delay_ms)
    state.mark_unit_dead(gid=int(gid), tick_ms=tick_ms)

    event = view.base_event("unit_dead")
    event.update({"gid": int(gid), "type": int(dead_type)})
    return event


def decode_ground_item_spawn(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 17:
        return None
    drop_gid = _i32(data, 2)
    item_id = _i32(data, 6)
    x = _u16(data, 13)
    y = _u16(data, 15)
    if None in (drop_gid, item_id, x, y):
        return None

    tick_ms = int(view.stream.delay_ms)
    linked = state.attach_drop_to_last_dead(tick_ms=tick_ms, item_id=int(item_id))

    event = view.base_event("item_drop")
    event.update(
        {
            "drop_gid": int(drop_gid),
            "item_id": int(item_id),
            "x": int(x),
            "y": int(y),
            "linked_to_last_dead": linked,
        }
    )
    return event


def decode_monster_spawn_090f(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 76:
        return None
    gid = _u32(data, 3)
    class_id = _u16(data, 19)
    pos = _decode_pos3(data, 55)
    name = _decode_string(data, 73)
    if gid is None or class_id is None or pos is None:
        return None

    x, y, direction = pos
    state.mark_mob_spawn(gid=int(gid), class_id=int(class_id), name=name)

    event = view.base_event("mob_spawn")
    event.update(
        {
            "gid": int(gid),
            "class_id": int(class_id),
            "name": name,
            "x": int(x),
            "y": int(y),
            "direction": int(direction),
            "variant": "0x090f",
        }
    )
    return event


def decode_monster_spawn_09dd(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 79:
        return None
    obj_type = data[4]
    if obj_type != 0x5:
        return None
    gid = _u32(data, 5)
    speed = _u16(data, 13)
    class_id = _u16(data, 23)
    pos = _decode_pos3(data, 59)
    level = _u16(data, 65)
    hp = _i32(data, 69)
    name = _decode_string(data, 78)
    if None in (gid, speed, class_id, level, hp) or pos is None:
        return None

    x, y, direction = pos
    state.mark_mob_spawn(gid=int(gid), class_id=int(class_id), name=name)

    event = view.base_event("mob_spawn")
    event.update(
        {
            "gid": int(gid),
            "class_id": int(class_id),
            "name": name,
            "x": int(x),
            "y": int(y),
            "direction": int(direction),
            "speed": int(speed),
            "level": int(level),
            "hp": max(0, int(hp)),
            "variant": "0x09dd",
        }
    )
    return event


def decode_monster_hp(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 14:
        return None
    gid = _u32(data, 2)
    hp = _i32(data, 6)
    hp_max = _i32(data, 10)
    if None in (gid, hp, hp_max):
        return None

    event = view.base_event("mob_hp")
    event.update({"gid": int(gid), "hp": int(hp), "hp_max": int(hp_max)})
    return event


def decode_player_seen_0915(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 75:
        return None

    obj_type = data[4]
    if obj_type != 0x0:
        return None

    gid = _u32(data, 5)
    class_id = _u16(data, 19)
    pos = _decode_pos3(data, 55)
    name = _decode_string(data, 74)
    if gid is None or class_id is None or pos is None:
        return None

    x, y, direction = pos
    tick_ms = int(view.stream.delay_ms)
    state.mark_player_seen(gid=int(gid), tick_ms=tick_ms, name=name, class_id=int(class_id))

    event = view.base_event("player_seen")
    event.update(
        {
            "gid": int(gid),
            "player_name": name,
            "class_id": int(class_id),
            "x": int(x),
            "y": int(y),
            "direction": int(direction),
            "variant": "0x0915",
        }
    )
    return event


def decode_player_seen_09ff(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 85:
        return None

    obj_type = data[4]
    if obj_type != 0x0:
        return None

    gid = _u32(data, 5)
    class_id = _u16(data, 23)
    pos = _decode_pos3(data, 63)
    name = _decode_string(data, 84)
    if gid is None or class_id is None or pos is None:
        return None

    x, y, direction = pos
    tick_ms = int(view.stream.delay_ms)
    state.mark_player_seen(gid=int(gid), tick_ms=tick_ms, name=name, class_id=int(class_id))

    event = view.base_event("player_seen")
    event.update(
        {
            "gid": int(gid),
            "player_name": name,
            "class_id": int(class_id),
            "x": int(x),
            "y": int(y),
            "direction": int(direction),
            "variant": "0x09ff",
        }
    )
    return event


def decode_player_seen_09db(view: PacketView, state: ParseState) -> dict[str, object] | None:
    data = view.packet.data
    if len(data) < 85:
        return None

    obj_type = data[4]
    if obj_type != 0x0:
        return None

    gid = _u32(data, 5)
    class_id = _u16(data, 23)
    pos = _decode_pos3(data, 63)
    name = _decode_string(data, 84)
    if gid is None or class_id is None or pos is None:
        return None

    x, y, direction = pos
    tick_ms = int(view.stream.delay_ms)
    state.mark_player_seen(gid=int(gid), tick_ms=tick_ms, name=name, class_id=int(class_id))

    event = view.base_event("player_seen")
    event.update(
        {
            "gid": int(gid),
            "player_name": name,
            "class_id": int(class_id),
            "x": int(x),
            "y": int(y),
            "direction": int(direction),
            "variant": "0x09db",
        }
    )
    return event


DECODERS: dict[int, DecoderFn] = {
    0x01DE: decode_skill_damage,
    0x09CB: decode_nodamage_09cb,
    0x011A: decode_nodamage_011a,
    0x0117: decode_ground_skill,
    0x0196: decode_status_change,
    0x00B1: decode_zeny_update,
    0x00B0: decode_status_param_update,
    0x0091: decode_map_change_0091,
    0x0AC7: decode_map_change_0ac7,
    0x0080: decode_unit_dead,
    0x0ADD: decode_ground_item_spawn,
    0x090F: decode_monster_spawn_090f,
    0x09DD: decode_monster_spawn_09dd,
    0x0977: decode_monster_hp,
    0x0915: decode_player_seen_0915,
    0x09FF: decode_player_seen_09ff,
    0x09DB: decode_player_seen_09db,
}


def decode_packet(packet: Chunk, stream: PacketStream, state: ParseState) -> dict[str, object] | None:
    if packet.header is None:
        return None
    decoder = DECODERS.get(packet.header)
    if decoder is None:
        return None
    view = PacketView(packet=packet, stream=stream)
    try:
        return decoder(view, state)
    except Exception as exc:
        state.warnings.append(f"Decoder failed for packet header 0x{packet.header:04x}: {exc}")
        return None
