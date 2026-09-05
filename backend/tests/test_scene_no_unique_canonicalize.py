import unittest

from app.db.init_db import _canonicalize_scene_no_for_unique_index
from app.services.scene_no_utils import canonicalize_progress_scene_marker
from app.services.script_progress_helpers import _normalize_scene_marker_id_from_scene


class SceneNoCanonicalizeTests(unittest.TestCase):
    def test_aliases_collapse_to_numeric(self):
        self.assertEqual(_canonicalize_scene_no_for_unique_index('EP01_SC03'), '3')
        self.assertEqual(_canonicalize_scene_no_for_unique_index('03'), '3')
        self.assertEqual(_canonicalize_scene_no_for_unique_index('3'), '3')
        self.assertEqual(_canonicalize_scene_no_for_unique_index('SC03'), '3')

    def test_letter_suffix_preserved(self):
        self.assertEqual(_canonicalize_scene_no_for_unique_index('EP01_SC03A'), 'EP01_SC03A')
        self.assertEqual(_canonicalize_scene_no_for_unique_index('ep01_sc03b'), 'EP01_SC03B')

    def test_progress_marker_maps_workspace_scene_no(self):
        self.assertEqual(canonicalize_progress_scene_marker('1', episode_prefix='EP01'), 'EP01_SC01')
        self.assertEqual(canonicalize_progress_scene_marker('EP01_SC01', episode_prefix='EP02'), 'EP01_SC01')
        self.assertEqual(canonicalize_progress_scene_marker('03', episode_prefix='EP02'), 'EP02_SC03')
        self.assertEqual(canonicalize_progress_scene_marker('EP01_SC03A'), 'EP01_SC03A')

    def test_normalize_scene_marker_ignores_episode_pk(self):
        from types import SimpleNamespace
        scene = SimpleNamespace(id=99, scene_no='1')
        self.assertEqual(
            _normalize_scene_marker_id_from_scene(scene, 5, episode_prefix='EP01'),
            'EP01_SC01',
        )
        self.assertEqual(
            _normalize_scene_marker_id_from_scene(scene, 5),
            'EP01_SC01',
        )


if __name__ == '__main__':
    unittest.main()
