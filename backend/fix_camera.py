import glob
import re

def aggressive_fix(filepath):
    print(f"Fixing {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    text = text.replace('"Camera ', '"Viewpoint ')
    text = text.replace(' Camera ', ' Viewpoint ')
    text = text.replace(' camera ', ' viewpoint ')
    text = text.replace('Camera ', 'Viewpoint ')
    text = text.replace('camera ', 'viewpoint ')
    text = text.replace('"Camera', '"Viewpoint')
    text = text.replace('"camera', '"viewpoint')
    
    text = text.replace('camera_direction', 'viewpoint_direction')
    text = text.replace('camera_movement', 'viewpoint_movement')
    text = text.replace('camera_action', 'viewpoint_action')
    text = text.replace('Camera Action', 'Viewpoint Action')
    text = text.replace('Camera Angle', 'Viewpoint Angle')
    text = text.replace('Camera Position', 'Viewpoint Position')
    text = text.replace('Camera Setup', 'Viewpoint Setup')
    text = text.replace('Camera Description', 'Shot Description')
    
    text = text.replace('机位(Camera)', '机位(Viewpoint)')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

for f in glob.glob('C:/storyboard/AIStory/backend/app/core/prompts/*.txt'):
    aggressive_fix(f)
aggressive_fix('C:/storyboard/AIStory/backend/app/core/prompts/templates.py')
aggressive_fix('C:/storyboard/AIStory/backend/app/core/prompts/PROMPT_CHAIN_MATRIX.md')

print("Replacement complete")
