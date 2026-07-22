from pathlib import Path
root = Path(r"c:\AS\AIStory\backend\app\api\routers")
for rel in [
 "workspace/shots.py",
 "workspace/episodes.py",
 "workspace/shared.py",
 "workspace/scenes.py",
 "prompts/analyze_scene.py",
 "prompts/progress_flow.py",
 "generation/batch_media.py",
 "generation/video_jobs.py",
]:
 p = root / rel
 if p.exists():
  print(f"{len(p.read_text(encoding='utf-8').splitlines()):5d}  {rel}")
print("--- shots ---")
p = root / "workspace/shots.py"
for i, l in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
    if l.startswith(("def ", "async def ", "@router", "class ")):
        print(f"{i:4d}  {l[:105]}")
