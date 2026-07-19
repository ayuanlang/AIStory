from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class SystemLogBase(BaseModel):
    action: str
    details: Optional[str] = None
    ip_address: Optional[str] = None

class SystemLogCreate(SystemLogBase):
    user_id: Optional[int] = None
    user_name: Optional[str] = None

class SystemLogOut(SystemLogBase):
    id: int
    user_id: Optional[int]
    user_name: Optional[str]
    timestamp: str

    class Config:
        from_attributes = True


class UiSystemLogEntry(BaseModel):
    message: str
    type: str = "info"
    client_time: Optional[str] = None


class UiSystemLogBatchCreate(BaseModel):
    entries: List[UiSystemLogEntry] = Field(default_factory=list)


class UiSystemLogBatchOut(BaseModel):
    ok: bool = True
    written: int = 0
    log_file: str = ""


class UiSystemLogReadEntry(BaseModel):
    stamp: str = ""
    level: str = "INFO"
    message: str = ""
    client_time: Optional[str] = None
    display: str = ""


class UiSystemLogListOut(BaseModel):
    ok: bool = True
    entries: List[UiSystemLogReadEntry] = Field(default_factory=list)
    log_file: str = ""


class ScriptAnalysisAiDiagnosisChatMessage(BaseModel):
    role: str = "user"
    content: str = ""


class ScriptAnalysisAiDiagnosisRequest(BaseModel):
    manual_text: str = ""
    system_logs: str = ""
    workspace_summary: str = ""
    user_note: str = ""
    # Multi-turn agent dialogue: prior + current user/assistant turns.
    history: List[ScriptAnalysisAiDiagnosisChatMessage] = Field(default_factory=list)
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    episode_label: str = ""
    system_api_id: Optional[int] = None
    function_name: str = "script_analysis"
    # Which editor page the diagnosis agent is for: script_analysis | assets
    page_scope: str = "script_analysis"
    send_to_ops: bool = False
    # When set with send_to_ops=True, skip LLM and only email this advice + materials.
    existing_advice: str = ""


class ScriptAnalysisAiDiagnosisOut(BaseModel):
    ok: bool = True
    advice: str = ""
    emailed_to_ops: bool = False
    ops_email: str = ""
    email_error: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class LLMCallLogOut(BaseModel):
    id: int
    tag: Optional[str]
    provider: Optional[str]
    model: Optional[str]
    api_url: Optional[str]
    payload_json: Optional[str]
    response_json: Optional[str]
    error_msg: Optional[str]
    latency_ms: Optional[int]
    timestamp: str

    class Config:
        from_attributes = True
