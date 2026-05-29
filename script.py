import re

with open(r'c:\AS\AIStory\backend\app\core\prompts\skills\shot_generation.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's delete from **三条示例的模板化重写到 the Markdown table headers, because the actual table has the examples.
# Actually, the template text is also huge. Let's find exactly what to cut.
