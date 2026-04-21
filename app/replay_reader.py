from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from io import BytesIO


class ReplayParseError(Exception):
    pass


class ContainerType(IntEnum):
    NONE = 0
    PACKET_STREAM = 1
    REPLAY_DATA = 2
    SESSION = 3
    STATUS = 4
    QUESTS = 6
    GROUP_AND_FRIENDS = 7
    ITEMS = 8
    UNKNOWN_CONTAINING_PET = 9
    UNKNOWN_10 = 10
    UNKNOWN_12 = 12
    UNKNOWN_13 = 13
    INITIAL_PACKETS = 14
    UNKNOWN_15 = 15
    UNKNOWN_16 = 16
    EFST = 17
    UNKNOWN_18 = 18
    UNKNOWN_19 = 19
    UNKNOWN_20 = 20
    UNKNOWN_21 = 21
    UNKNOWN_22 = 22
    UNKNOWN_23 = 23
    UNKNOWN_24 = 24


@dataclass
class Chunk:
    id: int
    length: int
    data: bytes
    time: int = 0
    header: int | None = None


@dataclass
class ChunkContainer:
    container_type: int
    length: int
    real_length: int
    offset: int
    data: list[Chunk] = field(default_factory=list)


@dataclass
class Replay:
    header: bytes
    version: int
    sig: bytes
    date_unused: int
    date: datetime
    size: int
    chunk_containers: list[ChunkContainer]


def _get_key1(date: datetime) -> int:
    raw = struct.pack("<hbb", date.year, date.month, date.day)
    return struct.unpack("<i", raw)[0]


def _get_key2(date: datetime) -> int:
    raw = struct.pack("<bbbb", 0, date.hour, date.minute, date.second)
    return struct.unpack("<i", raw)[0]


def crypt(date: datetime, size: int, buffer: bytes) -> bytes:
    if not buffer:
        return b""

    safe_size = max(0, min(size, len(buffer)))
    if safe_size == 0:
        return b""

    real_key1 = _get_key1(date) >> 5
    real_key2 = _get_key2(date) >> 3

    output = bytearray(safe_size)
    offset = 0
    cursor = 0

    while cursor < safe_size // 4:
        start = cursor * 4
        temp_old = struct.unpack("<i", buffer[start : start + 4])[0]
        key = (real_key1 + (cursor + 1)) * real_key2
        temp = (temp_old ^ key) & 0xFFFFFFFF
        output[start : start + 4] = struct.pack("<I", temp)
        offset += 4
        cursor += 1

    if safe_size - offset > 0:
        output[offset:safe_size] = buffer[offset:safe_size]

    return bytes(output)


def _read_datetime(reader: BytesIO) -> tuple[datetime, int]:
    date_raw = reader.read(8)
    if len(date_raw) != 8:
        raise ReplayParseError("Invalid replay date header")
    year, month, day, date_unused, hour, minute, second = struct.unpack("<hbbbbbb", date_raw)
    try:
        date = datetime(year, month, day, hour, minute, second)
    except ValueError as exc:
        raise ReplayParseError(f"Invalid replay date values: {exc}") from exc
    return date, date_unused


def parse_replay(file_bytes: bytes) -> Replay:
    if len(file_bytes) < 112:
        raise ReplayParseError("Replay file is too small")

    reader = BytesIO(file_bytes)
    header = reader.read(100)
    version_b = reader.read(1)
    sig = reader.read(3)

    if len(version_b) != 1 or len(sig) != 3:
        raise ReplayParseError("Invalid replay header")

    version = version_b[0]
    date, date_unused = _read_datetime(reader)

    replay = Replay(
        header=header,
        version=version,
        sig=sig,
        date_unused=date_unused,
        date=date,
        size=len(file_bytes),
        chunk_containers=[],
    )

    if version != 5:
        raise ReplayParseError(f"Unsupported replay version: {version}")

    for _ in range(24):
        descriptor = reader.read(10)
        if len(descriptor) != 10:
            raise ReplayParseError("Unexpected EOF while reading chunk containers")

        container_type_u16, length, offset = struct.unpack("<Hii", descriptor)
        real_length = length if length != 0 else replay.size - offset
        if offset < 0 or offset > replay.size:
            raise ReplayParseError(f"Invalid container offset: {offset}")

        if real_length < 0:
            raise ReplayParseError(f"Invalid container length: {real_length}")

        end = min(replay.size, offset + real_length)
        content = file_bytes[offset:end]

        container = ChunkContainer(
            container_type=int(container_type_u16),
            length=length,
            real_length=real_length,
            offset=offset,
            data=[],
        )

        if container.container_type == int(ContainerType.PACKET_STREAM):
            ptr = 0
            while ptr + 10 <= len(content):
                chunk_header = content[ptr : ptr + 10]
                packet_id, packet_time, packet_length = struct.unpack("<iiH", chunk_header)
                ptr += 10
                if packet_length < 0 or ptr + packet_length > len(content):
                    break
                encrypted_data = content[ptr : ptr + packet_length]
                packet_data = crypt(replay.date, packet_length, encrypted_data)
                packet_header = None
                if len(packet_data) >= 2:
                    packet_header = struct.unpack("<H", packet_data[:2])[0]
                container.data.append(
                    Chunk(
                        id=packet_id,
                        time=packet_time,
                        length=packet_length,
                        data=packet_data,
                        header=packet_header,
                    )
                )
                ptr += packet_length
        else:
            decrypted = crypt(replay.date, max(0, container.length), content)
            ptr = 0
            while ptr + 6 <= len(decrypted):
                chunk_id, chunk_length = struct.unpack("<hi", decrypted[ptr : ptr + 6])
                ptr += 6
                if chunk_length < 0 or ptr + chunk_length > len(decrypted):
                    break
                chunk_data = decrypted[ptr : ptr + chunk_length]
                container.data.append(Chunk(id=chunk_id, length=chunk_length, data=chunk_data))
                ptr += chunk_length

        replay.chunk_containers.append(container)

    return replay


def extract_main_packet_chunks(replay: Replay) -> list[Chunk]:
    containers = sorted(replay.chunk_containers, key=lambda x: len(x.data), reverse=True)

    trimmed: list[ChunkContainer] = []
    hit_valid = False
    for container in containers:
        if not hit_valid and container.data and container.data[0].header is None:
            continue
        hit_valid = True
        trimmed.append(container)

    chunks: list[Chunk] = []

    initial = next((c for c in trimmed if c.container_type == int(ContainerType.INITIAL_PACKETS)), None)
    if initial is not None:
        chunks.extend(initial.data)

    packet_stream = next((c for c in trimmed if c.container_type == int(ContainerType.PACKET_STREAM)), None)
    if packet_stream is None:
        raise ReplayParseError("Missing packet stream container")

    chunks.extend(packet_stream.data)
    chunks = [chunk for chunk in chunks if chunk.length > 0]

    for index, chunk in enumerate(chunks):
        chunk.id = index

    return chunks


def _decode_korean(data: bytes) -> str:
    end = data.find(b"\x00")
    chunk = data if end < 0 else data[:end]
    if not chunk:
        return ""
    for encoding in ("cp949", "euc-kr", "utf-8", "latin-1"):
        try:
            return chunk.decode(encoding, errors="strict")
        except Exception:
            continue
    return chunk.decode("latin-1", errors="replace")


def _decode_utf8_preferred(data: bytes) -> str:
    end = data.find(b"\x00")
    chunk = data if end < 0 else data[:end]
    if not chunk:
        return ""
    for encoding in ("utf-8", "cp874", "cp949", "euc-kr", "latin-1"):
        try:
            return chunk.decode(encoding, errors="strict")
        except Exception:
            continue
    return chunk.decode("latin-1", errors="replace")


def extract_replay_metadata(replay: Replay) -> dict[str, int | str | None]:
    player_aid: int | None = None
    player_name: str | None = None
    last_map: str | None = None
    last_zeny: int | None = None

    session = next((c for c in replay.chunk_containers if c.container_type == int(ContainerType.SESSION)), None)
    if session and len(session.data) > 1 and len(session.data[1].data) >= 4:
        player_aid = struct.unpack("<I", session.data[1].data[:4])[0]

    if session and len(session.data) > 42 and len(session.data[42].data) >= 4:
        last_zeny = struct.unpack("<i", session.data[42].data[:4])[0]

    replay_data = next((c for c in replay.chunk_containers if c.container_type == int(ContainerType.REPLAY_DATA)), None)
    if replay_data and len(replay_data.data) > 5:
        player_name = _decode_utf8_preferred(replay_data.data[4].data)
        last_map = _decode_korean(replay_data.data[5].data)

    return {
        "player_aid": player_aid,
        "player_name": player_name,
        "last_map": last_map,
        "last_zeny": last_zeny,
    }
