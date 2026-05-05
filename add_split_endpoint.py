import os

endpoint_code = """
class ScriptSplitRequest(BaseModel):
    script_content: str

@router.post("/projects/{project_id}/episodes/{episode_id}/split")
async def split_script(
    project_id: int,
    episode_id: int,
    req: ScriptSplitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    project = _require_project_access(db, project_id, current_user)
    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.project_id == project_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    script_content = (req.script_content or "").strip()
    if not script_content:
        raise HTTPException(status_code=400, detail="script_content is required")
        
    if async_mode == "1":
        tid = _submit_async(split_script, user_id=current_user.id,
                            kind="split_script", project_id=project_id, episode_id=episode_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})

    try:
        sys_prompt = _resolve_prompt_text("script_split.md")
    except FileNotFoundError:
        try:
            with open(os.path.join(os.path.dirname(__file__), "../core/prompts/script_split.md"), "r", encoding="utf-8") as f:
                sys_prompt = f.read()
        except:
            sys_prompt = "Split script into episodes of ~1000 chars, output JSON with 'episodes':[{title, content}]."
            
    llm_config = agent_service.get_active_llm_config(current_user.id, function_name="script_analysis") 
    if not llm_config:
         llm_config = agent_service.get_active_llm_config(current_user.id, category="LLM")
    if not llm_config:
         raise HTTPException(status_code=400, detail="No LLM config")
         
    try:
        resp = await agent_service.call_llm_agent(messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"【原始剧本】\\n{script_content}"}
        ], config=llm_config)
        content, _ = resp
    except AttributeError:
        # Fallback if call_llm_agent doesn't exist
        try:
            resp = await llm_service.chat_completion_with_fallback([
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"【原始剧本】\\n{script_content}"}
            ], llm_config)
            content = resp.get("content", "")
        except AttributeError:
            resp = await llm_service.generate_content_with_fallback(
                f"【原始剧本】\\n{script_content}",
                sys_prompt,
                llm_config
            )
            content = resp.get("content", "")

    import json, re
    match = re.search(r"```json\\s*(.*?)\\s*```", content, re.DOTALL)
    if match:
         content = match.group(1)
         
    try:
        data = json.loads(content)
        episodes_data = data.get("episodes", [])
    except Exception as e:
        logger.error(f"Failed to parse script split JSON: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM response")
        
    if episodes_data:
         episode.script_content = episodes_data[0].get("content", "")
         if episodes_data[0].get("title"):
             episode.title = episodes_data[0]["title"]
         db.commit()
         for ep_data in episodes_data[1:]:
             new_ep = Episode(
                 project_id=project_id,
                 title=ep_data.get("title", "New Episode"),
                 script_content=ep_data.get("content", ""),
                 episode_info=episode.episode_info
             )
             db.add(new_ep)
         db.commit()
         
    return {"status": "success", "episodes": episodes_data}
"""

with open("c:\\AS\\AIStory\\backend\\app\\api\\endpoints.py", "a", encoding="utf-8") as f:
    f.write("\\n" + endpoint_code + "\\n")
