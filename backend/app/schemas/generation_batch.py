# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class ShotMediaBatchStartRequest(BaseModel):
    mode: str = "keyframes"  # keyframes | videos
    shot_ids: Optional[List[int]] = None
    overwrite_existing: bool = False
    system_api_id: Optional[int] = None
    draft_mode: Optional[bool] = False
    use_prev_video: Optional[bool] = False
    sd2_auto_duration: Optional[bool] = False

