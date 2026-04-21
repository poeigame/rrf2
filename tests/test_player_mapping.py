from __future__ import annotations

import unittest

from app.state import ParseState


class PlayerMappingTests(unittest.TestCase):
    def test_player_mapping_collects_gid_and_name(self) -> None:
        state = ParseState()
        state.mark_player_seen(gid=100111, tick_ms=100, name="Alice", class_id=4010)
        state.mark_player_seen(gid=100222, tick_ms=200, name="Bob", class_id=4020)
        state.mark_player_seen(gid=100111, tick_ms=400, name="Alice", class_id=4010)

        aggregates = state.build_aggregates(events=[])
        mapping = aggregates["player_mapping"]

        self.assertEqual(len(mapping), 2)
        self.assertEqual(mapping[0]["gid"], 100111)
        self.assertEqual(mapping[0]["player_aid"], 100111)
        self.assertEqual(mapping[0]["player_name"], "Alice")
        self.assertEqual(mapping[0]["seen_count"], 2)

    def test_split_skill_by_player(self) -> None:
        state = ParseState()
        state.mark_player_seen(gid=100111, tick_ms=0, name="Alice", class_id=4001)
        state.mark_player_seen(gid=100222, tick_ms=0, name="Bob", class_id=4002)

        state.record_skill_damage_for_source(source_id=100111, skill_id=10, damage=1000, level=1, tick_ms=1000)
        state.record_skill_use_for_source(source_id=100111, skill_id=10, tick_ms=1200)
        state.record_skill_damage_for_source(source_id=100222, skill_id=20, damage=500, level=2, tick_ms=2000)

        aggregates = state.build_aggregates(events=[])
        split = aggregates["skill_by_player"]
        self.assertEqual(len(split), 2)
        self.assertEqual(split[0]["player_aid"], 100111)
        self.assertEqual(split[0]["player_name"], "Alice")
        self.assertEqual(split[0]["skill_summary"][0]["skill_id"], 10)
        self.assertIn("player_dps", split[0])


if __name__ == "__main__":
    unittest.main()
