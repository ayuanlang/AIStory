import datetime

def inject_history_logic(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # The schemas
    schema_code = """
class EntityHistoryOut(BaseModel):
    id: int
    entity_id: int
    remark: Optional[str] = None
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

"""

    # The endpoints
    endpoints_code = """
@router.get("/projects/{project_id}/entities/{entity_id}/history", response_model=List[EntityHistoryOut])
def get_entity_history(
    project_id: int,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_project_access(db, project_id, current_user)
    histories = db.query(models.EntityHistory).filter(models.EntityHistory.entity_id == entity_id).order_by(models.EntityHistory.created_at.desc()).all()
    return histories

@router.post("/projects/{project_id}/entities/{entity_id}/restore/{history_id}")
def restore_entity_history(
    project_id: int,
    entity_id: int,
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_project_access(db, project_id, current_user)
    entity = db.query(models.Entity).filter(models.Entity.id == entity_id, models.Entity.project_id == project_id).first()
    if not entity: raise HTTPException(404, "Entity not found")
    history = db.query(models.EntityHistory).filter(models.EntityHistory.id == history_id, models.EntityHistory.entity_id == entity_id).first()
    if not history: raise HTTPException(404, "History not found")
    
    # Save current state as history before restore
    current_snapshot = {c.name: getattr(entity, c.name) for c in entity.__table__.columns if c.name not in ["id", "project_id", "episode_id", "custom_attributes"]}
    # To preserve dict type mapping correctly
    current_snapshot['custom_attributes'] = entity.custom_attributes
    
    db.add(models.EntityHistory(entity_id=entity.id, project_id=project_id, snapshot=current_snapshot, remark="Backup before restore"))
    
    snapshot = history.snapshot
    for k, v in snapshot.items():
        if hasattr(entity, k) and k not in ["id", "project_id", "episode_id", "custom_attributes"]:
            setattr(entity, k, v)
    if "custom_attributes" in snapshot:
        entity.custom_attributes = snapshot["custom_attributes"]
        
    db.commit()
    return {"message": "Success"}

@router.post("/projects/{project_id}/entities/{entity_id}/sync_from/{old_entity_id}")
def sync_entity_from_old(
    project_id: int,
    entity_id: int,
    old_entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_project_access(db, project_id, current_user)
    
    entity = db.query(models.Entity).filter(models.Entity.id == entity_id, models.Entity.project_id == project_id).first()
    if not entity: raise HTTPException(404, "Entity not found")
        
    old_entity = db.query(models.Entity).filter(models.Entity.id == old_entity_id, models.Entity.project_id == project_id).first()
    if not old_entity: raise HTTPException(404, "Old Entity not found")
    
    # Save current state to history
    current_snapshot = {c.name: getattr(entity, c.name) for c in entity.__table__.columns if c.name not in ["id", "project_id", "episode_id", "custom_attributes"]}
    current_snapshot['custom_attributes'] = entity.custom_attributes
    
    db.add(models.EntityHistory(entity_id=entity.id, project_id=project_id, snapshot=current_snapshot, remark="Auto-backup before syncing from older entity"))
    
    # DO NOT sync ID, project, episode, or name
    # DO sync properties like descriptions, prompts, images, base details
    sync_fields = ["description", "image_url", "generation_prompt_en", "generation_prompt_cn", 
                   "anchor_description", "name_en", "base_name_en", "gender", "role", "archetype",
                   "appearance_cn", "clothing", "action_characteristics", "atmosphere", "visual_params",
                   "narrative_description", "dependency_strategy", "custom_attributes"]
    
    for f in sync_fields:
        if hasattr(old_entity, f):
            setattr(entity, f, getattr(old_entity, f))
            
    # Specially merge visual dependencies to include old entity
    new_deps = list(old_entity.visual_dependencies) if old_entity.visual_dependencies else []
    new_deps.append(f"existing_id:{old_entity.id}")
    entity.visual_dependencies = list(set(new_deps)) # remove duplicates if any

    db.commit()
    db.refresh(entity)
    return entity

"""

    # find place to insert schema (e.g. near class EntityUpdate)
    import re
    
    target_schema = "class EntityUpdate(BaseModel):"
    content = content.replace(target_schema, schema_code + target_schema)
    
    target_endpoint = 'def update_entity('
    endpoint_marker = '@router.put("/projects/{project_id}/entities/{entity_id}", response_model=EntityOut)'
    
    content = content.replace(endpoint_marker, endpoints_code + endpoint_marker)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

inject_history_logic(r"c:\AS\AIStory\backend\app\api\endpoints.py")
print("done")
