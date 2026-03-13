
from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Boolean, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.core.time_utils import now_bj_iso

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    hashed_password = Column(String)
    
    is_active = Column(Boolean, default=True)
    account_status = Column(Integer, default=1)  # 1=active, -1=pending email verification, 0=disabled
    email_verified = Column(Boolean, default=False)
    email_verification_code = Column(String, nullable=True)
    email_verification_expires_at = Column(String, nullable=True)
    is_superuser = Column(Boolean, default=False)
    is_authorized = Column(Boolean, default=False) # Can reuse system keys
    is_system = Column(Boolean, default=False) # Provider of shared keys
    preferences = Column(JSON, default={})
    
    credits = Column(Integer, default=0) # User points/credits

    projects = relationship("Project", back_populates="owner")
    shared_projects = relationship("ProjectShare", back_populates="user", cascade="all, delete-orphan")
    api_settings = relationship("APISetting", back_populates="user")
    assets = relationship("Asset", back_populates="owner")
    system_logs = relationship("SystemLog", back_populates="user")
    transactions = relationship("TransactionHistory", back_populates="user")


class TransactionHistory(Base):
    __tablename__ = "transaction_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    amount = Column(Integer, nullable=False) # Negative for cost, positive for refill
    balance_after = Column(Integer, nullable=False) # Snapshot of balance
    
    task_type = Column(String, index=True)
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    details = Column(JSON, default={}) # Extra metadata (e.g. prompt length, status)
    
    created_at = Column(String, default=now_bj_iso)
    
    user = relationship("User", back_populates="transactions")

class SystemLog(Base):
    __tablename__ = "system_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_name = Column(String, nullable=True)
    action = Column(String, index=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(String, default=now_bj_iso)
    
    user = relationship("User", back_populates="system_logs")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # Global Info as JSON
    # script_title, overall_genre, color_tone, borrowed_films, notes
    global_info = Column(JSON, default={})
    
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)
    
    owner = relationship("User", back_populates="projects")
    shares = relationship("ProjectShare", back_populates="project", cascade="all, delete-orphan")
    episodes = relationship("Episode", back_populates="project", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="project", cascade="all, delete-orphan")


class ProjectShare(Base):
    __tablename__ = "project_shares"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    created_at = Column(String, default=now_bj_iso)

    project = relationship("Project", back_populates="shares")
    user = relationship("User", back_populates="shared_projects")

class Episode(Base):
    __tablename__ = "episodes"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    title = Column(String) # e.g. "Episode 1"
    
    # Inherits from project global_info but can override
    episode_info = Column(JSON, default={})
    
    script_content = Column(Text, nullable=True)

    # Canonical character profiles defined by user and/or generated via LLM.
    # This is the single source of truth for character identity/appearance.
    character_profiles = Column(JSON, default=[])

    # Store AI Scene Analysis raw result separately (Markdown table / JSON), do NOT overwrite script_content
    ai_scene_analysis_result = Column(Text, nullable=True)
    
    project = relationship("Project", back_populates="episodes")
    scenes = relationship("Scene", back_populates="episode", cascade="all, delete-orphan")
    script_segments = relationship("ScriptSegment", back_populates="episode", cascade="all, delete-orphan")

class ScriptSegment(Base):
    __tablename__ = "script_segments"
    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"))
    
    pid = Column(String) # Paragraph ID (1, 2, 1-1 etc)
    title = Column(String)
    content_revised = Column(Text)
    content_original = Column(Text)
    narrative_function = Column(Text)
    analysis = Column(Text)
    
    episode = relationship("Episode", back_populates="script_segments")

class Scene(Base):
    __tablename__ = "scenes"
    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"))
    
    # Updated to match User Description exactly (snake_case)
    scene_no = Column(String)          # was scene_number
    scene_name = Column(String, nullable=True) # was title
    original_script_text = Column(Text) # was description

    equivalent_duration = Column(String, nullable=True)
    core_scene_info = Column(Text, nullable=True) # was core_goal
    environment_name = Column(Text, nullable=True) # was environment_anchor
    
    linked_characters = Column(Text, nullable=True) 
    key_props = Column(Text, nullable=True)
    # Raw LLM output (Markdown table). Stored as plain text to match import logic.
    ai_shots_result = Column(Text, nullable=True)

    episode = relationship("Episode", back_populates="scenes")
    shots = relationship("Shot", back_populates="scene", cascade="all, delete-orphan")

class Shot(Base):
    __tablename__ = "shots"
    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(Integer, ForeignKey("scenes.id"))
    
    # Indexed for faster lookups as requested
    project_id = Column(Integer, index=True, nullable=True) 
    episode_id = Column(Integer, index=True, nullable=True)

    # Header Mapping
    shot_id = Column(String)           # Mapped to 'Shot ID'
    shot_name = Column(String, nullable=True) # Mapped to 'Shot Name'
    # 'Scene ID' from header helps map to scene_id, but we store it for reference if needed, 
    # though strictly we rely on scene_id relationship. 
    # Let's keep a scene_index_code for the text value "1"
    scene_code = Column(String, nullable=True) 

    start_frame = Column(Text, nullable=True)   # Mapped to 'Start Frame'
    end_frame = Column(Text, nullable=True)     # Mapped to 'End Frame'
    video_content = Column(Text, nullable=True) # Mapped to 'Video Content'
    duration = Column(String, nullable=True)    # Mapped to 'Duration (s)'
    keyframes = Column(Text, nullable=True)     # Mapped to 'Keyframes'
    associated_entities = Column(Text, nullable=True) # Mapped to 'Associated Entities'
    shot_logic_cn = Column(Text, nullable=True) # Mapped to 'Shot Logic (CN)'
    
    # Legacy / AI Internal (Kept for compatibility/utility)
    technical_notes = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    prompt = Column(Text, nullable=True) # Internal generation prompt (derived from start/end/video content)
    
    scene = relationship("Scene", back_populates="shots")

class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String)
    type = Column(String) # character, environment, prop
    description = Column(Text)
    
    # Extended Fields for Character Import
    name_en = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    role = Column(String, nullable=True)
    archetype = Column(String, nullable=True)
    appearance_cn = Column(Text, nullable=True)
    clothing = Column(Text, nullable=True)
    action_characteristics = Column(Text, nullable=True)
    
    # New Detailed Fields
    atmosphere = Column(String, nullable=True)
    visual_params = Column(Text, nullable=True)
    narrative_description = Column(Text, nullable=True) # The "Description:" part

    visual_dependencies = Column(JSON, default=[])
    dependency_strategy = Column(JSON, default={})

    image_url = Column(String, nullable=True)
    generation_prompt_en = Column(Text, nullable=True)
    generation_prompt_cn = Column(Text, nullable=True)
    anchor_description = Column(Text, nullable=True)
    
    # Store arbitrary user-defined attributes
    custom_attributes = Column(JSON, default={})
    
    project = relationship("Project", back_populates="entities")

class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    type = Column(String) # image, video
    url = Column(String)
    filename = Column(String, nullable=True)
    meta_info = Column(JSON, default={}) # width, height, size, duration, format
    remark = Column(Text, nullable=True)
    
    created_at = Column(String, default=now_bj_iso)
    
    owner = relationship("User", back_populates="assets")

class APISetting(Base):
    __tablename__ = "api_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_api_settings_user_category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    category = Column(String, index=True) # LLM, Image, Video, Voice
    system_api_id = Column(Integer, ForeignKey("system_api_settings.id"), index=True, nullable=True)
    mode = Column(String, nullable=True)

    user = relationship("User", back_populates="api_settings")


class SystemAPISetting(Base):
    """系统�?API 模型配置表�?

    每一行代表一个可用的 AI 模型端点（LLM / Image / Video / Voice / Music 等）�?
    管理员通过后台配置，前端和业务服务�?category + modality 匹配可用模型�?

    字段说明:
      name      �?显示名称，默�?"System Setting"
      category  �?业务分类: LLM / Image / Video / Voice / Music
      provider  �?供应商标�? openai / dashscope / volcengine / minimax / kling / siliconflow �?
      api_key   �?API 密钥（多 key 逗号分隔，用于轮询）
      base_url  �?API 基础地址，为空则使用 SDK 默认�?
      model     �?模型标识，如 gpt-4o / seedream-3.0 / wan-x2.1-t2v-turbo
      modality  �?模态描�?(JSON)，v2 格式，结�?
                  {
                    "generation_modes": ["t2i","i2i"],  # 生成方式(缩写)，筛选匹配核�?
                    "max_resolution": "2048x2048",       # 最高输出分辨率
                    "aspect_ratios": ["1:1","16:9"],    # 支持画幅�?
                    "has_audio": false,                  # 是否支持音频(视频模型)
                    "max_duration": 10,                  # 最大生成时�?�?
                    "base_model": "seedream-4.5",       # 基础模型
                    "model_version": "v4.5",            # 模型版本
                    "model_type": "diffusion",          # 架构: diffusion/transformer
                    "input_formats": ["text","image"],  # 输入格式
                    "output_format": "image"             # 输出格式
                  }
                  generation_modes 缩写: t2i(文生�? i2i(图生�? t2v(文生视频)
                  i2v(图生视频) v2v(视频转视�? t2a(文生音频) a2t(语音识别)
                  a2a(音频转音�? s2v(语音驱动视频/数字�? i2t(图像理解)
      tags      �?模型标签 (JSON string[])，如 ["真人写实","局部重�?,"高清"]
      deprecated�?是否已弃�?
      config    �?额外配置 (JSON)，如 webhook_url / strategy / weights �?
    is_active �?是否为该类别默认 API（当用户未指定该类别时自动选用�?
    """
    __tablename__ = "system_api_settings"
    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, default="System Setting")
    category = Column(String, index=True)       # LLM / Image / Video / Voice / Music
    provider = Column(String, index=True)       # openai / dashscope / volcengine ...
    api_key = Column(String)                    # 多key逗号分隔用于轮询
    base_url = Column(String, nullable=True)    # 自定义API地址
    model = Column(String, nullable=True)       # 模型标识
    base_model = Column(String, nullable=True)  # 基础模型归类名（�?qwen-plus / gpt-4o�?
    modality = Column(JSON, nullable=True)      # 模态描�?v2 JSON), 详见 docstring

    # Wide modality columns (normalized from modality JSON + supplier docs extraction)
    generation_modes = Column(JSON, nullable=True)              # [t2i, i2i, i2v, t2v, s2v, image_edit, t2a, a2t, a2a, t2m]
    input_formats = Column(JSON, nullable=True)                 # generic input formats
    output_format = Column(String, nullable=True)               # generic output format
    supported_resolutions = Column(JSON, nullable=True)         # ["1280x720", "1080p", "4k", ...]
    aspect_ratios = Column(JSON, nullable=True)                 # ["1:1", "16:9", ...]
    max_images_per_call = Column(Integer, nullable=True)
    reference_image_limit = Column(String, nullable=True)       # e.g. "1-2 images"
    reference_video_limit = Column(String, nullable=True)
    durations_seconds = Column(JSON, nullable=True)             # [3,5,10]
    max_duration = Column(Integer, nullable=True)               # seconds
    fps_options = Column(JSON, nullable=True)                   # [24,30,60]
    image_size_values = Column(JSON, nullable=True)             # ["1K", "2K", "4K", ...]
    quality_values = Column(JSON, nullable=True)                # ["standard", "pro", ...]
    has_audio = Column(Boolean, nullable=True)
    sound_supported = Column(Boolean, nullable=True)            # explicit sound toggle support
    multi_shots_supported = Column(Boolean, nullable=True)      # supports multi_shots input
    mode_values = Column(JSON, nullable=True)                   # provider mode enums (std/pro/fast/...)

    # Category-specific capability objects (wide columns)
    text_capabilities = Column(JSON, nullable=True)             # LLM
    image_capabilities = Column(JSON, nullable=True)            # Image
    video_capabilities = Column(JSON, nullable=True)            # Video
    digital_human_capabilities = Column(JSON, nullable=True)    # DigitalHuman
    voice_capabilities = Column(JSON, nullable=True)            # Voice
    music_capabilities = Column(JSON, nullable=True)            # Music

    # Billing-related hints extracted from supplier docs
    pricing_unit = Column(String, nullable=True)                # per_call/per_image/per_second/per_minute/per_1k_tokens
    token_billing_supported = Column(Boolean, nullable=True)
    input_token_price = Column(Float, nullable=True)
    output_token_price = Column(Float, nullable=True)
    per_resolution_price_map = Column(JSON, nullable=True)
    per_duration_price_map = Column(JSON, nullable=True)
    has_tiered_pricing = Column(Boolean, nullable=True)
    free_quota = Column(String, nullable=True)
    currency = Column(String, nullable=True)

    tags = Column(JSON, nullable=True)          # 模型标签 string[]
    supplier_info = Column(JSON, nullable=True) # 原供应商API定价信息(审计对照�?
    deprecated = Column(Boolean, default=False) # 是否弃用
    config = Column(JSON, default={})           # 额外配置(webhook_url�?

    is_active = Column(Boolean, default=False)  # 是否为该类别默认 API


class TaskDefaultSystemAPI(Base):
    """Per-task default System API binding.

    This is the source of truth for category/task default routing,
    decoupled from system_api_settings.is_active.
    """

    __tablename__ = "system_task_default_apis"

    id = Column(Integer, primary_key=True, index=True)
    task_category = Column(String, unique=True, index=True, nullable=False)  # LLM/IMAGE/VIDEO/DIGITAL_HUMAN/VOICE/MUSIC
    system_api_id = Column(Integer, ForeignKey("system_api_settings.id"), index=True, nullable=False)
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)


class SystemAPIBillingRule(Base):
    """�?system_api_settings.id 绑定的细化计费规则（宽表）�?

    规则支持 Text/Image/Video 三类模式，按元信息匹配；命中多条时使用价格最高的规则�?
    """
    __tablename__ = "system_api_billing_rules"

    id = Column(Integer, primary_key=True, index=True)
    system_api_id = Column(Integer, ForeignKey("system_api_settings.id"), index=True, nullable=False)

    name = Column(String, nullable=False, default="Rule")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)

    # 模式开�?
    applies_to_text = Column(Boolean, default=False)
    applies_to_image = Column(Boolean, default=False)
    applies_to_video = Column(Boolean, default=False)

    # 通用匹配要素
    generation_mode = Column(String, nullable=True)  # t2i/i2i/t2v/i2v/v2v...
    input_format = Column(String, nullable=True)     # text/image/video/audio
    output_format = Column(String, nullable=True)    # text/image/video/audio
    has_audio = Column(Boolean, nullable=True)

    # Text 维度
    input_tokens_min = Column(Integer, nullable=True)
    input_tokens_max = Column(Integer, nullable=True)
    output_tokens_min = Column(Integer, nullable=True)
    output_tokens_max = Column(Integer, nullable=True)
    total_tokens_min = Column(Integer, nullable=True)
    total_tokens_max = Column(Integer, nullable=True)

    # Image 维度
    image_count_min = Column(Integer, nullable=True)
    image_count_max = Column(Integer, nullable=True)
    width_min = Column(Integer, nullable=True)
    width_max = Column(Integer, nullable=True)
    height_min = Column(Integer, nullable=True)
    height_max = Column(Integer, nullable=True)
    pixels_min = Column(Integer, nullable=True)
    pixels_max = Column(Integer, nullable=True)

    # Video 维度
    duration_seconds_min = Column(Float, nullable=True)
    duration_seconds_max = Column(Float, nullable=True)
    fps_min = Column(Float, nullable=True)
    fps_max = Column(Float, nullable=True)

    # 定价
    billing_unit_type = Column(String, default="per_call")
    billing_cost = Column(Integer, default=0)
    billing_cost_input = Column(Integer, default=0)
    billing_cost_output = Column(Integer, default=0)
    charge_multiplier = Column(Float, default=2.0)

    extra_conditions = Column(JSON, default={})
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)


class SMTPSystemConfig(Base):
    """Dedicated SMTP configuration storage.

    Kept separate from system_api_settings because SMTP is infrastructure config,
    not an AIGC model endpoint.
    """

    __tablename__ = "smtp_system_configs"

    id = Column(Integer, primary_key=True, index=True)
    host = Column(String, nullable=False, default="")
    port = Column(Integer, nullable=False, default=587)
    username = Column(String, nullable=False, default="")
    password = Column(String, nullable=False, default="")
    use_ssl = Column(Boolean, default=False)
    use_tls = Column(Boolean, default=True)
    from_email = Column(String, nullable=False, default="")
    frontend_base_url = Column(String, nullable=False, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)


class WechatPayConfig(Base):
    """Dedicated WeChat payment configuration storage.

    Kept separate from system_api_settings because payment config is platform
    infrastructure, not an AIGC model endpoint.
    """

    __tablename__ = "wechat_pay_configs"

    id = Column(Integer, primary_key=True, index=True)
    mchid = Column(String, nullable=False, default="")
    appid = Column(String, nullable=False, default="")
    api_v3_key = Column(String, nullable=False, default="")
    cert_serial_no = Column(String, nullable=False, default="")
    private_key = Column(Text, nullable=False, default="")
    notify_url = Column(String, nullable=False, default="")
    use_mock = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)


class TransactionAction(Base):
    """Transaction action audit records (reserve/settle/refund/cancel)."""
    __tablename__ = "transaction_action"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    transaction_id = Column(Integer, ForeignKey("transaction_history.id"), index=True, nullable=True)
    reservation_tx_id = Column(Integer, ForeignKey("transaction_history.id"), index=True, nullable=True)
    settlement_tx_id = Column(Integer, ForeignKey("transaction_history.id"), index=True, nullable=True)

    stage = Column(String, index=True)  # RESERVED / SETTLED / REFUND / CHARGE / CANCELED
    task_type = Column(String, index=True)
    provider = Column(String, index=True, nullable=True)
    model = Column(String, index=True, nullable=True)

    system_api_id = Column(Integer, ForeignKey("system_api_settings.id"), index=True, nullable=True)
    matched_rule_id = Column(Integer, ForeignKey("system_api_billing_rules.id"), index=True, nullable=True)

    reserved_cost = Column(Integer, default=0)
    actual_cost = Column(Integer, default=0)
    delta = Column(Integer, default=0)
    charged_amount = Column(Integer, default=0)
    refunded_amount = Column(Integer, default=0)
    outstanding_amount = Column(Integer, default=0)

    matched_rule_ids = Column(JSON, default=[])
    usage_metadata = Column(JSON, default={})
    billing_metadata = Column(JSON, default={})
    created_at = Column(String, default=now_bj_iso)


class ProviderKeyPool(Base):
    """Unified provider API key pool.

    One row stores one provider's key pool and routing strategy.
    The `provider` field is globally unique.
    """
    __tablename__ = "provider_key_pool"
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, unique=True, index=True, nullable=False)  # Provider identifier (lowercase)
    provider_alias = Column(String, nullable=True) # Display alias for user-facing settings UI
    api_keys = Column(JSON, default=[])           # 密钥列表 List[str]
    strategy = Column(String, default="random")   # random / round_robin / weighted
    weights = Column(JSON, default=[])            # Weights list when strategy=weighted
    intro_url = Column(String, nullable=True)     # Provider API documentation URL
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)


class RechargePlan(Base):
    __tablename__ = "recharge_plans"
    id = Column(Integer, primary_key=True, index=True)
    min_amount = Column(Integer, nullable=False) # In CNY
    max_amount = Column(Integer, nullable=False) # In CNY
    credit_rate = Column(Integer, default=100)   # Credits per 1 CNY
    bonus = Column(Integer, default=0)           # Extra fixed credits
    is_active = Column(Boolean, default=True)

class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    amount = Column(Integer, nullable=False) # In CNY
    credits = Column(Integer, nullable=False) # Total credits to add
    status = Column(String, default="PENDING") # PENDING, PAID, CANCELLED
    pay_url = Column(String, nullable=True) # QR Code Content
    
    provider = Column(String, default="wechat")
    created_at = Column(String, default=now_bj_iso)
    paid_at = Column(String, nullable=True)
    
    user = relationship("User")

