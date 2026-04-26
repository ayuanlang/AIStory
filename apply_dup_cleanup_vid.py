import re

def fix_video():
    path = r"c:\AS\AIStory\backend\app\api\endpoints.py"
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    # We need to find the specific block in _run_generate_video
    
    old_video_block = """        # Register Asset
        if result.get("url"):
            temp_url = result.get("url")

            # For videos, wait until provider URLs are fetched internally by media_service.
            if temp_url.startswith("http") and not _is_ephemeral_provider_media_url(temp_url):
                await asyncio.to_thread(_bind_generated_media_to_shot, db, current_user, req, temp_url)
                await asyncio.to_thread(_register_asset_helper, db, current_user.id, temp_url, req, result.get("metadata"))
            else:
                await asyncio.to_thread(_register_asset_helper, db, current_user.id, temp_url, req, result.get("metadata"))
                await asyncio.to_thread(_bind_generated_media_to_shot, db, current_user, req, temp_url)"""
                
    new_video_block = """        # Register Asset - For videos, wait until finalize persistence OR callback"""

    src = src.replace(old_video_block, new_video_block)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
        
if __name__ == "__main__":
    fix_video()
    print("Done")