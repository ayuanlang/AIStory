
from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from app.db.session import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String)
    
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_authorized = Column(Boolean, default=False) # Can reuse system keys
    is_system = Column(Boolean, default=False) # Provider of shared keys
    
    credits = Column(Integer, default=0) # User points/credits

    projects = relationship("Project", back_populates="owner")
    api_settings = relationship("APISetting", back_populates="user")
    assets = relationship("Asset", back_populates="owner")
    system_logs = relationship("SystemLog", back_populates="user")
    transactions = relationship("TransactionHistory", back_populates="user")


class PricingRule(Base):
    __tablename__ = "pricing_rules"
    id = Column(Integer, primary_key=True, index=True)
    
    provider = Column(String, nullable=True, index=True) # e.g. "openai", "midjourney"
    model = Column(String, nullable=True, index=True)    # e.g. "gpt-4", "mj-v6"
    task_type = Column(String, nullable=False, index=True) # "llm_chat", "image_gen", "video_gen", "analysis"
    
    cost = Column(Integer, default=1) # Points per unit (Base/Total if n/a)
    cost_input = Column(Integer, default=0) # For LLM, per unit input tokens
    cost_output = Column(Integer, default=0) # For LLM, per unit output tokens
    
    # Reference fields for UI auto-calculation (Store user inputs)
    ref_cost_cny = Column(Float, nullable=True)
    ref_cost_input_cny = Column(Float, nullable=True)
    ref_cost_output_cny = Column(Float, nullable=True)
    ref_markup = Column(Float, default=1.5)
    ref_exchange_rate = Column(Float, default=10.0)

    unit_type = Column(String, default="per_call") # per_call, per_token, per_million_tokens
    
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

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
    
    created_at = Column(String, default=datetime.datetime.utcnow().isoformat)
    
    user = relationship("User", back_populates="transactions")

class SystemLog(Base):
    __tablename__ = "system_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_name = Column(String, nullable=True)
    action = Column(String, index=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(String, default=datetime.datetime.utcnow().isoformat)
    
    user = relationship("User", back_populates="system_logs")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # Global Info as JSON
    # script_title, overall_genre, color_tone, borrowed_films, notes
    global_info = Column(JSON, default={})
    
    created_at = Column(String, default=datetime.datetime.utcnow().isoformat)
    updated_at = Column(String, default=datetime.datetime.utcnow().isoformat)
    
    owner = relationship("User", back_populates="projects")
    episodes = relationship("Episode", back_populates="project", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="project", cascade="all, delete-orphan")

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
    
    created_at = Column(String, default=datetime.datetime.utcnow().isoformat)
    
    owner = relationship("User", back_populates="assets")

class APISetting(Base):
    __tablename__ = "api_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    name = Column(String, default="Default")
    category = Column(String, index=True) # LLM, Image, Video, Voice
    provider = Column(String) # openai, midjourney, stability, etc.
    api_key = Column(String)
    base_url = Column(String, nullable=True)
    model = Column(String, nullable=True)
    config = Column(JSON, default={}) # Extra params
    
    is_active = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="api_settings")

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
    created_at = Column(String, default=datetime.datetime.utcnow().isoformat)
    paid_at = Column(String, nullable=True)
    
    user = relationship("User")
