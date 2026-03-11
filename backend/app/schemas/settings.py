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
    """前端模型选项展示。"""
    id: int
    name: Optional[str] = None
    user_id: Optional[int] = None
    provider: str
    category: Optional[str] = None          # LLM / Image / Video / Voice / Music
    model: Optional[str] = None
    generation_modes: Optional[List[str]] = None
    input_formats: Optional[List[str]] = None
    output_format: Optional[str] = None
    supported_resolutions: Optional[List[str]] = None
    aspect_ratios: Optional[List[str]] = None
    max_duration: Optional[int] = None
    has_audio: Optional[bool] = None
    mode_values: Optional[List[str]] = None
    tags: Optional[List[str]] = None           # 模型标签
    base_url: Optional[str] = None
    webhook_url: Optional[str] = None
    deprecated: bool = False
    is_active: bool = False  # Category default flag for this System API category
    has_api_key: bool = False
    api_key_masked: Optional[str] = None
    avg_price_estimate: Optional[int] = None
    avg_price_source: Optional[str] = None


class SystemAPIProviderSettings(BaseModel):
    provider: str
    category: str
    shared_key_configured: bool = False
    models: List[SystemAPIModelOption] = []


class SystemAPISelectionRequest(BaseModel):
    setting_id: int
    api_strategy: Optional[str] = "smart_default"


class SystemAPISettingManageUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    category: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    base_model: Optional[str] = None
    tags: Optional[List[str]] = None
    supplier_info: Optional[Dict[str, Any]] = None  # 原供应商API定价信息(审计用)
    generation_modes: Optional[List[str]] = None
    input_formats: Optional[List[str]] = None
    output_format: Optional[str] = None
    supported_resolutions: Optional[List[str]] = None
    aspect_ratios: Optional[List[str]] = None
    max_images_per_call: Optional[int] = None
    reference_image_limit: Optional[str] = None
    reference_video_limit: Optional[str] = None
    durations_seconds: Optional[List[float]] = None
    max_duration: Optional[int] = None
    fps_options: Optional[List[float]] = None
    has_audio: Optional[bool] = None
    mode_values: Optional[List[str]] = None
    text_capabilities: Optional[Dict[str, Any]] = None
    image_capabilities: Optional[Dict[str, Any]] = None
    video_capabilities: Optional[Dict[str, Any]] = None
    digital_human_capabilities: Optional[Dict[str, Any]] = None
    voice_capabilities: Optional[Dict[str, Any]] = None
    music_capabilities: Optional[Dict[str, Any]] = None
    pricing_unit: Optional[str] = None
    token_billing_supported: Optional[bool] = None
    input_token_price: Optional[float] = None
    output_token_price: Optional[float] = None
    per_resolution_price_map: Optional[Dict[str, Any]] = None
    per_duration_price_map: Optional[Dict[str, Any]] = None
    has_tiered_pricing: Optional[bool] = None
    free_quota: Optional[str] = None
    currency: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    billing_unit_type: Optional[str] = None
    billing_cost: Optional[int] = None
    billing_cost_input: Optional[int] = None
    billing_cost_output: Optional[int] = None
    has_granular_billing_rules: Optional[bool] = None
    is_active: Optional[bool] = None


class SystemAPISettingManageCreate(BaseModel):
    name: Optional[str] = "System Setting"
    provider: str
    category: str = "LLM"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    base_model: Optional[str] = None
    tags: Optional[List[str]] = None
    supplier_info: Optional[Dict[str, Any]] = None  # 原供应商API定价信息(审计用)
    generation_modes: Optional[List[str]] = None
    input_formats: Optional[List[str]] = None
    output_format: Optional[str] = None
    supported_resolutions: Optional[List[str]] = None
    aspect_ratios: Optional[List[str]] = None
    max_images_per_call: Optional[int] = None
    reference_image_limit: Optional[str] = None
    reference_video_limit: Optional[str] = None
    durations_seconds: Optional[List[float]] = None
    max_duration: Optional[int] = None
    fps_options: Optional[List[float]] = None
    has_audio: Optional[bool] = None
    mode_values: Optional[List[str]] = None
    text_capabilities: Optional[Dict[str, Any]] = None
    image_capabilities: Optional[Dict[str, Any]] = None
    video_capabilities: Optional[Dict[str, Any]] = None
    digital_human_capabilities: Optional[Dict[str, Any]] = None
    voice_capabilities: Optional[Dict[str, Any]] = None
    music_capabilities: Optional[Dict[str, Any]] = None
    pricing_unit: Optional[str] = None
    token_billing_supported: Optional[bool] = None
    input_token_price: Optional[float] = None
    output_token_price: Optional[float] = None
    per_resolution_price_map: Optional[Dict[str, Any]] = None
    per_duration_price_map: Optional[Dict[str, Any]] = None
    has_tiered_pricing: Optional[bool] = None
    free_quota: Optional[str] = None
    currency: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}
    billing_unit_type: Optional[str] = "per_call"
    billing_cost: Optional[int] = 0
    billing_cost_input: Optional[int] = 0
    billing_cost_output: Optional[int] = 0
    has_granular_billing_rules: Optional[bool] = False
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
    base_model: Optional[str] = None
    tags: Optional[List[str]] = None
    supplier_info: Optional[Dict[str, Any]] = None  # 原供应商API定价信息(审计用)
    generation_modes: Optional[List[str]] = None
    input_formats: Optional[List[str]] = None
    output_format: Optional[str] = None
    supported_resolutions: Optional[List[str]] = None
    aspect_ratios: Optional[List[str]] = None
    max_images_per_call: Optional[int] = None
    reference_image_limit: Optional[str] = None
    reference_video_limit: Optional[str] = None
    durations_seconds: Optional[List[float]] = None
    max_duration: Optional[int] = None
    fps_options: Optional[List[float]] = None
    has_audio: Optional[bool] = None
    mode_values: Optional[List[str]] = None
    text_capabilities: Optional[Dict[str, Any]] = None
    image_capabilities: Optional[Dict[str, Any]] = None
    video_capabilities: Optional[Dict[str, Any]] = None
    digital_human_capabilities: Optional[Dict[str, Any]] = None
    voice_capabilities: Optional[Dict[str, Any]] = None
    music_capabilities: Optional[Dict[str, Any]] = None
    pricing_unit: Optional[str] = None
    token_billing_supported: Optional[bool] = None
    input_token_price: Optional[float] = None
    output_token_price: Optional[float] = None
    per_resolution_price_map: Optional[Dict[str, Any]] = None
    per_duration_price_map: Optional[Dict[str, Any]] = None
    has_tiered_pricing: Optional[bool] = None
    free_quota: Optional[str] = None
    currency: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}
    billing_unit_type: Optional[str] = "per_call"
    billing_cost: Optional[int] = 0
    billing_cost_input: Optional[int] = 0
    billing_cost_output: Optional[int] = 0
    has_granular_billing_rules: Optional[bool] = False
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
    base_model: Optional[str] = None
    generation_modes: Optional[List[str]] = None
    input_formats: Optional[List[str]] = None
    output_format: Optional[str] = None
    supported_resolutions: Optional[List[str]] = None
    aspect_ratios: Optional[List[str]] = None
    max_images_per_call: Optional[int] = None
    reference_image_limit: Optional[int] = None
    reference_video_limit: Optional[int] = None
    durations_seconds: Optional[List[float]] = None
    max_duration: Optional[int] = None
    fps_options: Optional[List[float]] = None
    has_audio: Optional[bool] = None
    mode_values: Optional[List[str]] = None
    text_capabilities: Optional[Dict[str, Any]] = None
    image_capabilities: Optional[Dict[str, Any]] = None
    video_capabilities: Optional[Dict[str, Any]] = None
    digital_human_capabilities: Optional[Dict[str, Any]] = None
    voice_capabilities: Optional[Dict[str, Any]] = None
    music_capabilities: Optional[Dict[str, Any]] = None
    pricing_unit: Optional[str] = None
    token_billing_supported: Optional[bool] = None
    input_token_price: Optional[float] = None
    output_token_price: Optional[float] = None
    per_resolution_price_map: Optional[Dict[str, Any]] = None
    per_duration_price_map: Optional[Dict[str, Any]] = None
    has_tiered_pricing: Optional[bool] = None
    free_quota: Optional[str] = None
    currency: Optional[str] = None
    tags: Optional[List[str]] = None
    supplier_info: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = {}
    billing_unit_type: Optional[str] = None
    billing_cost: Optional[int] = None
    billing_cost_input: Optional[int] = None
    billing_cost_output: Optional[int] = None
    has_granular_billing_rules: Optional[bool] = None
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
    base_model: Optional[str] = None
    generation_modes: Optional[List[str]] = None
    input_formats: Optional[List[str]] = None
    output_format: Optional[str] = None
    supported_resolutions: Optional[List[str]] = None
    aspect_ratios: Optional[List[str]] = None
    max_images_per_call: Optional[int] = None
    reference_image_limit: Optional[int] = None
    reference_video_limit: Optional[int] = None
    durations_seconds: Optional[List[float]] = None
    max_duration: Optional[int] = None
    fps_options: Optional[List[float]] = None
    has_audio: Optional[bool] = None
    mode_values: Optional[List[str]] = None
    text_capabilities: Optional[Dict[str, Any]] = None
    image_capabilities: Optional[Dict[str, Any]] = None
    video_capabilities: Optional[Dict[str, Any]] = None
    digital_human_capabilities: Optional[Dict[str, Any]] = None
    voice_capabilities: Optional[Dict[str, Any]] = None
    music_capabilities: Optional[Dict[str, Any]] = None
    pricing_unit: Optional[str] = None
    token_billing_supported: Optional[bool] = None
    input_token_price: Optional[float] = None
    output_token_price: Optional[float] = None
    per_resolution_price_map: Optional[Dict[str, Any]] = None
    per_duration_price_map: Optional[Dict[str, Any]] = None
    has_tiered_pricing: Optional[bool] = None
    free_quota: Optional[str] = None
    currency: Optional[str] = None
    tags: Optional[List[str]] = None
    supplier_info: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = {}
    billing_unit_type: Optional[str] = None
    billing_cost: Optional[int] = None
    billing_cost_input: Optional[int] = None
    billing_cost_output: Optional[int] = None
    has_granular_billing_rules: Optional[bool] = None
    deprecated: Optional[bool] = None
    is_active: bool = False


class SystemAPIBillingRuleBase(BaseModel):
    system_api_id: int
    name: Optional[str] = "Rule"
    description: Optional[str] = None
    is_active: bool = True
    priority: int = 0
    applies_to_text: bool = False
    applies_to_image: bool = False
    applies_to_video: bool = False
    generation_mode: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    has_audio: Optional[bool] = None
    input_tokens_min: Optional[int] = None
    input_tokens_max: Optional[int] = None
    output_tokens_min: Optional[int] = None
    output_tokens_max: Optional[int] = None
    total_tokens_min: Optional[int] = None
    total_tokens_max: Optional[int] = None
    image_count_min: Optional[int] = None
    image_count_max: Optional[int] = None
    width_min: Optional[int] = None
    width_max: Optional[int] = None
    height_min: Optional[int] = None
    height_max: Optional[int] = None
    pixels_min: Optional[int] = None
    pixels_max: Optional[int] = None
    duration_seconds_min: Optional[float] = None
    duration_seconds_max: Optional[float] = None
    fps_min: Optional[float] = None
    fps_max: Optional[float] = None
    billing_unit_type: Optional[str] = "per_call"
    billing_cost: Optional[int] = 0
    billing_cost_input: Optional[int] = 0
    billing_cost_output: Optional[int] = 0
    charge_multiplier: Optional[float] = 2.0
    extra_conditions: Optional[Dict[str, Any]] = {}


class SystemAPIBillingRuleCreate(SystemAPIBillingRuleBase):
    pass


class SystemAPIBillingRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    applies_to_text: Optional[bool] = None
    applies_to_image: Optional[bool] = None
    applies_to_video: Optional[bool] = None
    generation_mode: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    has_audio: Optional[bool] = None
    input_tokens_min: Optional[int] = None
    input_tokens_max: Optional[int] = None
    output_tokens_min: Optional[int] = None
    output_tokens_max: Optional[int] = None
    total_tokens_min: Optional[int] = None
    total_tokens_max: Optional[int] = None
    image_count_min: Optional[int] = None
    image_count_max: Optional[int] = None
    width_min: Optional[int] = None
    width_max: Optional[int] = None
    height_min: Optional[int] = None
    height_max: Optional[int] = None
    pixels_min: Optional[int] = None
    pixels_max: Optional[int] = None
    duration_seconds_min: Optional[float] = None
    duration_seconds_max: Optional[float] = None
    fps_min: Optional[float] = None
    fps_max: Optional[float] = None
    billing_unit_type: Optional[str] = None
    billing_cost: Optional[int] = None
    billing_cost_input: Optional[int] = None
    billing_cost_output: Optional[int] = None
    charge_multiplier: Optional[float] = None
    extra_conditions: Optional[Dict[str, Any]] = None


class SystemAPIBillingRuleOut(SystemAPIBillingRuleBase):
    id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class SystemAPIMissingBillingRuleOut(BaseModel):
    id: int
    name: Optional[str] = None
    category: str
    provider: str
    model: Optional[str] = None
    base_model: Optional[str] = None
    deprecated: bool = False
    is_active: bool = False


class SystemAPIBillingRuleMultiplierResetRequest(BaseModel):
    """批量按成本重置计费规则倍率。"""
    system_api_ids: List[int] = Field(default_factory=list)
    min_multiplier: float = 1.1
    max_multiplier: float = 2.0
    default_multiplier: float = 2.0


class SystemAPIBillingRuleMultiplierResetResponse(BaseModel):
    requested_system_api_count: int = 0
    total_rules: int = 0
    updated_rules: int = 0
    min_cost: int = 0
    max_cost: int = 0
    min_multiplier: float = 1.1
    max_multiplier: float = 2.0
    default_multiplier: float = 2.0
    preview: List[Dict[str, Any]] = Field(default_factory=list)


class SystemAPIProviderImportItem(BaseModel):
    provider: str
    api_keys: List[str] = Field(default_factory=list)
    strategy: Optional[str] = None
    weights: Optional[List[float]] = None
    models: List[SystemAPIProviderModelImportItem] = Field(default_factory=list)


class SystemAPIProviderImportRequest(BaseModel):
    providers: List[SystemAPIProviderImportItem] = Field(default_factory=list)
    replace_all: bool = False


class SystemConfigSyncBundleImportRequest(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)
    replace_all: bool = True
    confirm_clear_existing: bool = False


class TaskDefaultSystemAPIManageCreate(BaseModel):
    task_category: str
    system_api_id: int


class TaskDefaultSystemAPIManageUpdate(BaseModel):
    system_api_id: int


class TaskDefaultSystemAPIManageOut(BaseModel):
    task_category: str
    system_api_id: int
    system_api_category: Optional[str] = None
    system_api_provider: Optional[str] = None
    system_api_model: Optional[str] = None
    system_api_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


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
    """AI助手模型输入。

    supplier_price / supplier_price_input / supplier_price_output: 供应商价格(元/CNY)。
    系统按 “价格(CNY) × 100 × 上浮倍率” 折算为积分(1积分=1分钱=0.01元)。
    supplier_raw_info: 原始供应商API定价信息，用于审计对照。
    """
    name: Optional[str] = None
    category: str = "LLM"
    model: str
    tags: Optional[List[str]] = None
    base_url: Optional[str] = None
    endpoint: Optional[str] = None
    unit_type: str = "per_call"
    supplier_price: Optional[float] = None          # 供应商价格(元/CNY)
    supplier_price_input: Optional[float] = None    # 供应商输入价格(元/CNY)
    supplier_price_output: Optional[float] = None   # 供应商输出价格(元/CNY)
    supplier_currency: Optional[str] = "CNY"       # 供应商价格币种，必须先换算为 CNY
    supplier_price_basis: Optional[str] = "money"  # 价格基准: money(金额) / points(供应商积分, 禁止直接换算)
    supplier_raw_info: Optional[Dict[str, Any]] = None  # 原始供应商定价信息(审计用)
    is_active: bool = False
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SystemAIAssistantRequest(BaseModel):
    """AI助手请求。

    multiplier: 上浮倍率，默认 2.0，在供应商成本上乘以此倍数作为利润。
    积分计算公式: credits = ceil(supplier_price_cny × 100 × multiplier)
    其中 100 为元转分(本系统 1积分=1分钱=0.01元)。
    """
    provider: str
    multiplier: float = 2.0
    models: List[SystemAIAssistantModelInput] = Field(default_factory=list)


class SystemAIAssistantSuggestion(BaseModel):
    """AI助手建议结果。

    cost / cost_input / cost_output: 计算后的积分数(已含上浮倍率)。
    supplier_raw_info: 原始供应商定价信息，用于审计对照。
    """
    action: str
    setting_id: Optional[int] = None
    provider: str
    category: str
    model: str
    tags: Optional[List[str]] = None
    name: Optional[str] = None
    base_url: Optional[str] = None
    unit_type: str
    supplier_price: Optional[float] = None          # 供应商价格(元/CNY)
    supplier_price_input: Optional[float] = None
    supplier_price_output: Optional[float] = None
    supplier_currency: Optional[str] = "CNY"
    supplier_price_basis: Optional[str] = "money"
    supplier_raw_info: Optional[Dict[str, Any]] = None  # 原始供应商定价信息(审计用)
    multiplier: float
    cost: int = 0                                   # 积分(含上浮倍率)
    cost_input: int = 0
    cost_output: int = 0
    reason: Optional[str] = None


class SystemAIAssistantResponse(BaseModel):
    provider: str
    multiplier: float
    suggestions: List[SystemAIAssistantSuggestion] = Field(default_factory=list)
    applied_count: int = 0


# ── AI助手 MCP 工具 Schemas ──────────────────────────────────────

class ExchangeRateRequest(BaseModel):
    """汇率兑换请求。"""
    from_currency: str = "USD"          # 源货币代码(如 USD, EUR, JPY)
    to_currency: str = "CNY"            # 目标货币代码, 默认人民币
    amount: Optional[float] = None      # 需转换的金额(不填则只返回汇率)


class ExchangeRateResponse(BaseModel):
    """汇率兑换结果。"""
    from_currency: str
    to_currency: str
    rate: Optional[float] = None        # 汇率(1源货币=?目标货币)
    from_amount: Optional[float] = None # 源金额
    to_amount: Optional[float] = None   # 转换后金额
    source: Optional[str] = None        # 数据源
    error: Optional[str] = None


class FetchPricingPageRequest(BaseModel):
    """定价页面读取请求。"""
    url: str                            # 供应商定价页面URL
    max_length: int = 30000             # 返回文本最大字符数


class FetchPricingPageResponse(BaseModel):
    """定价页面读取结果。"""
    url: str
    title: Optional[str] = None
    text_content: Optional[str] = None  # 提取的纯文本内容
    tables: Optional[List[Any]] = None  # 提取到的表格
    content_length: int = 0
    truncated: bool = False
    format: Optional[str] = None        # html/json
    error: Optional[str] = None


class SupplierApiFeatureAnalyzeRequest(BaseModel):
    provider: str
    source_urls: List[str] = Field(default_factory=list)
    selected_system_api_ids: List[int] = Field(default_factory=list)
    include_provider_intro_url: bool = True
    search_keywords: List[str] = Field(default_factory=list)
    user_supplement: Optional[str] = None
    max_length: int = 40000
    max_pages: int = 6
    save_to_db: bool = True
    create_missing_models: bool = True


class SupplierApiFeatureModel(BaseModel):
    provider: str
    category: str
    model: str
    base_model: Optional[str] = None
    generation_modes: List[str] = Field(default_factory=list)
    image_capabilities: Dict[str, Any] = Field(default_factory=dict)
    video_capabilities: Dict[str, Any] = Field(default_factory=dict)
    digital_human_capabilities: Dict[str, Any] = Field(default_factory=dict)
    text_capabilities: Dict[str, Any] = Field(default_factory=dict)
    voice_capabilities: Dict[str, Any] = Field(default_factory=dict)
    music_capabilities: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    confidence: float = 0.0


class SupplierApiFeatureAnalyzeResponse(BaseModel):
    provider: str
    analyzed_url_count: int = 0
    selected_system_api_count: int = 0
    selected_system_api_ids: List[int] = Field(default_factory=list)
    source_urls_used: List[str] = Field(default_factory=list)
    models: List[SupplierApiFeatureModel] = Field(default_factory=list)
    saved_created: int = 0
    saved_updated: int = 0
    warnings: List[str] = Field(default_factory=list)
    provider_summary: Optional[str] = None
    llm_input: Optional[str] = None
    llm_output: Optional[str] = None
    llm_raw: Optional[str] = None


class SupplierApiFeatureApplyRequest(BaseModel):
    provider: str
    models: List[SupplierApiFeatureModel] = Field(default_factory=list)
    create_missing_models: bool = True


class SupplierApiFeatureApplyResponse(BaseModel):
    provider: str
    requested_count: int = 0
    saved_created: int = 0
    saved_updated: int = 0
    skipped_count: int = 0
    warnings: List[str] = Field(default_factory=list)


class KIEPricingGenerateRequest(BaseModel):
    """KIE 定价规则生成请求。"""
    url: str = "https://kie.ai/zh-CN/pricing"
    max_length: int = 40000
    max_pages: int = 8
    provider_filter: str = "kie"
    include_deprecated: bool = False
    apply_base_rules: bool = False
    selected_system_api_ids: Optional[List[int]] = None
    confirmed: bool = False
    confirmed_pricing_text: Optional[str] = None
    confirmed_tables: Optional[List[Any]] = None
    confirmed_pricing_tables_text: Optional[str] = None


class KIEPricingApplyRequest(BaseModel):
    """KIE 定价规则应用请求（直接应用已有建议，不重新生成）。"""
    provider_filter: str = "kie"
    include_deprecated: bool = False
    selected_system_api_ids: Optional[List[int]] = None
    matches: List[Dict[str, Any]] = Field(default_factory=list)


class KIEPricingFetchRequest(BaseModel):
    """KIE 定价抓取请求（支持分页）。"""
    url: str = "https://kie.ai/zh-CN/pricing"
    max_length: int = 40000
    max_pages: int = 8


class KIEPricingFetchPage(BaseModel):
    """KIE 定价抓取的页面摘要。"""
    url: str
    title: Optional[str] = None
    content_length: int = 0
    table_count: int = 0


class KIEPricingFetchResponse(BaseModel):
    """KIE 定价抓取结果（供确认后再生成规则）。"""
    url: str
    page_count: int = 0
    has_pagination: bool = False
    pages: List[KIEPricingFetchPage] = Field(default_factory=list)
    combined_text: str = ""
    combined_tables: List[Any] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class KIEPricingRuleSuggestion(BaseModel):
    """KIE 定价规则建议项。"""
    system_api_id: int
    provider: str
    category: str
    model: str
    source_model_name: Optional[str] = None
    confidence: float = 0.0
    reason: Optional[str] = None
    base_rule: Dict[str, Any] = Field(default_factory=dict)
    granular_rules: List[Dict[str, Any]] = Field(default_factory=list)
    raw_price_note: Optional[str] = None


class KIEPricingApplyReceipt(BaseModel):
    """KIE 应用写入回执。"""
    system_api_id: int
    base_rule_id: int
    action: str = "upserted"


class KIEPricingGenerateResponse(BaseModel):
    """KIE 定价规则生成结果。"""
    url: str
    title: Optional[str] = None
    provider_filter: str = "kie"
    system_model_count: int = 0
    suggestion_count: int = 0
    apply_requested: bool = False
    apply_status: str = "not_requested"
    apply_message: Optional[str] = None
    applied_count: int = 0
    applied_system_api_ids: List[int] = Field(default_factory=list)
    apply_receipts: List[KIEPricingApplyReceipt] = Field(default_factory=list)
    matches: List[KIEPricingRuleSuggestion] = Field(default_factory=list)
    unmatched_source_models: List[str] = Field(default_factory=list)
    unmatched_system_models: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    tables_parse_status: str = "none"
    tables_parse_warning: Optional[str] = None
    llm_input: Optional[str] = None
    llm_output: Optional[str] = None
    llm_raw: Optional[str] = None
    error: Optional[str] = None


class KIEPricingApplyResponse(BaseModel):
    """KIE 定价规则应用结果（不含 LLM 生成步骤）。"""
    provider_filter: str = "kie"
    requested_count: int = 0
    applied_count: int = 0
    apply_status: str = "not_requested"
    apply_message: Optional[str] = None
    applied_system_api_ids: List[int] = Field(default_factory=list)
    apply_receipts: List[KIEPricingApplyReceipt] = Field(default_factory=list)


# ── provider_key_pool CRUD schemas ──

class ProviderKeyPoolCreate(BaseModel):
    provider: str
    api_keys: Optional[List[str]] = Field(default_factory=list)
    strategy: Optional[str] = "random"
    weights: Optional[List[float]] = None
    intro_url: Optional[str] = None

class ProviderKeyPoolUpdate(BaseModel):
    provider: Optional[str] = None
    api_keys: Optional[List[str]] = None
    strategy: Optional[str] = None
    weights: Optional[List[float]] = None
    intro_url: Optional[str] = None

class ProviderKeyPoolOut(BaseModel):
    id: int
    provider: str
    api_keys: Optional[List[str]] = []
    strategy: Optional[str] = "random"
    weights: Optional[List[float]] = []
    intro_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    class Config:
        from_attributes = True
