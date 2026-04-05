import os

def patch_backend():
    file_path = '../backend/app/api/endpoints.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    lines = lines[:29870]
    lines.append('@router.post("/analyze_scene/stream")\n')
    lines.append('async def stream_analyze_scene_endpoint(\n')
    lines.append('    request: AnalyzeSceneRequest,\n')
    lines.append('    current_user: User = Depends(get_current_user),\n')
    lines.append('    db: Session = Depends(get_db)\n')
    lines.append('):\n')
    lines.append('    return await analyze_scene(request=request, current_user=current_user, db=db, async_mode="0", is_stream=True)\n')
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

patch_backend()