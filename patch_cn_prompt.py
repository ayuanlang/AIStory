import re
with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Pattern 1 (in single shot logic)
def repl1(m):
    return m.group(0) + '''
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
 ordered_video_refs,
 )
 tech[\video_prompt_cn\] = video_prompt_cn
 shot.technical_notes = json.dumps(tech, ensure_ascii=False)
 item_db.add(shot)
 item_db.commit()
 
 multi_prompt_payload = None
 if video_prompt_cn:
 multi_prompt_payload = [
 {\prompt\: video_prompt, \type\: \en\},
 {\prompt\: video_prompt_cn, \type\: \zh\}
 ]
'''
# We must find the EXACT block where video_prompt = _append_video_api_ref_mapping occurs in shot_media_batch

matcher = r''' video_prompt = _append_video_api_ref_mapping\(
 video_prompt,
 ordered_video_refs,
 normalized_refs,
 normalized_last_frame_url,
 None,
 \)'''

matches = re.findall(matcher, text)
print('Found single shot matches:', len(matches))

