import re

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Remove the broken imports and functions cleanly
start_idx = text.find('from fastapi import File, UploadFile, Form\nfrom app.core._vision_v2 import process_image_with_vlm')
if start_idx != -1:
    text = text[:start_idx]

funcs = '''
from fastapi import File, UploadFile, Form
import json
import base64

@router.post("/projects/{project_id}/entities/llm-text", response_model=EntityOut)
async def api_generate_entity_from_text(
    project_id: int,
    text_desc: str = Form(...),
    model: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)
    
    sys_prompt = "You are an AI assistant that extracts Character/Prop information. Output valid JSON only."
    user_prompt = f"""
    Please generate a subject JSON based on the user's description.
    Ensure keys are exactly: "name", "name_en", "type" (character, prop, environment, poster), "bio", "features", "personality".
    User description: {text_desc}
    """
    
    llm_config = agent_service.get_active_llm_config(current_user.id, category="LLM", function_name="script_analysis")
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM config available")
        
    try:
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
        content = llm_service.sanitize_text_output(str(resp.get("content") or ""))
        
        # Try parse JSON
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
        else:
            result = {"name": "Parsed Error Entity", "bio": content}
            
        new_entity = Entity(
            project_id=project_id,
            name=result.get("name", "Generated Entity"),
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/entities/llm-image", response_model=EntityOut)
async def api_generate_entity_from_image(
    project_id: int,
    file: UploadFile = File(...),
    model: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)
    
    content = await file.read()
    b64_img = base64.b64encode(content).decode('utf-8')
    mime_type = file.content_type or 'image/jpeg'
    data_uri = f"data:{mime_type};base64,{b64_img}"
    
    sys_prompt = "You are a Vision AI assistant. Extract character details from the image. Output valid JSON only."
    user_prompt = "Please analyze this image and extract a subject JSON with keys: 'name', 'name_en', 'type', 'bio', 'features', 'personality'."
    
    llm_config = agent_service.get_active_llm_config(current_user.id, category="VLM", function_name="vision_analysis")
    if not llm_config:
        llm_config = agent_service.get_active_llm_config(current_user.id, category="LLM", function_name="script_analysis")
        
    try:
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config, image_urls=[data_uri])
        content_txt = llm_service.sanitize_text_output(str(resp.get("content") or ""))
        
        import re
        json_match = re.search(r'\{.*\}', content_txt, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
        else:
            result = {"name": "Image Entity", "features": content_txt}
            
        new_entity = Entity(
            project_id=project_id,
            name=result.get("name", "Image Generated Entity"),
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/entities/llm-derive", response_model=EntityOut)
async def api_generate_entity_from_derive(
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
        
    sys_prompt = "You are an AI assistant that modifies existing subject descriptions. Output valid JSON only."
    user_prompt = f"""
    Please generate a new subject JSON by applying the modification constraints onto the base entity.
    Base Entity Name: {base_entity.name}
    Base Bio: {base_entity.bio}
    Base Features: {base_entity.features}
    Base Personality: {base_entity.personality}
    
    Modification needed: {derive_desc}
    
    Return ONLY a JSON matching exactly: 'name', 'name_en', 'type', 'bio', 'features', 'personality'.
    """
    
    llm_config = agent_service.get_active_llm_config(current_user.id, category="LLM", function_name="script_analysis")
    
    try:
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
        content_txt = llm_service.sanitize_text_output(str(resp.get("content") or ""))
        
        import re
        json_match = re.search(r'\{.*\}', content_txt, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
        else:
            result = {"name": base_entity.name + " (Modified)", "bio": content_txt}
            
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
'''

text += "\n" + funcs
with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Re-patched endpoints.py correctly")
