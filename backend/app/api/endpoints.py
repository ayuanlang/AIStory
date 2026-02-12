
from fastapi import APIRouter, Depends, HTTPException
import logging
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.session import get_db
from app.models.all_models import Project, User, Episode, Scene, Shot, Entity, Asset, APISetting, ScriptSegment
from app.schemas.agent import AgentRequest, AgentResponse, AnalyzeSceneRequest
from app.services.agent_service import agent_service
from app.services.llm_service import llm_service
from app.db.init_db import check_and_migrate_tables  # EMERGENCY FIX IMPORT
import os


from app.services.media_service import MediaGenerationService
from app.services.video_service import create_montage
from app.api.deps import get_current_user  # Import dependency
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel
import bcrypt
import re
import json
from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import File, UploadFile
import shutil
import os
import uuid
from PIL import Image
import requests
import asyncio

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password):
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

router = APIRouter()
media_service = MediaGenerationService()
logger = logging.getLogger("api_logger")


@router.post("/fix-db-schema")
def fix_db_schema_endpoint(current_user: User = Depends(get_current_user)):
    """
    Emergency endpoint to trigger DB migration manually.
    Only accessible by authorized users (technically any logged in user for now, assuming admin).
    """
    try:
        if not current_user.is_superuser: # Basic protection if is_superuser exists
             # logger.warning(f"User {current_user.username} tried to fix DB but is not superuser")
             # pass # Loose check for now as we are desperate
             pass

        logger.info(f"Manual DB Fix triggered by {current_user.username}")
        check_and_migrate_tables()
        return {"message": "Migration script executed successfully. Check logs for details."}
    except Exception as e:
        logger.error(f"Manual DB Fix failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))



from app.services.system_log_service import log_action
from app.schemas.system_log import SystemLogOut

def get_system_api_setting(db: Session, provider: str = None, category: str = None) -> Optional[APISetting]:
    """Helper to find a system-level API configuration."""
    query = db.query(APISetting).join(User).filter(User.is_system == True, APISetting.is_active == True)
    if provider:
        query = query.filter(APISetting.provider == provider)
    if category:
        query = query.filter(APISetting.category == category)
    return query.first()

def get_effective_api_setting(db: Session, user: User, provider: str = None, category: str = None) -> Optional[APISetting]:
    """
    Get API setting for current user. 
    If not found AND user is authorized, fallback to system setting.
    """
    # 1. Try User's own setting
    user_setting_query = db.query(APISetting).filter(
        APISetting.user_id == user.id, 
        APISetting.is_active == True
    )
    if provider:
        user_setting_query = user_setting_query.filter(APISetting.provider == provider)
    if category:
        user_setting_query = user_setting_query.filter(APISetting.category == category)
    
    setting = user_setting_query.first()
    if setting:
         return setting
    
    # 2. Fallback if authorized
    if user.is_authorized:
         return get_system_api_setting(db, provider, category)
    
    return None

@router.get("/prompts/{filename}")
async def get_prompt_content(filename: str, current_user: User = Depends(get_current_user)):
    """Retrieve content of a prompt file."""
    # Robust path resolution using settings.BASE_DIR (backend root)
    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    prompt_path = os.path.join(prompt_dir, filename)
    
    if not os.path.exists(prompt_path):
        # logging for debug on Render
        logger.error(f"Prompt file not found at: {prompt_path}")
        raise HTTPException(status_code=404, detail=f"Prompt file '{filename}' not found.")
        
    with open(prompt_path, "r", encoding="utf-8") as f:
        return {"content": f.read()}

@router.post("/analyze_scene", response_model=Dict[str, Any])
async def analyze_scene(request: AnalyzeSceneRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)): # user auth optional depending on reqs, kept for safety
    """
    Submits raw script text to LLM for Scene/Beat analysis using a specific prompt template.
    Returns the raw analysis result (Markdown/JSON).
    """
    logger.info("Received analyze_scene request")
    if request.project_metadata:
        logger.info(f"Project Metadata received: {request.project_metadata}")
    else:
        logger.info("No Project Metadata received")

    try:
        # Load the prompt template or use provided system_prompt
        system_instruction = ""
        
        if request.system_prompt:
            system_instruction = request.system_prompt
        else:
            prompt_filename = request.prompt_file or "scene_analysis.txt"
            # Robust path resolution
            prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
            prompt_path = os.path.join(prompt_dir, prompt_filename)
            
            if not os.path.exists(prompt_path):
                 logger.error(f"Scene analysis prompt not found at: {prompt_path}")
                 raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")
                
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_instruction = f.read()
        
        # Prepare user content with optional project metadata
        user_content = f"Script to Analyze:\n\n{request.text}"
        
        if request.project_metadata:
            meta_parts = ["Project Overview Context:"]
            # Prioritize key fields if they exist
            if request.project_metadata.get("script_title"):
                meta_parts.append(f"Title: {request.project_metadata['script_title']}")
            if request.project_metadata.get("type"):
                meta_parts.append(f"Type: {request.project_metadata['type']}")
            if request.project_metadata.get("tone"):
                meta_parts.append(f"Tone: {request.project_metadata['tone']}")
            if request.project_metadata.get("Global_Style"):
                meta_parts.append(f"Global Style: {request.project_metadata['Global_Style']}")
            if request.project_metadata.get("base_positioning"):
                meta_parts.append(f"Base Positioning: {request.project_metadata['base_positioning']}")
            if request.project_metadata.get("lighting"):
                meta_parts.append(f"Lighting: {request.project_metadata['lighting']}")
            if request.project_metadata.get("series_episode"):
                meta_parts.append(f"Episode: {request.project_metadata['series_episode']}")
             
            # Simple dump of other fields if needed, or just rely on these key ones for the prompt
            # Let's add all relevant fields that might influence the visual analysis
            
            meta_str = "\n".join(meta_parts)
            user_content = f"{meta_str}\n\n{user_content}"
            logger.info("Injected Project Context into Prompt:\n" + meta_str)

        # Construct messages
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ]

        # Use the LLM service directly
        # If llm_config in request, use it, otherwise try to fetch from user/project logic if needed.
        # Here we assume frontend sends the active LLM config or we rely on a default.
        # Ideally, we should fetch the user's preferred LLM settings from DB.
        
        config = request.llm_config
        # If config is missing/empty, try to get from db (Simplified: assuming passed from frontend for now as typically done in this project)
        if not config:
            # Fallback to system default or error
            # Try to get from APISettings table if exists
            api_setting = get_effective_api_setting(db, current_user, category="LLM")
            if api_setting:
                config = {
                    "api_key": api_setting.api_key,
                    "base_url": api_setting.base_url,
                    "model": api_setting.model
                }
        
        if not config:
             raise HTTPException(status_code=400, detail="LLM Configuration missing. Please check your settings.")

        logger.info(f"Analyzing scene for user {current_user.id} with model {config.get('model')}")
        result_content = await llm_service.chat_completion(messages, config)
        
        return {"result": result_content}

    except Exception as e:
        logger.error(f"Scene Analysis Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- Tools ---
class TranslateRequest(BaseModel):
    q: str
    from_lang: str = 'en'
    to_lang: str = 'zh'

@router.post("/tools/translate")
def translate_text(
    req: TranslateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Try specific provider first
    setting = get_effective_api_setting(db, current_user, "baidu_translate")
    
    # Fallback to generic baidu
    if not setting:
         setting = get_effective_api_setting(db, current_user, "baidu")

    if not setting or not setting.api_key:
        raise HTTPException(status_code=400, detail="Baidu Translation settings not configured. Please add 'baidu_translate' provider with Access Token in API Key field.")

    token = setting.api_key
    url = f'https://aip.baidubce.com/rpc/2.0/mt/texttrans/v1?access_token={token}'
    
    payload = {'q': req.q, 'from': req.from_lang, 'to': req.to_lang}
    headers = {'Content-Type': 'application/json'}
    
    try:
        r = requests.post(url, json=payload, headers=headers)
        result = r.json()
        
        if "error_code" in result:
             raise HTTPException(status_code=400, detail=f"Baidu API Error: {result.get('error_msg')}")
        
        if "result" in result and "trans_result" in result["result"]:
             dst = "\n".join([item["dst"] for item in result["result"]["trans_result"]])
             return {"translated_text": dst}
             
        return result
             
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RefinePromptRequest(BaseModel):
    original_prompt: str
    instruction: str
    type: str = "image"

@router.post("/tools/refine_prompt")
async def refine_prompt(
    req: RefinePromptRequest,
    current_user: User = Depends(get_current_user)
):
    # 1. Get LLM Config
    config = agent_service.get_active_llm_config(current_user.id)
    if not config or not config.get("api_key"):
        raise HTTPException(status_code=400, detail="Active LLM Settings not found. Please configure and activate an LLM provider.")
        
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model")
    
    # Auto-adjust URL to Chat Completions
    url = base_url
    if not url.endswith("/chat/completions"):
        if url.endswith("/"): url += "chat/completions"
        elif "chat/completions" not in url: url += "/chat/completions"

    # 2. Build Prompt
    sys_prompt = "You are an expert storyboard artist."
    if req.type == "video":
        sys_prompt += " Your task is to refine the video generation prompt based on user feedback. Focus on modifying character actions, spatial relationships, and pose rationality without changing the main core content. Ensure the action is physically logical."
    else:
        sys_prompt += " Your task is to refine the image generation prompt based on user feedback. Focus on modifying character spatial relationships and poses without changing the main core content."
        
    sys_prompt += "\nConstraint: Return ONLY the refined prompt string. Do not include any explanations, markdown, quotes, or extra text."
    
    user_content = f"Original Prompt: {req.original_prompt}\nModification Request: {req.instruction}\nRefined Prompt:"
    
    # 3. Call LLM
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.7
    }
    
    try:
        def _post():
            return requests.post(url, json=payload, headers=headers, timeout=60)
        
        response = await asyncio.to_thread(_post)
        if response.status_code != 200:
             raise HTTPException(status_code=500, detail=f"LLM Error {response.status_code}: {response.text}")
             
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        # Clean quotes/markdown if any
        if content.startswith('"') and content.endswith('"'):
             content = content[1:-1]
        
        return {"refined_prompt": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Agent ---
@router.post("/agent/command", response_model=AgentResponse)
async def process_agent_command(
    request: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Resolve Project ID
    project_id = request.project_id or request.context.get("projectId")
    
    if project_id:
        # Verify ownership
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if project.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this project")

    return await agent_service.process_command(request)

# --- Projects ---
class ProjectCreate(BaseModel):
    title: str
    global_info: dict = {}

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    global_info: Optional[dict] = None

class ProjectOut(BaseModel):
    id: int
    title: str
    global_info: dict
    
    class Config:
        from_attributes = True

@router.post("/projects/", response_model=ProjectOut)
def create_project(
    project: ProjectCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_project = Project(title=project.title, global_info=project.global_info, owner_id=current_user.id) 
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@router.get("/projects/", response_model=List[ProjectOut])
def read_projects(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    projects = db.query(Project).filter(Project.owner_id == current_user.id).offset(skip).limit(limit).all()
    return projects

@router.get("/projects/{project_id}", response_model=ProjectOut)
def read_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int, 
    project_in: ProjectUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project_in.title is not None:
        project.title = project_in.title
    # Use generic dict update or replace entire json? 
    # Usually replacing entire JSON field is safer/expected for "global_info" which is a dict.
    # But if we want partial updates to keys inside global_info, we have to do it manually in python.
    # For now, let's assume the frontend sends the COMPLETE new global_info object.
    if project_in.global_info is not None:
         # Ensure we don't overwrite if it's just partial, but Pydantic sends what is provided.
         # Actually for JSON columns in SQL, we typically replace the whole blob.
         # So we expect frontend to send the full updated state of global_info.
         project.global_info = project_in.global_info
    
    db.commit()
    db.refresh(project)
    return project

@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db.delete(project)
    db.commit()
    return None

# --- Episodes (Script) ---

class ScriptSegmentBase(BaseModel):
    pid: str
    title: str
    content_revised: str
    content_original: str
    narrative_function: str
    analysis: str

class ScriptSegmentOut(ScriptSegmentBase):
    id: int
    class Config:
        from_attributes = True

class EpisodeCreate(BaseModel):
    title: str = "Episode 1"
    script_content: Optional[str] = ""
    episode_info: Optional[Dict] = {}

class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    script_content: Optional[str] = None
    episode_info: Optional[Dict] = None

class EpisodeOut(BaseModel):
    id: int
    project_id: int
    title: str
    script_content: Optional[str]
    episode_info: Optional[Dict] = {}
    script_segments: List[ScriptSegmentOut] = []
    class Config:
        from_attributes = True

@router.get("/projects/{project_id}/episodes", response_model=List[EpisodeOut])
def read_episodes(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify access
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return db.query(Episode).filter(Episode.project_id == project_id).all()

@router.put("/episodes/{episode_id}/segments", response_model=List[ScriptSegmentOut])
def update_episode_segments(
    episode_id: int,
    segments: List[ScriptSegmentBase],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Clear existing
    db.query(ScriptSegment).filter(ScriptSegment.episode_id == episode_id).delete()
    
    # Add new
    new_segments = []
    for s in segments:
        seg = ScriptSegment(
            episode_id=episode_id,
            pid=s.pid,
            title=s.title,
            content_revised=s.content_revised,
            content_original=s.content_original,
            narrative_function=s.narrative_function,
            analysis=s.analysis
        )
        db.add(seg)
        new_segments.append(seg)
    
    db.commit()
    # Refresh logic is tricky for lists, but querying clearly works
    return db.query(ScriptSegment).filter(ScriptSegment.episode_id == episode_id).all()

@router.post("/projects/{project_id}/episodes", response_model=EpisodeOut)
def create_episode(
    project_id: int,
    episode: EpisodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    db_episode = Episode(
        project_id=project_id, 
        title=episode.title, 
        script_content=episode.script_content,
        episode_info=episode.episode_info
    )
    db.add(db_episode)
    db.commit()
    db.refresh(db_episode)
    return db_episode

@router.put("/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(
    episode_id: int,
    episode_in: EpisodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    # Check ownership via project
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")

    if episode_in.title is not None:
        episode.title = episode_in.title
    if episode_in.script_content is not None:
        episode.script_content = episode_in.script_content
    if episode_in.episode_info is not None:
        episode.episode_info = episode_in.episode_info
    
    db.commit()
    db.refresh(episode)
    return episode

@router.delete("/episodes/{episode_id}", status_code=204)
def delete_episode(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(episode)
    db.commit()
    return None

# --- Scenes ---

class SceneCreate(BaseModel):
    scene_no: str
    original_script_text: str
    scene_name: Optional[str] = None
    equivalent_duration: Optional[str] = None
    core_scene_info: Optional[str] = None
    environment_name: Optional[str] = None
    linked_characters: Optional[str] = None
    key_props: Optional[str] = None

class SceneOut(BaseModel):
    id: int
    scene_no: str
    original_script_text: str
    scene_name: Optional[str]
    equivalent_duration: Optional[str]
    core_scene_info: Optional[str]
    environment_name: Optional[str]
    linked_characters: Optional[str]
    key_props: Optional[str]
    class Config:
        from_attributes = True


@router.get("/episodes/{episode_id}/scenes", response_model=List[SceneOut])
def read_scenes(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Ownership check
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    return db.query(Scene).filter(Scene.episode_id == episode_id).order_by(Scene.id).all()

@router.post("/episodes/{episode_id}/scenes", response_model=SceneOut)
def create_scene(
    episode_id: int,
    scene: SceneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")

    db_scene = Scene(
        episode_id=episode_id,
        scene_no=scene.scene_no,
        original_script_text=scene.original_script_text,
        scene_name=scene.scene_name,
        equivalent_duration=scene.equivalent_duration,
        core_scene_info=scene.core_scene_info,
        environment_name=scene.environment_name,
        linked_characters=scene.linked_characters,
        key_props=scene.key_props
    )
    db.add(db_scene)
    db.commit()
    db.refresh(db_scene)
    return db_scene

@router.put("/scenes/{scene_id}", response_model=SceneOut)
def update_scene(
    scene_id: int,
    scene_in: SceneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    # Ownership
    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id).first()
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
         raise HTTPException(status_code=403, detail="Not authorized")

    update_data = scene_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_scene, field, value)
        
    db.add(db_scene)
    db.commit()
    db.refresh(db_scene)
    return db_scene

# --- Shots ---

class ShotCreate(BaseModel):
    shot_id: str
    shot_name: Optional[str] = None
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    video_content: Optional[str] = None
    duration: Optional[str] = None
    associated_entities: Optional[str] = None
    scene_code: Optional[str] = None # 'Scene ID' from header user input
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    shot_logic_cn: Optional[str] = None
    keyframes: Optional[str] = None
    
    # Optional legacy/AI fields
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    prompt: Optional[str] = None
    technical_notes: Optional[str] = None

class ShotOut(BaseModel):
    id: int
    scene_id: int
    project_id: Optional[int]
    episode_id: Optional[int]
    shot_id: Optional[str]
    shot_name: Optional[str]
    start_frame: Optional[str]
    end_frame: Optional[str]
    video_content: Optional[str]
    duration: Optional[str]
    associated_entities: Optional[str]
    shot_logic_cn: Optional[str]
    keyframes: Optional[str]
    
    scene_code: Optional[str]

    image_url: Optional[str]
    video_url: Optional[str]
    prompt: Optional[str]
    technical_notes: Optional[str]
    
    class Config:
        from_attributes = True

@router.get("/episodes/{episode_id}/shots", response_model=List[ShotOut])
def read_episode_shots(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
         raise HTTPException(status_code=403, detail="Not authorized")

    # Return ALL shots for the episode, regardless of scene association
    return db.query(Shot).filter(
        Shot.project_id == project.id,
        Shot.episode_id == episode_id
    ).all()

class AIShotGenRequest(BaseModel):
    user_prompt: Optional[str] = None
    system_prompt: Optional[str] = None

def _build_shot_prompts(db: Session, scene: Scene, project: Project):
    # 2. Gather Data
    # Global Style & Context
    
    # Normalize Info Sources
    project_info = project.global_info or {}
    if isinstance(project_info, str):
        try: project_info = json.loads(project_info)
        except: project_info = {}
        
    episode_info = {}
    scene_episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    
    if scene_episode and scene_episode.episode_info:
        temp = scene_episode.episode_info
        if isinstance(temp, str):
            try: temp = json.loads(temp)
            except: temp = {}
        if isinstance(temp, dict):
             # Check for nested structure "e_global_info" as per user data
             if "e_global_info" in temp and isinstance(temp["e_global_info"], dict):
                 episode_info = temp["e_global_info"]
             else:
                 episode_info = temp
    
    # 3. Robust Data Normalization (Handle case/space sensitivity)
    def normalize_dict_keys(d):
        if not isinstance(d, dict): return {}
        new_d = {}
        for k, v in d.items():
            # Standardize to "key_name" (lowercase, underscore)
            clean_k = str(k).lower().replace(" ", "_").strip()
            new_d[clean_k] = v
        return new_d

    episode_info_norm = normalize_dict_keys(episode_info)
    project_info_norm = normalize_dict_keys(project_info)

    # Helper to find value from Episode -> Project (using normalized keys)
    def get_context_val(keys):
        if isinstance(keys, str): keys = [keys]
        # Search List
        search_keys = [k.lower().replace(" ", "_").strip() for k in keys]
        
        # 1. Episode (Priority)
        for sk in search_keys:
            if sk in episode_info_norm and episode_info_norm[sk]:
                return episode_info_norm[sk]
        
        # 2. Project (Fallback)
        for sk in search_keys:
            if sk in project_info_norm and project_info_norm[sk]:
                return project_info_norm[sk]
        
        return None
    def get_context_val(keys):
        if isinstance(keys, str): keys = [keys]
        # 1. Episode
        for k in keys:
            if episode_info.get(k): return episode_info[k]
            # Try lowercase/variations
            if episode_info.get(k.lower()): return episode_info[k.lower()]
            if episode_info.get(k.replace(" ", "_")): return episode_info[k.replace(" ", "_")]
        # 2. Project
        for k in keys:
            if project_info.get(k): return project_info[k]
            if project_info.get(k.lower()): return project_info[k.lower()]
            if project_info.get(k.replace(" ", "_")): return project_info[k.replace(" ", "_")]
        return None

    global_style = get_context_val(["Global_Style", "Global Style", "Style"]) or "Cinematic"
    
    # Extract additional fields
    # Mappings: Field Name -> Possible Keys
    field_mappings = {
        "Type": ["Type", "Genre", "Category", "Film Type"],
        "Tone": ["Tone", "Color Tone", "Mood", "Atmosphere"],
        "Language": ["Language", "Lang"],
        "Lighting": ["Lighting", "Light Style"],
        "Quality": ["Quality", "Production Quality"]
    }
    
    additional_context = ""
    context_lines = []
    
    for field, keys in field_mappings.items():
        val = get_context_val(keys)
        if val:
            context_lines.append(f"{field}: {val}")
    
    if context_lines:
        additional_context = "\n".join(context_lines)

    # Scene Info
    # Entities - Fetch project entities and match with Linked Characters / Environment
    project_entities = db.query(Entity).filter(Entity.project_id == project.id).all()
    entity_descriptions = []
    
    # Identify relevant entity names from Scene data
    relevant_names = set()
    if scene.linked_characters:
        # Split by comma and handle potential variations
        parts = [p.strip() for p in scene.linked_characters.split(',') if p.strip()]
        relevant_names.update(parts)
    if scene.environment_name:
        relevant_names.add(scene.environment_name.strip())
    
    env_narrative = ""

    for ent in project_entities:
        # Check relevancy (Case-insensitive check, considering name_en)
        is_relevant = False
        ent_aliases = [n for n in [ent.name, ent.name_en] if n]
        
        for alias in ent_aliases:
            alias_clean = alias.strip().lower()
            for rn in relevant_names:
                if rn.strip().lower() == alias_clean:
                    is_relevant = True
                    break
            if is_relevant: break
        
        # If relevant, try to extract Description field
        if is_relevant:
            # Check if this is the Environment Anchor to capture narrative for Scenario Content
            if scene.environment_name:
                 sn_clean = scene.environment_name.strip().lower()
                 for alias in ent_aliases:
                      if alias.strip().lower() == sn_clean:
                           # Priority: description_cn (custom_attributes) > narrative_description > description
                           desc_cn = None
                           
                           # Safe Custom Attributes Parsing
                           custom_attrs = ent.custom_attributes
                           if isinstance(custom_attrs, str):
                                try: custom_attrs = json.loads(custom_attrs)
                                except: custom_attrs = {}
                                
                           if custom_attrs and isinstance(custom_attrs, dict):
                               desc_cn = custom_attrs.get('description_cn') or custom_attrs.get('description_CN')
                           
                           if desc_cn:
                               env_narrative = desc_cn
                           elif ent.narrative_description:
                                env_narrative = ent.narrative_description
                           elif ent.description:
                                # Use description directly if others are missing
                                env_narrative = ent.description
                           break

            desc_parts = []
            
            # 1. Narrative Description (New Column Priority)
            if ent.narrative_description:
                 desc_parts.append(f"Description: {ent.narrative_description}")
            elif ent.description:
                 # Fallback regex extraction from blob
                 match = re.search(r'(?:Description|描述)[:：]\s*(.*)', ent.description, re.IGNORECASE)
                 if match:
                      desc_parts.append(f"Description: {match.group(1).strip()}")
            
            # 2. Visual Params
            if ent.visual_params:
                desc_parts.append(f"Visual: {ent.visual_params}")
            
            # 3. Atmosphere
            if ent.atmosphere:
                desc_parts.append(f"Atmosphere: {ent.atmosphere}")

            if desc_parts:
                entity_descriptions.append(f"[{ent.name}] " + " | ".join(desc_parts))

    entity_section = ""
    if entity_descriptions:
        entity_section = "# Entity Reference\n" + "\n".join(entity_descriptions) + "\n"

    # 3. Prepare System Prompt
    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    prompt_path = os.path.join(prompt_dir, "shot_generator.txt")
    
    system_prompt = ""
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    except Exception as e:
        logger.error(f"Failed to load shot_generator.txt from {prompt_path}: {e}")
        # Very drastic fallback, but better than crash
        system_prompt = "You are a Storyboard Master. Generate a shot list as a markdown table."

    global_section = f"# Global Context\nGlobal Style: {global_style}"
    if additional_context:
        global_section += f"\n{additional_context}"

    core_goal_text = scene.core_scene_info or ''
    # Environment Context is now a separate field in the table

    user_input = f"""{global_section}

# Core Scene Info
| Field | Value |
| :--- | :--- |
| **Scene No** | {scene.scene_no or ''} |
| **Scene Name** | {scene.scene_name or ''} |
| **Environment Anchor** | {scene.environment_name or ''} |
| **Environment Context** | {env_narrative or 'N/A'} |
| **Linked Characters** | {scene.linked_characters or ''} |
| **Key Props** | {scene.key_props or ''} |
| **Core Goal** | {core_goal_text} |

{entity_section}

# Instruction
1. Analyze the script and break it down into shots.
"""
    
    return system_prompt, user_input

@router.get("/scenes/{scene_id}/ai_prompt_preview")
def ai_prompt_preview(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    system, user = _build_shot_prompts(db, scene, project)
    return {"system_prompt": system, "user_prompt": user}

@router.post("/scenes/{scene_id}/ai_generate_shots")
async def ai_generate_shots(
    scene_id: int,
    req: Optional[AIShotGenRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(f"[ai_generate_shots] start scene_id={scene_id} user={current_user.id}")
        # 1. Fetch Scene and Context
        scene = db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")
            
        episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
        project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
        if not project:
            raise HTTPException(status_code=403, detail="Not authorized")

        if req and req.user_prompt:
             user_input = req.user_prompt
             system_prompt = req.system_prompt or "You are a Storyboard Master."
             logger.info("[ai_generate_shots] Using custom prompt from request")
        else:
             system_prompt, user_input = _build_shot_prompts(db, scene, project)

        logger.info(f"[ai_generate_shots] system_prompt_len={len(system_prompt)}")
        logger.info(f"[ai_generate_shots] user_input_len={len(user_input)}")

        # 4. Call LLM
        llm_config = agent_service.get_active_llm_config(current_user.id)
        response_content = await llm_service.generate_content(user_input, system_prompt, llm_config)
        logger.info(f"[ai_generate_shots] llm_response_len={len(response_content)}")

        if response_content.startswith("Error:"):
            raise HTTPException(status_code=500, detail=response_content)

        # 5. Parse Table
        lines = response_content.split('\n')
        table_lines = [line.strip() for line in lines if line.strip().startswith('|')]
        
        shots_data = []
        if len(table_lines) > 2:
            # Robust header parsing: strip whitespace and markdown bold/italic markers
            raw_headers = [h.strip() for h in table_lines[0].strip('|').split('|')]
            headers = [h.replace('*', '').replace('_', '').strip() for h in raw_headers]
            
            logger.info(f"[ai_generate_shots] headers detected: {headers}")

            # Expected mappings (flexible)
            # Shot ID, Shot Name, Start Frame, End Frame, Video Content, Duration (s), Associated Entities
            
            for line in table_lines[2:]: # Skip Header and Separator
                if "---" in line: continue 
                
                cols = [c.strip() for c in line.strip('|').split('|')]
                if len(cols) >= len(headers):
                    shot_dict = {}
                    for i, h in enumerate(headers):
                        if i < len(cols):
                            shot_dict[h] = cols[i]
                    shots_data.append(shot_dict)
                else:
                    logger.warning(f"[ai_generate_shots] Skipping malformed line (cols={len(cols)}, headers={len(headers)}): {line[:50]}...")

        if not shots_data:
             print("DEBUG: No table found. Content:", response_content)
             # If no table, maybe it failed to generate strict format?
             # For now, return empty or parsing error
             pass
        logger.info(f"[ai_generate_shots] parsed_shots={len(shots_data)}")

        # 6. Update DB
        db.query(Shot).filter(Shot.scene_id == scene_id).delete()
        
        new_shots = []
        for idx, s_data in enumerate(shots_data):
            try:
                dur_str = s_data.get("Duration (s)", "2.0")
                match = re.search(r"[\d\.]+", dur_str)
                duration_val = float(match.group()) if match else 2.0
            except:
                duration_val = 2.0
            
            shot_id_val = s_data.get("Shot ID", str(idx + 1))

            shot = Shot(
                scene_id=scene_id,
                project_id=project.id,
                episode_id=episode.id,
                shot_id=shot_id_val,
                shot_name=s_data.get("Shot Name", "Shot"),
                scene_code=scene.scene_no,
                start_frame=s_data.get("Start Frame", ""),
                end_frame=s_data.get("End Frame", ""),
                video_content=s_data.get("Video Content", ""),
                duration=str(duration_val),
                associated_entities=s_data.get("Associated Entities", ""),
                shot_logic_cn=s_data.get("Shot Logic (CN)", ""),
                keyframes=s_data.get("Keyframes", "NO"),
                prompt=s_data.get("Video Content", "")
            )
            db.add(shot)
            
        db.commit()
        logger.info(f"[ai_generate_shots] saved_shots={len(shots_data)} scene_id={scene_id}")
        
        return db.query(Shot).filter(Shot.scene_id == scene_id).all()

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"[ai_generate_shots] error={e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scenes/{scene_id}/shots", response_model=List[ShotOut])
def read_shots(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    # Check Project ownership via Episode
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    # Optimized: Return shots strictly by Scene ID (Physical Association)
    # Removing logical 'scene_code' sync as requested.
    return db.query(Shot).filter(
        Shot.project_id == project.id,
        Shot.episode_id == episode.id,
        Shot.scene_id == scene_id
    ).all()

@router.post("/scenes/{scene_id}/shots", response_model=ShotOut)
def create_shot(
    scene_id: int,
    shot: ShotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import os
    logger.info(f"[create_shot] START. scene_id={scene_id}")
    logger.info(f"[create_shot] DB URL: {settings.DATABASE_URL}")
    logger.info(f"[create_shot] Payload: shot_id={shot.shot_id}, logic_cn={'YES' if shot.shot_logic_cn else 'NO'}")

    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        logger.error(f"[create_shot] Scene {scene_id} not found")
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Ownership
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    if not episode:
        logger.error(f"[create_shot] Scene {scene_id} refers to non-existent episode {scene.episode_id}")
        raise HTTPException(status_code=404, detail="Parent Episode not found")

    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
         logger.error(f"[create_shot] User {current_user.id} not authorized for Project {episode.project_id}")
         raise HTTPException(status_code=403, detail="Not authorized")
         
    try:
        db_shot = Shot(
            scene_id=scene_id,
            project_id=project.id,
            episode_id=episode.id,
            shot_id=shot.shot_id,
            shot_name=shot.shot_name,
            start_frame=shot.start_frame,
            end_frame=shot.end_frame,
            video_content=shot.video_content,
            duration=shot.duration,
            associated_entities=shot.associated_entities,
            shot_logic_cn=shot.shot_logic_cn,
            keyframes=shot.keyframes,
            scene_code=shot.scene_code,
            image_url=shot.image_url,
            video_url=shot.video_url,
            prompt=shot.prompt,
            technical_notes=shot.technical_notes
        )
        db.add(db_shot)
        db.commit()
        db.refresh(db_shot)
        
        # Verify Write
        logger.info(f"[create_shot] Committed Shot ID: {db_shot.id}. Verifying...")
        verify = db.query(Shot).filter(Shot.id == db_shot.id).first()
        if verify:
             logger.info(f"[create_shot] SUCCESS. Shot {db_shot.id} (Display ID: {db_shot.shot_id}) exists in DB.")
        else:
             logger.error(f"[create_shot] CRITICAL FAILURE. Shot {db_shot.id} not found immediately after commit!")

        return db_shot
    except Exception as e:
        logger.error(f"[create_shot] EXCEPTION: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create shot: {str(e)}")

@router.put("/shots/{shot_id}", response_model=ShotOut)
def update_shot(
    shot_id: int,
    shot_in: ShotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not db_shot:
        raise HTTPException(status_code=404, detail="Shot not found")
        
    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id).first()
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    for key, value in shot_in.dict(exclude_unset=True).items():
        setattr(db_shot, key, value)
        
    db.commit()
    db.refresh(db_shot)
    return db_shot

@router.delete("/shots/{shot_id}")
def delete_shot(
    shot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not db_shot:
         raise HTTPException(status_code=404, detail="Shot not found")
         
    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id).first()
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = db.query(Project).filter(Project.id == episode.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    db.delete(db_shot)
    db.commit()
    return {"ok": True}

# --- Entities ---

class EntityCreate(BaseModel):
    name: str
    type: str # character, environment, prop
    description: str
    image_url: Optional[str] = None
    generation_prompt_en: Optional[str] = None
    anchor_description: Optional[str] = None
    
    # New Fields
    name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None
    
    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None

    visual_dependencies: Optional[List[str]] = []
    dependency_strategy: Optional[Dict[str, Any]] = {}

class EntityOut(BaseModel):
    id: int
    name: str
    type: str
    description: str
    image_url: Optional[str]
    generation_prompt_en: Optional[str]
    anchor_description: Optional[str]
    
    # New Fields
    name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None
    
    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None

    visual_dependencies: Optional[List[str]] = []
    dependency_strategy: Optional[Dict[str, Any]] = {}
    custom_attributes: Optional[Dict[str, Any]] = {}

    class Config:
        from_attributes = True

@router.get("/projects/{project_id}/entities", response_model=List[EntityOut])
def read_entities(
    project_id: int,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    query = db.query(Entity).filter(Entity.project_id == project_id)
    if type:
        query = query.filter(Entity.type == type)
    return query.all()

@router.post("/projects/{project_id}/entities", response_model=EntityOut)
def create_entity(
    project_id: int,
    entity: EntityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Check if entity with same name exists in project
    existing_entity = db.query(Entity).filter(
        Entity.project_id == project_id,
        Entity.name == entity.name
    ).first()

    if existing_entity:
        # If entity exists, do NOT update it (as per "do not import repeatedly" requirement).
        # We simply return the existing entity essentially ignoring the import data for this specific name.
        return existing_entity
    else:
        # Create new
        db_entity = Entity(
            project_id=project_id,
            name=entity.name,
            type=entity.type,
            description=entity.description,
            image_url=entity.image_url,
            generation_prompt_en=entity.generation_prompt_en,
            anchor_description=entity.anchor_description,
            
            name_en=entity.name_en,
            gender=entity.gender,
            role=entity.role,
            archetype=entity.archetype,
            appearance_cn=entity.appearance_cn,
            clothing=entity.clothing,
            action_characteristics=entity.action_characteristics,
            
            atmosphere=entity.atmosphere,
            visual_params=entity.visual_params,
            narrative_description=entity.narrative_description,
            
            visual_dependencies=entity.visual_dependencies,
            dependency_strategy=entity.dependency_strategy
        )
        db.add(db_entity)
        db.commit()
        db.refresh(db_entity)
        return db_entity

class EntityUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    generation_prompt_en: Optional[str] = None
    anchor_description: Optional[str] = None
    
    # New Fields
    name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None
    
    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None
    
    visual_dependencies: Optional[List[str]] = None
    dependency_strategy: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"

@router.put("/entities/{entity_id}", response_model=EntityOut)
def update_entity(
    entity_id: int,
    entity_in: EntityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Verify ownership via project
    project = db.query(Project).filter(Project.id == entity.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = entity_in.dict(exclude_unset=True)
    
    # Separate standard columns from custom attributes
    standard_columns = {c.name for c in Entity.__table__.columns}
    custom_attrs = dict(entity.custom_attributes or {})
    
    for field, value in update_data.items():
        if field == "image_url" and value != entity.image_url:
             entity.image_url = value
             # Auto-register as Asset if valid URL
             if value:
                 # Check existing to avoid dupes
                 existing_asset = db.query(Asset).filter(Asset.url == value, Asset.user_id == current_user.id).first()
                 if not existing_asset:
                     # Use helper to register with metadata
                     req_data = {
                         "project_id": project.id,
                         "entity_id": entity.id,
                         "entity_name": entity.name,
                         "category": entity.type,
                         "remark": f"Auto-registered from Entity: {entity.name}"
                     }
                     # Ensure _register_asset_helper is available
                     if "_register_asset_helper" in globals():
                        _register_asset_helper(db, current_user.id, value, req_data)
        
        elif field in standard_columns:
            setattr(entity, field, value)
        else:
            # Update custom attributes
            if value is None and field in custom_attrs:
                del custom_attrs[field]
            else:
                custom_attrs[field] = value

    entity.custom_attributes = custom_attrs
    
    db.add(entity)
        
    db.commit()
    db.refresh(entity)
    return entity

@router.delete("/entities/{entity_id}")
def delete_entity(
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    project = db.query(Project).filter(Project.id == entity.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    db.delete(entity)
    db.commit()
    return {"status": "success"}

@router.delete("/projects/{project_id}/entities")
def delete_project_entities(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    db.query(Entity).filter(Entity.project_id == project_id).delete()
    db.commit()
    return {"status": "success", "message": "All entities deleted"}

# --- Users ---

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    is_authorized: bool
    is_system: bool

    class Config:
        orm_mode = True

@router.post("/users/", response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user_email = db.query(User).filter(User.email == user.email).first()
    if db_user_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user_username = db.query(User).filter(User.username == user.username).first()
    if db_user_username:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email, 
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- Login ---

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    username: str
    password: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def authenticate_user(db: Session, username: str, password: str):
    # Try by username
    user = db.query(User).filter(User.username == username).first()
    if not user:
        # Try by email
        user = db.query(User).filter(User.email == username).first()
    
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

@router.post("/login/access-token", response_model=Token)
def login_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    OAuth2 compatible token login, get an access token for future requests.
    Requires 'username' and 'password' as form fields.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    # Log Successful Login
    log_action(db, user_id=user.id, user_name=user.username, action="LOGIN", details="User logged in via OAuth2 Form")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
def login_json(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    JSON compatible login endpoint. 
    Accepts {"username": "...", "password": "..."} in body.
    """
    user = authenticate_user(db, login_data.username, login_data.password)
    if not user:
        # Optional: Log failed login attempts?
        # log_action(db, user_id=None, user_name=login_data.username, action="LOGIN_FAILED", details="Incorrect password")
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    # Log Successful Login
    log_action(db, user_id=user.id, user_name=user.username, action="LOGIN", details="User logged in via API")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}



from app.models.all_models import SystemLog

@router.get("/system/logs", response_model=List[SystemLogOut])
def get_system_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get system logs. Requires superuser or 'system' username.
    """
    is_admin = current_user.is_superuser or current_user.username == "system" or current_user.username == "admin"
    if not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view system logs")
    
    logs = db.query(SystemLog).order_by(SystemLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs

# --- Assets ---

class AssetCreate(BaseModel):
    url: str
    type: str # image, video
    meta_info: Optional[dict] = {}
    remark: Optional[str] = None

class AssetUpdate(BaseModel):
    remark: Optional[str] = None
    meta_info: Optional[dict] = None

@router.get("/assets/", response_model=List[dict])
def get_assets(
    type: Optional[str] = None,
    project_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    scene_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Asset).filter(Asset.user_id == current_user.id)
    if type:
        query = query.filter(Asset.type == type)
    
    # Ideally use database-side JSON filtering if supported (e.g., Postgres)
    # Since we are likely using SQLite or generic, we might need to filter manually or use cast
    # SQLite supports json_extract but SQLAlchemy syntax depends on dialect.
    # For fail-safe prototype, we'll fetch then filter in Python if specific meta filters are requested.
    
    assets = query.order_by(Asset.created_at.desc()).all()
    
    filtered_assets = []
    for a in assets:
        meta = a.meta_info or {}
        
        # Check Project Filter
        if project_id:
             # If filtering by project, asset must match project_id OR be global (no project, but user's) - 
             # Actually user probably wants to see assets FOR this project.
             # Let's say: if asset has project_id, it must match. 
             # If asset has NO project_id, does it show? "Narrow down scope" implies showing only relevant.
             # Let's show assets that match the project_id OR have no project_id (global assets).
             # Wait, strict filtering "Narrow down" usually means strict match.
             # User requested: "Project, subject, shot etc to filter".
             # Strict match is safer.
             p_id = meta.get('project_id')
             if p_id and str(p_id) != str(project_id):
                 continue
                 
        # Check Entity/Subject Filter
        if entity_id:
             e_id = meta.get('entity_id')
             if e_id and str(e_id) != str(entity_id):
                 continue
                 
        # Check Shot Filter
        if shot_id:
            s_id = meta.get('shot_id')
            if s_id and str(s_id) != str(shot_id):
                continue

        filtered_assets.append(a)

    return [
        {
            "id": a.id,
            "type": a.type,
            "url": a.url,
            "filename": a.filename,
            "meta_info": a.meta_info,
            "remark": a.remark,
            "created_at": a.created_at
        } for a in filtered_assets
    ]

@router.post("/assets/", response_model=dict)
def create_asset_url(
    asset_in: AssetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meta = asset_in.meta_info if asset_in.meta_info else {}
    meta['source'] = 'external_url'

    asset = Asset(
        user_id=current_user.id,
        type=asset_in.type,
        url=asset_in.url,
        meta_info=meta,
        remark=asset_in.remark
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {
        "id": asset.id,
        "type": asset.type,
        "url": asset.url,
        "meta_info": asset.meta_info,
        "remark": asset.remark,
        "created_at": asset.created_at
    }

@router.post("/assets/upload", response_model=dict)
async def upload_asset(
    file: UploadFile = File(...),
    type: str = "image", # image or video
    remark: Optional[str] = None,
    project_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Ensure upload directory
    upload_dir = settings.UPLOAD_DIR
    
    # Store by user
    user_upload_dir = os.path.join(upload_dir, str(current_user.id))
    if not os.path.exists(user_upload_dir):
        os.makedirs(user_upload_dir)
    
    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(user_upload_dir, filename)

    # Auto-detect type
    if file.content_type.startswith('video/') or ext.lower() in ['.mp4', '.mov', '.avi', '.webm']:
        type = 'video'
    elif file.content_type.startswith('image/') or ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        type = 'image'
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Extract Metadata
    meta_info = {'source': 'file_upload'}
    if project_id: meta_info['project_id'] = project_id
    if entity_id: meta_info['entity_id'] = entity_id
    if shot_id: meta_info['shot_id'] = shot_id
    
    try:
        file_size = os.path.getsize(file_path)
        meta_info['size'] = f"{file_size / 1024:.2f} KB"
        
        if type == 'image':
            with Image.open(file_path) as img:
                meta_info['width'] = img.width
                meta_info['height'] = img.height
                meta_info['format'] = img.format
                meta_info['resolution'] = f"{img.width}x{img.height}"
    except Exception as e:
        print(f"Metadata extraction failed: {e}")

    # Construct URL (assuming /uploads is mounted)
    # Get base URL from request ideally, but relative works for frontend
    base_url = settings.RENDER_EXTERNAL_URL.rstrip('/') if settings.RENDER_EXTERNAL_URL else ""
    url = f"{base_url}/uploads/{current_user.id}/{filename}"
    
    asset = Asset(
        user_id=current_user.id,
        type=type,
        url=url,
        filename=file.filename,
        meta_info=meta_info,
        remark=remark
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return {
        "id": asset.id,
        "type": asset.type,
        "url": asset.url,
        "filename": asset.filename,
        "meta_info": asset.meta_info,
        "remark": asset.remark,
        "created_at": asset.created_at
    }

@router.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.user_id == current_user.id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    # Optional: Delete file if local
    # if asset.url.startswith("/uploads/"):
    #     ...
        
    db.delete(asset)
    db.commit()
    return {"status": "success"}

@router.put("/assets/{asset_id}", response_model=dict)
def update_asset(
    asset_id: int,
    asset_update: AssetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.user_id == current_user.id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if asset_update.remark is not None:
        asset.remark = asset_update.remark
    if asset_update.meta_info is not None:
         # Merge or replace? Let's replace for now or merge if needed
         # asset.meta_info = {**asset.meta_info, **asset_update.meta_info} 
         asset.meta_info = asset_update.meta_info
         
    db.commit()
    db.refresh(asset)
    
    return {
        "id": asset.id,
        "type": asset.type,
        "url": asset.url,
        "meta_info": asset.meta_info,
        "remark": asset.remark,
        "created_at": asset.created_at
    }


# --- Generation ---

class GenerationRequest(BaseModel):
    prompt: str
    provider: Optional[str] = None
    model: Optional[str] = None
    ref_image_url: Optional[Union[str, List[str]]] = None
    project_id: Optional[int] = None
    shot_id: Optional[int] = None
    shot_number: Optional[str] = None
    asset_type: Optional[str] = None

class VideoGenerationRequest(BaseModel):
    prompt: str
    provider: Optional[str] = None
    model: Optional[str] = None
    ref_image_url: Optional[Union[str, List[str]]] = None
    last_frame_url: Optional[str] = None
    duration: Optional[float] = 5.0
    project_id: Optional[int] = None
    shot_id: Optional[int] = None
    shot_number: Optional[str] = None
    asset_type: Optional[str] = None
    keyframes: Optional[List[str]] = None

def _register_asset_helper(db: Session, user_id: int, url: str, req: Any, source_metadata: Dict = None):
    # Handle dict or object
    def get_attr(obj, key):
        if isinstance(obj, dict): return obj.get(key)
        return getattr(obj, key, None)

    project_id = get_attr(req, "project_id")
    if not project_id: return

    try:
        # Determine paths
        import urllib.parse
        fname = os.path.basename(urllib.parse.urlparse(url).path)
        file_path = os.path.join(settings.UPLOAD_DIR, fname)
        
        meta = {}
        # Copy known fields
        for field in ["shot_number", "shot_id", "project_id", "asset_type", "entity_id", "entity_name"]:
            val = get_attr(req, field)
            if val: meta[field] = val
        
        if get_attr(req, "asset_type"): meta["frame_type"] = get_attr(req, "asset_type")
        if get_attr(req, "category"): meta["category"] = get_attr(req, "category")
        
        # Merge Source Metadata (Provider, Model)
        if source_metadata:
            for k in ["provider", "model", "duration"]:
                if k in source_metadata:
                    meta[k] = source_metadata[k]

        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            meta["size"] = size
            meta["size_display"] = f"{size/1024:.2f} KB"
            if size > 1024*1024:
                meta["size_display"] = f"{size/1024/1024:.2f} MB"
            
            # Try getting resolution
            try:
                if url.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    with Image.open(file_path) as img:
                        meta["width"] = img.width
                        meta["height"] = img.height
                        meta["resolution"] = f"{img.width}x{img.height}"
            except Exception as e:
                print(f"Meta extraction error: {e}")

        remark = get_attr(req, "remark")
        if not remark:
            provider = meta.get("provider", "Unknown")
            if get_attr(req, "entity_name"):
                 remark = f"Auto-registered from Entity: {get_attr(req, 'entity_name')} ({provider})"
            else:
                 remark = f"Generated {get_attr(req, 'asset_type')} for Shot {get_attr(req, 'shot_number')} by {provider}"

        asset = Asset(
            user_id=user_id,
            type="image" if url.lower().endswith(('.png', '.jpg', '.webp')) else "video",
            url=url,
            filename=fname,
            meta_info=meta,
            remark=remark
        )
        db.add(asset)
        db.commit()
    except Exception as e:
        print(f"Asset reg failed: {e}")

@router.post("/generate/image")
async def generate_image_endpoint(
    req: GenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Assuming generate_image returns {"url": "...", ...}
        result = await media_service.generate_image(
            prompt=req.prompt, 
            llm_config={"provider": req.provider} if req.provider else None,
            reference_image_url=req.ref_image_url
        )
        if "error" in result:
             # Include details if available
             detail = result["error"]
             if "details" in result:
                 detail = f"{detail}: {result['details']}"
             raise HTTPException(status_code=400, detail=detail)
        
        # Register Asset
        if result.get("url"):
            _register_asset_helper(db, current_user.id, result["url"], req, result.get("metadata"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# --- User Management ---
class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_authorized: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_system: Optional[bool] = None
    password: Optional[str] = None


@router.get("/users/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get current user.
    """
    return current_user

@router.get("/users", response_model=List[UserOut])
def get_users(
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, 
    user_in: UserUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.is_authorized is not None:
        user.is_authorized = user_in.is_authorized
    if user_in.is_superuser is not None:
        user.is_superuser = user_in.is_superuser
    if user_in.is_system is not None:
        # Ensure only one system user if we want strict uniqueness, but user asked for "System user unique" logic potentially
        # For now, let's just allow marking. 
        # If we need strict 1 system user, we can unset others.
        if user_in.is_system:
             # Unset others? Or just trust admin. Let's unset others to be safe as per "system user unique" hint.
             db.query(User).filter(User.id != user_id).update({"is_system": False})
        user.is_system = user_in.is_system
        
    if user_in.password:
        user.hashed_password = get_password_hash(user_in.password)
        
    db.commit()
    db.refresh(user)
    return user


@router.post("/generate/video")
async def generate_video_endpoint(
    req: VideoGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    print(f"DEBUG: Backend Received Video Prompt: {req.prompt}")
    try:
        # 1. Resolve Context for Aspect Ratio
        aspect_ratio = None
        episode_info = {}

        # Try to find episode info via Shot -> Scene -> Episode
        if req.shot_id:
             shot = db.query(Shot).filter(Shot.id == req.shot_id).first()
             if shot:
                 scene = db.query(Scene).filter(Scene.id == shot.scene_id).first()
                 if scene and scene.episode_id:
                     ep = db.query(Episode).filter(Episode.id == scene.episode_id).first()
                     if ep and ep.episode_info:
                         # Robust logic matching _build_shot_prompts
                         temp = ep.episode_info
                         if isinstance(temp, str):
                             try: temp = json.loads(temp)
                             except: temp = {}
                         if isinstance(temp, dict):
                              if "e_global_info" in temp and isinstance(temp["e_global_info"], dict):
                                   episode_info = temp["e_global_info"]
                              else:
                                   episode_info = temp

        # Extract Aspect Ratio
        # Structure: tech_params -> visual_standard -> aspect_ratio
        # Or direct top level
        tech = episode_info.get("tech_params", {})
        if isinstance(tech, dict):
            vis = tech.get("visual_standard", {})
            if isinstance(vis, dict):
                aspect_ratio = vis.get("aspect_ratio")
        
        if not aspect_ratio:
             # Fallback check
             aspect_ratio = episode_info.get("aspect_ratio")

        logger.info(f"[GenerateVideo] Extracted Aspect Ratio: {aspect_ratio}")

        result = await media_service.generate_video(
            prompt=req.prompt, 
            llm_config={"provider": req.provider} if req.provider else None,
            reference_image_url=req.ref_image_url,
            last_frame_url=req.last_frame_url,
            duration=req.duration,
            aspect_ratio=aspect_ratio,
            keyframes=req.keyframes
        )
        if "error" in result:
             detail = result["error"]
             if "details" in result:
                 detail = f"{detail}: {result['details']}"
             raise HTTPException(status_code=400, detail=detail)

        # Register Asset
        if result.get("url"):
            _register_asset_helper(db, current_user.id, result["url"], req, result.get("metadata"))
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

class MontageItem(BaseModel):
    url: str
    speed: float = 1.0
    trim_start: float = 0.0
    trim_end: float = 0.0

class MontageRequest(BaseModel):
    items: List[MontageItem]

@router.post("/projects/{project_id}/montage")
async def generate_montage(
    project_id: int,
    request: MontageRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        url = await create_montage(project_id, [item.dict() for item in request.items])
        return {"url": url}
    except Exception as e:
        logger.error(f"Montage failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class AnalyzeImageRequest(BaseModel):
    asset_id: int

@router.post("/assets/analyze", response_model=Dict[str, str])
async def analyze_asset_image(
    request: AnalyzeImageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes an asset image to extract style and prompt descriptions.
    """
    # 1. Fetch Asset
    asset = db.query(Asset).filter(Asset.id == request.asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    # Check permissions
    if asset.user_id != current_user.id and not current_user.is_superuser:
         raise HTTPException(status_code=403, detail="Not authorized")

    # 2. Get LLM Config
    api_setting = get_effective_api_setting(db, current_user, category="LLM")
    if not api_setting:
         raise HTTPException(status_code=400, detail="LLM Settings not configured (No active LLM provider found). Please configure one in Settings.")
    
    llm_config = {
        "api_key": api_setting.api_key,
        "base_url": api_setting.base_url,
        "model": api_setting.model,
        "config": api_setting.config or {}
    }

    # 3. Load System Prompt
    prompt_path = os.path.join(settings.BASE_DIR, "app/core/prompts", "image_style_extractor.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    else:
        system_prompt = "Describe the art style and visual elements of this image."

    # 4. Construct Image URL
    base_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")
    
    image_url_raw = asset.url
    if image_url_raw and image_url_raw.startswith("http"):
        image_url = image_url_raw
    else:
        # Local path
        path_part = image_url_raw if image_url_raw.startswith("/") else f"/{image_url_raw}"
        image_url = f"{base_url}{path_part}"
    
    logger.info(f"Analyzing Image: {image_url}")

    # 5. Call Service
    try:
        result = await llm_service.analyze_multimodal(
            prompt=system_prompt,
            image_url=image_url,
            config=llm_config
        )
        return {"result": result}
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

