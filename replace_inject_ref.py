import os
import re

file_path = r'c:\AS\AIStory\frontend\src\pages\editor\components\ShotsView.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('injectRefPrefix', 'usePrevVideo')
content = content.replace('setInjectRefPrefix', 'setUsePrevVideo')
content = content.replace("'注入图', 'Inject Refs'", "'上镜视频', 'Prev Video'")
content = content.replace('生成视频时，强制将参考图片以"图N"的形式注入提示词。', '生成视频时，将上一镜生成的视频作为参考视频加入并提交给大模型。')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

file_path_be = r'c:\AS\AIStory\backend\app\api\endpoints.py'
with open(file_path_be, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('inject_ref_prefix', 'use_prev_video')

with open(file_path_be, 'w', encoding='utf-8') as f:
    f.write(content)
