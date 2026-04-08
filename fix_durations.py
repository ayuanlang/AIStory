import re

def main():
    with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
        text = f.read()

    to_replace = '("/openapi/v2/rhart-video/sparkvideo-2.0-fast/multimodal-video", [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),'
    
    replacement = '''("/openapi/v2/rhart-video/sparkvideo-2.0-fast/multimodal-video", [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
                ("/openapi/v2/rhart-video/sparkvideo-2.0/multimodal-video", [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),'''

    text = text.replace(to_replace, replacement)

    with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
        f.write(text)

    print('Fixed durations!')

if __name__ == '__main__':
    main()
