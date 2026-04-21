def patch2():
    with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
        text = f.read()

    p2_target = '''                        _release_db_connection(db, "shot_media_batch_video")
                        asyncio.run(_run_stage_with_retry(
                            lambda: _run_generate_video(req=video_req, current_user=user_principal, db=db),
                            "video",
                            shot_label,
                        ))'''
    
    p2_new = '''                        _release_db_connection(db, "shot_media_batch_video")
                        try:
                            callback_ticket_val = f"video-shot-{shot.id}"
                            callback_url_val = str(media_service._resolve_provider_callback_url({}, callback_ticket_val) or "").strip()
                        except Exception:
                            callback_ticket_val = f"video-shot-{shot.id}"
                            callback_url_val = ""

                        asyncio.run(_run_stage_with_retry(
                            lambda: _run_generate_video(
                                req=video_req,
                                current_user=user_principal,
                                db=db,
                                provider_callback_ticket=callback_ticket_val,
                                provider_callback_url=callback_url_val
                            ),
                            "video",
                            shot_label,
                        ))'''
    
    if p2_target in text:
        text = text.replace(p2_target, p2_new, 1)
        with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
            f.write(text)
        print('Patch 2 Applied!')
    else:
        print('Target not found')

patch2()
