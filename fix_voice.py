import re

def fix_file():
    with open(r'C:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix Voice
    old_voice = """        # Register voice asset so frontend can resolve metadata panels by URL.
        if voice_url:
            if not _is_ephemeral_provider_media_url(voice_url):
                try:
                    await asyncio.to_thread(
                        _register_asset_helper,
                        db,
                        current_user.id,
                        voice_url,
                        req,
                        (result.get("metadata") if isinstance(result, dict) else None),
                    )
                except Exception as asset_err:
                    logger.warning("[GenerateVoice] asset registration failed: %s", asset_err)

            if voice_url.startswith("http"):"""
            
    new_voice = """        # Register voice asset so frontend can resolve metadata panels by URL.
        if voice_url:
            if voice_url.startswith("http"):"""

    if old_voice in content:
        content = content.replace(old_voice, new_voice)
        print("Voice: Replaced first duplicate registration")

    old_voice_bg = """                                        bg_db.commit()
                            
                            # Register asset
                            await asyncio.to_thread(_register_asset_helper, bg_db, bg_user.id, norm_url, req_obj, norm_meta)
                    except Exception as e:"""

    new_voice_bg = """                                        bg_db.commit()
                            
                        # Register correctly whether OSS'd or not
                        final_url = norm_url if (norm_url and norm_url != raw_url) else raw_url
                        final_meta = norm_meta if norm_meta is not None else meta
                        await asyncio.to_thread(_register_asset_helper, bg_db, bg_user.id, final_url, req_obj, final_meta)
                    except Exception as e:"""

    if old_voice_bg in content:
        content = content.replace(old_voice_bg, new_voice_bg)
        print("Voice: Fixed bg registration to only register final_url")

    with open(r'C:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix_file()