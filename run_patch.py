def patch_endpoints():
    with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # Patch 1: _generate_entity_ref_videos inside db=item_db
    p1_target = '''        _release_db_connection(item_db, "shot_media_batch_video")
        asyncio.run(_run_stage_with_retry(
            lambda: _run_generate_video(req=video_req, current_user=user_principal, db=item_db),
        ))'''
    
    p1_new = '''        _release_db_connection(item_db, "shot_media_batch_video")
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
                db=item_db,
                provider_callback_ticket=callback_ticket_val,
                provider_callback_url=callback_url_val
            ),
        ))'''
    text = text.replace(p1_target, p1_new, 1)

    # Patch 2: _generate_entity_ref_videos inside db=db
    p2_target = '''                        _release_db_connection(db, "shot_media_batch_video")
                        asyncio.run(_run_stage_with_retry(
                            lambda: _run_generate_video(req=video_req, current_user=user_principal, db=db),
                            "video",
                            shot_label,
                            progress_fn,
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
                            progress_fn,
                        ))'''
    text = text.replace(p2_target, p2_new, 1)

    # Patch 3: /generate/video endpoint
    p3_target = '''        existing_task = _VIDEO_INFLIGHT_BY_KEY.get(dedup_key)
        if existing_task is None:
            _release_db_connection(db, "generate_video_sync_wait")
            existing_task = asyncio.create_task(_run_generate_video(req, current_user, db))
            _VIDEO_INFLIGHT_BY_KEY[dedup_key] = existing_task'''
    
    p3_new = '''        existing_task = _VIDEO_INFLIGHT_BY_KEY.get(dedup_key)
        if existing_task is None:
            _release_db_connection(db, "generate_video_sync_wait")
            try:
                callback_ticket_val = f"video-shot-{req.shot_id}" if getattr(req, "shot_id", None) else None
                callback_url_val = str(media_service._resolve_provider_callback_url({}, callback_ticket_val) or "").strip() if callback_ticket_val else ""
            except Exception:
                callback_ticket_val = f"video-shot-{req.shot_id}" if getattr(req, "shot_id", None) else None
                callback_url_val = ""
            
            existing_task = asyncio.create_task(_run_generate_video(
                req,
                current_user,
                db,
                provider_callback_ticket=callback_ticket_val,
                provider_callback_url=callback_url_val
            ))
            _VIDEO_INFLIGHT_BY_KEY[dedup_key] = existing_task'''
    text = text.replace(p3_target, p3_new, 1)

    with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
        f.write(text)
    
    # Check replacements
    if p1_new in text:
        print("Patch 1 True")
    if p2_new in text:
        print("Patch 2 True")
    if p3_new in text:
        print("Patch 3 True")

if __name__ == '__main__':
    patch_endpoints()
