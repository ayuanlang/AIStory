"""Previous-episode asset dependency selection."""

from app.services.generation_runtime.asset_registration import select_prior_same_name_entity
from app.services.project_episode_utils import pick_nearest_prior_match


class _Row:
    def __init__(self, row_id, episode_id, name, entity_type, image_url="img", name_en=""):
        self.id = row_id
        self.episode_id = episode_id
        self.name = name
        self.name_en = name_en
        self.type = entity_type
        self.image_url = image_url


def test_same_type_and_name_uses_the_nearest_previous_entity_image():
    rows = [
        _Row(1, 10, "林月", "character", "ep1.png"),
        _Row(2, 20, "林月", "character", "ep2.png"),
        _Row(9, 20, "林月", "prop", "prop.png"),
    ]
    numbers = {10: 1, 20: 2}
    chosen = select_prior_same_name_entity(rows, "character", {"林月"}, numbers)
    assert chosen.id == 2
    assert chosen.image_url == "ep2.png"


def test_different_type_is_not_a_source():
    rows = [_Row(9, 20, "林月", "prop", "prop.png")]
    chosen = select_prior_same_name_entity(rows, "character", {"林月"}, {20: 2})
    assert chosen is None


def test_entity_without_an_image_is_not_a_source():
    rows = [_Row(2, 20, "林月", "character", "")]
    chosen = select_prior_same_name_entity(rows, "角色", {"林月"}, {20: 2})
    assert chosen is None


def test_pick_nearest_prior_episode_not_the_earliest_or_a_later_one():
    rows = [
        _Row(1, 10, "林月", "character", "ep1.png"),
        _Row(2, 20, "林月", "character", "ep2.png"),
        _Row(4, 40, "林月", "character", "ep4.png"),
    ]
    numbers = {10: 1, 20: 2, 30: 3, 40: 4}
    chosen = pick_nearest_prior_match(rows, 30, numbers)
    assert chosen.id == 2


def test_pick_returns_none_when_only_a_later_episode_matches():
    numbers = {30: 3, 40: 4}
    chosen = pick_nearest_prior_match([_Row(4, 40, "林月", "character")], 30, numbers)
    assert chosen is None


def test_unknown_host_episode_keeps_the_first_match():
    rows = [
        _Row(1, 10, "林月", "character"),
        _Row(2, 20, "林月", "character"),
    ]
    chosen = pick_nearest_prior_match(rows, None, {10: 1, 20: 2})
    assert chosen.id == 1
