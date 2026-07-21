# -*- coding: utf-8 -*-
"""Residual admin/queue config, split, llm_logs, backup (P6+)."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal, get_db
from app.models.all_models import *
logger = logging.getLogger("api_logger")
router = APIRouter(tags=["workspace-residual"])

def _bind_endpoint_helpers() -> None:
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__)

_bind_endpoint_helpers()


class QueueConfigBase(BaseModel):
    queue_threads: int
    callback_threads: int
    pure_callback_mode_auto: bool = True
    pure_callback_mode: bool = False
    callback_loss_retry_enabled: bool = True
    callback_loss_retry_after_seconds: int = 1200
    callback_loss_max_submit_retries: int = 1
    callback_compensation_scan_enabled: bool = True
    callback_compensation_scan_interval_seconds: int = 60
    callback_compensation_scan_batch_size: int = 10
    callback_compensation_image_share_percent: int = 50

@router.get("/admin/queue/config", response_model=QueueConfigBase)
async def admin_get_queue_config(current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return QueueConfigBase(**load_queue_config())

@router.put("/admin/queue/config", response_model=QueueConfigBase)
async def admin_update_queue_config(config: QueueConfigBase, current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    payload = config.model_dump() if hasattr(config, "model_dump") else config.dict()
    saved_config = save_queue_config(payload)
    
    # Keep process-local runtime config in sync for flags that are read live.
    # queue_threads / callback_threads still require a backend restart to resize workers.
    global _q_conf
    _q_conf = dict(saved_config)
    return QueueConfigBase(**saved_config)
    



class ScriptSplitRequest(BaseModel):
    script_content: str

@router.post("/projects/{project_id}/episodes/{episode_id}/split")
async def split_script(
    project_id: int,
    episode_id: int,
    req: ScriptSplitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    project = _require_project_access(db, project_id, current_user)
    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.project_id == project_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    script_content = (req.script_content or "").strip()
    if not script_content:
        raise HTTPException(status_code=400, detail="script_content is required")
        
    if async_mode == "1":
        tid = _submit_async(split_script, user_id=current_user.id,
                            kind="split_script", project_id=project_id, episode_id=episode_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})

    try:
        sys_prompt = _resolve_prompt_text("script_split.md")
    except FileNotFoundError:
        try:
            with open(os.path.join(os.path.dirname(__file__), "../core/prompts/script_split.md"), "r", encoding="utf-8") as f:
                sys_prompt = f.read()
        except:
            sys_prompt = "Split script into episodes of ~1000 chars, output JSON with 'episodes':[{title, content}]."
            
    llm_config = agent_service.get_active_llm_config(current_user.id, function_name="script_split")
    if not llm_config:
         llm_config = agent_service.get_active_llm_config(current_user.id, function_name="script_analysis") 
    if not llm_config:
         llm_config = agent_service.get_active_llm_config(current_user.id, category="LLM")
    if not llm_config:
         raise HTTPException(status_code=400, detail="No LLM config")
         
    import json
    import re
    try:
        resp = await agent_service.call_llm_agent(messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"【原始剧本】\n{script_content}"}
        ], config=llm_config)
        content, _ = resp
    except Exception:
        # Fallback if call_llm_agent doesn't exist
        try:
            resp = await llm_service.chat_completion_with_fallback([
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"【原始剧本】\n{script_content}"}
            ], llm_config)
            content = resp.get("content", "")
        except Exception:
            resp = await llm_service.generate_content_with_fallback(
                f"【原始剧本】\n{script_content}",
                sys_prompt,
                llm_config
            )
            content = resp.get("content", "")

    match = re.search(r"```json(?:\s|\n)*(.*?)(?:\s|\n)*```", content, re.DOTALL)
    if match:
         content = match.group(1)
         
    try:
        data = json.loads(content)
        episodes_data = data.get("episodes", [])
    except Exception as e:
        logger.error(f"Failed to parse script split JSON: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM response")
        
    if episodes_data:
         episode.script_content = episodes_data[0].get("content", "")
         if episodes_data[0].get("title"):
             episode.title = episodes_data[0]["title"]
         db.commit()
         for ep_data in episodes_data[1:]:
             new_ep = Episode(
                 project_id=project_id,
                 title=ep_data.get("title", "New Episode"),
                 script_content=ep_data.get("content", ""),
                 episode_info=episode.episode_info
             )
             db.add(new_ep)
         db.commit()
         
    return {"status": "success", "episodes": episodes_data}





# entity history/sync/llm moved to entities router

@router.get('/admin/llm_logs')
def get_llm_logs(
    limit: int = 100, 
    offset: int = 0, 
    provider: str = None, 
    tag: str = None, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superusers can view LLM Call Logs")
    query = db.query(LLMCallLog).order_by(LLMCallLog.timestamp.desc())
    if provider:
        query = query.filter(LLMCallLog.provider == provider)
    if tag:
        query = query.filter(LLMCallLog.tag == tag)
    logs = query.offset(offset).limit(limit).all()
    return logs


@router.get("/projects/{project_id}/backup_export")
def export_project_backup(
    project_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id,
        _active_project_clause(),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied")
    
    # Preload required data
    episodes = db.query(Episode).filter(
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).all()
    entities = db.query(Entity).filter(Entity.project_id == project_id).all()
    assets = db.query(Asset).filter(Asset.project_id == project_id, _active_asset_clause()).all()
    
    ep_ids = [e.id for e in episodes]
    scenes = db.query(Scene).filter(Scene.episode_id.in_(ep_ids), _active_scene_clause()).all() if ep_ids else []
    script_segments = db.query(ScriptSegment).filter(ScriptSegment.episode_id.in_(ep_ids)).all() if ep_ids else []
    
    sc_ids = [s.id for s in scenes]
    shots = db.query(Shot).filter(Shot.scene_id.in_(sc_ids), _active_shot_clause()).all() if sc_ids else []

    def to_dict(obj):
        d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        return d

    return {
        "project": to_dict(project),
        "episodes": [to_dict(e) for e in episodes],
        "entities": [to_dict(e) for e in entities],
        "assets": [to_dict(a) for a in assets],
        "scenes": [to_dict(s) for s in scenes],
        "script_segments": [to_dict(seg) for seg in script_segments],
        "shots": [to_dict(sh) for sh in shots]
    }

class ImportBackupPayload(BaseModel):
    backup: dict

@router.post("/projects/import_backup")
def import_project_backup(
    payload: ImportBackupPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    data = payload.backup
    if not data or "project" not in data:
        raise HTTPException(status_code=400, detail="Invalid backup payload")

    p_data = data["project"]
    proj = Project(
        title=p_data.get("title", "Imported Project") + " (Imported)",
        owner_id=current_user.id,
        global_info=p_data.get("global_info", {})
    )
    db.add(proj)
    db.flush()

    new_project_id = proj.id

    episodes = data.get("episodes", [])
    entities = data.get("entities", [])
    assets = data.get("assets", [])
    scenes = data.get("scenes", [])
    script_segments = data.get("script_segments", [])
    shots = data.get("shots", [])

    # Maps old ids to new ids
    ep_map = {}
    sc_map = {}

    for ep in episodes:
        old_ep_id = ep.get("id")
        new_ep = Episode(
            project_id=new_project_id,
            title=ep.get("title", ""),
            episode_info=ep.get("episode_info", {}),
            script_content=ep.get("script_content", ""),
            character_profiles=ep.get("character_profiles", []),
            ai_scene_analysis_result=ep.get("ai_scene_analysis_result"),
            ai_scene_analysis_scene_markdown=ep.get("ai_scene_analysis_scene_markdown"),
            ai_scene_analysis_subject_index=ep.get("ai_scene_analysis_subject_index"),
            ai_scene_analysis_adaptation=ep.get("ai_scene_analysis_adaptation"),
            ai_entity_design_result=ep.get("ai_entity_design_result"),
            ai_stage_outputs=ep.get("ai_stage_outputs")
        )
        db.add(new_ep)
        db.flush()
        ep_map[old_ep_id] = new_ep.id

    for ent in entities:
        new_ent = Entity(
            project_id=new_project_id,
            episode_id=ep_map.get(ent.get("episode_id")) if ent.get("episode_id") else None,
            name=ent.get("name"),
            type=ent.get("type"),
            description=ent.get("description"),
            name_en=ent.get("name_en"),
            base_name_en=ent.get("base_name_en"),
            gender=ent.get("gender"),
            role=ent.get("role"),
            archetype=ent.get("archetype"),
            appearance_cn=ent.get("appearance_cn"),
            clothing=ent.get("clothing"),
            action_characteristics=ent.get("action_characteristics"),
            atmosphere=ent.get("atmosphere"),
            visual_params=ent.get("visual_params"),
            narrative_description=ent.get("narrative_description"),
            visual_dependencies=ent.get("visual_dependencies", []),
            dependency_strategy=ent.get("dependency_strategy", {}),
            image_url=ent.get("image_url"),
            generation_prompt_en=ent.get("generation_prompt_en"),
            generation_prompt_cn=ent.get("generation_prompt_cn"),
            anchor_description=ent.get("anchor_description"),
            custom_attributes=ent.get("custom_attributes", {})
        )
        db.add(new_ent)

    for a in assets:
        new_asset = Asset(
            user_id=current_user.id,
            project_id=new_project_id,
            episode_id=ep_map.get(a.get("episode_id")) if a.get("episode_id") else None,
            is_current_project_asset=a.get("is_current_project_asset", False),
            type=a.get("type"),
            url=a.get("url"),
            filename=a.get("filename"),
            meta_info=a.get("meta_info", {}),
            remark=a.get("remark")
        )
        db.add(new_asset)

    for seg in script_segments:
        new_seg = ScriptSegment(
            episode_id=ep_map.get(seg.get("episode_id")),
            pid=seg.get("pid"),
            title=seg.get("title"),
            content_revised=seg.get("content_revised"),
            content_original=seg.get("content_original"),
            narrative_function=seg.get("narrative_function"),
            analysis=seg.get("analysis")
        )
        db.add(new_seg)

    for sc in scenes:
        old_sc_id = sc.get("id")
        new_sc = Scene(
            episode_id=ep_map.get(sc.get("episode_id")),
            scene_no=sc.get("scene_no"),
            scene_name=sc.get("scene_name"),
            original_script_text=sc.get("original_script_text"),
            equivalent_duration=sc.get("equivalent_duration"),
            core_scene_info=sc.get("core_scene_info"),
            environment_name=sc.get("environment_name"),
            linked_characters=sc.get("linked_characters"),
            key_props=sc.get("key_props"),
            ai_shots_result=sc.get("ai_shots_result")
        )
        db.add(new_sc)
        db.flush()
        sc_map[old_sc_id] = new_sc.id

    for sh in shots:
        new_sh = Shot(
            scene_id=sc_map.get(sh.get("scene_id")),
            project_id=new_project_id,
            episode_id=ep_map.get(sh.get("episode_id")),
            shot_id=sh.get("shot_id"),
            shot_name=sh.get("shot_name"),
            scene_code=sh.get("scene_code"),
            start_frame=sh.get("start_frame"),
            end_frame=sh.get("end_frame"),
            video_content=sh.get("video_content"),
            duration=sh.get("duration"),
            keyframes=sh.get("keyframes"),
            associated_entities=sh.get("associated_entities"),
            shot_logic_cn=sh.get("shot_logic_cn"),
            technical_notes=sh.get("technical_notes"),
            image_url=sh.get("image_url"),
            video_url=sh.get("video_url"),
            prompt=sh.get("prompt")
        )
        db.add(new_sh)

    db.commit()
    return {"message": "Import successful", "project_id": new_project_id}



# Refresh cross-router helpers after local definitions are complete.
_bind_endpoint_helpers()

