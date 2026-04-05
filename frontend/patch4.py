def patch4():
    file_path = '../backend/app/api/endpoints.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if line.startswith('async def analyze_scene(request: AnalyzeSceneRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), async_mode: str = Query("0")):'):
            lines[i] = 'async def analyze_scene(request: AnalyzeSceneRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), async_mode: str = Query("0"), is_stream: bool = False):\n'
            break
            
    with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

patch4()