from __future__ import annotations

import unittest

from app.state import ParseState


class SkillMetricTests(unittest.TestCase):
    def test_skill_dps_cast_per_second_and_hits_per_second(self) -> None:
        state = ParseState()

        state.record_skill_damage_for_source(source_id=100111, skill_id=100, damage=1500, level=10, tick_ms=1000)
        state.record_skill_damage_for_source(source_id=100111, skill_id=100, damage=500, level=10, tick_ms=2000)

        agg = state.build_aggregates(events=[])
        skill = agg["skill_usage"][0]

        self.assertEqual(skill["skill_id"], 100)
        self.assertEqual(skill["skill_name"], "skill_100")
        self.assertEqual(skill["total_damage"], 2000)
        self.assertEqual(skill["uses"], 2)
        self.assertEqual(skill["hits"], 2)
        self.assertEqual(skill["dps"], 2000.0)
        self.assertEqual(skill["cast_count"], 2)
        self.assertEqual(skill["cast_per_second"], 2.0)
        self.assertEqual(skill["hits_per_second"], 2.0)

        summary_skill = agg["skill_summary"][0]
        self.assertEqual(summary_skill["skill_id"], 100)

        overview = agg["damage_overview"]
        self.assertEqual(overview["overall_skill_hits_per_second"], 2.0)


if __name__ == "__main__":
    unittest.main()
