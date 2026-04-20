import sys

def patch():
    with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
        text = f.read()

    old_snippet_1 = '''        video_prompt = _append_video_api_ref_mapping(
            video_prompt,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
        )'''

    new_snippet_1 = '''        video_prompt = _append_video_api_ref_mapping(
            video_prompt,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
        )

        video_prompt_cn_raw = str(tech.get(" video_prompt_cn\) or \\).strip()
 video_prompt_cn = \\
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
 # Store updated prompt back in tech
 tech[\video_prompt_cn\] = video_prompt_cn
 try:
 import json
 shot.technical_notes = json.dumps(tech, ensure_ascii=False)
 item_db.add(shot)
 item_db.commit()
 except Exception:
 pass
'''

 text = text.replace(old_snippet_1, new_snippet_1, 1)

 old_snippet_2 = ''' video_prompt = _append_video_api_ref_mapping(
 video_prompt,
 ordered_video_refs,
 normalized_refs,
 normalized_last_frame_url,
 None,
 )'''

 new_snippet_2 = ''' video_prompt = _append_video_api_ref_mapping(
 video_prompt,
 ordered_video_refs,
 normalized_refs,
 normalized_last_frame_url,
 None,
 )

 video_prompt_cn_raw = str(tech.get(\video_prompt_cn\) or \\).strip()
 video_prompt_cn = \\
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
 tech[\video_prompt_cn\] = video_prompt_cn
 try:
 import json
 shot.technical_notes = json.dumps(tech, ensure_ascii=False)
 db.add(shot)
 db.commit()
 except Exception:
 pass
'''

 text = text.replace(old_snippet_2, new_snippet_2, 1)

 # Now add multi_prompt to the VideoGenerationRequest creations.
 # We can pass multi_prompt kwarg to VideoGenerationRequest.
 # single shot VideoGenerationRequest:
 old_req_1 = ''' video_req = VideoGenerationRequest(
 prompt=video_prompt,
 ref_image_url=normalized_refs,'''
 
 new_req_1 = ''' multi_prompt_payload = None
 if video_prompt_cn:
 multi_prompt_payload = [
 {\prompt\: video_prompt, \type\: \en\},
 {\prompt\: video_prompt_cn, \type\: \zh\}
 ]
 video_req = VideoGenerationRequest(
 prompt=video_prompt,
 multi_prompt=multi_prompt_payload,
 ref_image_url=normalized_refs,'''

 text = text.replace(old_req_1, new_req_1, 1)

 # batch shot VideoGenerationRequest:
 old_req_2 = ''' video_req = VideoGenerationRequest(
 prompt=video_prompt,
 ref_image_url=normalized_refs,'''
 
 new_req_2 = ''' multi_prompt_payload = None
 if video_prompt_cn:
 multi_prompt_payload = [
 {\prompt\: video_prompt, \type\: \en\},
 {\prompt\: video_prompt_cn, \type\: \zh\}
 ]
 video_req = VideoGenerationRequest(
 prompt=video_prompt,
 multi_prompt=multi_prompt_payload,
 ref_image_url=normalized_refs,'''

 text = text.replace(old_req_2, new_req_2, 1)

 with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
 f.write(text)
 print(\Applied!\)

patch()
