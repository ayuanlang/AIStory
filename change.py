with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

old_image_block = '''    updated_text = text
    for mapped_idx, entity_name, anchor_text in pairs:
        prefix = f"@Image{mapped_idx} "
        if prefix in updated_text and entity_name in updated_text:
            continue'''

new_image_block = '''    updated_text = text
    for mapped_idx, entity_name, anchor_text in pairs:
        prefix = f"@image{mapped_idx}"
        if prefix.lower() in updated_text.lower() and entity_name.lower() in updated_text.lower():
            continue'''

old_video_block = '''    if reference_video_urls and is_seedance:
        if original_use_prev_video:
            vid_tag = "@Video 1"
            vid_tag_nospace = "@Video1"
            if vid_tag not in updated_text and vid_tag_nospace not in updated_text:
                updated_text = f"延长\n\n{vid_tag}\n，一镜到底运镜。\n\n{updated_text.strip()}"
        
        added_videos = False
        for idx in range(1, len(reference_video_urls) + 1):
            vid_tag = f"@Video {idx}"
            vid_tag_nospace = f"@Video{idx}"
            if vid_tag not in updated_text and vid_tag_nospace not in updated_text:
                if not added_videos:
                    updated_text = f"{updated_text.strip()}，参考视频是 {vid_tag}"
                    added_videos = True
                else:
                    updated_text = f"{updated_text.strip()} {vid_tag}"'''

new_video_block = '''    if reference_video_urls and is_seedance:
        if original_use_prev_video:
            vid_tag = "@vedio1"
            if not re.search(r'@[Vv]ideo 1|@[Vv]ideo1|@[Vv]edie1|@[Vv]edio1', updated_text):
                updated_text = f"延长{vid_tag}，一镜到底运镜。{updated_text.strip()}"
        
        added_videos = False
        for idx in range(1, len(reference_video_urls) + 1):
            vid_tag = f"@vedio{idx}"
            if not re.search(r'@[Vv]ideo ' + str(idx) + r'|@[Vv]ideo' + str(idx) + r'|@[Vv]edie' + str(idx) + r'|@[Vv]edio' + str(idx), updated_text):
                if not added_videos:
                    updated_text = f"{updated_text.strip()}，参考视频是{vid_tag}"
                    added_videos = True
                else:
                    updated_text = f"{updated_text.strip()} {vid_tag}"'''

text = text.replace(old_image_block, new_image_block)
text = text.replace(old_video_block, new_video_block)

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Replaced!")
