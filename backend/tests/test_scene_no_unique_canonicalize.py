import unittest

from app.db.init_db import _canonicalize_scene_no_for_unique_index


class SceneNoCanonicalizeTests(unittest.TestCase):
    def test_aliases_collapse_to_numeric(self):
        self.assertEqual(_canonicalize_scene_no_for_unique_index('EP01_SC03'), '3')
        self.assertEqual(_canonicalize_scene_no_for_unique_index('03'), '3')
        self.assertEqual(_canonicalize_scene_no_for_unique_index('3'), '3')
        self.assertEqual(_canonicalize_scene_no_for_unique_index('SC03'), '3')

    def test_letter_suffix_preserved(self):
        self.assertEqual(_canonicalize_scene_no_for_unique_index('EP01_SC03A'), 'EP01_SC03A')
        self.assertEqual(_canonicalize_scene_no_for_unique_index('ep01_sc03b'), 'EP01_SC03B')


if __name__ == '__main__':
    unittest.main()
