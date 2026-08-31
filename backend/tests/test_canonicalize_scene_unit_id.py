import unittest

from app.services.script_analysis_flow import canonicalize_scene_unit_id


class CanonicalizeSceneUnitIdTests(unittest.TestCase):
    def test_aliases_collapse_to_padded_episode_id(self):
        prefix = "EP01"
        expected = "EP01_SC01"
        for raw in ("EP01_SC01", "ep01_sc01", "EP1_SC01", "EP01_SC1", "SC01", "SC1", "1"):
            self.assertEqual(canonicalize_scene_unit_id(raw, 1, prefix), expected, raw)

    def test_ep_head_uses_episode_prefix(self):
        self.assertEqual(canonicalize_scene_unit_id("EP02_SC01", 1, "EP01"), "EP01_SC01")
        self.assertEqual(canonicalize_scene_unit_id("EP1_SC02", 2, "EP03"), "EP03_SC02")

    def test_letter_suffix_preserved(self):
        self.assertEqual(canonicalize_scene_unit_id("EP01_SC01A", 1, "EP01"), "EP01_SC01A")
        self.assertEqual(canonicalize_scene_unit_id("ep1_sc03b", 3, "EP01"), "EP01_SC03B")


if __name__ == "__main__":
    unittest.main()
