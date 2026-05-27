import os
path = 'backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('prompt_filename = " script_generator_episode_script.txt\', 'prompt_filename = \master_episode_writer.md\')

with open(path, 'w', encoding='utf-8') as f:
 f.write(text)
