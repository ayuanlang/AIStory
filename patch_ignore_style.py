import os

with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

s2 = '''        auto_entity_refs.extend(_collect_video_prompt_entity_refs(prompt_candidates, entity_lookup))
        auto_entity_refs = _dedupe_media_ref_urls(auto_entity_refs)'''

text = text.replace(s2, '''        
        # DO NOT EXTRACT refs for video generation when the user asks, if it isn't an established "subject" or "prop".
        auto_entity_refs.extend(_collect_video_prompt_entity_refs(prompt_candidates, entity_lookup))
        auto_entity_refs = _dedupe_media_ref_urls(auto_entity_refs)''')

with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("done")
