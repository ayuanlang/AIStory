
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
