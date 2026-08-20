
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class AgentRequest(BaseModel):
    query: str
    project_id: Optional[int] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    context: Dict[str, Any] = {}
    history: List[Dict[str, Any]] = []
    llm_config: Optional[Dict[str, Any]] = None

class AgentAction(BaseModel):
    tool: str
    parameters: Dict[str, Any]
    status: str = "pending"
    result: Optional[Any] = None

class AgentResponse(BaseModel):
    reply: str
    actions: List[AgentAction] = []
    updated_data: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None

class AnalyzeSceneRequest(BaseModel):
    text: str
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    llm_config: Optional[Dict[str, Any]] = None
    prompt_file: Optional[str] = "skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md"
    system_prompt: Optional[str] = None
    project_metadata: Optional[Dict[str, Any]] = None
    scene_analysis_mode: Optional[str] = None
    scene_analysis_features: Optional[Dict[str, Any]] = None
    analysis_attention_notes: Optional[str] = None
    reuse_subject_assets: Optional[List[Dict[str, Any]]] = None
    include_negative_prompt: Optional[bool] = True
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    # Explicit user-facing label for llm_call_logs (flow node/subskill name).
    action_name: Optional[str] = None
    analysis_trace_id: Optional[str] = None
    skip_episode_persist: Optional[bool] = False
    # Client-provided Subject Index for downstream gates when episode field is empty/contaminated.
    subject_index_text: Optional[str] = None
    # Marker IDs (EPxx_SCyy) for single/subset scene-beats orchestration.
    target_scene_id: Optional[str] = None
    target_scene_ids: Optional[List[str]] = None
