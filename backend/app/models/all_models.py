from sqlalchemy import event, func, DateTime, Column, Integer, String, Text, ForeignKey, JSON, Boolean, Float, UniqueConstraint
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
    
    is_active = Column(Integer, default=1)
    account_status = Column(Integer, default=1)  # 1=active, -1=pending email verification, 0=disabled
    email_verified = Column(Boolean, default=False)
    email_verification_code = Column(String, nullable=True)
    email_verification_expires_at = Column(String, nullable=True)
    is_superuser = Column(Boolean, default=False)
    is_authorized = Column(Boolean, default=False) # Can reuse system keys
    is_system = Column(Boolean, default=False) # Provider of shared keys
    preferences = Column(JSON, default={})
    
    credits = Column(Integer, default=0) # User points/credits

    current_group_id = Column(Integer, ForeignKey("user_groups.id"), nullable=True)
    current_group = relationship("UserGroup", foreign_keys=[current_group_id])
    groups = relationship("UserGroupMembership", back_populates="user", cascade="all, delete-orphan")

    projects = relationship("Project", back_populates="owner")
    shared_projects = relationship("ProjectShare", back_populates="user", cascade="all, delete-orphan")
    requested_asset_review_threads = relationship(
        "ProjectAssetReviewThread",
        foreign_keys="ProjectAssetReviewThread.requester_user_id",
        back_populates="requester",
    )
    assigned_asset_review_threads = relationship(
        "ProjectAssetReviewThread",
        foreign_keys="ProjectAssetReviewThread.reviewer_user_id",
        back_populates="reviewer",
    )
    asset_review_messages = relationship("ProjectAssetReviewMessage", back_populates="sender")
    api_settings = relationship("APISetting", back_populates="user")
    assets = relationship("Asset", back_populates="owner")
    system_logs = relationship("SystemLog", back_populates="user")
    transactions = relationship("TransactionHistory", back_populates="user")


class UserGroup(Base):
    __tablename__ = "user_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    credits = Column(Integer, default=0)
    # When False (default), billing only uses members' personal credits.
    allow_group_credit_billing = Column(Boolean, default=False, nullable=False)

    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", foreign_keys=[owner_id])
    
    members = relationship("UserGroupMembership", back_populates="group", cascade="all, delete-orphan")

    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)

class UserGroupMembership(Base):
    __tablename__ = "user_group_memberships"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    group_id = Column(Integer, ForeignKey("user_groups.id"), index=True, nullable=False)
    
    permission_level = Column(Integer, default=1)
    credit_share_limit = Column(Integer, default=0)
    
    user = relationship("User", back_populates="groups")
    group = relationship("UserGroup", back_populates="members")

    created_at = Column(String, default=now_bj_iso)


class ProjectGroupCreditAllocation(Base):
    __tablename__ = "project_group_credit_allocations"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=False)
    group_id = Column(Integer, ForeignKey("user_groups.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    
    credit_limit = Column(Integer, default=10000) # -1 implies unlimited
    used_credits = Column(Integer, default=0)
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)




class TransactionHistory(Base):
    __tablename__ = "transaction_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    target_group_id = Column(Integer, ForeignKey("user_groups.id"), nullable=True)

    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=True)

    amount = Column(Integer, nullable=False) # Negative for cost, positive for refill
    balance_after = Column(Integer, nullable=False) # Snapshot of balance
    
    description = Column(String, nullable=True) # 支出/充值描述

    details = Column(JSON, default={}) # Extra metadata (e.g. status)

    created_at = Column(String, default=now_bj_iso)

    user = relationship("User", back_populates="transactions")
    project = relationship("Project", foreign_keys=[project_id])
    episode = relationship("Episode", foreign_keys=[episode_id])
    action_audit = relationship("TransactionAction", foreign_keys="[TransactionAction.transaction_id]", back_populates="ledger_entry", uselist=False)

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


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"
    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String, index=True, nullable=True)
    provider = Column(String, index=True, nullable=True)
    model = Column(String, index=True, nullable=True)
    api_url = Column(String, nullable=True)
    payload_json = Column(Text, nullable=True)
    response_json = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    request_id = Column(String, index=True, nullable=True)
    timestamp = Column(String, default=now_bj_iso)


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
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(String, nullable=True)
    
    owner = relationship("User", back_populates="projects")
    shares = relationship("ProjectShare", back_populates="project", cascade="all, delete-orphan")
    episodes = relationship("Episode", back_populates="project", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="project", cascade="all, delete-orphan")
    asset_review_threads = relationship("ProjectAssetReviewThread", back_populates="project", cascade="all, delete-orphan")


@event.listens_for(Project, "before_update")
def _project_set_updated_at(_mapper, _connection, target):
    target.updated_at = now_bj_iso()


class ProjectShare(Base):
    __tablename__ = "project_shares"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    role = Column(String, nullable=False, default="editor")
    permissions = Column(JSON, default={})
    created_at = Column(String, default=now_bj_iso)

    project = relationship("Project", back_populates="shares")
    user = relationship("User", back_populates="shared_projects")


class DeletionBatch(Base):
    __tablename__ = "deletion_batches"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=False)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    action_type = Column(String, nullable=False, index=True)
    label = Column(String, nullable=True)
    item_count = Column(Integer, nullable=False, default=0)
    created_at = Column(String, default=now_bj_iso)
    restored_at = Column(String, nullable=True)


class DeletionBatchItem(Base):
    __tablename__ = "deletion_batch_items"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, ForeignKey("deletion_batches.id"), index=True, nullable=False)
    resource_type = Column(String, index=True, nullable=False)
    resource_id = Column(Integer, index=True, nullable=False)


class ProjectAssetReviewThread(Base):
    __tablename__ = "project_asset_review_threads"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=False)
    requester_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String, nullable=True)
    status = Column(String, nullable=False, default="open")
    latest_round_no = Column(Integer, nullable=False, default=0)
    latest_activity_at = Column(String, default=now_bj_iso)
    requester_last_read_at = Column(String, nullable=True)
    reviewer_last_read_at = Column(String, nullable=True)
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)

    project = relationship("Project", back_populates="asset_review_threads")
    requester = relationship("User", foreign_keys=[requester_user_id], back_populates="requested_asset_review_threads")
    reviewer = relationship("User", foreign_keys=[reviewer_user_id], back_populates="assigned_asset_review_threads")
    rounds = relationship("ProjectAssetReviewRound", back_populates="thread", cascade="all, delete-orphan")


class ProjectAssetReviewRound(Base):
    __tablename__ = "project_asset_review_rounds"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("project_asset_review_threads.id"), index=True, nullable=False)
    round_no = Column(Integer, nullable=False, default=1)
    initiated_by_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    request_message = Column(Text, nullable=True)
    scope_type = Column(String, nullable=False, default="all_current")
    entity_required = Column(Boolean, nullable=False, default=True)
    shot_required = Column(Boolean, nullable=False, default=True)
    entity_decision = Column(String, nullable=False, default="pending")
    shot_decision = Column(String, nullable=False, default="pending")
    overall_status = Column(String, nullable=False, default="pending_reviewer")
    entity_feedback = Column(Text, nullable=True)
    shot_feedback = Column(Text, nullable=True)
    due_at = Column(String, nullable=True)
    selected_entity_ids = Column(JSON, default=[])
    selected_shot_ids = Column(JSON, default=[])
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)
    closed_at = Column(String, nullable=True)

    thread = relationship("ProjectAssetReviewThread", back_populates="rounds")
    initiator = relationship("User", foreign_keys=[initiated_by_user_id])
    messages = relationship("ProjectAssetReviewMessage", back_populates="round", cascade="all, delete-orphan")


class ProjectAssetReviewMessage(Base):
    __tablename__ = "project_asset_review_messages"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("project_asset_review_rounds.id"), index=True, nullable=False)
    sender_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    sender_role = Column(String, nullable=False, default="requester")
    message_type = Column(String, nullable=False, default="message")
    message_text = Column(Text, nullable=True)
    entity_decision = Column(String, nullable=True)
    shot_decision = Column(String, nullable=True)
    entity_feedback = Column(Text, nullable=True)
    shot_feedback = Column(Text, nullable=True)
    created_at = Column(String, default=now_bj_iso)

    round = relationship("ProjectAssetReviewRound", back_populates="messages")
    sender = relationship("User", back_populates="asset_review_messages")

class APIRoutingConfig(Base):
    __tablename__ = "api_routing_configs"
    id = Column(Integer, primary_key=True, index=True)
    use_function_based_routing = Column(Boolean, default=False)
    explicit_selection = Column(Boolean, default=False)
    strict_provider = Column(Boolean, default=False)

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
    ai_scene_analysis_scene_markdown = Column(Text, nullable=True)
    ai_scene_analysis_subject_index = Column(Text, nullable=True)
    ai_scene_analysis_adaptation = Column(Text, nullable=True)
    ai_entity_design_result = Column(Text, nullable=True)
    ai_stage_outputs = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(String, nullable=True)

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
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(String, nullable=True)

    episode = relationship("Episode", back_populates="scenes")
    shots = relationship("Shot", back_populates="scene", cascade="all, delete-orphan")

class Shot(Base):
    __tablename__ = "shots"
    # Active-row uniqueness is enforced in init_db as partial unique index
    # uq_shots_proj_ep_shot_id_active on (project_id, episode_id, upper(trim(shot_id)))
    # WHERE coalesce(is_deleted,false)=false — soft-deleted rows may reuse the same Shot ID.
    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(Integer, ForeignKey("scenes.id"))
    
    # Indexed for faster lookups as requested
    project_id = Column(Integer, index=True, nullable=True) 
    episode_id = Column(Integer, index=True, nullable=True)

    # Header Mapping — business key EP##_SC##_SH## (unique per project+episode when active)
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
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(String, nullable=True)
    
    scene = relationship("Scene", back_populates="shots")


class ScriptProgressSceneUnit(Base):
    __tablename__ = "script_progress_scene_units"
    __table_args__ = (
        UniqueConstraint("project_id", "episode_id", "scene_id", name="uq_script_progress_scene_units_project_episode_scene"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=False)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=False)
    script_id = Column(String, index=True, nullable=True)
    scene_id = Column(String, index=True, nullable=False)
    scene_order = Column(Integer, nullable=True)
    scene_text = Column(Text, nullable=True)
    scene_markdown = Column(Text, nullable=True)
    marker_start_token = Column(String, nullable=True)
    marker_end_token = Column(String, nullable=True)
    parse_status = Column(String, default="success")
    import_status = Column(String, default="queued")
    parse_error_code = Column(String, nullable=True)
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)


class ScriptProgressPipelineNode(Base):
    __tablename__ = "script_progress_pipeline_nodes"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "episode_id",
            "node_name",
            "scene_id",
            "asset_type",
            name="uq_script_progress_pipeline_nodes_scope",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=False)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=False)
    script_id = Column(String, index=True, nullable=True)
    scene_id = Column(String, index=True, nullable=True)
    node_name = Column(String, index=True, nullable=False)
    asset_type = Column(String, index=True, nullable=True)
    status = Column(String, index=True, default="queued")
    progress_percent = Column(Float, default=0.0)
    started_at = Column(String, nullable=True)
    ended_at = Column(String, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    retry_count = Column(Integer, default=0)
    retry_limit = Column(Integer, default=3)
    depends_on = Column(JSON, default=[])
    runtime_meta = Column(JSON, default={})
    last_error_code = Column(String, nullable=True)
    last_error_message = Column(Text, nullable=True)
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)


class ScriptProgressIssue(Base):
    __tablename__ = "script_progress_issues"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=False)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=True)
    script_id = Column(String, index=True, nullable=True)
    scene_id = Column(String, index=True, nullable=True)
    severity = Column(String, index=True, default="WARNING")
    status = Column(String, index=True, default="open")
    issue_code = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    owner_domain = Column(String, index=True, nullable=True)
    node_ref = Column(String, nullable=True)
    first_seen_at = Column(String, default=now_bj_iso)
    last_seen_at = Column(String, default=now_bj_iso)
    created_at = Column(String, default=now_bj_iso)
    updated_at = Column(String, default=now_bj_iso)


class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=True)
    name = Column(String)
    type = Column(String) # character, environment, prop
    description = Column(Text)
    
    # Extended Fields for Character Import
    name_en = Column(String, nullable=True)
    base_name_en = Column(String, nullable=True)
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
    video_url = Column(String, nullable=True)
    audio_url = Column(String, nullable=True)
    generation_prompt_en = Column(Text, nullable=True)
    generation_prompt_cn = Column(Text, nullable=True)
    anchor_description = Column(Text, nullable=True)
    
    # Store arbitrary user-defined attributes
    custom_attributes = Column(JSON, default={})
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(String, nullable=True)
    
    project = relationship("Project", back_populates="entities")
    episode = relationship("Episode", foreign_keys=[episode_id])

class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=True)
    is_current_project_asset = Column(Boolean, default=False, index=True, nullable=False)
    
    type = Column(String) # image, video
    url = Column(String)
    url_normalized = Column(String, index=True, nullable=True)
    filename = Column(String, nullable=True)
    meta_info = Column(JSON, default={}) # width, height, size, duration, format
    remark = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(String, nullable=True)
    
    created_at = Column(String, default=now_bj_iso)
    
    owner = relationship("User", back_populates="assets")
    project = relationship("Project", foreign_keys=[project_id])
    episode = relationship("Episode", foreign_keys=[episode_id])


class APISetting(Base):
    __tablename__ = "api_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_api_settings_user_category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    category = Column(String, index=True) # LLM, Image, Video, Voice
    system_api_id = Column(Integer, ForeignKey("system_api_settings.id"), index=True, nullable=True)
    api_strategy = Column(String, nullable=True)
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

    tags = Column(JSON, nullable=True)          # 模型标签 string[]
    supplier_info = Column(JSON, nullable=True) # 原供应商API定价信息(审计对照�?
    deprecated = Column(Boolean, default=False) # 是否弃用
    config = Column(JSON, default={})           # 额外配置(webhook_url�?

    # Precomputed pricing summary (persisted on table for fast reads)
    price_avg_cost = Column(Integer, nullable=True)
    price_source = Column(String, nullable=True)
    price_min_cost = Column(Integer, nullable=True)
    price_max_cost = Column(Integer, nullable=True)
    price_sample_prices = Column(JSON, nullable=True)
    price_updated_at = Column(String, nullable=True)

    provider_price_avg_cost = Column(Integer, nullable=True)
    provider_price_source = Column(String, nullable=True)
    provider_price_min_cost = Column(Integer, nullable=True)
    provider_price_max_cost = Column(Integer, nullable=True)
    provider_price_sample_prices = Column(JSON, nullable=True)
    provider_price_updated_at = Column(String, nullable=True)

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

class FunctionAPIConfig(Base):
    """高级功能到可用 API 的配置表 (JSON 格式存储).

    每一个特定的功能对应一条记录。
    支持的功能：
      generate_subjects      (生成实体：角色、道具、环境、不含封面)
generate_subjects_t2i  (文生图：角色、道具、环境、不含封面)`ngenerate_subjects_i2i  (图生图：角色、道具、环境、不含封面)
      generate_cover         (生成封面)
      generate_shot_images   (生成分镜图片)
      generate_videos        (生成视频)
      script_analysis        (剧本分析)
      subject_image_analysis (subjects图片分析)

    fields:
      function_name: 功能名称，全局唯一
      api_settings: JSON数组，例如 [{"system_api_id": 1, "priority": 10, "is_fallback": true}, ...]
    """
    __tablename__ = "function_api_configs"

    id = Column(Integer, primary_key=True, index=True)
    function_name = Column(String, unique=True, index=True, nullable=False)   
    api_settings = Column(JSON, default=list) # 存储的是配置项列表： [{system_api_id, priority, is_fallback}]
    # 功能级用户计费：在规则倍率结果之上再乘倍率（默认1）并加固定积分（默认0）
    billing_multiplier = Column(Float, nullable=False, default=1.0)
    billing_add_credits = Column(Integer, nullable=False, default=0)
    
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

    # 定价：供应商价（CNY）持久化 → 派生基础积分成本 → 倍率加成后为用户价
    billing_unit_type = Column(String, default="per_call")
    supplier_price = Column(Float, nullable=True)
    supplier_price_input = Column(Float, nullable=True)
    supplier_price_output = Column(Float, nullable=True)
    supplier_currency = Column(String, nullable=True, default="CNY")
    supplier_price_basis = Column(String, nullable=True, default="money")
    billing_cost = Column(Integer, default=0)  # 派生：ceil(supplier_price_cny * 100)
    billing_cost_input = Column(Integer, default=0)
    billing_cost_output = Column(Integer, default=0)
    charge_multiplier = Column(Float, default=2.0)  # 倍率：用户价 = 基础成本 * 倍率

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


class QueueSystemConfig(Base):
    """Global generation-queue / callback thread configuration.

    Stored in DB so admin changes survive process restarts and deploys.
    Single active row (lowest id) is the source of truth.
    """

    __tablename__ = "queue_system_configs"

    id = Column(Integer, primary_key=True, index=True)
    config_json = Column(JSON, nullable=False, default=dict)
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

    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=True)
    project = relationship("Project", foreign_keys=[project_id])
    episode = relationship("Episode", foreign_keys=[episode_id])
    reservation_tx_id = Column(Integer, ForeignKey("transaction_history.id"), index=True, nullable=True)
    settlement_tx_id = Column(Integer, ForeignKey("transaction_history.id"), index=True, nullable=True)

    stage = Column(String, index=True)  # RESERVED / SETTLED / REFUND / CHARGE / CANCELED
    task_type = Column(String, index=True)
    provider = Column(String, index=True, nullable=True)
    model = Column(String, index=True, nullable=True)

    system_api_id = Column(Integer, ForeignKey("system_api_settings.id"), index=True, nullable=True)

    ledger_entry = relationship("TransactionHistory", foreign_keys="[TransactionAction.transaction_id]", back_populates="action_audit")
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


class OSSProviderPool(Base):
    __tablename__ = "oss_provider_pools"
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, index=True, nullable=False)
    provider_alias = Column(String, nullable=True)
    endpoint = Column(String, nullable=False)
    region = Column(String, nullable=True)
    bucket = Column(String, nullable=False)
    public_base_url = Column(String, nullable=True)
    root_prefix = Column(String, nullable=True)
    credentials = Column(JSON, default=[])
    strategy = Column(String, default="random")
    weights = Column(JSON, default=[])
    default_storage_class = Column(String, nullable=True)
    retention_days = Column(Integer, nullable=True)
    force_path_style = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
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
    target_group_id = Column(Integer, ForeignKey("user_groups.id"), nullable=True)
    
    amount = Column(Integer, nullable=False) # In CNY
    credits = Column(Integer, nullable=False) # Total credits to add
    status = Column(String, default="PENDING") # PENDING, PAID, CANCELLED
    invoice_status = Column(String, default="UNINVOICED") # UNINVOICED, REQUESTING, INVOICED
    pay_url = Column(String, nullable=True) # QR Code Content
    
    provider = Column(String, default="wechat")
    created_at = Column(String, default=now_bj_iso)
    paid_at = Column(String, nullable=True)
    
    user = relationship("User")


class DeletedMedia(Base):
    __tablename__ = "deleted_media"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)
    deleted_at = Column(DateTime(timezone=True), default=func.now())

class InvoiceProfile(Base):
    __tablename__ = "invoice_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("user_groups.id"), nullable=True)
    type = Column(String, default="ENTERPRISE") # ENTERPRISE, PERSONAL
    title = Column(String, nullable=False)
    tax_number = Column(String, nullable=True)
    email = Column(String, nullable=True)
    created_at = Column(String, default=now_bj_iso)

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("payment_orders.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    tax_number = Column(String, nullable=True)
    email = Column(String, nullable=True)
    status = Column(String, default="PENDING") # PENDING, ISSUED, FAILED
    wechat_invoice_id = Column(String, nullable=True)
    pdf_url = Column(String, nullable=True)
    created_at = Column(String, default=now_bj_iso)


import datetime

class EntityHistory(Base):
    __tablename__ = "entity_history"
    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), index=True)
    
    # Store history snapshot fields
    name = Column(String)
    type = Column(String)
    description = Column(Text)
    
    # Extended Fields for Character Import
    name_en = Column(String, nullable=True)
    base_name_en = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    role = Column(String, nullable=True)
    archetype = Column(String, nullable=True)
    appearance_cn = Column(Text, nullable=True)
    clothing = Column(Text, nullable=True)
    action_characteristics = Column(Text, nullable=True)
    atmosphere = Column(String, nullable=True)
    visual_params = Column(Text, nullable=True)
    narrative_description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class MarketIntelReport(Base):
    """Time-indexed industry analysis / trending hot-list snapshots per project."""
    __tablename__ = "market_intel_reports"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=False)
    # industry_analysis | trending_dramas
    report_kind = Column(String, index=True, nullable=False)
    # YYYY-MM anchor used as the primary time index
    report_month = Column(String, index=True, nullable=False)
    report_period = Column(String, nullable=True)
    fetched_at = Column(String, nullable=True, index=True)
    summary = Column(Text, nullable=True)
    markdown = Column(Text, nullable=True)
    payload_json = Column(JSON, default={})
    created_at = Column(String, default=now_bj_iso, index=True)
