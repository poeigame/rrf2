from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.skill_names import get_skill_name


def _is_player_aid(value: int) -> bool:
    return 100000 <= value < 199999


@dataclass
class SkillAggregate:
    skill_id: int
    hits: int = 0
    total_damage: int = 0
    min_damage: int | None = None
    max_damage: int | None = None
    levels: set[int] = field(default_factory=set)
    first_tick_ms: int | None = None
    last_tick_ms: int | None = None
    uses: int = 0
    cast_ticks: set[int] = field(default_factory=set)

    def add_hit(self, damage: int, level: int | None = None) -> None:
        self.hits += 1
        self.total_damage += damage
        if self.min_damage is None:
            self.min_damage = damage
        else:
            self.min_damage = min(self.min_damage, damage)
        if self.max_damage is None:
            self.max_damage = damage
        else:
            self.max_damage = max(self.max_damage, damage)
        if level is not None:
            self.levels.add(level)

    def add_use(self) -> None:
        self.uses += 1

    def mark_tick(self, tick_ms: int) -> None:
        if self.first_tick_ms is None:
            self.first_tick_ms = tick_ms
        self.last_tick_ms = tick_ms

    def add_cast_tick(self, tick_ms: int) -> None:
        self.cast_ticks.add(tick_ms)


@dataclass
class MobAggregate:
    gid: int
    class_id: int | None = None
    name: str | None = None
    spawn_count: int = 0
    death_count: int = 0
    drops: dict[int, int] = field(default_factory=dict)

    def add_drop(self, item_id: int) -> None:
        self.drops[item_id] = self.drops.get(item_id, 0) + 1


@dataclass
class PlayerAggregate:
    gid: int
    name: str | None = None
    class_id: int | None = None
    seen_count: int = 0
    first_tick_ms: int | None = None
    last_tick_ms: int | None = None

    def mark_seen(self, tick_ms: int, name: str | None, class_id: int | None) -> None:
        self.seen_count += 1
        if self.first_tick_ms is None:
            self.first_tick_ms = tick_ms
        self.last_tick_ms = tick_ms
        if name:
            self.name = name
        if class_id is not None:
            self.class_id = class_id


@dataclass
class ParseState:
    replay_last_map: str | None = None
    replay_last_zeny: int | None = None
    current_hp: int | None = None
    current_sp: int | None = None
    zeny: int | None = None
    map_name: str | None = None
    event_type_counts: dict[str, int] = field(default_factory=dict)
    skill_usage: dict[int, SkillAggregate] = field(default_factory=dict)
    player_skill_usage: dict[int, dict[int, SkillAggregate]] = field(default_factory=dict)
    mobs: dict[int, MobAggregate] = field(default_factory=dict)
    players: dict[int, PlayerAggregate] = field(default_factory=dict)
    mob_deaths_by_class: dict[int, int] = field(default_factory=dict)
    map_sequence: list[str] = field(default_factory=list)
    first_skill_tick_ms: int | None = None
    last_skill_tick_ms: int | None = None
    last_dead_gid: int | None = None
    last_dead_tick_ms: int | None = None
    warnings: list[str] = field(default_factory=list)

    def count_event(self, event_type: str) -> None:
        self.event_type_counts[event_type] = self.event_type_counts.get(event_type, 0) + 1

    def add_skill_damage(self, skill_id: int, damage: int, level: int | None) -> None:
        if skill_id not in self.skill_usage:
            self.skill_usage[skill_id] = SkillAggregate(skill_id=skill_id)
        self.skill_usage[skill_id].add_hit(damage=damage, level=level)

    def add_skill_use(self, skill_id: int) -> None:
        if skill_id not in self.skill_usage:
            self.skill_usage[skill_id] = SkillAggregate(skill_id=skill_id)
        self.skill_usage[skill_id].add_use()

    def mark_skill_tick(self, tick_ms: int, skill_id: int) -> None:
        if self.first_skill_tick_ms is None:
            self.first_skill_tick_ms = tick_ms
        self.last_skill_tick_ms = tick_ms
        if skill_id not in self.skill_usage:
            self.skill_usage[skill_id] = SkillAggregate(skill_id=skill_id)
        self.skill_usage[skill_id].mark_tick(tick_ms)

    def mark_map_change(self, map_name: str) -> None:
        self.map_name = map_name
        self.map_sequence.append(map_name)

    def mark_mob_spawn(self, gid: int, class_id: int | None, name: str | None) -> None:
        if gid not in self.mobs:
            self.mobs[gid] = MobAggregate(gid=gid)
        mob = self.mobs[gid]
        mob.spawn_count += 1
        if class_id is not None:
            mob.class_id = class_id
        if name:
            mob.name = name

    def mark_unit_dead(self, gid: int, tick_ms: int) -> None:
        self.last_dead_gid = gid
        self.last_dead_tick_ms = tick_ms
        if gid in self.mobs:
            mob = self.mobs[gid]
            mob.death_count += 1
            if mob.class_id is not None:
                class_id = mob.class_id
                self.mob_deaths_by_class[class_id] = self.mob_deaths_by_class.get(class_id, 0) + 1

    def mark_player_seen(self, gid: int, tick_ms: int, name: str | None, class_id: int | None) -> None:
        if gid not in self.players:
            self.players[gid] = PlayerAggregate(gid=gid)
        self.players[gid].mark_seen(tick_ms=tick_ms, name=name, class_id=class_id)

    def _player_skill(self, player_aid: int, skill_id: int) -> SkillAggregate:
        if player_aid not in self.player_skill_usage:
            self.player_skill_usage[player_aid] = {}
        player_skills = self.player_skill_usage[player_aid]
        if skill_id not in player_skills:
            player_skills[skill_id] = SkillAggregate(skill_id=skill_id)
        return player_skills[skill_id]

    def record_skill_use_for_source(self, source_id: int | None, skill_id: int, tick_ms: int) -> None:
        self.add_skill_use(skill_id)
        self.mark_skill_tick(tick_ms=tick_ms, skill_id=skill_id)

        if source_id is None:
            return
        if source_id in self.mobs:
            return

        self.mark_player_seen(gid=source_id, tick_ms=tick_ms, name=None, class_id=None)
        per_player = self._player_skill(source_id, skill_id)
        per_player.add_use()
        per_player.mark_tick(tick_ms)

    def record_skill_damage_for_source(
        self,
        source_id: int | None,
        skill_id: int,
        damage: int,
        level: int | None,
        tick_ms: int,
    ) -> None:
        self.add_skill_use(skill_id)
        self.add_skill_damage(skill_id=skill_id, damage=damage, level=level)
        self.mark_skill_tick(tick_ms=tick_ms, skill_id=skill_id)
        self.skill_usage[skill_id].add_cast_tick(tick_ms)

        if source_id is None:
            return
        if source_id in self.mobs:
            return

        self.mark_player_seen(gid=source_id, tick_ms=tick_ms, name=None, class_id=None)
        per_player = self._player_skill(source_id, skill_id)
        per_player.add_use()
        per_player.add_hit(damage=damage, level=level)
        per_player.mark_tick(tick_ms)
        per_player.add_cast_tick(tick_ms)

    def attach_drop_to_last_dead(self, tick_ms: int, item_id: int) -> bool:
        if self.last_dead_gid is None or self.last_dead_tick_ms is None:
            return False
        if tick_ms - self.last_dead_tick_ms > 300:
            return False
        mob = self.mobs.get(self.last_dead_gid)
        if mob is None:
            return False
        mob.add_drop(item_id)
        return True

    def build_aggregates(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        total_damage = sum(agg.total_damage for agg in self.skill_usage.values())
        skill_damage_event_count = sum(agg.hits for agg in self.skill_usage.values())
        total_skill_uses = sum(agg.uses for agg in self.skill_usage.values())
        total_skill_hits = sum(agg.hits for agg in self.skill_usage.values())

        if self.first_skill_tick_ms is not None and self.last_skill_tick_ms is not None:
            skill_window_ms = max(1, self.last_skill_tick_ms - self.first_skill_tick_ms)
        else:
            skill_window_ms = 0
        skill_window_sec = skill_window_ms / 1000 if skill_window_ms > 0 else 0

        skill_usage = []
        for skill_id, agg in sorted(self.skill_usage.items(), key=lambda x: x[0]):
            if agg.first_tick_ms is not None and agg.last_tick_ms is not None:
                span_ms = max(1, agg.last_tick_ms - agg.first_tick_ms)
                span_sec = span_ms / 1000
            else:
                span_sec = 0

            dps = round(agg.total_damage / span_sec, 3) if span_sec > 0 else float(agg.total_damage)
            cast_count = len(agg.cast_ticks)
            if cast_count > 1:
                cast_span_ms = max(1, max(agg.cast_ticks) - min(agg.cast_ticks))
                cast_span_sec = cast_span_ms / 1000
            else:
                cast_span_sec = 0
            cast_per_second = round(cast_count / cast_span_sec, 3) if cast_span_sec > 0 else float(cast_count)
            hits_per_second = cast_per_second

            skill_usage.append(
                {
                    "skill_id": skill_id,
                    "skill_name": get_skill_name(skill_id),
                    "uses": agg.uses,
                    "hits": agg.hits,
                    "total_damage": agg.total_damage,
                    "min_damage": agg.min_damage,
                    "max_damage": agg.max_damage,
                    "levels": sorted(agg.levels),
                    "window_ms": int(span_sec * 1000) if span_sec > 0 else 0,
                    "dps": dps,
                    "cast_count": cast_count,
                    "cast_per_second": cast_per_second,
                    "hits_per_second": hits_per_second,
                }
            )

        skill_summary = sorted(skill_usage, key=lambda x: x["total_damage"], reverse=True)

        drop_statistics = []
        mob_stats = []
        player_mapping = []
        for gid, mob in sorted(self.mobs.items(), key=lambda x: x[0]):
            total_drops = sum(mob.drops.values())
            class_deaths = self.mob_deaths_by_class.get(mob.class_id or -1, 0) if mob.class_id is not None else 0
            drop_rates = []
            if class_deaths > 0:
                for item_id, count in sorted(mob.drops.items(), key=lambda x: x[0]):
                    drop_rates.append(
                        {
                            "item_id": item_id,
                            "dropped": count,
                            "rate_per_kill": round(count / class_deaths, 6),
                        }
                    )

            mob_stats.append(
                {
                    "gid": gid,
                    "class_id": mob.class_id,
                    "name": mob.name,
                    "spawn_count": mob.spawn_count,
                    "death_count": mob.death_count,
                    "total_drops": total_drops,
                }
            )

            if total_drops > 0:
                drop_statistics.append(
                    {
                        "gid": gid,
                        "class_id": mob.class_id,
                        "name": mob.name,
                        "drops": drop_rates,
                    }
                )

        for gid, player in sorted(self.players.items(), key=lambda x: x[0]):
            if not _is_player_aid(gid):
                continue
            player_mapping.append(
                {
                    "player_aid": gid,
                    "gid": gid,
                    "player_name": player.name or f"player_{gid}",
                    "class_id": player.class_id,
                    "seen_count": player.seen_count,
                    "first_tick_ms": player.first_tick_ms,
                    "last_tick_ms": player.last_tick_ms,
                }
            )

        skill_by_player = []
        for player_aid, skills in sorted(self.player_skill_usage.items(), key=lambda x: x[0]):
            if not _is_player_aid(player_aid):
                continue
            player = self.players.get(player_aid)
            player_name = player.name if player and player.name else f"player_{player_aid}"
            player_rows = []
            total_damage_player = 0
            total_hits_player = 0
            total_uses_player = 0
            player_first_tick: int | None = None
            player_last_tick: int | None = None

            for skill_id, agg in sorted(skills.items(), key=lambda x: x[0]):
                if agg.first_tick_ms is not None and agg.last_tick_ms is not None:
                    span_ms = max(1, agg.last_tick_ms - agg.first_tick_ms)
                    span_sec = span_ms / 1000
                else:
                    span_sec = 0

                dps = round(agg.total_damage / span_sec, 3) if span_sec > 0 else float(agg.total_damage)
                cast_count = len(agg.cast_ticks)
                if cast_count > 1:
                    cast_span_ms = max(1, max(agg.cast_ticks) - min(agg.cast_ticks))
                    cast_span_sec = cast_span_ms / 1000
                else:
                    cast_span_sec = 0
                cast_per_second = round(cast_count / cast_span_sec, 3) if cast_span_sec > 0 else float(cast_count)
                hits_per_second = cast_per_second

                total_damage_player += agg.total_damage
                total_hits_player += agg.hits
                total_uses_player += agg.uses
                if agg.first_tick_ms is not None:
                    player_first_tick = agg.first_tick_ms if player_first_tick is None else min(player_first_tick, agg.first_tick_ms)
                if agg.last_tick_ms is not None:
                    player_last_tick = agg.last_tick_ms if player_last_tick is None else max(player_last_tick, agg.last_tick_ms)

                player_rows.append(
                    {
                        "skill_id": skill_id,
                        "skill_name": get_skill_name(skill_id),
                        "uses": agg.uses,
                        "hits": agg.hits,
                        "total_damage": agg.total_damage,
                        "dps": dps,
                        "cast_count": cast_count,
                        "cast_per_second": cast_per_second,
                        "hits_per_second": hits_per_second,
                    }
                )

            player_rows = sorted(player_rows, key=lambda x: x["total_damage"], reverse=True)
            if player_first_tick is not None and player_last_tick is not None:
                player_window_ms = max(1, player_last_tick - player_first_tick)
                player_window_sec = player_window_ms / 1000
            else:
                player_window_ms = 0
                player_window_sec = 0

            player_dps = round(total_damage_player / player_window_sec, 3) if player_window_sec > 0 else float(total_damage_player)
            skill_by_player.append(
                {
                    "player_aid": player_aid,
                    "player_name": player_name,
                    "total_skill_damage": total_damage_player,
                    "total_skill_hits": total_hits_player,
                    "total_skill_uses": total_uses_player,
                    "window_ms": player_window_ms,
                    "player_dps": player_dps,
                    "skill_summary": player_rows,
                }
            )

        return {
            "skill_usage": skill_usage,
            "skill_summary": skill_summary,
            "damage_overview": {
                "total_skill_damage": total_damage,
                "skill_damage_event_count": skill_damage_event_count,
                "total_skill_uses": total_skill_uses,
                "total_skill_hits": total_skill_hits,
                "skill_window_ms": skill_window_ms,
                "overall_skill_dps": round(total_damage / skill_window_sec, 3) if skill_window_sec > 0 else float(total_damage),
                "overall_skill_hits_per_second": round(total_skill_hits / skill_window_sec, 3)
                if skill_window_sec > 0
                else float(total_skill_hits),
            },
            "map_activity": {
                "latest_map": self.map_name or self.replay_last_map,
                "map_change_count": self.event_type_counts.get("map_change", 0),
                "map_sequence": self.map_sequence,
            },
            "status": {
                "current_hp": self.current_hp,
                "current_sp": self.current_sp,
                "zeny": self.zeny if self.zeny is not None else self.replay_last_zeny,
            },
            "player_mapping": player_mapping,
            "skill_by_player": skill_by_player,
            "mob_stats": mob_stats,
            "drop_statistics": drop_statistics,
        }
