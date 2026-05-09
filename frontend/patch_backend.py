import re

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

funcs = '''
from fastapi import File, UploadFile, Form
from app.core._vision_v2 import process_image_with_vlm

@router.post("/projects/{project_id}/entities/llm-text")
def api_generate_entity_from_text(
    project_id: int,
    text_desc: str = Form(...),
    model: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)
    
    # Very simple implementation using the core LLM utility
    import json
    from app.core._llm import _call_llm_json_with_retry, get_llm_model_name_for
    prompt = f"""
    Please generate a subject JSON based on the user's description.
    Use the following entity_design.md structure as reference.
    User description: {text_desc}
    Return ONLY valid JSON.
    """
    
    try:
        model_name = model or get_llm_model_name_for(project_id, "script_analysis", db)
        result = _call_llm_json_with_retry(prompt, model=model_name)
        if isinstance(result, dict):
            # Convert dict back to EntityCreate to insert
            if "name" not in result:
                result["name"] = "Unknown Entity"
            
            new_entity = Entity(
                project_id=project_id,
                name=result.get("name"),
                name_en=result.get("name_en", ""),
                type=result.get("type", "character"),
                bio=result.get("bio", ""),
                features=result.get("features", ""),
                personality=result.get("personality", ""),
                user_id=current_user.id
            )
            db.add(new_entity)
            db.commit()
            db.refresh(new_entity)
            return new_entity
        return {"error": "Invalid format from LLM"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/entities/llm-image")
def api_generate_entity_from_image(
    project_id: int,
    file: UploadFile = File(...),
    model: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)
    
    import base64
    content = file.file.read()
    b64_img = base64.b64encode(content).decode('utf-8')
    
    prompt = "Please analyze this character image and extract a subject JSON with 'name', 'name_en', 'type', 'bio', 'features', 'personality'."
    
    try:
        from app.core._llm import _call_llm_json_with_retry, get_llm_model_name_for
        model_name = model or get_llm_model_name_for(project_id, "vision_analysis", db)
        
        # Depending on how the project handles vision, we use process_image_with_vlm or pass it to llm
        result = _call_llm_json_with_retry(prompt, model=model_name, images=[b64_img])
        
        if isinstance(result, dict):
            new_entity = Entity(
                project_id=project_id,
                name=result.get("name", "Image Entity"),
                name_en=result.get("name_en", ""),
                type=result.get("type", "character"),
                bio=result.get("bio", ""),
                features=result.get("features", ""),
                personality=result.get("personality", ""),
                user_id=current_user.id
            )
            db.add(new_entity)
            db.commit()
            db.refresh(new_entity)
            return new_entity
        return {"error": "Invalid format from Vision LLM"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/entities/llm-derive")
def api_generate_entity_from_derive(
    project_id: int,
    base_entity_id: str = Form(...),
    derive_desc: str = Form(...),
    model: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)
    
    base_entity = db.query(Entity).filter(Entity.id == int(base_entity_id), Entity.project_id == project_id).first()
    if not base_entity:
        raise HTTPException(status_code=404, detail="Base entity not found")
        
    prompt = f"""
    Please generate a new subject JSON by taking the base entity and applying the modification constraints.
    Base Entity Name: {base_entity.name}
    Base Bio: {base_entity.bio}
    Base Features: {base_entity.features}
    Base Personality: {base_entity.personality}
    
    Modification needed: {derive_desc}
    
    Return ONLY a JSON matching 'name', 'name_en', 'type', 'bio', 'features', 'personality'.
    """
    
    try:
        from app.core._llm import _call_llm_json_with_retry, get_llm_model_name_for
        model_name = model or get_llm_model_name_for(project_id, "script_analysis", db)
        
        result = _call_llm_json_with_retry(prompt, model=model_name)
        if isinstance(result, dict):
            new_entity = Entity(
                project_id=project_id,
                name=result.get("name", base_entity.name + " (Variant)"),
                name_en=result.get("name_en", base_entity.name_en),
                type=result.get("type", base_entity.type),
                bio=result.get("bio", ""),
                features=result.get("features", ""),
                personality=result.get("personality", ""),
                user_id=current_user.id
            )
            db.add(new_entity)
            db.commit()
            db.refresh(new_entity)
            return new_entity
        return {"error": "Invalid format from LLM"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
'''

if 'api_generate_entity_from_text' not in text:
    text += "\n" + funcs
    with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Patched endpoints.py")
else:
    print("endpoints.py already patched")
