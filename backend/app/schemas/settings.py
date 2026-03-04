from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class APISettingBase(BaseModel):
    name: Optional[str] = "Default"
    provider: str
    category: Optional[str] = "LLM"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}
    is_active: bool = False

class APISettingCreate(APISettingBase):
    pass

class APISettingUpdate(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    provider: Optional[str] = None
    category: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class APISettingOut(APISettingBase):
    id: int
    user_id: int # In a real app we might not expose this, but fine here
    
    class Config:
        from_attributes = True

class UserSettings(BaseModel):
    api_settings: List[APISettingOut] = []
    
class SystemSettings(BaseModel):
    # Aggregated settings for simpler frontend consumption
    openai: Optional[APISettingOut] = None
    stability: Optional[APISettingOut] = None
    # etc...


class SystemAPIModelOption(BaseModel):
    id: int
    name: Optional[str] = None
    user_id: Optional[int] = None
    provider: str
    category: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    webhook_url: Optional[str] = None
    deprecated: bool = False
    is_active: bool = False
    has_api_key: bool = False
    api_key_masked: Optional[str] = None


class SystemAPIProviderSettings(BaseModel):
    provider: str
    category: str
    shared_key_configured: bool = False
    models: List[SystemAPIModelOption] = []


class SystemAPISelectionRequest(BaseModel):
    setting_id: int


class SystemAPISettingManageUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    category: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class SystemAPISettingManageCreate(BaseModel):
    name: Optional[str] = "System Setting"
    provider: str
    category: str = "LLM"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}
    is_active: bool = False


class SystemAPISettingToggleDeprecatedRequest(BaseModel):
    deprecated: Optional[bool] = None


class SystemAPISettingToggleDeprecatedByKeyRequest(BaseModel):
    provider: str
    category: str
    model: Optional[str] = None
    setting_id: Optional[int] = None
    deprecated: Optional[bool] = None


class SystemAPIProviderBatchDeprecatedRequest(BaseModel):
    deprecated: bool
    category: Optional[str] = None


class SystemAPIProviderKeysUpdateRequest(BaseModel):
    keys: List[str] = Field(default_factory=list)
    strategy: Optional[str] = None
    weights: Optional[List[float]] = None


class SystemAPISettingOut(BaseModel):
    id: int
    name: Optional[str] = None
    category: str
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}
    deprecated: bool = False
    is_active: bool = False

    class Config:
        from_attributes = True


class SystemAPISettingImportItem(BaseModel):
    name: Optional[str] = "System Setting"
    category: str = "LLM"
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}
    deprecated: Optional[bool] = None
    is_active: bool = False


class SystemAPISettingImportRequest(BaseModel):
    items: List[SystemAPISettingImportItem] = Field(default_factory=list)
    replace_all: bool = False


class SystemAPIProviderModelImportItem(BaseModel):
    name: Optional[str] = "System Setting"
    category: str = "LLM"
    base_url: Optional[str] = None
    model: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}
    deprecated: Optional[bool] = None
    is_active: bool = False


class SystemAPIProviderImportItem(BaseModel):
    provider: str
    api_keys: List[str] = Field(default_factory=list)
    strategy: Optional[str] = None
    weights: Optional[List[float]] = None
    models: List[SystemAPIProviderModelImportItem] = Field(default_factory=list)


class SystemAPIProviderImportRequest(BaseModel):
    providers: List[SystemAPIProviderImportItem] = Field(default_factory=list)
    replace_all: bool = False


class SystemAPIProviderModelCatalog(BaseModel):
    category: str
    provider: str
    models: List[str] = []


class AgentToolPolicyUpdate(BaseModel):
    default_allow: Optional[bool] = True
    roles: Dict[str, Dict[str, List[str]]] = Field(default_factory=dict)


class AgentToolPolicyOut(BaseModel):
    default_allow: bool = True
    roles: Dict[str, Dict[str, List[str]]] = Field(default_factory=dict)


class SystemAIAssistantModelInput(BaseModel):
    name: Optional[str] = None
    category: str = "LLM"
    model: str
    base_url: Optional[str] = None
    endpoint: Optional[str] = None
    unit_type: str = "per_call"
    supplier_price: Optional[float] = None
    supplier_price_input: Optional[float] = None
    supplier_price_output: Optional[float] = None
    is_active: bool = False
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SystemAIAssistantRequest(BaseModel):
    provider: str
    multiplier: float = 1.0
    models: List[SystemAIAssistantModelInput] = Field(default_factory=list)


class SystemAIAssistantSuggestion(BaseModel):
    action: str
    setting_id: Optional[int] = None
    provider: str
    category: str
    model: str
    name: Optional[str] = None
    base_url: Optional[str] = None
    unit_type: str
    supplier_price: Optional[float] = None
    supplier_price_input: Optional[float] = None
    supplier_price_output: Optional[float] = None
    multiplier: float
    cost: int = 0
    cost_input: int = 0
    cost_output: int = 0
    reason: Optional[str] = None


class SystemAIAssistantResponse(BaseModel):
    provider: str
    multiplier: float
    suggestions: List[SystemAIAssistantSuggestion] = Field(default_factory=list)
    applied_count: int = 0
