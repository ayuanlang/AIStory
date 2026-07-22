from pathlib import Path
p = Path(r"c:\AS\AIStory\backend\app\api\routers\prompts\analyze_scene.py")
lines = p.read_text(encoding="utf-8").splitlines()
print("total", len(lines))
for i, l in enumerate(lines, 1):
    if l.startswith(("def ", "async def ", "@router", "class ")) or (l.startswith("from app.services") and i < 80):
        print(f"{i:4d}  {l[:110]}")
