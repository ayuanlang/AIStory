import json

def main():
    with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # Block 1
    s1_old = '''        video_prompt = _append_video_api_ref_mapping(
            video_prompt,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
        )'''
    s1_new = s1_old + '''

        video_prompt_cn_raw = str(tech.get("video_prompt_cn") or "").strip()
        video_prompt_cn = ""
        if video_prompt_cn_raw:
            video_cn_ref_index_map = _compute_subject_ref_index_map(video_prompt_cn_raw, entity_lookup)
            video_prompt_cn = _inject_shot_prompt_anchors(video_prompt_cn_raw, entity_lookup, global_style, video_cn_ref_index_map)
            video_prompt_cn = _append_video_api_ref_mapping(
                video_prompt_cn,
                ordered_video_refs,
                normalized_refs,
                normalized_last_frame_url,
                None,
            )
            tech["video_prompt_cn"] = video_prompt_cn
            item_db.query(type(shot)).filter(type(shot).id == shot.id).update({"technical_notes": json.dumps(tech, ensure_ascii=False)})
            item_db.commit()'''
    text = text.replace(s1_old, s1_new, 1)

    # Block 2
    s2_old = '''                        video_prompt = _append_video_api_ref_mapping(
                            video_prompt,
                            ordered_video_refs,
                            normalized_refs,
                            normalized_last_frame_url,
                            None,
                        )'''
    s2_new = s2_old + '''

                        video_prompt_cn_raw = str(tech.get("video_prompt_cn") or "").strip()
                        video_prompt_cn = ""
                        if video_prompt_cn_raw:
                            video_cn_ref_index_map = _compute_subject_ref_index_map(video_prompt_cn_raw, entity_lookup)
                            video_prompt_cn = _inject_shot_prompt_anchors(video_prompt_cn_raw, entity_lookup, global_style, video_cn_ref_index_map)
                            video_prompt_cn = _append_video_api_ref_mapping(
                                video_prompt_cn,
                                ordered_video_refs,
                                normalized_refs,
                                normalized_last_frame_url,
                                None,
                            )
                            tech["video_prompt_cn"] = video_prompt_cn
                            db.query(type(shot)).filter(type(shot).id == shot.id).update({"technical_notes": json.dumps(tech, ensure_ascii=False)})
                            db.commit()'''
    text = text.replace(s2_old, s2_new, 1)

    r1_old = '''        video_req = VideoGenerationRequest(
            prompt=video_prompt,
            ref_image_url=normalized_refs,'''
    r1_new = '''        multi_prompt_payload = None
        if video_prompt_cn:
            multi_prompt_payload = [
                {"prompt": video_prompt, "type": "en"},
                {"prompt": video_prompt_cn, "type": "zh"}
            ]
        video_req = VideoGenerationRequest(
            prompt=video_prompt,
            multi_prompt=multi_prompt_payload,
            ref_image_url=normalized_refs,'''
    text = text.replace(r1_old, r1_new, 1)

    r2_old = '''                        video_req = VideoGenerationRequest(
                            prompt=video_prompt,
                            ref_image_url=normalized_refs,'''
    r2_new = '''                        multi_prompt_payload = None
                        if video_prompt_cn:
                            multi_prompt_payload = [
                                {"prompt": video_prompt, "type": "en"},
                                {"prompt": video_prompt_cn, "type": "zh"}
                            ]
                        video_req = VideoGenerationRequest(
                            prompt=video_prompt,
                            multi_prompt=multi_prompt_payload,
                            ref_image_url=normalized_refs,'''
    text = text.replace(r2_old, r2_new, 1)

    with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('done patching endpoints')

if __name__ == '__main__':
    main()
