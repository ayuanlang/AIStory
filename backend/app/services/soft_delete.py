# -*- coding: utf-8 -*-
"""Soft-delete active-row SQLAlchemy clauses."""
from __future__ import annotations

from sqlalchemy import or_

from app.models.all_models import Asset, Entity, Episode, Project, Scene, Shot

def _active_project_clause():
    return or_(Project.is_deleted.is_(False), Project.is_deleted.is_(None))


def _active_episode_clause():
    return or_(Episode.is_deleted.is_(False), Episode.is_deleted.is_(None))


def _active_scene_clause():
    return or_(Scene.is_deleted.is_(False), Scene.is_deleted.is_(None))


def _active_shot_clause():
    return or_(Shot.is_deleted.is_(False), Shot.is_deleted.is_(None))


def _active_asset_clause():
    return or_(Asset.is_deleted.is_(False), Asset.is_deleted.is_(None))


def _active_entity_clause():
    return or_(Entity.is_deleted.is_(False), Entity.is_deleted.is_(None))

