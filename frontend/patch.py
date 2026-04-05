import os
f = open('../backend/app/api/endpoints.py', 'r', encoding='utf-8')
lines = f.readlines()[:29870]
f.close()
lines.append('@router.post(\"/analyze_scene/stream\")\n')
lines.append('async def stream_analyze_scene_endpoint(request: AnalyzeSceneRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):\n')
lines.append('    return await analyze_scene(request=request, current_user=current_user, db=db, async_mode=\"0\", is_stream=True)\n')
f = open('../backend/app/api/endpoints.py', 'w', encoding='utf-8')
f.writelines(lines)
lines = f.readlines()[:29870]
f.close()
lines.append("@router.post(\"/analyze_scene/stream\")\n")
lines.append("async def stream_analyze_scene_endpoint(request: AnalyzeSceneRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):\n")
lines.append("    return await analyze_scene(request=request, current_user=current_user, db=db, async_mode=\"0\", is_stream=True)\n")
f = open('../backend/app/api/endpoints.py', 'w', encoding='utf-8')
f.writelines(lines)
f.close()
