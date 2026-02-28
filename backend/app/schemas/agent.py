
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class AgentRequest(BaseModel):
    query: str
    project_id: Optional[int] = None
    context: Dict[str, Any] = {}
    history: List[Dict[str, str]] = []
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
    episode_id: Optional[int] = None
    llm_config: Optional[Dict[str, Any]] = None
    prompt_file: Optional[str] = "scene_analysis.txt"
    system_prompt: Optional[str] = None
    project_metadata: Optional[Dict[str, Any]] = None
    analysis_attention_notes: Optional[str] = None
    reuse_subject_assets: Optional[List[Dict[str, Any]]] = None
    include_negative_prompt: Optional[bool] = True
