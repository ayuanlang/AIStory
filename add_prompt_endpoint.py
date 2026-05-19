import os

with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'a', encoding='utf-8') as f:
    f.write('''

@router.get("/system/prompts/{prompt_name}")
async def get_system_prompt(prompt_name: str):
    import os
    from fastapi import HTTPException
    
    # 允许访问的项目根目录文件
    allowed_prompts = ["storyboard_prompt"]
    if prompt_name not in allowed_prompts:
        raise HTTPException(status_code=403, detail="Forbidden or unknown prompt")
        
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), f"{prompt_name}.md")
    if not os.path.exists(prompt_path):
        raise HTTPException(status_code=404, detail="Prompt file not found")
        
    with open(prompt_path, "r", encoding="utf-8") as pf:
        return {"content": pf.read().strip()}
''')

print("Done appending endpoint.")