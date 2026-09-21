# -*- coding: utf-8 -*-
"""Legacy story-project promo routes removed.

Commercial promo now lives on independent promo_projects tables/APIs:
GET/POST /promo-projects/
GET/PUT/DELETE /promo-projects/{id}
POST /promo-projects/{id}/planner/analyze-asset
POST /promo-projects/{id}/planner/generate
PUT /promo-projects/{id}/planner/input
PUT /promo-projects/{id}/planner/result
"""
from __future__ import annotations

from app.api.routers.workspace import shared as _shared

router = _shared.router
