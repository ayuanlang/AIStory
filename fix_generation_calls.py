import os
import re

FILE_PATH = "c:/storyboard/AIStory/frontend/src/pages/Editor.jsx"

def fix_generation_calls():
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Problem:
    # shot_id: editingShot.id,
    # shot_id: editingShot.shot_id,
    
    # We want:
    # shot_id: editingShot.id,
    # shot_number: editingShot.shot_id,
    
    # Regex to find double shot_id assignment
    # match `shot_id: ...,` followed by whitespace `shot_id: ...`
    # patterns likely:
    # shot_id: editingShot.id,\s+shot_id: editingShot.shot_id
    
    # But checking broadly:
    # If we see `shot_id: editingShot.shot_id`, it is definitely the LABEL (since .shot_id is string label now).
    # If we see `shot_id: editingShot.id`, it is the PK.
    
    # So replacing `shot_id: editingShot.shot_id` with `shot_number: editingShot.shot_id` should fix it.
    # Same for `currentShot.shot_id` and `shot.shot_id`.
    
    objects = ["editingShot", "currentShot", "shot", "s"]
    
    for obj in objects:
        pattern = f"shot_id: {obj}.shot_id"
        replacement = f"shot_number: {obj}.shot_id"
        content = content.replace(pattern, replacement)
        
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Fixed generation calls.")

if __name__ == "__main__":
    fix_generation_calls()
