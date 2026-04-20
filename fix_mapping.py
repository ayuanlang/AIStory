import re

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
    s1_new = '''        video_prompt = _append_video_api_ref_mapping(
            video_prompt,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
            reference_video_urls=None,
            entity_lookup=entity_lookup,
        )'''
    text = text.replace(s1_old, s1_new)

    # Block 2
    s2_old = '''                        video_prompt = _append_video_api_ref_mapping(
                            video_prompt,
                            ordered_video_refs,
                            normalized_refs,
                            normalized_last_frame_url,
                            None,
                        )'''
    s2_new = '''                        video_prompt = _append_video_api_ref_mapping(
                            video_prompt,
                            ordered_video_refs,
                            normalized_refs,
                            normalized_last_frame_url,
                            None,
                            reference_video_urls=None,
                            entity_lookup=entity_lookup,
                        )'''
    text = text.replace(s2_old, s2_new)

    with open('backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
        f.write(text)

if __name__ == '__main__':
    main()
