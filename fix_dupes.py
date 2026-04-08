import re

def main():
    with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # Find the double elif "multimodal-video" in endpoint_lower: and reduce it
    dupe_pattern = r'        elif "multimodal-video" in endpoint_lower:.*?(?=        elif "multimodal-video" in endpoint_lower:)'
    text = re.sub(dupe_pattern, '', text, flags=re.DOTALL)

    with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
        f.write(text)

    print('Fixed dupes!')

if __name__ == '__main__':
    main()
