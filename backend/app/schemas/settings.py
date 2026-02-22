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


class SystemAPISettingOut(BaseModel):
    id: int
    name: Optional[str] = None
    category: str
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}
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
    is_active: bool = False


class SystemAPISettingImportRequest(BaseModel):
    items: List[SystemAPISettingImportItem] = Field(default_factory=list)
    replace_all: bool = False


class SystemAPIProviderModelCatalog(BaseModel):
    category: str
    provider: str
    models: List[str] = []
