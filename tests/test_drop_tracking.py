from __future__ import annotations

import unittest

from app.state import ParseState


class DropTrackingTests(unittest.TestCase):
    def test_drop_links_to_recent_dead_mob(self) -> None:
        state = ParseState()
        state.mark_mob_spawn(gid=2001, class_id=1111, name="Poring")
        state.mark_unit_dead(gid=2001, tick_ms=5000)

        linked = state.attach_drop_to_last_dead(tick_ms=5200, item_id=909)
        self.assertTrue(linked)

        agg = state.build_aggregates(events=[])
        drops = agg["drop_statistics"]
        self.assertEqual(len(drops), 1)
        self.assertEqual(drops[0]["drops"][0]["item_id"], 909)


if __name__ == "__main__":
    unittest.main()
