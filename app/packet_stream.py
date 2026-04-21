from __future__ import annotations

from dataclasses import dataclass

from app.replay_reader import Chunk


@dataclass
class PacketStream:
    packets: list[Chunk]
    position: int = 0
    _last_interval_tick: float = 0

    def __post_init__(self) -> None:
        self.time_start = self.packets[0].time if self.packets else 0

    @property
    def can_read(self) -> bool:
        return self.position < len(self.packets)

    @property
    def current_packet(self) -> Chunk:
        return self.packets[self.position]

    @property
    def current_tick(self) -> int:
        return self.current_packet.time if self.can_read else 0

    @property
    def delay_ms(self) -> float:
        if self.position > 0:
            return float(self.current_tick - self.time_start)
        return 0.0

    @property
    def interval_ms(self) -> float:
        if self.position > 0:
            current = self.delay_ms - self._last_interval_tick
            self._last_interval_tick = self.delay_ms
            return current
        return 0.0

    def next_packet(self) -> None:
        self.position += 1

    def reset(self) -> None:
        self.position = 0
        self._last_interval_tick = 0
